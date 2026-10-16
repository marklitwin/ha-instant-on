"""Async client for the (unofficial) HPE Aruba Networking Instant On cloud API.

Auth flow reverse-engineered by https://blog.puddle.town/instant-on/ :
  settings.json -> MFA validate (session token) -> OAuth2 authorize w/ PKCE -> token.
The API is undocumented and may change without notice.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import asyncio

import aiohttp

from .const import API_VERSION, PORTAL_SETTINGS_URL, TOKEN_LIFETIME_FALLBACK

_LOGGER = logging.getLogger(__name__)


class InstantOnError(Exception):
    """Generic API error."""


class InstantOnAuthError(InstantOnError):
    """Credentials rejected (bad password, MFA enabled, account locked)."""


@dataclass
class PortalSettings:
    rest_api_url: str
    sso_fqdn: str
    client_id: str
    redirect_uri: str


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


class InstantOnClient:
    """Minimal read-only client."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._settings: PortalSettings | None = None
        self._token: str | None = None
        self._token_expiry: float = 0
        self._login_lock = asyncio.Lock()

    # ---------------------------------------------------------------- auth
    async def _load_settings(self) -> PortalSettings:
        async with self._session.get(PORTAL_SETTINGS_URL) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        try:
            self._settings = PortalSettings(
                rest_api_url=data["restApiUrl"].rstrip("/"),
                sso_fqdn=data["ssoFqdn"].rstrip("/"),
                client_id=data["ssoClientIdAuthZ"],
                redirect_uri=data["ssoRedirectUrl"],
            )
        except KeyError as err:
            raise InstantOnError(f"settings.json missing key {err}") from err
        return self._settings

    async def login(self) -> None:
        """Run the full login flow and store a bearer token."""
        settings = await self._load_settings()
        verifier, challenge = _pkce_pair()

        # 1. Username/password -> session token (fails if MFA is enabled).
        async with self._session.post(
            f"{settings.sso_fqdn}/aio/api/v1/mfa/validate/full",
            data={"username": self._username, "password": self._password},
        ) as resp:
            if resp.status in (400, 401, 403):
                raise InstantOnAuthError(f"Credential validation failed ({resp.status})")
            resp.raise_for_status()
            body = await resp.json(content_type=None)
        session_token = body.get("access_token")
        if not session_token:
            # Most likely MFA is enabled on the account.
            raise InstantOnAuthError("No session token returned (is MFA enabled?)")

        # 2. Authorize -> code in Location header (do not follow redirect).
        state = secrets.token_urlsafe(16)
        async with self._session.get(
            f"{settings.sso_fqdn}/as/authorization.oauth2",
            params={
                "client_id": settings.client_id,
                "redirect_uri": settings.redirect_uri,
                "response_type": "code",
                "scope": "profile openid",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "sessionToken": session_token,
            },
            allow_redirects=False,
        ) as resp:
            location = resp.headers.get("Location", "")
        query = parse_qs(urlparse(location).query)
        if query.get("state", [state])[0] != state or "code" not in query:
            raise InstantOnAuthError("Authorization step did not return a code")
        code = query["code"][0]

        # 3. Code -> bearer token.
        async with self._session.post(
            f"{settings.sso_fqdn}/as/token.oauth2",
            data={
                "client_id": settings.client_id,
                "redirect_uri": settings.redirect_uri,
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
            },
        ) as resp:
            if resp.status >= 400:
                raise InstantOnAuthError(f"Token exchange failed ({resp.status})")
            tok = await resp.json(content_type=None)

        self._token = tok["access_token"]
        # expires_in is not documented; refresh a minute early if present.
        lifetime = int(tok.get("expires_in", TOKEN_LIFETIME_FALLBACK))
        self._token_expiry = time.monotonic() + max(lifetime - 60, 60)
        _LOGGER.debug("Instant On login OK, token valid ~%ss", lifetime)

    # ----------------------------------------------------------------- API
    async def _get(self, path: str, _retry: bool = True) -> Any:
        async with self._login_lock:  # avoid parallel logins from gathered requests
            if not self._token or time.monotonic() >= self._token_expiry:
                await self.login()
        assert self._settings
        async with self._session.get(
            f"{self._settings.rest_api_url}{path}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "x-ion-api-version": API_VERSION,
                "Accept": "application/json",
            },
        ) as resp:
            if resp.status == 401 and _retry:
                self._token_expiry = 0
                return await self._get(path, _retry=False)
            if resp.status == 401:
                raise InstantOnAuthError("Bearer token rejected")
            if resp.status >= 400:
                raise InstantOnError(f"GET {path} -> HTTP {resp.status}")
            return await resp.json(content_type=None)

    async def _elements(self, path: str) -> list[dict[str, Any]]:
        data = await self._get(path)
        if isinstance(data, dict):
            return data.get("elements", [])
        return data or []

    async def get_sites(self) -> list[dict[str, Any]]:
        return await self._elements("/api/sites/")

    async def get_clients(self, site_id: str) -> list[dict[str, Any]]:
        return await self._elements(f"/api/sites/{site_id}/clientSummary")

    async def get_inventory(self, site_id: str) -> list[dict[str, Any]]:
        return await self._elements(f"/api/sites/{site_id}/inventory")

    async def get_alerts(self, site_id: str) -> list[dict[str, Any]]:
        return await self._elements(f"/api/sites/{site_id}/alerts")

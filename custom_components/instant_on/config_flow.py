"""Config flow: credentials -> site selection; options for interval/sites/tracking."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers import selector

from .api import InstantOnAuthError, InstantOnClient, InstantOnError
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SITES,
    CONF_TRACK_CLIENTS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

CREDS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


async def _fetch_sites(hass, username: str, password: str) -> dict[str, str]:
    client = InstantOnClient(async_create_clientsession(hass), username, password)
    await client.login()
    return {str(s["id"]): s.get("name", str(s["id"])) for s in await client.get_sites()}


class InstantOnConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, Any] = {}
        self._sites: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            try:
                self._sites = await _fetch_sites(
                    self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except InstantOnAuthError:
                errors["base"] = "invalid_auth"
            except InstantOnError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                if not self._sites:
                    errors["base"] = "no_sites"
                else:
                    self._creds = user_input
                    return await self.async_step_sites()
        return self.async_show_form(step_id="user", data_schema=CREDS_SCHEMA, errors=errors)

    async def async_step_sites(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._creds[CONF_USERNAME],
                data={**self._creds, CONF_SITES: user_input[CONF_SITES]},
            )
        return self.async_show_form(
            step_id="sites",
            data_schema=vol.Schema(
                {vol.Required(CONF_SITES, default=list(self._sites)): cv_multi(self._sites)}
            ),
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _fetch_sites(self.hass, entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
            except InstantOnAuthError:
                errors["base"] = "invalid_auth"
            except InstantOnError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return InstantOnOptionsFlow()


class InstantOnOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                    vol.Required(
                        CONF_TRACK_CLIENTS, default=opts.get(CONF_TRACK_CLIENTS, True)
                    ): bool,
                }
            ),
        )


def cv_multi(options: dict[str, str]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=k, label=v) for k, v in options.items()],
            multiple=True,
        )
    )

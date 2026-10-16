"""Diagnostics: dumps raw payloads so the undocumented schema can be inspected."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import InstantOnConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "macAddress", "mac", "ipAddress", "serialNumber", "hostName", "name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InstantOnConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "sites": async_redact_data(
            {sid: asdict(sd) for sid, sd in (coordinator.data or {}).items()}, TO_REDACT
        ),
    }

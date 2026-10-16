"""HPE Aruba Networking Instant On integration (unofficial cloud API)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import InstantOnClient
from .coordinator import InstantOnCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]

type InstantOnConfigEntry = ConfigEntry[InstantOnCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: InstantOnConfigEntry) -> bool:
    # Own session (own cookie jar) so SSO cookies don't leak into HA's shared session.
    session = async_create_clientsession(hass)
    client = InstantOnClient(session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = InstantOnCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: InstantOnConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: InstantOnConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

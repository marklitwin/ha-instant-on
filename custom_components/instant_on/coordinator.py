"""Data coordinator: one cloud poll per interval for all selected sites."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InstantOnAuthError, InstantOnClient, InstantOnError
from .const import CONF_SCAN_INTERVAL, CONF_SITES, DEFAULT_SCAN_INTERVAL, DOMAIN, client_mac

_LOGGER = logging.getLogger(__name__)


@dataclass
class SiteData:
    site: dict[str, Any]
    clients: dict[str, dict[str, Any]] = field(default_factory=dict)  # keyed by MAC
    inventory: list[dict[str, Any]] = field(default_factory=list)


class InstantOnCoordinator(DataUpdateCoordinator[dict[str, SiteData]]):
    """Polls sites (incl. alert counts + health), clients and inventory."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: InstantOnClient) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, SiteData]:
        wanted = set(self.config_entry.options.get(CONF_SITES) or self.config_entry.data.get(CONF_SITES, []))
        try:
            sites = await self.client.get_sites()
            result: dict[str, SiteData] = {}
            for site in sites:
                site_id = str(site.get("id"))
                if wanted and site_id not in wanted:
                    continue
                clients, inventory = await asyncio.gather(
                    self.client.get_clients(site_id),
                    self.client.get_inventory(site_id),
                )
                result[site_id] = SiteData(
                    site=site,
                    clients={m: c for c in clients if (m := client_mac(c))},
                    inventory=inventory,
                )
            return result
        except InstantOnAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (InstantOnError, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Instant On API error: {err}") from err

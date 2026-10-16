"""Poll-interval control on the site device."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InstantOnConfigEntry
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL
from .entity import InstantOnEntity, site_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: InstantOnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PollIntervalNumber(coordinator, site_id) for site_id in coordinator.data)


class PollIntervalNumber(InstantOnEntity, NumberEntity):
    _attr_translation_key = "poll_interval"
    _attr_native_min_value = MIN_SCAN_INTERVAL
    _attr_native_max_value = MAX_SCAN_INTERVAL
    _attr_native_step = 15
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer-cog"

    def __init__(self, coordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_poll_interval"
        self._attr_device_info = site_device_info(coordinator.data[site_id])

    @property
    def native_value(self) -> float:
        opts = self.coordinator.config_entry.options
        data = self.coordinator.config_entry.data
        return opts.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

    async def async_set_native_value(self, value: float) -> None:
        entry = self.coordinator.config_entry
        self.hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_SCAN_INTERVAL: int(value)},
        )

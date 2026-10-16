"""Connectivity binary sensor per AP / switch in the site inventory."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InstantOnConfigEntry
from .const import is_online
from .entity import InstantOnEntity, inventory_device_info, inventory_id

_ATTRS = (
    "deviceType", "health", "operationalState", "uptimeInSeconds",
    "numberOfSecondsSinceLastCommunication", "uplinkDeviceName", "isUpToDate",
    "wiredClientsCount", "inputPowerSource",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: InstantOnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DeviceOnline(coordinator, site_id, dev_id)
        for site_id, sd in coordinator.data.items()
        for dev in sd.inventory
        if (dev_id := inventory_id(dev))
    )


class DeviceOnline(InstantOnEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = None  # use the device name

    def __init__(self, coordinator, site_id: str, dev_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._dev_id = dev_id
        self._attr_unique_id = f"dev_{dev_id}_online"
        self._attr_device_info = inventory_device_info(site_id, self._dev)

    @property
    def _dev(self) -> dict[str, Any]:
        if self.site_data:
            for dev in self.site_data.inventory:
                if inventory_id(dev) == self._dev_id:
                    return dev
        return {}

    @property
    def is_on(self) -> bool | None:
        return is_online(self._dev)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {k: self._dev[k] for k in _ATTRS if k in self._dev}

"""Base entities and device-registry helpers."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InstantOnCoordinator, SiteData


def site_device_info(site_data: SiteData) -> DeviceInfo:
    site = site_data.site
    return DeviceInfo(
        identifiers={(DOMAIN, f"site_{site['id']}")},
        name=f"Instant On {site.get('name', site['id'])}",
        manufacturer="HPE Aruba Networking",
        model="Instant On site",
        configuration_url="https://portal.instant-on.hpe.com",
    )


def inventory_id(dev: dict[str, Any]) -> str | None:
    return dev.get("id") or dev.get("macAddress")  # id is the device MAC


def inventory_device_info(site_id: str, dev: dict[str, Any]) -> DeviceInfo:
    mac = dev.get("macAddress")
    return DeviceInfo(
        identifiers={(DOMAIN, f"dev_{inventory_id(dev)}")},
        connections={(CONNECTION_NETWORK_MAC, mac.lower())} if mac else set(),
        name=dev.get("name") or dev.get("defaultName") or inventory_id(dev),
        manufacturer="HPE Aruba Networking",
        model=dev.get("model"),
        model_id=dev.get("sku"),
        serial_number=dev.get("serialNumber"),
        sw_version=dev.get("currentFirmwareVersion") or dev.get("deviceSoftwareVersion"),
        via_device=(DOMAIN, f"site_{site_id}"),
    )


class InstantOnEntity(CoordinatorEntity[InstantOnCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: InstantOnCoordinator, site_id: str) -> None:
        super().__init__(coordinator)
        self.site_id = site_id

    @property
    def site_data(self) -> SiteData | None:
        return (self.coordinator.data or {}).get(self.site_id)

    @property
    def available(self) -> bool:
        return super().available and self.site_data is not None

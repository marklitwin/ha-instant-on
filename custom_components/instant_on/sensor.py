"""Per-site summary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InstantOnConfigEntry
from .const import is_online, is_wireless
from .coordinator import SiteData
from .entity import InstantOnEntity, client_device_info, site_device_info
from .traffic import (
    client_activity_bytes,
    client_bytes_last_24h,
    client_bytes_session,
    client_downstream_bps,
    client_signal_dbm,
    client_telemetry,
    client_total_bps,
    client_upstream_bps,
    online_clients,
    top_clients_by_bytes,
    top_clients_by_throughput,
)


def _online(d: SiteData) -> list:
    return [c for c in d.clients.values() if is_online(c)]


@dataclass(frozen=True, kw_only=True)
class SiteSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SiteData], int | None]


SENSORS = (
    SiteSensorDescription(
        key="clients", translation_key="clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(_online(d)),
    ),
    SiteSensorDescription(
        key="wireless_clients", translation_key="wireless_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: sum(is_wireless(c) for c in _online(d)),
    ),
    SiteSensorDescription(
        key="wired_clients", translation_key="wired_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: sum(not is_wireless(c) for c in _online(d)),
    ),
    SiteSensorDescription(
        key="devices", translation_key="devices",
        value_fn=lambda d: len(d.inventory),
    ),
    SiteSensorDescription(
        key="active_alerts", translation_key="active_alerts",
        value_fn=lambda d: d.site.get("activeAlertsCount"),
    ),
    SiteSensorDescription(
        key="health_score", translation_key="health_score",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: (d.site.get("currentHealthScore") or {}).get("score"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: InstantOnConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                SiteSensor(coordinator, site_id, desc)
                for site_id in coordinator.data
                for desc in SENSORS
            ),
            *(
                SiteTrafficSensor(coordinator, site_id)
                for site_id in coordinator.data
            ),
            *(
                MostActiveClientSensor(coordinator, site_id)
                for site_id in coordinator.data
            ),
            *(
                BusiestClientSensor(coordinator, site_id)
                for site_id in coordinator.data
            ),
        ]
    )

    known: set[str] = set()

    @callback
    def _add_clients() -> None:
        new: list[SensorEntity] = []
        for site_id, site_data in coordinator.data.items():
            for mac, client in site_data.clients.items():
                if mac in known:
                    continue
                known.add(mac)
                new.extend(
                    [
                        ClientRateSensor(coordinator, site_id, mac, "download"),
                        ClientRateSensor(coordinator, site_id, mac, "upload"),
                        ClientTransferredSensor(coordinator, site_id, mac),
                    ]
                )
                if is_wireless(client) or client_signal_dbm(client) is not None:
                    new.append(ClientSignalSensor(coordinator, site_id, mac))
        if new:
            async_add_entities(new)

    _add_clients()
    entry.async_on_unload(coordinator.async_add_listener(_add_clients))


class SiteSensor(InstantOnEntity, SensorEntity):
    entity_description: SiteSensorDescription

    def __init__(self, coordinator, site_id: str, desc: SiteSensorDescription) -> None:
        super().__init__(coordinator, site_id)
        self.entity_description = desc
        self._attr_unique_id = f"{site_id}_{desc.key}"
        self._attr_device_info = site_device_info(coordinator.data[site_id])

    @property
    def native_value(self) -> int | None:
        return self.entity_description.value_fn(self.site_data) if self.site_data else None

    @property
    def extra_state_attributes(self):
        if not self.site_data:
            return None
        site = self.site_data.site
        if self.entity_description.key == "active_alerts":
            return {"latest_alert": site.get("latestActiveAlert"), **(site.get("activeAlertsCounters") or {})}
        if self.entity_description.key == "health_score":
            return {"health": site.get("health"), "reason": site.get("healthReason")}
        if self.entity_description.key == "clients":
            online = online_clients(self.site_data.clients)
            online.sort(key=client_total_bps, reverse=True)
            return {"online_clients": [client_telemetry(c) for c in online]}
        return None


class SiteTrafficSensor(InstantOnEntity, SensorEntity):
    """Sum of current client throughput on the site."""

    _attr_translation_key = "total_throughput"
    _attr_native_unit_of_measurement = UnitOfDataRate.BITS_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_total_throughput"
        self._attr_device_info = site_device_info(coordinator.data[site_id])

    @property
    def native_value(self) -> int | None:
        if not self.site_data:
            return None
        total = sum(client_total_bps(c) for c in online_clients(self.site_data.clients))
        return total

    @property
    def extra_state_attributes(self) -> dict | None:
        if not self.site_data:
            return None
        top = top_clients_by_throughput(self.site_data.clients)
        return {"top_by_throughput": top} if top else None


class MostActiveClientSensor(InstantOnEntity, SensorEntity):
    """Client with the highest current throughput (upload + download)."""

    _attr_translation_key = "most_active_client"
    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_most_active_client"
        self._attr_device_info = site_device_info(coordinator.data[site_id])

    @property
    def native_value(self) -> str | None:
        if not self.site_data:
            return None
        top = top_clients_by_throughput(self.site_data.clients, limit=1)
        if not top or not top[0].get("throughput_bps"):
            return None
        return top[0].get("name") or top[0].get("mac")

    @property
    def extra_state_attributes(self) -> dict | None:
        if not self.site_data:
            return None
        top = top_clients_by_throughput(self.site_data.clients)
        if not top or not top[0].get("throughput_bps"):
            return None
        leader, *rest = top
        attrs = dict(leader)
        if rest:
            attrs["also_active"] = rest
        return attrs


class BusiestClientSensor(InstantOnEntity, SensorEntity):
    """Client with the most data transferred (24 h counters when present, else session)."""

    _attr_translation_key = "busiest_client"
    _attr_icon = "mdi:cloud-download"

    def __init__(self, coordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_busiest_client"
        self._attr_device_info = site_device_info(coordinator.data[site_id])

    @property
    def native_value(self) -> str | None:
        if not self.site_data:
            return None
        top = top_clients_by_bytes(self.site_data.clients, limit=1)
        if not top or not top[0].get("activity_bytes"):
            return None
        return top[0].get("name") or top[0].get("mac")

    @property
    def extra_state_attributes(self) -> dict | None:
        if not self.site_data:
            return None
        top = top_clients_by_bytes(self.site_data.clients)
        if not top or not top[0].get("activity_bytes"):
            return None
        leader, *rest = top
        attrs = dict(leader)
        if rest:
            attrs["also_busy"] = rest
        return attrs


class _ClientSensor(InstantOnEntity, SensorEntity):
    def __init__(self, coordinator, site_id: str, mac: str) -> None:
        super().__init__(coordinator, site_id)
        self._mac = mac
        client = self._client or {}
        self._attr_device_info = client_device_info(site_id, mac, client)

    @property
    def _client(self) -> dict | None:
        return self.site_data.clients.get(self._mac) if self.site_data else None


class ClientRateSensor(_ClientSensor):
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.BITS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, site_id: str, mac: str, direction: str) -> None:
        super().__init__(coordinator, site_id, mac)
        self._direction = direction
        self._attr_translation_key = f"client_{direction}"
        self._attr_unique_id = f"client_{mac}_{direction}"
        self._attr_icon = "mdi:download" if direction == "download" else "mdi:upload"

    @property
    def native_value(self) -> int | None:
        client = self._client
        if not client or not is_online(client):
            return 0
        if self._direction == "download":
            return client_downstream_bps(client)
        return client_upstream_bps(client)


class ClientSignalSensor(_ClientSensor):
    _attr_translation_key = "client_signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, site_id: str, mac: str) -> None:
        super().__init__(coordinator, site_id, mac)
        self._attr_unique_id = f"client_{mac}_signal"

    @property
    def native_value(self) -> int | None:
        client = self._client
        if not client or not is_online(client):
            return None
        return client_signal_dbm(client)


class ClientTransferredSensor(_ClientSensor):
    _attr_translation_key = "client_transferred"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-donut"

    def __init__(self, coordinator, site_id: str, mac: str) -> None:
        super().__init__(coordinator, site_id, mac)
        self._attr_unique_id = f"client_{mac}_transferred"

    @property
    def native_value(self) -> int | None:
        client = self._client
        if not client:
            return None
        return client_bytes_last_24h(client) if client_bytes_last_24h(client) is not None else client_bytes_session(client)

    @property
    def extra_state_attributes(self) -> dict | None:
        client = self._client
        if not client:
            return None
        attrs = {}
        if (b24 := client_bytes_last_24h(client)) is not None:
            attrs["bytes_last_24h"] = b24
        if (sess := client_bytes_session(client)) is not None:
            attrs["bytes_session"] = sess
        attrs["activity_bytes"] = client_activity_bytes(client)
        return attrs or None

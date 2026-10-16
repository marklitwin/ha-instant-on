"""Parse client traffic fields from clientSummary (field names vary by API version)."""
from __future__ import annotations

from typing import Any

from .const import client_mac, client_name, is_online


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _lookup_int(record: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        if (val := _as_int(record.get(key))) is not None:
            return val
    return None


def _traffic_sources(client: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = [client]
    data_traffic = client.get("dataTraffic")
    if isinstance(data_traffic, dict):
        sources.append(data_traffic)
    return sources


def client_upstream_bps(client: dict[str, Any]) -> int:
    for src in _traffic_sources(client):
        if (val := _lookup_int(
            src,
            "upstreamThroughputInBitsPerSecond",
            "upstreamSpeedInBitsPerSecond",
        )) is not None:
            return val
    return 0


def client_downstream_bps(client: dict[str, Any]) -> int:
    for src in _traffic_sources(client):
        if (val := _lookup_int(
            src,
            "downstreamThroughputInBitsPerSecond",
            "downstreamSpeedInBitsPerSecond",
        )) is not None:
            return val
    return 0


def client_total_bps(client: dict[str, Any]) -> int:
    return client_upstream_bps(client) + client_downstream_bps(client)


def client_bytes_last_24h(client: dict[str, Any]) -> int | None:
    for src in _traffic_sources(client):
        if (total := _lookup_int(src, "totalDataTransferredDuringLast24HoursInBytes")) is not None:
            return total
        up = _lookup_int(src, "upstreamDataTransferredDuringLast24HoursInBytes")
        down = _lookup_int(src, "downstreamDataTransferredDuringLast24HoursInBytes")
        if up is not None or down is not None:
            return (up or 0) + (down or 0)
    return None


def client_bytes_session(client: dict[str, Any]) -> int | None:
    for src in _traffic_sources(client):
        for key in (
            "totalDataTransferredInBytes",
            "dataTransferredInBytes",
            "totalBytesTransferred",
            "bytesTransferred",
        ):
            if (val := _lookup_int(src, key)) is not None:
                return val
    return None


def client_activity_bytes(client: dict[str, Any]) -> int:
    """Best-effort byte counter for ranking 'busiest' clients."""
    return (
        client_bytes_last_24h(client)
        or client_bytes_session(client)
        or 0
    )


def online_clients(clients: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in clients.values() if is_online(c)]


def top_clients_by_throughput(
    clients: dict[str, dict[str, Any]], limit: int = 5
) -> list[dict[str, Any]]:
    ranked = sorted(online_clients(clients), key=client_total_bps, reverse=True)
    return [_client_snapshot(c, throughput_bps=client_total_bps(c)) for c in ranked[:limit]]


def top_clients_by_bytes(
    clients: dict[str, dict[str, Any]], limit: int = 5
) -> list[dict[str, Any]]:
    ranked = sorted(online_clients(clients), key=client_activity_bytes, reverse=True)
    out: list[dict[str, Any]] = []
    for c in ranked[:limit]:
        snap = _client_snapshot(c, bytes_24h=client_bytes_last_24h(c), bytes_session=client_bytes_session(c))
        snap["activity_bytes"] = client_activity_bytes(c)
        out.append(snap)
    return out


def _client_snapshot(
    client: dict[str, Any],
    *,
    throughput_bps: int | None = None,
    bytes_24h: int | None = None,
    bytes_session: int | None = None,
) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "name": client_name(client),
        "mac": client_mac(client),
        "ip": client.get("ipAddress") or None,
        "connection": client.get("clientType"),
    }
    if throughput_bps is not None:
        snap["throughput_bps"] = throughput_bps
        snap["upstream_bps"] = client_upstream_bps(client)
        snap["downstream_bps"] = client_downstream_bps(client)
    if bytes_24h is not None:
        snap["bytes_last_24h"] = bytes_24h
    if bytes_session is not None:
        snap["bytes_session"] = bytes_session
    return snap

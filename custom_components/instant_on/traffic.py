"""Parse client traffic fields from clientSummary (field names vary by API version)."""
from __future__ import annotations

from typing import Any

from .const import client_mac, client_name, is_online


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _norm(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "")


def _walk(obj: Any):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _is_up(name: str) -> bool:
    return name.startswith(("up", "tx", "upload")) or "upstream" in name or "uplink" in name


def _is_down(name: str) -> bool:
    return name.startswith(("down", "rx", "download")) or "downstream" in name or "downlink" in name


def _rate_bits(name: str, value: int) -> int | None:
    if "bitspersecond" in name or name.endswith("bps"):
        return value
    if "bytespersecond" in name:
        return value * 8
    if ("throughput" in name or "speed" in name) and "second" in name:
        # Portal UI reports bytes/s; older API samples used bits/s in the key name.
        return value * 8 if "bit" not in name else value
    return None


def _directional_rate(client: dict[str, Any], direction: str) -> int:
    match = _is_up if direction == "up" else _is_down
    for key, value in _walk(client):
        name = _norm(key)
        if not match(name):
            continue
        if (raw := _as_int(value)) is None:
            continue
        if (bits := _rate_bits(name, raw)) is not None:
            return bits
    return 0


def client_upstream_bps(client: dict[str, Any]) -> int:
    return _directional_rate(client, "up")


def client_downstream_bps(client: dict[str, Any]) -> int:
    return _directional_rate(client, "down")


def client_total_bps(client: dict[str, Any]) -> int:
    return client_upstream_bps(client) + client_downstream_bps(client)


def _byte_total(client: dict[str, Any], *, last_24h: bool) -> int | None:
    totals: list[int] = []
    parts: list[int] = []
    for key, value in _walk(client):
        name = _norm(key)
        if (raw := _as_int(value)) is None:
            continue
        is_24h = "24hour" in name or "lastday" in name
        if is_24h != last_24h:
            continue
        if "persecond" in name or "throughput" in name or "speed" in name:
            continue
        if not any(token in name for token in ("transferred", "datatransfer", "datausage")):
            continue
        if "total" in name:
            totals.append(raw)
        else:
            parts.append(raw)
    if totals:
        return max(totals)
    if parts:
        return sum(parts)
    return None


def client_bytes_last_24h(client: dict[str, Any]) -> int | None:
    return _byte_total(client, last_24h=True)


def client_bytes_session(client: dict[str, Any]) -> int | None:
    return _byte_total(client, last_24h=False)


def client_activity_bytes(client: dict[str, Any]) -> int:
    """Best-effort byte counter for ranking busiest clients."""
    return client_bytes_last_24h(client) or client_bytes_session(client) or 0


def client_signal_dbm(client: dict[str, Any]) -> int | None:
    for key, value in _walk(client):
        name = _norm(key)
        if name in {"signalindbm", "signalstrength", "rssi", "signal"} or name.endswith("dbm"):
            if (raw := _as_int(value)) is not None:
                return raw
    return None


def online_clients(clients: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in clients.values() if is_online(c)]


def client_telemetry(client: dict[str, Any]) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "name": client_name(client),
        "mac": client_mac(client),
        "ip": client.get("ipAddress") or None,
        "connection": client.get("clientType"),
        "upstream_bps": client_upstream_bps(client),
        "downstream_bps": client_downstream_bps(client),
        "throughput_bps": client_total_bps(client),
    }
    if (signal := client_signal_dbm(client)) is not None:
        snap["signal_dbm"] = signal
    if (b24 := client_bytes_last_24h(client)) is not None:
        snap["bytes_last_24h"] = b24
    if (sess := client_bytes_session(client)) is not None:
        snap["bytes_session"] = sess
    return snap


def top_clients_by_throughput(
    clients: dict[str, dict[str, Any]], limit: int = 5
) -> list[dict[str, Any]]:
    ranked = sorted(online_clients(clients), key=client_total_bps, reverse=True)
    return [client_telemetry(c) for c in ranked[:limit]]


def top_clients_by_bytes(
    clients: dict[str, dict[str, Any]], limit: int = 5
) -> list[dict[str, Any]]:
    ranked = sorted(online_clients(clients), key=client_activity_bytes, reverse=True)
    out: list[dict[str, Any]] = []
    for client in ranked[:limit]:
        snap = client_telemetry(client)
        snap["activity_bytes"] = client_activity_bytes(client)
        out.append(snap)
    return out

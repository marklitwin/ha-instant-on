"""Constants for the HPE Instant On integration."""
DOMAIN = "instant_on"

PORTAL_SETTINGS_URL = "https://portal.instant-on.hpe.com/settings.json"
API_VERSION = "7"
TOKEN_LIFETIME_FALLBACK = 3600  # seconds, used if token response has no expires_in

CONF_SITES = "sites"
CONF_TRACK_CLIENTS = "track_clients"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60  # be polite to an unofficial cloud API
MIN_SCAN_INTERVAL = 30


def client_mac(client: dict) -> str | None:
    mac = client.get("macAddress") or client.get("mac")
    return mac.lower() if mac else None


def client_name(client: dict) -> str | None:
    return client.get("name") or client.get("hostName")


def is_wireless(client: dict) -> bool:
    if (kind := client.get("clientType")) is not None:
        return kind == "wireless"
    return bool(client.get("wirelessNetworkId"))


def is_online(item: dict) -> bool:
    """clientSummary also lists recently-seen clients with status "down"."""
    return item.get("status") == "up"

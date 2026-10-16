# HPE Instant On for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
![Version](https://img.shields.io/badge/version-0.3.0-blue)

An **unofficial, read-only** Home Assistant integration for **HPE Aruba Networking Instant On** access points and switches.
It polls the same cloud API the Instant On web portal uses, so you get presence detection for every client on your network, plus
the online status of each AP and switch and the health of each site.

> [!WARNING]
> This integration uses an **undocumented** API that HPE does not support. It can break without notice.
> It is not affiliated with or endorsed by HPE.

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Step 1: create a dedicated account](#step-1-create-a-dedicated-account)
- [Step 2: install](#step-2-install)
- [Step 3: configure](#step-3-configure)
- [Entities](#entities)
- [Example automations](#example-automations)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Limitations](#limitations)
- [Documentation](#documentation)
- [Credits and license](#credits-and-license)

## Features

- **Presence detection** for every wired and wireless client (`device_tracker`), with the AP or switch port it's connected to
- **Online/offline sensor** for every AP and switch, with uptime, health, uplink and firmware-currency attributes
- **Per-site sensors**: total, wireless and wired client counts, network device count, active alerts, health score, aggregate throughput, most active and busiest clients
- Set up entirely in the UI, with site selection, re-authentication and options (poll interval, client tracking on/off)
- Downloadable **diagnostics** with personal data redacted
- Supports multiple sites per account and multiple accounts

## Requirements

| | |
|---|---|
| Home Assistant | 2024.11 or later |
| Instant On | Any site managed in the Instant On cloud portal (APs and/or switches) |
| Account | A dedicated Instant On account with **MFA off** and **view-only** access ([why](#step-1-create-a-dedicated-account)) |
| Network | Outbound HTTPS from Home Assistant to `portal.instant-on.hpe.com` and `sso.arubainstanton.com` |

## Step 1: create a dedicated account

The API sign-in uses an email and password and **cannot answer an MFA prompt**. Don't turn off MFA on your admin account. Instead:

1. In the Instant On portal or app, open **Site → Administration → Invite** (wording varies by version) and invite a new email address
   (for example `you+homeassistant@example.com`) with the **view-only** role.
2. Accept the invitation and set a strong, unique password.
3. Make sure MFA is **off** for this new account. To check, sign in at <https://portal.instant-on.hpe.com>: you should not be asked for a code.

View-only access is enough for everything this integration does.

## Step 2: install

### HACS (recommended)

1. In HACS, open the three-dot menu → **Custom repositories**.
2. Add `https://github.com/marklitwin/ha-instant-on` with category **Integration**.
3. Search for **HPE Instant On**, then click **Download**.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/instant_on` from this repository into `/config/custom_components/` on your Home Assistant host.
2. Restart Home Assistant.

## Step 3: configure

1. Go to **Settings → Devices & services → Add integration** and search for **HPE Instant On**.
2. Enter the dedicated account's email and password.
3. Choose which sites to include. All sites are selected by default.

### Options

Open **Configure** on the integration card to change:

| Option | Default | Notes |
|---|---|---|
| Poll interval | 60 s | 15 to 3600 s. Also a **Poll interval** number entity on the site device. Lower values refresh stats sooner and send more requests to HPE. |
| Create device trackers for clients | On | Turn off if you only want the site and device sensors. |

### Enable the trackers you care about

A site can have hundreds of clients, so **client trackers are created disabled**. To enable them, go to
**Settings → Entities**, search for `device_tracker.` and filter by the integration, select the clients you want (phones, for example),
then click **Enable selected**.

## Entities

### Per site (device: *Instant On &lt;site name&gt;*)

| Entity | State | Attributes |
|---|---|---|
| `number.<site>_poll_interval` | Seconds between cloud polls | |
| `sensor.<site>_clients` | Connected clients | `online_clients` (name, rates, signal, bytes) |
| `sensor.<site>_wireless_clients` | Connected wireless clients | |
| `sensor.<site>_wired_clients` | Connected wired clients | |
| `sensor.<site>_network_devices` | APs and switches in inventory | |
| `sensor.<site>_active_alerts` | Active alert count | `latest_alert`, info/minor/major counts |
| `sensor.<site>_health_score` | Site health score, 0 to 100 | `health`, `reason` |
| `sensor.<site>_total_throughput` | Sum of online client bit rates | `top_by_throughput` (top 5) |
| `sensor.<site>_most_active_client` | Client with highest current throughput | `throughput_bps`, `upstream_bps`, `downstream_bps`, `also_active` |
| `sensor.<site>_busiest_client` | Client with most data transferred | `activity_bytes`, `bytes_last_24h`, `bytes_session`, `also_busy` |

### Per AP or switch (one device each, linked to the site)

| Entity | State | Attributes |
|---|---|---|
| `binary_sensor.<device name>` | `on` = connected (status `up`) | `deviceType`, `health`, `operationalState`, `uptimeInSeconds`, `numberOfSecondsSinceLastCommunication`, `uplinkDeviceName`, `isUpToDate`, `wiredClientsCount`, `inputPowerSource` |

The device registry entry includes the model, SKU, serial number, firmware version and MAC address.

### Per client

Each client is a device under the site, with these sensors enabled:

| Entity | State |
|---|---|
| `sensor.<client>_download` | Current download rate |
| `sensor.<client>_upload` | Current upload rate |
| `sensor.<client>_signal_strength` | Wireless signal, dBm |
| `sensor.<client>_data_transferred` | Bytes moved (24 h total when the API sends it, otherwise the session total) |

Device trackers are still created disabled. Enable the ones you want for presence.

| Entity | State | Attributes |
|---|---|---|
| `device_tracker.<client name>` | `home` / `not_home` | `ip`, `host_name`, `mac`, `connection` (wired/wireless), `deviceName` (AP or switch), `switch_port`, `wirelessBand`, `wirelessNetworkName`, `wiredNetworkName`, `signalQuality`, `snrInDb`, `health`, `stateDurationInSeconds`, `throughput_bps`, `upstream_bps`, `downstream_bps`, `bytes_last_24h`, `bytes_session` (when connected) |

You can assign these trackers to a **Person** for presence.

## Example automations

<details>
<summary>Notify when an access point goes offline</summary>

```yaml
alias: Instant On - AP offline
triggers:
  - trigger: state
    entity_id: binary_sensor.upstairsap
    to: "off"
    for: "00:05:00"
actions:
  - action: notify.notify
    data:
      message: "Upstairs AP has been offline for 5 minutes"
```
</details>

<details>
<summary>Notify on new Instant On alerts</summary>

```yaml
alias: Instant On - new alert
triggers:
  - trigger: state
    entity_id: sensor.instant_on_home_active_alerts
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.state | int(0) > trigger.from_state.state | int(0) }}"
actions:
  - action: notify.notify
    data:
      message: "Instant On has {{ trigger.to_state.state }} active alert(s)"
```
</details>

<details>
<summary>Turn off lights when everyone's phone leaves Wi-Fi</summary>

```yaml
alias: Everyone left
triggers:
  - trigger: state
    entity_id:
      - device_tracker.alex_phone
      - device_tracker.sam_phone
    to: not_home
    for: "00:10:00"
conditions:
  - condition: state
    entity_id:
      - device_tracker.alex_phone
      - device_tracker.sam_phone
    state: not_home
actions:
  - action: light.turn_off
    target:
      area_id: living_room
```
</details>

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| **"Login failed"** during setup | Wrong password, or MFA is still on for the account. Sign in at the portal and check you're not asked for a code. |
| **"This account has no sites"** | The account wasn't invited to a site, or the invitation wasn't accepted. |
| A **re-authenticate** notification appears | The password changed or the account was locked. Click **Reconfigure** and enter the new password. |
| All entities are **unavailable** | Your internet connection or the Instant On cloud is down, or the API changed. Check the logs. |
| A wired client has **no IP** | Expected: the API reports no IP for most wired clients. Presence uses the MAC address. |
| Phone flips to `not_home` while at home | The phone's Wi-Fi sleeps or it uses a private (random) MAC. Turn off private MAC for your home network on the phone. |
| A value looks wrong | Download diagnostics (integration card → three-dot menu → **Download diagnostics**) and open an issue with the file attached. |

### Debug logging

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.instant_on: debug
```

## FAQ

**Does it talk to my devices locally?** No. Everything goes through HPE's cloud, the same as the Instant On app.

**Can it block clients, toggle SSIDs or power-cycle PoE ports?** Not yet. The integration is read-only by design, and a view-only account
can't make changes anyway. Write support would need the portal's change requests mapped out first. Contributions are welcome.

**How much traffic does it generate?** Each poll makes `1 + 2 × number of sites` small HTTPS requests. The sign-in token lasts about 30 minutes,
so it signs in again (3 requests) roughly every 30 minutes.

**Where are my credentials stored?** In Home Assistant's config entry storage (`/config/.storage/core.config_entries`), unencrypted, like most
integrations. This is why the account should be dedicated, view-only and used for nothing else.

## Limitations

- Unofficial API: it may change or be blocked at any time (the old `wiredClientSummary` endpoint already returns 404).
- Cloud only: presence updates once per poll interval, and the integration doesn't work while the internet or the HPE cloud is down.
- MFA must be off on the integration's account.
- Alerts come from the site summary. The alert detail endpoint isn't used yet.

## Documentation

- [Architecture](docs/ARCHITECTURE.md): components, data flow, sign-in sequence, error handling
- [API notes](docs/API.md): endpoints and fields seen on a live site
- [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

## Credits and license

- Forked from [grahamfairbank/ha-instant-on](https://github.com/grahamfairbank/ha-instant-on), with client throughput and “most active” sensors added.
- The sign-in flow and endpoints were first documented by [blog.puddle.town/instant-on](https://blog.puddle.town/instant-on/).
- Released under the [MIT License](LICENSE).
- HPE, Aruba and Instant On are trademarks of Hewlett Packard Enterprise. This project is not affiliated with HPE.

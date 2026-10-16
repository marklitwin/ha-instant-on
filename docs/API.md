# Instant On API notes

These are notes on the **undocumented** Instant On portal API, as seen on a live site on 2026-10-16
(firmware 3.4.2 on AP-505 access points and JL681A/JL684A switches). HPE can change any of this.
The sign-in flow was first documented at <https://blog.puddle.town/instant-on/>.

## Discovery

`GET https://portal.instant-on.hpe.com/settings.json` (no authentication needed)

```json
{
  "restApiUrl": "https://portal.instant-on.hpe.com",
  "healthApiUrl": "https://health.portal.instant-on.hpe.com",
  "ssoRedirectUrl": "https://portal.instant-on.hpe.com",
  "ssoClientIdAuthZ": "<client id>",
  "ssoFqdn": "https://sso.arubainstanton.com",
  "featureFlags": { "federatedSSO": true }
}
```

## Authentication

| Step | Request | Response |
|---|---|---|
| 1 | `POST {ssoFqdn}/aio/api/v1/mfa/validate/full`, form: `username`, `password` | `200 {access_token, expires_in, success, token_type}`, or `400 {"error":"invalid_grant", ...}` |
| 2 | `GET {ssoFqdn}/as/authorization.oauth2` with `client_id`, `redirect_uri`, `response_type=code`, `scope=profile openid`, `state`, `code_challenge`, `code_challenge_method=S256`, `sessionToken` (don't follow redirects) | `302`, with `code` and `state` in the `Location` query string |
| 3 | `POST {ssoFqdn}/as/token.oauth2`, form: `client_id`, `redirect_uri`, `code`, `code_verifier`, `grant_type=authorization_code` | `200 {access_token, expires_in: 1799, id_token, refresh_token, scope, token_type}` |

## REST calls

All calls are `GET {restApiUrl}/api/...` with these headers:

```
Authorization: Bearer <access_token>
x-ion-api-version: 7
Accept: application/json
```

Lists come back as `{"elements": [...], "kind": ..., "totalCount": ..., ...}`.

| Endpoint | Used | Contents |
|---|---|---|
| `/api/sites/` | yes | Sites |
| `/api/sites/{id}/clientSummary` | yes | Wired and wireless clients, including recently disconnected ones |
| `/api/sites/{id}/inventory` | yes | APs and switches |
| `/api/sites/{id}/alerts` | no | Alerts (none were present, so the format wasn't seen) |
| `/api/sites/{id}/networksSummary` | no | Wi-Fi and wired network definitions |
| `/api/sites/{id}/wiredClientSummary` | n/a | **Removed (404)** |

## Key fields

### Site (`/api/sites/` elements)

`id`, `name`, `status` (`up`), `health` (`good`…), `healthReason`, `currentHealthScore.{score, scoreSeverity, conditionsCount}`,
`activeAlertsCount`, `activeAlertsCounters.{activeInfoAlertsCount, activeMinorAlertsCount, activeMajorAlertsCount}`,
`latestActiveAlert`, `latestAlert`, `timezoneIana`, `isMaintenanceMode`, `updateInProgress`, `userRoleOnSite`.

### Client (`clientSummary` elements)

| Field | Notes |
|---|---|
| `id`, `macAddress` | Client MAC (identical) |
| `name`, `hostName` | Friendly name; hostname |
| `status` | `up` = connected, `down` = recently disconnected but still listed |
| `clientType` | `wireless` / `wired` |
| `ipAddress` | Often `""` for wired clients |
| `deviceId`, `deviceName` | AP or switch the client is connected to |
| `connectedToPorts[]` | Wired only: `deviceName`, `portName`, `portNumber`, `portSpeed`, `duplex`, PoE flags |
| `wirelessNetworkId/Name`, `wirelessBand`, `wirelessRadioId` | Wireless only |
| `wiredNetworkId/Name` | Network (VLAN) name |
| `signalQuality`, `snrInDb`, `health` | Wireless quality |
| `stateDurationInSeconds` | Time in the current state |
| `dataTraffic`, `upstream/downstreamThroughputInBitsPerSecond` | Traffic counters (also `upstreamSpeedInBitsPerSecond` / `downstreamSpeedInBitsPerSecond` on older payloads) |
| `dataTraffic.totalDataTransferredDuringLast24HoursInBytes` | Optional 24 h total |
| `dataTraffic.upstream/downstreamDataTransferredDuringLast24HoursInBytes` | Optional 24 h per direction |
| `totalDataTransferredInBytes` | Session total (sometimes on the client or inside `dataTraffic`) |
| `isBlocked`, `isBlockable`, `isWatchlisted` | Client controls (read-only here) |

### Device (`inventory` elements)

| Field | Notes |
|---|---|
| `id`, `macAddress` | Device MAC (identical) |
| `name`, `defaultName` | User-set name; default name (the serial number) |
| `deviceType`, `deviceRole` | `accessPoint` / `switch` |
| `model`, `sku`, `serialNumber` | e.g. `AP-505` / `R4W01A` |
| `status`, `operationalState`, `health` | `up`, `active`, `good` |
| `uptimeInSeconds`, `numberOfSecondsSinceLastCommunication` | |
| `currentFirmwareVersion`, `deviceSoftwareVersion`, `isUpToDate` | |
| `uplinkDeviceName`, `uplinkDeviceMacAddress` | Upstream switch |
| `inputPowerSource`, `poePdClass`, `poePseStatus` | Power |
| `radios[]` | APs: `band`, `channel`, `channelWidth`, `utilizationPercent` |
| `ethernetPorts[]` | Per-port configuration and state |
| `wirelessNetworks[]` | SSIDs on the AP |
| `ipAddress`, `subnetMask`, `defaultGateway`, `primaryDns` | Management IP |

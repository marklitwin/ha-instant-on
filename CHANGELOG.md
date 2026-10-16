# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-16

### Added
- Per-site **total throughput** sensor (sum of online clients' upload + download bit rates).
- **Most active client** sensor (highest current throughput) with a ranked `also_active` attribute list.
- **Busiest client** sensor (most bytes transferred, preferring 24 h counters from `dataTraffic`) with `also_busy`.
- Client device trackers now expose throughput and byte counters when connected.

## [0.1.0] - 2026-10-16

### Added
- First release: UI setup with site selection, re-authentication and options (poll interval, client tracking).
- Per-site sensors: clients, wireless clients, wired clients, network devices, active alerts, health score.
- Connectivity binary sensor for each AP and switch.
- Device tracker for each client (disabled by default), with the connected AP or switch port.
- Diagnostics with personal data redacted.
- Hostnames and the OAuth client ID are read from the portal's `settings.json` instead of being hard-coded.

### Notes
- Tested against a live site with AP-505 access points and JL681A/JL684A switches (firmware 3.4.2).

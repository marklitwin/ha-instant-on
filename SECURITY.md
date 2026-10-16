# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for security problems. Use GitHub's
[private vulnerability reporting](../../security/advisories/new) instead. You should get a reply within 7 days.

## How the integration handles credentials

- The Instant On email and password are stored in Home Assistant's config entry storage (`.storage/core.config_entries`),
  which is **not encrypted**. Anyone with access to your Home Assistant config directory or backups can read them.
- Bearer tokens are kept in memory only.
- Diagnostics redact credentials, MAC and IP addresses, hostnames, names and serial numbers.
- The integration only makes `GET` requests to the REST API.

## Recommendations

- Use a **dedicated** Instant On account with the **view-only** role, used for nothing else.
- MFA has to be off for that account, so give it a long, unique password.
- **Never** turn off MFA on an account with admin rights.
- If you think the password has leaked, change it in Instant On, then re-authenticate in Home Assistant.
- Treat Home Assistant backups as sensitive.

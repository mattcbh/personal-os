# PnT Runtime Inventory

Observed production host at hardening time: Mac Mini (`homeserver@brain`) on 2026-03-11.

## Runtime Identity

- Production repo path: `~/Projects/pnt-data-warehouse`
- Production host: Mac Mini only
- Current observed production branch at hardening time: `feature/paper-supplies-in-prime-cost`
- Branch policy after hardening:
  - the active production branch must be explicit
  - it must have an upstream on GitHub
  - branch state is checked with `automation-machine-config/bin/check-pnt-runtime.sh`

## Launchd Jobs

| Label | Schedule | Script |
|---|---|---|
| `com.pnt.daily-sync` | Daily 4:00 AM | `scripts/daily_sync.sh` |
| `com.pnt.systematiq-monitor` | Daily 4:30 AM | `scripts/systematiq_monitor.py` |
| `com.pnt.weekly-flash-preview` | Sunday 10:15 PM | `scripts/weekly_flash_preview.sh` |
| `com.pnt.weekly-flash` | Sunday 10:30 PM | `scripts/weekly_flash.sh` |
| `com.pnt.weekly-se-sync` | Sunday 4:00 AM | `scripts/weekly_se_sync.sh` |
| `com.pnt.backfill-monitor` | 9:00 AM and 9:00 PM daily | `scripts/backfill_monitor.py` |

## Persistent Services

| Label | Mode | Purpose |
|---|---|---|
| `com.pnt.metabase` | KeepAlive / RunAtLoad | Metabase server on port 3001 |
| `com.pnt.chart-server` | KeepAlive / RunAtLoad | Local chart server on port 3002 |
| `com.pnt.cloudflared-tunnel` | KeepAlive / RunAtLoad | Named Cloudflare tunnel |
| `com.pnt.cloudflared-charts` | KeepAlive / RunAtLoad | Public tunnel to chart server |
| `com.pnt.cloudflared-metabase` | KeepAlive / RunAtLoad | Public tunnel to Metabase |

## Logs

- Primary logs directory: `~/Library/Logs/pnt-data-warehouse/`
- Additional service logs:
  - `/tmp/metabase-launchd.log`
  - `/tmp/chart-server.log`
  - `/tmp/cloudflared-tunnel.log`
  - `/tmp/cloudflared-charts.log`
  - `/tmp/cloudflared-metabase.log`

## Secrets And Runtime-Only Material

Keep these local to the Mac Mini and out of Git:

- `~/Projects/pnt-data-warehouse/.env.toast`
- `~/Projects/pnt-data-warehouse/data/*-session.json`
- `~/Projects/pnt-data-warehouse/data/qbo-tokens.json`
- `~/Projects/pnt-data-warehouse/data/*-exports/`
- `~/Projects/pnt-data-warehouse/data/screenshots/`
- generated weekly flash artifacts and HTML outputs in the repo root

## Operational Rules

- This cluster is intentionally separate from `automation-runtime-personal` and `automation-runtime-work`.
- Do not move it into the runtime split during this hardening pass.
- Use `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh` from the laptop to verify:
  - repo branch and upstream
  - working-tree dirtiness
  - launchd job presence
  - log path existence
  - key runtime files

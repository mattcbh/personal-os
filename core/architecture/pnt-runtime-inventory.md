# PnT Runtime Inventory

Observed production host at hardening time: Mac Mini (`homeserver@brain`) on 2026-03-11.

## Runtime Identity

- Production repo path: `~/Projects/pnt-data-warehouse`
- Production host: Mac Mini only
- Current production branch: `feature/pnt-production-baseline`
- Branch policy after hardening:
  - the active production branch must be explicit and human-readable
  - it must have an upstream on GitHub before it is treated as production
  - `main` is the long-lived integration branch, not an auto-deployed branch
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
| `com.pnt.cloudflared-charts` | KeepAlive / RunAtLoad | Legacy direct tunnel to chart server |
| `com.pnt.cloudflared-metabase` | KeepAlive / RunAtLoad | Legacy direct tunnel to Metabase |

## Optional Service Policy

These services are intentionally not all treated as mandatory:

| Label | Current policy | Notes |
|---|---|---|
| `com.pnt.backfill-monitor` | Dormant unless a finite backfill campaign is active | Last observed log activity was February 2026. Re-enable only for bounded cleanup or backfill work. |
| `com.pnt.cloudflared-charts` | Disabled by default | Superseded by the named Cloudflare tunnel. Keep plist for fallback only. |
| `com.pnt.cloudflared-metabase` | Disabled by default | Superseded by the named Cloudflare tunnel. Keep plist for fallback only. |

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
- Use `feature/pnt-production-baseline` as the pinned production branch on the Mini until a deliberate promotion to `main` happens.
- Do not treat stale feature-branch names as stable production identifiers.
- Use `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh` from the laptop to verify:
  - repo branch and upstream
  - working-tree dirtiness
  - launchd job presence
  - log path existence
  - key runtime files
- Follow `core/architecture/pnt-operator-runbook.md` for promotion, rollback, and service decisions.

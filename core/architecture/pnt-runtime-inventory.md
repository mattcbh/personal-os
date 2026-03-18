# PnT Runtime Inventory

Observed live Mini state verified on 2026-03-18.

## Runtime Identity

- Production host: Mini only
- Warehouse authoring repo: `~/Projects/pnt-data-warehouse`
- Warehouse production runtime: `~/Production/pnt-data-warehouse-runtime`
- Observed authoring repo branch: `main`
- Observed production runtime branch: `main`
- Observed authoring repo commit: `7a62479`
- Observed production runtime commit: `a4024e2`
- Shared secret path:
  - `~/Production/pnt-data-warehouse-runtime/.env.toast` is a symlink to `~/Projects/pnt-data-warehouse/.env.toast`

## Current-State Notes

- Most installed warehouse launchd jobs on the Mini run from `~/Production/pnt-data-warehouse-runtime`.
- One installed job currently points at the authoring repo instead:
  - `com.pnt.weekly-prime-margin` -> `~/Projects/pnt-data-warehouse/scripts/weekly_cogs_pipeline.sh`
- `automation-machine-config/bin/check-pnt-runtime.sh` still validates `~/Projects/pnt-data-warehouse` as the primary repo path, so it does not fully describe the live production-runtime split by itself.

## Launchd Jobs

| Label | Schedule | Runtime path |
|---|---|---|
| `com.pnt.daily-sync` | Daily 4:00 AM | `~/Production/pnt-data-warehouse-runtime/scripts/daily_sync.sh` |
| `com.pnt.systematiq-monitor` | Daily 4:30 AM | `~/Production/pnt-data-warehouse-runtime/scripts/systematiq_monitor.py` |
| `com.pnt.foot-traffic-rollup-hourly` | Hourly at `:00` | `~/Production/pnt-data-warehouse-runtime/scripts/foot_traffic_rollup_hourly.sh` |
| `com.pnt.foot-traffic-health-check` | 8:00 AM through 10:00 PM, every 2 hours | `~/Production/pnt-data-warehouse-runtime/scripts/foot_traffic_health_check.sh` |
| `com.pnt.weekly-flash-preview` | Sunday 10:15 PM | `~/Production/pnt-data-warehouse-runtime/scripts/weekly_flash_preview.sh` |
| `com.pnt.weekly-flash` | Sunday 10:30 PM | `~/Production/pnt-data-warehouse-runtime/scripts/weekly_flash.sh` |
| `com.pnt.weekly-se-sync` | Sunday 4:00 AM | `~/Production/pnt-data-warehouse-runtime/scripts/weekly_se_sync.sh` |
| `com.pnt.weekly-prime-margin` | Wednesday 6:00 AM | `~/Projects/pnt-data-warehouse/scripts/weekly_cogs_pipeline.sh` |
| `com.pnt.backfill-monitor` | 9:00 AM and 9:00 PM daily | `~/Production/pnt-data-warehouse-runtime/scripts/backfill_monitor.py` |

## Persistent Services

| Label | Mode | Purpose |
|---|---|---|
| `com.pnt.metabase` | KeepAlive / RunAtLoad | Metabase server on port 3001 |
| `com.pnt.chart-server` | KeepAlive / RunAtLoad | Local chart server on port 3002 |
| `com.pnt.cloudflared-tunnel` | KeepAlive / RunAtLoad | Named Cloudflare tunnel |
| `com.pnt.cloudflared-charts` | KeepAlive / RunAtLoad | Legacy direct tunnel to chart server |
| `com.pnt.cloudflared-metabase` | KeepAlive / RunAtLoad | Legacy direct tunnel to Metabase |

## Optional Service Policy

These services are intentionally not all treated as mandatory, and the live Mini currently does not have every installed service loaded:

| Label | Current policy | Notes |
|---|---|---|
| `com.pnt.backfill-monitor` | Installed but currently not loaded | Re-enable only for bounded cleanup or backfill work. |
| `com.pnt.foot-traffic-rollup-hourly` | Loaded | Live on the Mini and should stay in the warehouse inventory. |
| `com.pnt.foot-traffic-health-check` | Loaded | Live on the Mini and should stay in the warehouse inventory. |
| `com.pnt.weekly-prime-margin` | Loaded | Currently runs from the authoring repo path, not the production runtime path. |
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

Keep these local to the Mini and out of Git:

- `~/Projects/pnt-data-warehouse/.env.toast`
- `~/Production/pnt-data-warehouse-runtime/data/*-session.json`
- `~/Production/pnt-data-warehouse-runtime/data/qbo-tokens.json`
- `~/Production/pnt-data-warehouse-runtime/data/*-exports/`
- `~/Production/pnt-data-warehouse-runtime/data/screenshots/`
- generated weekly flash artifacts and HTML outputs in the repo root

## Operational Rules

- This cluster is intentionally separate from `automation-runtime-personal` and `automation-runtime-work`.
- Do not move it into the runtime split during this hardening pass.
- Do not assume the warehouse has a single canonical Mini runtime path until the authoring/production split is formally reconciled.
- Do not treat older feature-branch documentation as the live production truth without checking the Mini first.
- Use `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh` from the Laptop to verify:
  - authoring repo branch and upstream
  - authoring repo working-tree dirtiness
  - launchd job presence
  - log path existence
  - key authoring-repo runtime files
- Use direct Mini inspection as well when validating the live production runtime path:
  - `~/Production/pnt-data-warehouse-runtime`
  - installed warehouse plists in `~/Library/LaunchAgents/`
- Follow `core/architecture/pnt-operator-runbook.md` for promotion, rollback, and service decisions.

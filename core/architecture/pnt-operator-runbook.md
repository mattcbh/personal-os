# PnT Operator Runbook

This runbook defines how to inspect, change, validate, and recover the standalone PnT production system on the Mini.

## Current Baseline

- Production host: `homeserver@brain` on the Mini
- Warehouse authoring repo: `~/Projects/pnt-data-warehouse`
- Warehouse production runtime: `~/Production/pnt-data-warehouse-runtime`
- Observed authoring repo branch: `main`
- Observed production runtime branch: `main`
- Health check script: `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh`
- Important limitation:
  - `check-pnt-runtime.sh` validates the authoring repo path and the presence of key launchd jobs, but it does not fully encode the current authoring/production runtime split.

## Branch Policy

- `main` is the observed live branch in both the warehouse authoring repo and the current production runtime.
- If a future production branch diverges from `main`, document that explicitly in:
  - `core/architecture/pnt-runtime-inventory.md`
  - `core/architecture/system-architecture.md`
- Branch promotion is not considered complete until:
  - the relevant GitHub branch exists and has an upstream
  - the Mini production runtime path has been updated deliberately
  - `check-pnt-runtime.sh` passes
  - the installed launchd targets still point at the intended runtime path

## Safe Change Flow

1. Make and test changes in a normal clone or worktree.
2. Push the branch to GitHub before touching the Mini.
3. On the Mini:
   - `ssh homeserver@brain`
   - inspect both paths before changing anything:
     - `cd ~/Projects/pnt-data-warehouse`
     - `cd ~/Production/pnt-data-warehouse-runtime`
   - `git fetch origin`
   - switch and update the path that actually owns the installed job you intend to change
4. Verify with:
   - `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh`
   - `ls -1 ~/Library/LaunchAgents/com.pnt*.plist`
   - `plutil -p ~/Library/LaunchAgents/<label>.plist`
5. Only promote to `main` after the production branch is stable and reviewed.

## Promotion To Main

Use this only when you want the long-lived integration branch to absorb the current production branch:

1. Review the delta:
   - `git log --oneline origin/main..<branch>`
   - `git diff --stat origin/main...<branch>`
2. Merge or rebase deliberately from a non-production clone.
3. Push `main`.
4. Decide whether the Mini production runtime should stay pinned to the current checkout or switch back to `main`.

## Rollback

If the active production branch becomes unhealthy:

1. Find the last known good commit:
   - `git log --oneline --decorate --max-count=20`
2. Identify which Mini path owns the failing launchd target:
   - `~/Projects/pnt-data-warehouse`
   - `~/Production/pnt-data-warehouse-runtime`
3. Reset the production branch only if you intend to move branch history:
   - `git reset --hard <good-commit>`
4. Prefer safer rollback by switching the Mini back to a known-good branch or commit and only then deciding what to do with branch history.
4. Re-run:
   - `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh`

## Service Policy

Mandatory scheduled jobs:

- `com.pnt.daily-sync`
- `com.pnt.systematiq-monitor`
- `com.pnt.weekly-flash`

Normally active supporting jobs and services:

- `com.pnt.foot-traffic-rollup-hourly`
- `com.pnt.foot-traffic-health-check`
- `com.pnt.weekly-flash-preview`
- `com.pnt.weekly-prime-margin`
- `com.pnt.weekly-se-sync`
- `com.pnt.metabase`
- `com.pnt.chart-server`
- `com.pnt.cloudflared-tunnel`

Dormant or fallback services:

- `com.pnt.backfill-monitor`
  - Keep disabled unless a bounded backfill or repair campaign is active.
- `com.pnt.cloudflared-charts`
  - Keep disabled by default. The named tunnel is the primary public ingress path.
- `com.pnt.cloudflared-metabase`
  - Keep disabled by default. The named tunnel is the primary public ingress path.

## Useful Commands

Status:

```bash
~/Projects/automation-machine-config/bin/check-pnt-runtime.sh
```

Branch + working tree:

```bash
ssh homeserver@brain 'cd ~/Projects/pnt-data-warehouse && git branch -vv && git status --short'
```

Production runtime branch + working tree:

```bash
ssh homeserver@brain 'cd ~/Production/pnt-data-warehouse-runtime && git branch -vv && git status --short'
```

Launchd status:

```bash
ssh homeserver@brain 'for label in \
  com.pnt.daily-sync \
  com.pnt.systematiq-monitor \
  com.pnt.foot-traffic-rollup-hourly \
  com.pnt.foot-traffic-health-check \
  com.pnt.weekly-flash \
  com.pnt.weekly-flash-preview \
  com.pnt.weekly-prime-margin \
  com.pnt.weekly-se-sync \
  com.pnt.metabase \
  com.pnt.chart-server \
  com.pnt.cloudflared-tunnel; do
  echo "[$label]"
  launchctl print gui/$(id -u)/$label | sed -n "1,12p"
  echo "---"
done'
```

Installed target for a specific warehouse job:

```bash
ssh homeserver@brain 'plutil -p ~/Library/LaunchAgents/com.pnt.daily-sync.plist'
```

Recent logs:

```bash
ssh homeserver@brain 'ls -lt ~/Library/Logs/pnt-data-warehouse | head'
```

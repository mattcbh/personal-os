# PnT Operator Runbook

This runbook defines how to change, validate, and recover the standalone PnT production system on the Mac Mini.

## Current Baseline

- Production host: `homeserver@brain`
- Production repo: `~/Projects/pnt-data-warehouse`
- Active production branch: `feature/pnt-production-baseline`
- Integration branch: `main`
- Health check: `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh`

## Branch Policy

- `feature/pnt-production-baseline` is the pinned production branch on the Mac Mini.
- `main` is the integration branch. It is not auto-deployed.
- Feature branches are acceptable for production only when:
  - the Mini is explicitly switched to that branch
  - the branch has an upstream on GitHub
  - `check-pnt-runtime.sh` passes after the change
- If a feature branch becomes the long-lived production branch, rename it to a descriptive production-facing name before treating it as stable.

## Safe Change Flow

1. Make and test changes in a normal clone or worktree.
2. Push the branch to GitHub before touching the Mini.
3. On the Mini:
   - `ssh homeserver@brain`
   - `cd ~/Projects/pnt-data-warehouse`
   - `git fetch origin`
   - `git switch <branch>`
   - `git pull --ff-only origin <branch>`
4. Verify with:
   - `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh`
5. Only promote to `main` after the production branch is stable and reviewed.

## Promotion To Main

Use this only when you want the long-lived integration branch to absorb the current production branch:

1. Review the delta:
   - `git log --oneline origin/main..feature/pnt-production-baseline`
   - `git diff --stat origin/main...feature/pnt-production-baseline`
2. Merge or rebase deliberately from a non-production clone.
3. Push `main`.
4. Decide whether the Mini should stay pinned to the production branch or switch back to `main`.

## Rollback

If the active production branch becomes unhealthy:

1. Find the last known good commit:
   - `git log --oneline --decorate --max-count=20`
2. Reset the production branch only if you intend to move branch history:
   - `git reset --hard <good-commit>`
3. Prefer safer rollback by switching the Mini back to a known-good branch or commit and only then deciding what to do with branch history.
4. Re-run:
   - `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh`

## Service Policy

Mandatory scheduled jobs:

- `com.pnt.daily-sync`
- `com.pnt.systematiq-monitor`
- `com.pnt.weekly-flash`

Normally active supporting jobs and services:

- `com.pnt.weekly-flash-preview`
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

Launchd status:

```bash
ssh homeserver@brain 'for label in \
  com.pnt.daily-sync \
  com.pnt.systematiq-monitor \
  com.pnt.weekly-flash \
  com.pnt.weekly-flash-preview \
  com.pnt.weekly-se-sync \
  com.pnt.metabase \
  com.pnt.chart-server \
  com.pnt.cloudflared-tunnel; do
  echo "[$label]"
  launchctl print gui/$(id -u)/$label | sed -n "1,12p"
  echo "---"
done'
```

Recent logs:

```bash
ssh homeserver@brain 'ls -lt ~/Library/Logs/pnt-data-warehouse | head'
```

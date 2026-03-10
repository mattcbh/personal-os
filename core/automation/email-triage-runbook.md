# Email Triage Runbook

Legacy v1 runbook. For the rebuilt cloud-first implementation, see `core/automation/email-triage-v2-runbook.md`.

## Manual dry-run

```bash
cd ~/Obsidian/personal-os
./core/automation/email-triage.sh --run-label am --dry-run --log-json
```

Dry-run is side-effect free: no outbound triage email, no draft queueing, no Things task creation, no project/state writes.

## Manual live run

```bash
cd ~/Obsidian/personal-os
./core/automation/email-triage.sh --run-label am --log-json

# or pin model explicitly
./core/automation/email-triage.sh --run-label am --model opus --log-json
```

`email-triage.sh` now enforces:
- lock guard to prevent overlapping runs
- MCP preflight check (both Gmail accounts)
- hard timeout for Claude triage execution
- one retry on `opus` with reduced scope (25 most recent) when timeout/transport errors occur
- deterministic markdown rendering from `logs/email-triage-records-YYYY-MM-DD-<am|pm>.json`
- validator gate before final send

Optional env overrides:

```bash
EMAIL_TRIAGE_PRECHECK_TIMEOUT_SECONDS=90
EMAIL_TRIAGE_CLAUDE_TIMEOUT_SECONDS=600
EMAIL_TRIAGE_SEND_TIMEOUT_SECONDS=180
EMAIL_TRIAGE_RETRY_DELAY_SECONDS=10
```

## Validate latest digest

```bash
python3 core/automation/email-triage-validator.py report \
  --markdown Knowledge/DIGESTS/triage-YYYY-MM-DD-am.md \
  --contract core/automation/email-triage-contract.json
```

Validation is now strict for critical issues (duplicate threads, malformed/wrong Superhuman links, invalid unsubscribe links).

## Identity resolution check (manual)

```bash
python3 core/automation/email-identity-resolver.py --email amitmshah74@gmail.com --name "Amit Shah"
```

## Validate/repair state files

```bash
python3 core/automation/email-triage-validator.py state \
  --triage-state core/state/email-triage-state.json \
  --monitor-state core/state/email-monitor-state.json \
  --write
```

## Logs

- Plain log: `logs/email-triage.log`
- Structured events: `logs/email-triage.jsonl`
- Per-run Claude output: `logs/email-triage-<runid>.claude.log`
- Per-run validation report: `logs/email-triage-<runid>.validation.json`
- Draft outcome state: `core/state/superhuman-draft-status.json`

## Launchd integration

- Morning: `launchd-plists/com.brain.email-triage-morning.plist`
- Evening: `launchd-plists/com.brain.email-triage-evening.plist`
- Install/update all plists: `./core/automation/setup-on-brain.sh`

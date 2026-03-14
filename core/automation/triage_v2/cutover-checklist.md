# Email Triage v2 Cutover Checklist

Reference copy only. Run these commands from `~/Projects/automation-runtime-work/` on the target machine.

## 1. Pre-cutover validation

1. Validate Gmail OAuth for both accounts:
   ```bash
   cd ~/Projects/automation-runtime-work
   export PYTHONPATH=core/automation/triage_v2/src
   python3 -m triage_v2 check-gmail-auth
   ```
2. If any account fails auth, re-auth that account and re-run check:
   ```bash
   export PYTHONPATH=core/automation/triage_v2/src
   python3 -m triage_v2 oauth-init --account work --oauth-client ~/.config/personal-os-secrets/google-oauth/gcp-oauth.keys.json
   python3 -m triage_v2 oauth-init --account personal --oauth-client ~/.config/personal-os-secrets/google-oauth/gcp-oauth.keys.json
   ```
3. Place required missed-email regression fixture at:
   `core/state/email-triage-v2/missed-email-fixture.json`

## 2. Dry-run verification (no live send)

1. Execute end-to-end dry run:
   ```bash
   ./core/automation/email-triage-v2.sh --run-type manual --force-reconcile --dry-run
   ```
2. Capture `run_id` from output and verify status:
   ```bash
   export PYTHONPATH=core/automation/triage_v2/src
   python3 -m triage_v2 run-status --run-id <run_id>
   python3 -m triage_v2 verify-fixture --run-id <run_id> --fixture core/state/email-triage-v2/missed-email-fixture.json
   ```
3. Required pass criteria:
   - run status = `succeeded`
   - coverage `missing_count = 0`
   - fixture check `pass = true`

## 3. Live v2 smoke test

1. Trigger one manual live run:
   ```bash
   ./core/automation/email-triage-v2.sh --run-type manual --force-reconcile
   ```
2. Confirm digest arrival, links, and draft statuses.

## 4. Scheduler cutover

1. Switch launchd from v1 to v2:
   ```bash
   ./core/automation/setup-email-triage-v2-on-brain.sh
   ```
2. Verify active launchd jobs:
   ```bash
   launchctl list | grep "email-triage"
   ```
3. Confirm `com.matthewlieber.automation-work.email-triage-v2-morning` and `com.matthewlieber.automation-work.email-triage-v2-evening` are loaded.

## 5. 48-hour hypercare

1. After each scheduled run, verify:
   - run status
   - coverage report
   - digest send status
2. If v2 has any critical failure, rollback immediately:
   - unload v2 plists
   - reload the prior production labels only if the active runtime repo/runbook for that environment still defines them

## 6. GCP production rollout (after local stabilization)

1. Build/push container image from `core/automation/triage_v2/Dockerfile`
2. Apply Terraform in `core/automation/triage_v2/infra/gcp`
3. Populate Secret Manager values (OAuth + LLM keys)
4. Run API-triggered manual run and validate the same pass criteria as local

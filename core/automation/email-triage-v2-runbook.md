# Email Triage v2 Runbook

This runbook is a reference copy in the vault. The live implementation and runnable commands live in `~/Projects/automation-runtime-work/`.

## Local fallback run

```bash
cd ~/Projects/automation-runtime-work
./core/automation/email-triage-v2.sh --init-db
./core/automation/email-triage-v2.sh --run-type am --force-reconcile --dry-run
```

`--dry-run` keeps Gmail ingestion active but writes outbound digest payloads to local outbox instead of sending.

Digest artifacts now carry:

- semantic `summary_latest` text for every thread, including newsletters and spam
- `response_needed` for reply-worthy threads
- `suggested_response` and `suggested_action` for chief-of-staff style action guidance

Draft routing is Superhuman first when `TRIAGE_V2_SUPERHUMAN_ENABLED=1`; if Superhuman cannot queue the draft, the run falls back to a Gmail draft URL and labels it as `Draft ready in Gmail`.

To run work inbox only (exclude personal), set:

```bash
export TRIAGE_V2_ACCOUNTS=work
```

## Validate Gmail OAuth state

```bash
cd ~/Projects/automation-runtime-work
export PYTHONPATH=core/automation/triage_v2/src
python3 -m triage_v2 check-gmail-auth
```

If a token is revoked, re-auth that account:

```bash
python3 -m triage_v2 oauth-init --account personal \
  --oauth-client ~/.config/personal-os-secrets/google-oauth/gcp-oauth.keys.json
# or for work:
python3 -m triage_v2 oauth-init --account work \
  --oauth-client ~/.config/personal-os-secrets/google-oauth/gcp-oauth.keys.json
```

This writes:

- SQLite state: `core/state/email-triage-v2/triage-v2.db`
- Artifacts: `core/state/email-triage-v2/artifacts/`
- Outbox payloads: `core/state/email-triage-v2/outbox/`

## Test suite

```bash
cd ~/Projects/automation-runtime-work
export PYTHONPATH=core/automation/triage_v2/src
python3 -m pytest core/automation/triage_v2/tests -q
```

## Queue + worker mode

```bash
cd ~/Projects/automation-runtime-work
./core/automation/email-triage-v2.sh --run-type pm --enqueue-only
./core/automation/email-triage-v2.sh --worker-once
```

## API mode (local)

```bash
cd ~/Projects/automation-runtime-work
export PYTHONPATH=core/automation/triage_v2/src
python3 -m triage_v2 serve-api --host 0.0.0.0 --port 8080
```

Endpoints:

- `POST /triage/runs`
- `GET /triage/runs/{run_id}`
- `GET /triage/runs/{run_id}/digest`
- `POST /triage/drafts/retry`

## Required missed-email fixture validation

```bash
cd ~/Projects/automation-runtime-work
export PYTHONPATH=core/automation/triage_v2/src
python3 -m triage_v2 verify-fixture \
  --run-id <run_id> \
  --fixture core/state/email-triage-v2/missed-email-fixture.json
```

Fixture format:

```json
{
  "missing_message_ids": ["abc123", "def456"]
}
```

## GCP target

Terraform scaffolding lives in `core/automation/triage_v2/infra/gcp/`.

Deploy target services:

- Cloud Run: `triage-api`, `triage-worker`
- Cloud Tasks queues for run/draft/send/reconcile
- Cloud SQL Postgres for persistent state
- Cloud Scheduler for AM/PM triggers

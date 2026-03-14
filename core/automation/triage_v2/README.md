# Inbox Triage v2

Cloud-first inbox triage pipeline with a local fallback runtime.

This directory is a reference copy in the vault. Run the live implementation from `~/Projects/automation-runtime-work/`.

## What this implements

- Queue-backed run orchestration (`triage_run` tasks)
- Semantic thread enrichment for summaries, reply guidance, and bucket refinement
- Deterministic fallback normalization when Claude enrichment is unavailable
- Coverage invariant checks (`missing == 0`, duplicate thread key detection)
- Draft adapter routing: Superhuman preferred, Gmail fallback
- Explicit `draft_status` per entry
- Explicit `response_needed` and `suggested_response` fields per entry
- API surface for run trigger, status, digest retrieval, draft retry
- Local outbox sender for safe testing

## Layout

```text
core/automation/triage_v2/
├── src/triage_v2/
│   ├── api.py
│   ├── cli.py
│   ├── pipeline.py
│   ├── db.py
│   ├── render.py
│   ├── validate.py
│   └── providers/
├── fixtures/
├── tests/
└── infra/gcp/
```

## Quick start (local)

```bash
cd ~/Projects/automation-runtime-work
export PYTHONPATH=core/automation/triage_v2/src
python3 -m triage_v2 init-db
TRIAGE_V2_PROVIDER_MODE=file TRIAGE_V2_SENDER_MODE=local_outbox \
  python3 -m triage_v2 run-now --run-type manual --force-reconcile
python3 -m triage_v2 run-status --run-id <run_id>
python3 -m pytest core/automation/triage_v2/tests -q
```

OAuth health check:

```bash
python3 -m triage_v2 check-gmail-auth
python3 -m triage_v2 oauth-init --account personal --oauth-client ~/.config/personal-os-secrets/google-oauth/gcp-oauth.keys.json
```

## Environment variables

- `TRIAGE_V2_DB_PATH` (default `core/state/email-triage-v2/triage-v2.db`)
- `TRIAGE_V2_STATE_DIR`
- `TRIAGE_V2_ARTIFACT_DIR`
- `TRIAGE_V2_OUTBOX_DIR`
- `TRIAGE_V2_FIXTURE_DIR`
- `TRIAGE_V2_PROVIDER_MODE` (`file` or `gmail`)
- `TRIAGE_V2_SENDER_MODE` (`local_outbox` or `gmail`)
- `TRIAGE_V2_DRAFT_MODE` (`superhuman_preferred` or `gmail_only`)
- `TRIAGE_V2_SUPERHUMAN_ENABLED` (`1` to enable script execution)
- `TRIAGE_V2_SUPERHUMAN_SCRIPT`
- `TRIAGE_V2_POLICY_FILE` (default `core/automation/triage_v2/policy.json`)
- `TRIAGE_V2_GMAIL_WORK_HOME` (default `~/.gmail-mcp`)
- `TRIAGE_V2_GMAIL_PERSONAL_HOME` (default `~/.gmail-mcp-personal`)
- `TRIAGE_V2_ACCOUNTS` (comma-separated: `work`, `personal`; default `work,personal`)
- `TRIAGE_V2_DIGEST_TO` (default `matt@cornerboothholdings.com`)
- `TRIAGE_V2_DIGEST_SENDER_ACCOUNT` (`work` or `personal`)
- `TRIAGE_V2_ALWAYS_RECONCILE` (`1` default, runs query reconciliation in addition to history fetch)

## Notes

- `gmail` provider/sender adapters are wired to Gmail REST APIs using existing OAuth token files.
- Digest rendering uses `summary_latest` for all sections, including newsletter and spam line items; subject lines are kept only as supporting context in expanded rows.
- Reply-worthy items render `Draft ready in Superhuman` when queued into Superhuman and `Draft ready in Gmail` when the flow falls back to Gmail drafts.
- Cloud deployment target is defined under `infra/gcp`.

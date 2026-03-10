# Automated Email Triage

Canonical policy files (take precedence if duplicated guidance conflicts):
- `core/policies/email-drafting.md`
- `core/policies/scheduling.md`
- `core/policies/voice-and-writing.md`
- `core/policies/paths-and-state.md`

## Parameters

- Today: {{DAY_OF_WEEK}}, {{FULL_DATE}}, {{TIME_DISPLAY}}
- Run type: {{TIME_LABEL}} ({{TRIAGE_SUFFIX}})
- Last triage: {{LAST_TRIAGE_TIMESTAMP}}
- Date: {{DATE_ISO}}
- Contract file: {{TRIAGE_CONTRACT_FILE}}

## Load Context

Load these files first:
1. `core/context/email-contacts.md`
2. `core/context/people.md`
3. `core/context/writing-style.md`

Identity resolution is mandatory: use exact email as canonical identity key before name matching.

## Step 1: Read State

Read `core/state/email-triage-state.json` and extract:
- `last_triage_timestamp`
- `processed_message_ids`

If state is missing/empty/null timestamp, treat as cold start and scan last 12 hours.

## Step 2: Fetch Candidate Emails (both accounts)

Use BOTH inboxes:
- Work: `mcp__google__gmail_users_messages_list(query='newer_than:1d -label:sent -label:draft', max_results=50)`
- Personal: `mcp__google-personal__gmail_users_messages_list(query='newer_than:1d -label:sent -label:draft', max_results=50)`

Filter to:
- received AFTER `last_triage_timestamp` (unless cold start)
- not in `processed_message_ids`

Track per email:
- `messageId`, `threadId`, `account` (`work|personal`), sender, subject, timestamp

Build a normalized thread record map immediately:
- key: `account + ":" + threadId`
- fields per key:
  - `account`, `threadId`
  - `messageIds[]` (all messages in thread seen this run)
  - `sender_email` (exact email key)
  - `sender_name`
  - `subject_latest`
  - `summary_latest` (1-2 sentence plain-text summary, max 240 chars)
  - `bucket_candidate`
  - `draft_status` (`queued|clipboard|failed|none`)
  - `suggested_action` (required for `Action Needed`, one sentence)
  - `monitoring_owner`, `monitoring_deliverable`, `monitoring_deadline` (for `Monitoring` when known)
  - `unsubscribe_url` (only for newsletters/spam; real URL only)

If over 50 emails after filtering, keep 50 most recent and note cap in report.

## Step 2.7: Front-Running Detection

Fetch recent sent mail once per account:
- Work: `mcp__google__gmail_users_messages_list(query='in:sent newer_than:1d', max_results=50)`
- Personal: `mcp__google-personal__gmail_users_messages_list(query='in:sent newer_than:1d', max_results=50)`

If Matt has a sent message newer than incoming in same thread, classify as `ALREADY ADDRESSED` and skip further decisioning.

## Step 2.8: Unknown Sender Enrichment

For unknown senders not found in `email-contacts.md`, check up to 5 senders per run:
- Contacts: `mcp__contacts__lookup_name(name='...')`
- Calendar: `mcp__google__calendar_events_list(q='...', timeMin='6 months ago', timeMax='1 month from now')`

If either matches, treat sender as Tier 3 (Professional Network), not spam.

## Step 2.9: Identity Disambiguation (Required)

Before classification, resolve sender identity using this precedence:
1. Exact email match in `email-contacts.md`
2. Domain match in `email-contacts.md`
3. Name match only after steps 1-2

Never merge people by first name only. If emails differ, treat as different people unless explicit proof says otherwise.

Known high-risk collisions:
- `amitmshah74@gmail.com` = Amit Shah (Alex Blumberg intro, engineering), not Kern + Lead
- `amit@kernandlead.com` = Amit Savyon (Kern + Lead)
- `mav@cornerboothholdings.com` / `mav@heapsicecream.com` = Mav Placino (Matt's executive assistant), not Kern + Lead

Never merge or summarize across different `threadId` values, even when sender name is the same.
Each output entry must correspond to exactly one `account + threadId`.

For ambiguous or repeated names, run:

```bash
python3 "{{IDENTITY_RESOLVER_SCRIPT}}" --email "<sender_email>" --name "<sender_name>"
```

Use resolver output as the canonical identity source before writing summaries.

## Step 3: Classification

Read each candidate email with `gmail_users_messages_get` in matching account.

Decision order:
1. Already replied by Matt after incoming? -> `ALREADY ADDRESSED`
2. Explicit sender/domain override? Apply it first:
   - `Cora Briefs` -> `NEWSLETTERS`
   - `Ramp` -> `FYI`
   - LinkedIn digests / no-reply Amazon / Compass listing alerts / PEF digests / Double Good / Grubhub / Square promos+notifications / cold sales pitches -> `SPAM / MARKETING`
3. Editorial sender or true editorial newsletter? -> `NEWSLETTERS`
4. Tier 2 Personal + implicit action pattern (overdue/payment due/enrollment deadline/forms due/response required/RSVP by)? -> `ACTION NEEDED`
5. Explicit ask/question/request directed at Matt? -> `ACTION NEEDED`
6. Ask directed at someone else while Matt monitors? -> `MONITORING`
7. If your own summary says no action required now -> `FYI`
8. Otherwise informational -> `FYI`

Never classify as `ACTION NEEDED` when description says "no action needed", "none required now", or equivalent.
Do not treat `List-Unsubscribe` alone as sufficient evidence for `NEWSLETTERS`.
Default non-person, non-editorial mail to `SPAM / MARKETING` unless it is clearly an operational system/vendor alert worth keeping in `FYI`.

## Step 3.5: Thread-Level Dedupe (Required)

If a thread has conflicting bucket candidates, keep exactly one by this priority:
1. `Action Needed`
2. `Monitoring`
3. `Already Addressed`
4. `FYI`
5. `Newsletters`
6. `Spam / Marketing`

Apply this once to normalized thread records before report generation.

## Step 4: Actions

### 4a: ACTION NEEDED suggested action

For each `ACTION NEEDED`, provide specific one-line suggestion.

### 4b: Draft pairing

If suggestion implies replying by email, create a draft using:

```bash
{{SUPERHUMAN_DRAFT_SCRIPT}} --queue "{threadId}" "{draft_text}" "{account_email}"
```

Rules:
- Work account: `matt@cornerboothholdings.com`
- Personal account: `lieber.matt@gmail.com`
- Run drafts serially
- If script returns `FALLBACK: Chrome is not running`, note "Draft in clipboard only"
- Max 10 drafts/run
- Capture and store per-thread draft outcome for this run:
  - `queued` (script output includes `QUEUED:`)
  - `clipboard` (script output includes `FALLBACK:`)
  - `failed` (any error/no queue file)

Pre-draft gate:
- Read full thread first
- If another participant already fully answered, reclassify as `FYI` (or courtesy) and do not draft redundant reply
- If the latest message is addressed to someone other than Matt (for example `Hi Jack`), do not draft a reply for Matt; keep only an operational `Next step` and use `MONITORING` when there is a blocker, owner, or deadline

### 4c: Courtesy drafts

For FYI items needing social acknowledgement, draft 1-2 sentence courtesy reply.
Use the same per-thread draft outcome tracking (`queued|clipboard|failed`).

### 4e: Draft Outcome Reconciliation (Required)

Before report generation, reconcile per-thread draft outcomes with:
- `core/state/superhuman-draft-status.json`

For each thread in report:
- if final status is `queued`, draft-ready labels are allowed
- if final status is `clipboard` or `failed`, do not use draft-ready labels
- if no record exists, treat as `failed`

### 4d: Monitoring follow-up

For each `MONITORING` item:
- derive owner + deliverable + deadline (AM default 5 PM today, PM default noon tomorrow unless explicit deadline)
- create Things follow-up task
- append to `core/state/email-monitor-state.json` `watched_threads[]`

## Step 5: Build Markdown Digest First (Required)

Save markdown digest first (before sending email):
`Knowledge/DIGESTS/triage-{{DATE_ISO}}-{{TRIAGE_SUFFIX}}.md`

Also persist normalized thread records for this run to:
`logs/email-triage-records-{{DATE_ISO}}-{{TRIAGE_SUFFIX}}.json`
Include final `bucket`, `account`, `threadId`, `sender_email`, `subject_latest`, `summary_latest`, `draft_status`, `unsubscribe_url`, `messageIds`.
For `Action Needed`, include `suggested_action`.
For `Monitoring`, include `monitoring_owner`, `monitoring_deliverable`, `monitoring_deadline` when available.

Required section order (skip zero sections):
1. Action Needed
2. Already Addressed
3. Monitoring
4. FYI
5. Newsletters
6. Spam / Marketing

Within each section, group Work then Personal with `### Work` / `### Personal`.
- Add `### Work` and/or `### Personal` ONCE per section (not before every item).
- List all items for that account directly under that subsection heading.

HTML style rules:
- For every section header, use a full-width divider via the header element itself:
  `<p style="display:block;width:100%;border-bottom:2px solid {section_color};padding-bottom:4px;margin-top:24px;">Section Title (N)</p>`
- The divider must span the full email content width for every section.
- `Action Needed` section must use black text only (`color:#000` or default text color) for both header and entries.
- Do not use red text for `Action Needed` header, labels, borders, or entry copy.
- If entry cards/blocks are used, `Action Needed` cards must use neutral styling only (white/light-gray background, black/dark-gray text, dark-gray border). No red accents.
- Restore section shading/color for the other sections:
  - `Already Addressed` green
  - `Monitoring` amber
  - `FYI` blue
  - `Newsletters` and `Spam / Marketing` muted gray headers with compact entries
- Link color should be subtle blue (not oxblood).

Formatting constraints:
- no numbered lists
- no horizontal rules
- newsletters/spam listed individually (never counts like `25+`)
- every entry must have exactly one markdown Superhuman thread link
- do not use raw `Thread: https://...` lines; use markdown links only
- newsletters/spam must also have Unsubscribe link
- do not show score labels (no `[85]`, `[75]`, or any numeric score prefix)
- do not prefix each item with `[WORK]` or `[PERSONAL]`
- do not combine multiple thread IDs in one entry
- every FYI item must use the same full-entry structure; do not switch to lighter or unbolded line-only formatting mid-section
- when present, bold labels for `From`, `Summary`, `Recommended response`, `Next step`, `Monitoring`, and `Draft note`

Link rules:
- Work thread URL: `https://mail.superhuman.com/matt@cornerboothholdings.com/thread/{threadId}`
- Personal thread URL: `https://mail.superhuman.com/lieber.matt@gmail.com/thread/{threadId}`
- Build each link from that entry's own `threadId`; never reuse link from another entry
- Verify sender+subject match the linked thread before final output
- In `Action Needed`, link text must be `[Draft ready](...)` or `[View thread](...)`
- In `FYI` courtesy drafts, link text must be `[Courtesy draft ready](...)` or `[View](...)`
- In all other sections, link text must be `[View](...)`

Unsubscribe rules (Newsletters / Spam only):
- Include `[Unsubscribe](url)` per entry
- URL must be extracted from real email headers/body (`List-Unsubscribe` first, footer second)
- Never use Superhuman thread URLs or Gmail inbox URLs as unsubscribe links
- If no real unsubscribe URL exists, use: `Unsubscribe unavailable`
- In `Newsletters`, list `Cora Briefs` first, then editorial newsletters (`On my Om`, `Casey Newton`, `Matt Levine`, `One Great Story / New York Mag`), then the remaining true newsletters

ACTION NEEDED link text:
- with actual queued draft for that thread (`draft_status=queued`): `Draft ready`
- without draft: `View thread`
- clipboard fallback: `View thread` (line above: `Draft in clipboard.`)

FYI courtesy link text:
- only when `draft_status=queued` for that exact thread: `Courtesy draft ready`
- when `draft_status` is `clipboard` or `failed`, use `View` (and include `Draft in clipboard.` or `No draft.` in entry text)

All other links:
- `View`

Never use `Draft ready` or `Courtesy draft ready` unless that thread's draft was actually queued in this run.
For any entry that uses `Draft ready` or `Courtesy draft ready`, include `Draft status: queued` in the entry text.

## Step 5.5: Validation Gate (required)

Before final send, validate markdown digest:

```bash
python3 "{{TRIAGE_VALIDATOR_SCRIPT}}" report --markdown "Knowledge/DIGESTS/triage-{{DATE_ISO}}-{{TRIAGE_SUFFIX}}.md" --contract "{{TRIAGE_CONTRACT_FILE}}"
```

If validation fails:
- do not send full HTML report
- send short failure report with validator errors
- set `emails_processed` to 0 for this run

## Step 5.7: Send Email After Validation

Only after validation passes, send report email to `matt@cornerboothholdings.com` using `mcp__google__gmail_users_messages_send` with BOTH fields:
- `body`: plain-text fallback (no HTML tags)
- `html_body`: rendered HTML report
- Never put HTML markup in `body`

Subject:
`Inbox Triage — {{DAY_OF_WEEK}} {{FULL_DATE}}, {{TIME_DISPLAY}} (N new)`

## Step 6: Project Brief Updates (max 5)

Use `projects/README.md` match signals and append new relevant comms to project briefs.
Skip newsletters/spam/duplicates/ack-only messages.
Prioritize P0 projects.

## Step 7: Update State

Update `core/state/email-triage-state.json`:
- `last_triage_timestamp` = now ISO8601
- append processed IDs; keep last 500
- `last_triage_type` = `{{TRIAGE_SUFFIX}}`
- `emails_processed` = count processed this run

## Critical Constraints

- Headless run: do not ask user questions
- Never send replies on Matt's behalf (only triage report email is sent)
- Consolidate multiple emails in same thread to most recent entry
- Do not append a second run into existing digest file for same suffix
- If no new mail: send short "no new emails" report and still update state
- Beeper checks are optional: if tools unavailable, continue without failing run
- Do not infer two contacts are the same person from shared first name, similar meeting titles, or recurring calendar patterns

---
name: chief-of-staff
description: Interactive chief of staff for email triage, drafting, promise tracking, and follow-up management. Invoke with /cos.
---

# Chief of Staff (`/cos`)

Interactive email and communications management. Use this when Matt wants to work through his inbox, draft responses, track promises, or check on follow-ups.

**Commands:**
- `/cos triage` — Score, pre-draft, and batch-triage the full inbox
- `/cos draft [person or subject]` — Draft a response with full context
- `/cos promises` — Track email commitments Matt has made
- `/cos followup` — Check what Matt is waiting on from others

Canonical policy files (take precedence if duplicated guidance conflicts):
- `core/policies/email-drafting.md`
- `core/policies/scheduling.md`
- `core/policies/voice-and-writing.md`
- `core/policies/paths-and-state.md`

---

## `/cos triage` — Score, Pre-Draft, and Batch-Triage the Full Inbox

Be a chief of staff, not a mail sorter. Score every email, pre-draft responses where possible, batch low-priority actions, and present a dashboard. Matt should spend his time on decisions only he can make, not on emails a good CoS can handle.

### Key Principles

- **Dashboard first.** Present a summary of the entire inbox before diving into individual emails.
- **Pre-draft whenever possible.** If the reply pattern is clear, draft it before Matt sees it.
- **Batch low-value actions.** Archive candidates and quick acks get batched, not presented one-by-one.
- **Oldest backlog first.** Within each priority tier, process the oldest emails first to drive toward inbox zero.
- **Always download and read attachments.** PDFs, spreadsheets, images — summarize them as part of the briefing.
- **Recommendations are mandatory.** Every actionable email gets a specific recommendation with reasoning.
- **Both accounts, always.** Work and personal, deduped, clearly tagged.

### Phase 1: Intelligence Gathering (silent — no output to Matt yet)

#### Step 1 — Load Context

Load these files before scanning:
- `core/context/email-contacts.md` — sender tier classification
- `core/context/people.md` — proper names, roles, relationships
- `core/context/writing-style.md` — Matt's voice for pre-drafts
- `projects/README.md` — active projects for context matching
- `core/context/scheduling.md` — calendar patterns and meeting preferences (for emails involving scheduling)

Identity rule: email address is the canonical identity key. Never merge contacts by first name only.

**Conditional context (load when triggered):**
- When any email matches PnT Park Slope buildout AND contains financial content (EA, invoice, payment, tracking sheet, change order, budget, cost, pricing), also load:
  - `Knowledge/WORK/244-Flatbush-OSD-Project-Tracker.md` — authoritative OSD budget tracker
  - This gives you the full budget picture so you can present the delta (what's new vs what's already tracked) rather than briefing Matt on information he already has.

#### Step 2 — Full Inbox Scan

Search the full inbox on both accounts (not just last 24 hours):

- **Work:** `mcp__google__gmail_users_messages_list(query='in:inbox', max_results=50)`
- **Personal:** `mcp__google-personal__gmail_users_messages_list(query='in:inbox', max_results=50)`
- Track which Gmail account each email came from. This determines the Superhuman URL. Never reclassify based on content.

Deduplicate — same threadId across accounts counts once.

#### Step 2.7 — Front-Running Detection

Before scoring, batch-search Matt's sent mail to identify threads he already replied to:
- **Work:** `mcp__google__gmail_users_messages_list(query='in:sent newer_than:1d', max_results=50)`
- **Personal:** `mcp__google-personal__gmail_users_messages_list(query='in:sent newer_than:1d', max_results=50)`

Collect all threadIds from sent messages. For each inbox email, if Matt has a sent reply newer than the incoming email in the same thread, flag it as **ALREADY ADDRESSED**. These skip scoring entirely and go straight to a summary section showing what Matt already handled.

#### Step 2.8 — Identity Disambiguation (Required)

Resolve each sender by exact email first, then domain, then name.
If two contacts have different emails, treat them as different people unless explicit evidence proves otherwise.

Known collisions to guard:
- Amit Shah (`amitmshah74@gmail.com`) is not Amit Savyon (`amit@kernandlead.com`)
- Mav Placino (`mav@cornerboothholdings.com`, `mav@heapsicecream.com`) is Matt's executive assistant, not Kern + Lead

#### Step 3 — Score Every Email (0-100)

For each email, calculate a score based on these factors:

| Factor | Points | How to assess |
|--------|--------|---------------|
| **Sender tier** | Tier 1: +40, Tier 2: +25, Tier 3: +10, Tier 4: 0 | Match against `email-contacts.md` |
| **Age/backlog penalty** | +2 per day in inbox, max +20 | Older emails are more urgent to resolve |
| **Directness** | To: +10, CC: +3 | Is Matt the primary recipient? |
| **Thread state** | Reply to Matt's thread: +10 | Someone answered Matt's question |
| **Project relevance** | P0 match: +10, P1: +5 | Match subject/sender against project match signals in `email-contacts.md` |
| **Urgency signals** | +10 | Keywords: urgent, ASAP, deadline, approval needed, time-sensitive |
| **Budget relevance** | +5 | OSD/Darragh emails containing: EA, invoice, payment, tracking sheet, change order, cost, pricing. Always goes to NEEDS MATT'S BRAIN. Flag with `[BUDGET]` |
| **Scheduling signal** | +5 | Email from Tier 1/2/3 sender contains scheduling language (see signal list below). Flag with `[SCHEDULING]` |

Read each email with `gmail_read` (correct account's tool) to assess content. Download and read attachments (excluding inline signature images) for emails scoring 40+.

**Scheduling signal detection:** Scan each email from Tier 1/2/3 senders for scheduling language. Explicit signals: "find time", "grab coffee/lunch", "schedule a call", "are you free", "let's meet/connect/catch up", "can we talk", "send some times", "Calendly", "would love to meet/connect". Implicit signals: "I'll be in [city]", "better discussed live", "overdue for a catch-up", forwarded introductions implying a follow-up meeting. Flag matching emails with `[SCHEDULING]`. Skip if: email confirms an already-scheduled meeting, is a calendar invite, sender is Tier 4/spam, or Matt is CC'd on someone else's scheduling.

#### Step 4 — Classify into Action Buckets

Based on score + content analysis + front-running detection, place each email into one bucket:

| Bucket | Criteria | What the CoS does |
|--------|----------|-------------------|
| **ALREADY ADDRESSED** | Matt already replied (from Step 2.7) | Show summary of Matt's reply + thread link. No action needed. |
| **DRAFT READY** | Score 50+, clear reply pattern, AND (explicit ask/question/request directed at Matt OR implicit action pattern from Tier 2 Personal sender) — OR — email flagged `[SCHEDULING]` from Tier 1/2/3 sender (scheduling override, see below) | Pre-draft a response using `writing-style.md`. For `[SCHEDULING]` emails, draft includes proposed meeting times. Present for Matt's approval. |
| **NEEDS MATT'S BRAIN** | Score 40+, requires judgment, AND (explicit ask OR implicit action pattern from Tier 2 Personal sender) | Full briefing + recommendation. Deep one-at-a-time triage. |
| **COURTESY RESPONSE** | FYI email where a brief acknowledgment is appropriate (no ask, but silence might seem dismissive) | Pre-draft a 1-2 sentence courtesy reply ("thanks, plan sounds good"). Batch with Quick Acks. |
| **MONITORING** | Action needed from someone else, Matt tracks | Register follow-up, show who owes what by when. |
| **QUICK ACK** | Score 20-40, simple reply needed | Batch together. Canned "thanks" / "got it" / "received" responses. |
| **ARCHIVE CANDIDATE** | Score <20, old/resolved/informational | Batch for removal. Present list, Matt approves, CoS archives. |
| **AUTO-SKIP** | Tier 4 senders, newsletters, spam | List individually with thread links and unsubscribe links. |

**Important:** A high score alone does not qualify an email as DRAFT READY or NEEDS MATT'S BRAIN. There must be (a) an explicit ask, question, or request directed at Matt, OR (b) an implicit action pattern from a Tier 2 Personal sender (e.g., overdue balance from CBE, tuition due from Berkeley Carroll, enrollment deadline from Keewaydin, payment due from Absolute Mechanical). Status updates and informational emails from Tier 1/2 senders are COURTESY RESPONSE (if acknowledgment appropriate) or ARCHIVE CANDIDATE (if no response needed), regardless of score. Newsletters, calendars, and general updates from Tier 2 Personal orgs remain COURTESY RESPONSE or ARCHIVE CANDIDATE.

**Scheduling override:** Emails flagged `[SCHEDULING]` from Tier 1/2/3 senders are upgraded to DRAFT READY regardless of their otherwise-determined bucket. An email that would be COURTESY RESPONSE or ARCHIVE CANDIDATE gets a scheduling draft if someone in Matt's network is asking to meet, find time, or catch up. The scheduling flag does not change the email's score, but it does change its bucket assignment.

For **DRAFT READY** emails: before drafting, apply the **pre-draft gate** — read the FULL thread (all messages). If another participant already communicated what Matt would say (answered the question, confirmed the plan, provided the requested info), do NOT draft a redundant reply. Reclassify as COURTESY RESPONSE or ARCHIVE CANDIDATE instead, noting "No draft — [person] already addressed this in the thread."

If the pre-draft gate passes, actually draft the response now (silently). Use the existing `/cos draft` context-gathering flow (match sender to people.md, check project briefs, search transcripts) but write the draft without presenting it yet. Store it for Phase 2.

**Verification rules (apply during classification):**
- **Acknowledgment ≠ action.** When Matt's last reply in a thread is a simple acknowledgment ("perfect will do", "sounds good", "got it"), do NOT assume the underlying task was completed. Check whether the actual action was taken (e.g., filing submitted, payment made, form approved). If the email resurfaced (via snooze, reminder, or is still in inbox), it likely means the action was never completed.

### Phase 2: Dashboard Presentation

Present a summary dashboard first. Example:

```
INBOX TRIAGE — Feb 17, 2026
16 emails

ALREADY ADDRESSED (3): Matt already replied — just FYI
DRAFTED FOR YOUR REVIEW (3): Pre-written responses for aging backlog
NEEDS YOUR BRAIN (3): Decisions only you can make
MONITORING (2): Waiting on others — follow-ups registered
COURTESY RESPONSES (2): Brief "thanks" / "sounds good" drafts ready
ARCHIVE CANDIDATES (2): Probably dead, batch archive?
QUICK ACKS (1): Simple "thanks" / "got it" replies
Newsletters (4): Listed individually with links
Spam/Marketing (2): Listed individually with unsubscribe links
```

Then process each bucket in this order (fastest wins first):

#### 0. Already Addressed (Matt already replied)

Present as a quick summary list (no action needed):

```
ALREADY ADDRESSED (3):
1. Darragh O'Sullivan — "EA#10 Revised" — Matt replied: "Approved, thanks Darragh" — View thread2. Morgan Comey — "Flight details" — Matt replied: "Perfect, thanks Morgan" — View thread3. Jeff Phillips — "Equipment list" — Matt replied: "Looks good, go ahead" — View thread```

No interaction needed. These are shown for awareness only. Include thread links for reference.

#### 1. Drafted for Your Review (pre-drafted responses)

For each pre-drafted response:
- Present the full briefing (sender with context, summary, attachments, project context)
- Show the pre-drafted reply
- **For `[SCHEDULING]` drafts**, also show:
  - Calendar check results (what's on the calendar for the next 5 business days)
  - The 2 proposed time slots with reasoning (why these slots were chosen — e.g., "adjacent to your 11 AM call", "Wednesday morning is open", "allows 45-min travel buffer from Park Slope")
  - Whether the meeting is proposed as in-person or virtual, and any travel buffer applied
- Use **AskUserQuestion** to let Matt choose:
  - **Send to drafts as-is** — create draft in Superhuman via automation, share thread link
  - **Edit first** — Matt provides changes, CoS revises, then saves
  - **Adjust times** (for `[SCHEDULING]` drafts) — Matt picks different slots or changes format (in-person vs call)
  - **Scrap and discuss** — drop the pre-draft, switch to deep triage mode for this email
  - **Create task instead** — defer to Things with full context
  - **Skip** — move on

On approval: create the draft in Superhuman using the Superhuman Draft Automation (see below). Share the thread URL.

#### 3. Needs Matt's Brain (deep triage)

These require judgment. Process one at a time, oldest first within priority tier:

**For each email:**

a. **Read & Download** — `gmail_read` the full message. Download attachments to `/tmp/cos-triage/` using `gmail_download_attachment`, then read them. For PDF attachments: extract a structured financial digest (amounts, line items, changes from prior versions). Skip attachments >10MB or <10KB (signature images). Max 5 PDFs per session.

b. **Contextualize** — Match sender to `people.md`. Match topic to active projects (read the project brief if matched). Search `Knowledge/TRANSCRIPTS/` for the sender's name (last 3 matching transcripts). Note thread history.

c. **Present Briefing** — Structured format:

```
From: Darragh O'Sullivan (OSD Builders, GC for Park Slope buildout) [72 — Tier 2 + P0 match + aging]
SUMMARY: Sent EA#09 for the light fixture package and Lutron Vive lighting
control system at 244 Flatbush.

ATTACHMENT: EA#09 PDF — total cost $47K (fixtures $28K + Lutron startup $19K)

PROJECT CONTEXT: Park Slope opening is March 21 (32 days out). 3-week lead
time means fixtures must be ordered by ~Feb 28. On the critical path.

MY RECOMMENDATION: Approve fixtures now to lock in lead time. Hold Lutron
startup pending the electrician's cheaper vendor quote. Ask Darragh for the
electrician's timeline on that quote.
```

**Recommendations with future triggers:** When a recommendation involves a deferred action ("follow up when in Boston," "revisit after opening"), state the deferred action concretely:
- BAD: "Reply warmly and grab coffee next time you're in Boston."
- GOOD: "Reply warmly and keep the door open. I'll flag this when a Boston trip appears on your calendar and draft outreach to Brian with a specific time and place."

The deferred action must specify: (1) what the trigger is, (2) what the CoS will do when it fires, (3) whether a Things task or calendar watch is needed. Always state this explicitly in the recommendation.

d. **Work Through It** — Use **AskUserQuestion**:
  - **Draft response** — with recommendation pre-loaded
  - **Modify recommendation** — discuss and iterate, then draft
  - **Create task** — defer to Things with full context
  - **Skip** — no action needed right now

Draft flow: use `writing-style.md` for Matt's voice. Present draft for review. On approval: create draft in Superhuman via automation (see Superhuman Draft Automation below). Share thread URL.

#### 3.5. Monitoring (waiting on others)

For emails where someone else needs to act and Matt is tracking:

```
MONITORING (2):
1. Doug Mara — "Lighting quote request" — Waiting on Doug for quote by Feb 20, 5 PM — View thread | Follow-up registered2. Marc McQuade — "Revised drawings" — Waiting on Marc for updated set by Feb 21 — View thread | Follow-up registered```

For each MONITORING email:
- Show who owes what and by when
- Use **AskUserQuestion**:
  - **Register follow-up** (default) — create Things task + add to `watched_threads` in state file
  - **Adjust deadline** — Matt specifies a different deadline
  - **Reclassify as ACTION NEEDED** — Matt realizes he needs to act
  - **Skip** — no follow-up needed

On registration:
- Create Things 3 task: `open "things:///add?title=Follow%20up%3A%20{person}%20on%20{topic}&when={date}@{time}&notes={thread_url}"`
- Add to `core/state/email-monitor-state.json` → `watched_threads[]`:
  ```json
  {"thread_id": "...", "subject": "...", "waiting_on": "Doug Mara",
   "waiting_for": "Lighting quote", "deadline": "2026-02-20T17:00:00-05:00",
   "followup_drafted": false, "account": "work"}
  ```

#### 4. Archive Candidates (batch)

Present the full list at once:

```
ARCHIVE CANDIDATES (3):
1. LinkedIn notification — "5 people viewed your profile" (12 days old) [8 — Tier 4, no urgency]2. Toast payroll confirmation — Jan 31 payroll processed (17 days old) [12 — Tier 4 + aging]3. Dropbox — "Your files were synced" (9 days old) [5 — Tier 4, informational]
Archive all 3? Or flag any exceptions.
```

Use **AskUserQuestion**: **Archive all** / **Flag exceptions first**

On approval, **actually archive in Gmail**: `gmail_modify_labels` with `removeLabelIds: ["INBOX"]` for each email. Use the correct account's tool. This is the "batch approve, then execute" model.

#### 5. Quick Acks (batch)

Present batched with suggested canned responses:

```
QUICK ACKS (2):
1. Marc McQuade — "Updated drawings attached" → "Got it, thanks Marc" [32 — Tier 2 + direct To]2. Morgan Comey — "Flight booked for Montana" → "Perfect, thanks Morgan" [28 — Tier 2 + project match]
Save both as drafts? Or modify any.
```

Use **AskUserQuestion**: **Save all as drafts** / **Modify first**

On approval, create each draft in Superhuman via automation (run sequentially, one per thread). Share thread links.

#### 5.5. Courtesy Responses (batch)

FYI emails where a brief acknowledgment is appropriate. Pre-drafted as 1-2 sentence replies.

```
COURTESY RESPONSES (2):
1. Matt Rosenstein — "Cash flow update for Feb" → "Thanks Matt, plan sounds good." [55 — Tier 2 + FYI, no ask]2. Darragh O'Sullivan — "Schedule update for next week" → "Got it, thanks Darragh." [48 — Tier 2 + FYI, no ask]
Save both as drafts? Or modify any.
```

Use **AskUserQuestion**: **Save all as drafts** / **Modify first** / **Skip all (no courtesy needed)**

On approval, create each draft in Superhuman via automation (run sequentially, one per thread). Share thread links.

**Rules for courtesy drafts:**
- Maximum 1-2 sentences. Purely social/acknowledging.
- No substantive content, no follow-up questions, no action items.
- If another participant already said what Matt would say in the thread, skip entirely.

#### 6. Newsletters & Spam (listed individually)

**You MUST list every single newsletter and spam email individually.** Never summarize as a count (e.g., "4 newsletters received"). Each one gets its own line with sender, subject, thread link, and unsubscribe link so Matt can scan and click through:

```
NEWSLETTERS (4):
1. NRN — "QSR Chains Report Q4 Revenue" — View | Unsubscribe
2. Franchise Times — "Top 500 Franchises" — View
3. Eater NY — "Best New Restaurants Feb 2026" — View | Unsubscribe
4. Substack — "Restaurant Finance Weekly" — View | Unsubscribe

SPAM / MARKETING (2):
1. ColdOutreach Inc — "Scale Your Restaurant Chain" — View | Unsubscribe
2. SaaS Vendor — "AI for Restaurants" — View | Unsubscribe
```

- Include `List-Unsubscribe` link when available in the email headers
- Include Gmail thread link for each — every single one, no exceptions
- Never combine or summarize newsletters/spam into counts
- No interaction needed unless Matt wants to take action

### Phase 3: Wrap-up

After all buckets are processed:

1. **Summary of actions taken:**
   ```
   SESSION COMPLETE
   - 3 already addressed (Matt replied before triage)
   - 3 drafts created (ready to send in Superhuman)
   - 4 pre-drafted responses approved
   - 2 monitoring threads registered for follow-up
   - 2 quick acks saved as drafts
   - 3 emails archived
   - 1 task added to Things
   - 2 emails skipped (Matt will revisit)
   - 4 newsletters listed, 2 spam listed
   - 1 email still needs a decision (flagged for next session)
   ```

2. **Inbox zero check:** How many emails remain in inbox after this session? If zero, celebrate. If not, note what's left and why.

3. **Update session state:** Write to `core/state/email-triage-state.json`:
   - `last_triage_timestamp`: current ISO 8601
   - `processed_message_ids`: append all processed IDs (keep last 500)
   - `inbox_snapshot`: count of emails remaining in each inbox
   - `last_triage_type`: "interactive"

### Project Brief Enrichment

After each email is resolved (draft approved, task created, archived, or skipped), if it matched a project during scoring, **append an update to that project's brief file**.

**When to enrich:**
- The email contained genuinely new information (not a simple acknowledgment)
- The email matched a project via sender, keywords, or thread context
- The resolution involved a decision, commitment, cost change, or timeline update

**What to append** to the project's `## Recent Communications` section (insert as the first entry, newest on top):

```markdown
### 2026-02-17 — [Source: Email] Darragh O'Sullivan
- EA#09 received for light fixture package and Lutron Vive system
- Total cost: $47K (fixtures $28K + Lutron startup $19K)
- 3-week lead time on fixtures, must order by ~Feb 28
- Matt's response: approved fixtures, holding Lutron pending alt quote
```

**If the email creates action items**, also append to the project's `## Next Actions` table:

```markdown
| Order lighting fixtures (approved EA#09) | Matt | Feb 28, 2026 | Email from Darragh 2026-02-17 |
```

**Format rules:**
- Header: `### YYYY-MM-DD — [Source: Email/Beeper/Transcript/Phone] [Name]`
- Bullets: factual, concise, focus on new information, decisions, commitments, changed dates/costs
- Insert as the newest entry at the top of Recent Communications (newest first)
- Only append genuinely new information. Don't repeat what's already in Recent Communications.
- If the email is a simple acknowledgment with no new info, skip the update
- After enriching, update `Last Updated:` in the brief's header to today's date
- Match signals in the brief's header should also be updated if a new contact or keyword is discovered

**Project brief file mapping** (from `projects/README.md`):

Match signals are sourced from each brief's `Match Signals:` header field. When that field is updated, this table should be refreshed.

| Project | Brief file | Match signals |
|---------|-----------|---------------|
| PnT Park Slope (P0) | `projects/pnt-park-slope.md` | OSD, Darragh, Marc McQuade, 244 Flatbush, Background Office, ABO, construction, buildout, Singer, Phil |
| Brown Bag Sandwich Co. (P0) | `projects/brown-bag-acquisition.md` | Brown Bag, BBS, Gilli, Tony, Antonio Barbieri, Daniel Gulati, Stripes, chopped sandwich |
| Project Carroll / CSG (P0) | `projects/project-carroll.md` | Court Street Grocers, CSG, Project Carroll, Alec Sottosanti, Matt Ross, Eric Finkelstein, Matt Wagman |
| CBH Cash Flow (P0) | `projects/cbh-cash-flow.md` | Integrus, Freedman Wang, Regan Dally, Jay Anand, cash flow, capital, funding, FY26, burn rate, estimated taxes |
| Automation Platform (P1) | `projects/automation-platform.md` | Austin Thompson, automation, data warehouse, onboarding, technical director, Lakeside Strategy, Athena Labs |
| Park Slope Marketing (P1) | `projects/park-slope-marketing.md` | Mona Creative, Sophie, Kern + Lead, K+L, press, launch, marketing, Mailchimp, campaign, 20th anniversary |
| PnT Real Estate (P1) | `projects/pnt-real-estate.md` | Jacqueline Klinger, TSCG, Ian, Gracie, MRG, Moshe Farhi, real estate, expansion, lease |
| Lily High School (P1) | `projects/lily-high-school.md` | LaGuardia, Berkeley Carroll, Kate Mollica, Birbal Kaikini, audition, viola, ISEE, SSAT, high school |
| Lily Bat Mitzvah (P1) | `projects/lily-bat-mitzvah.md` | bat mitzvah, CBEBK, CBE, Leslie Goldberg, Rana Bickel, Celia Tedde, Zach Rolf, B'nei Mitzvah |
| Downing Mountain Trip (P2) | `projects/downing-ski-trip.md` | Downing, Montana, Hamilton, John Lehrman, Morgan Comey, Ben Pomeroy, Willy Oppenheim, ski trip, backcountry |
| Summer Camp 2026 (P2) | `projects/summer-camp-2026.md` | Keewaydin, camp, Emily Schoelzel, John Frazier, Annette Franklin, Wyonegonic, CampMinder |

### Budget Tracker Enrichment

After Matt's decision on any email flagged `[BUDGET]` (OSD/buildout financial emails), update the OSD project tracker:

**File:** `Knowledge/WORK/244-Flatbush-OSD-Project-Tracker.md`

1. **New EAs:** Append a new EA section using the existing format (heading, amount table, scope bullets, exclusions, status).
2. **New invoices:** Append a new invoice section with amount, coverage period, notes from Darragh, and payment status.
3. **Status changes:** Update the status line of existing EAs/invoices in-place (e.g., "PENDING" to "APPROVED Feb 18").
4. **Budget projection:** If a new EA significantly changes the budget picture, update the Budget Projection table and best/likely/worst estimates.
5. **Payment verification:** Query Supabase (`billcom_bills WHERE vendor_name ILIKE '%OSD%'` and `transaction_detail WHERE name ILIKE '%OSD%'`) to check if any invoices previously marked as unpaid are now confirmed paid. Update the Payment Verification section.
6. **Timestamps:** Update `Last Updated` and `Last Verified` with today's date and `(source: interactive)`.
7. **Outstanding Items:** Move resolved items to the Resolved list, add new pending items.

**When NOT to update:** If the email is purely informational with no new financial data (e.g., scheduling, photos, general updates), skip the tracker update.

### Gmail Action Model: Batch Approve, Then Execute

The CoS takes real actions only after Matt approves:
- **Archive**: `gmail_modify_labels` with `removeLabelIds: ["INBOX"]`
- **Draft replies**: Create in Superhuman via `superhuman-draft.sh` (see Superhuman Draft Automation below)
- **Draft new messages**: Create in Superhuman via `superhuman-draft.sh --new` (compose mode)
- **Never auto-send**: All replies appear as drafts in Superhuman. Matt reviews and sends.

### Superhuman Draft Automation

Drafts are created by automating Chrome's Superhuman web app on the Mac Mini. This ensures drafts appear directly in Superhuman and sync to Matt's other devices (MacBook, iPhone). **Never use `gmail_draft_email` as a fallback.** Gmail API drafts are invisible in Superhuman.

**Script:** `core/automation/superhuman-draft.sh`

**Reply mode** (responding to an existing thread):
```bash
~/Obsidian/personal-os/core/automation/superhuman-draft.sh "<gmail_thread_id>" "<draft_text>" "<account_email>"
```

- `gmail_thread_id` — Gmail thread ID (hex string from Gmail API search results `threadId` field)
- `draft_text` — The full reply body text
- `account_email` — `matt@cornerboothholdings.com` (default) or `lieber.matt@gmail.com`

**Compose mode** (new message, no existing thread):
```bash
~/Obsidian/personal-os/core/automation/superhuman-draft.sh --new "<to_addresses>" "<subject>" "<draft_text>" "<account_email>"
```

- `to_addresses` — Comma-separated recipient emails (e.g. `"a@b.com,c@d.com"`)
- `subject` — Email subject line
- `draft_text` — The full message body text
- `account_email` — `matt@cornerboothholdings.com` (default) or `lieber.matt@gmail.com`

**When to use which mode:**
- **Reply mode**: Always prefer this. Search for a recent thread with the recipient first.
- **Compose mode**: Only when there's genuinely no prior conversation with the person.

**What reply mode does:**
1. Finds the account's Superhuman Chrome tab
2. Navigates to the thread via Cmd+L address bar (preserves SPA routing)
3. Presses Shift+R to open Reply All compose
4. Pastes draft text from clipboard
5. Escapes compose (auto-saves draft) and navigates back to inbox

**What compose mode does:**
1. Finds the account's Superhuman Chrome tab
2. Presses c to open Compose window
3. Pastes To recipients (confirms each with Tab)
4. Pastes Subject line
5. Tabs to Body and pastes draft text
6. Escapes compose (auto-saves draft) and navigates back to inbox

**Prerequisites:** Superhuman must be open in Chrome with one tab per account:
- `mail.superhuman.com/matt@cornerboothholdings.com`
- `mail.superhuman.com/lieber.matt@gmail.com`

**Fallback (Chrome not running):** The script auto-detects and falls back to clipboard-only mode:
- Copies draft to clipboard
- Tells Matt to open Superhuman and paste manually

**Batch drafts (Quick Acks, Courtesy Responses):** Run the script sequentially for each thread. The script includes auto-save pauses between drafts.

**After creating each draft:**
1. Share the Superhuman thread link

**Drafting rules (mandatory for ALL draft replies):**
1. **Specific dates and times for scheduling.** When proposing a meeting or call time:
   - State the exact day, date, and time (e.g., "Tuesday, February 24th at 10:00 AM"). Never use vague windows.
   - Offer exactly 2 slots: one preferred, one backup. Never 3+.
   - Check the actual calendar before proposing. Find slots adjacent to existing meetings.
   - Load and follow `core/context/scheduling.md` for Matt's calendar patterns, recurring blocks, and preferences.
2. **Verify past interactions before referencing them.** Before drafting any phrase that implies a past conversation ("Great catching up," "Really enjoyed our conversation," "As we discussed"):
   - Search `Knowledge/TRANSCRIPTS/`, Beeper, and calendar for concrete evidence the interaction happened.
   - Email threads do not prove a conversation occurred. Email ≠ meeting.
   - If no evidence found, use neutral openers: "Thanks for reaching out," "Good to connect," "Thanks for the note."
   - When in doubt, err neutral. A warm-but-vague opener is better than a fabricated reference.

---

## `/cos draft [person or subject]` — Draft a Response

Draft a reply to an email thread with full context from all available sources.

### Steps

1. **Find the thread:**
   - Search **both** accounts for the person or subject:
     - **Work:** `mcp__google__gmail_users_messages_list(query='from:{name} OR to:{name} OR subject:{subject}')`
     - **Personal:** `mcp__google-personal__gmail_users_messages_list(query='from:{name} OR to:{name} OR subject:{subject}')`
   - If multiple threads match, use AskUserQuestion to let Matt pick
   - Read the full thread with the matching account's `gmail_read` tool
   - **Track which account** the thread belongs to — this determines which tools to use for drafting

2. **Gather context from all sources:**

   **A. Meeting transcripts** — Search `Knowledge/TRANSCRIPTS/` for the person's name:
   - Grep across all transcript files for the sender's name
   - Read the 3 most recent matching transcripts
   - Extract relevant discussion points, decisions, commitments

   **B. Beeper messages** — Check for recent messages:
   - Use `mcp__contacts__lookup_name` to get phone number
   - Search Beeper by phone number (format: `XXX XXX XXXX` with spaces)
   - Read recent messages for context

   **C. People reference** — Check `core/context/people.md`:
   - Get proper names, titles, roles
   - Note any relationship context

   **D. Project briefs** — If the email relates to a known project:
   - Check `projects/README.md` for matching projects
   - Read relevant project brief for current status

3. **Report context consulted** before drafting. Present a brief summary so Matt can see what informed the draft:
   ```
   Context loaded:
   - Project brief: pnt-park-slope.md (last updated Feb 23)
   - Transcripts: 2 recent (Feb 20 call with Darragh, Feb 18 team sync)
   - Beeper: 3 messages from Darragh (last: Feb 22)
   - People: Darragh O'Sullivan — GC, OSD Builders
   ```
   If a source had no results, note it: "Transcripts: none found for this contact." This makes gaps visible.

4. **Draft the reply:**
   - **Verify past interactions before referencing them.** Search transcripts, Beeper, and calendar before using phrases like "Great catching up." If no evidence of a meeting or call exists, use neutral openers only.
   - Load `core/context/writing-style.md` and follow Matt's voice
   - Draft in plain text (email formatting rules from writing-style.md)
   - Keep it concise and direct
   - Reference specific context from the research (shows Matt is on top of things)
   - **Scheduling**: Load `core/context/scheduling.md`. Offer exactly 2 slots (check the actual calendar first). State exact day, date, and time.
   - Present the draft to Matt for review. On approval, create it in Superhuman:
   - **Reply (existing thread):**
     - **Work:** `~/Obsidian/personal-os/core/automation/superhuman-draft.sh "<thread_id>" "<draft_text>" "matt@cornerboothholdings.com"`
     - **Personal:** `~/Obsidian/personal-os/core/automation/superhuman-draft.sh "<thread_id>" "<draft_text>" "lieber.matt@gmail.com"`
   - **New message (no existing thread):**
     - **Work:** `~/Obsidian/personal-os/core/automation/superhuman-draft.sh --new "<to_addresses>" "<subject>" "<draft_text>" "matt@cornerboothholdings.com"`
     - **Personal:** `~/Obsidian/personal-os/core/automation/superhuman-draft.sh --new "<to_addresses>" "<subject>" "<draft_text>" "lieber.matt@gmail.com"`

5. **Share thread link:**
   - **Work:** `https://mail.superhuman.com/matt@cornerboothholdings.com/thread/{threadId}`
   - **Personal:** `https://mail.superhuman.com/lieber.matt@gmail.com/thread/{threadId}`
   - Tell Matt to review and send when ready

---

## `/cos promises` — Track Email Commitments

Scan Matt's sent emails for promises he made that haven't been fulfilled yet.

### Important Boundary

This command scans **sent emails only**. It does NOT scan meeting transcripts for commitments. Matt already triages meeting tasks each morning via `pending-tasks.md`. Tasks he discards from that review are intentional decisions, not forgotten promises. This command fills a different gap: promises made in email that have no existing review process.

### Steps

1. **Search sent emails from both accounts** (last 14 days):
   - **Work:** `mcp__google__gmail_users_messages_list(query='in:sent newer_than:14d', max_results=50)`
   - **Personal:** `mcp__google-personal__gmail_users_messages_list(query='in:sent newer_than:14d', max_results=50)`
   - Track which account each promise came from for URL routing and report badges

2. **Read each sent email** and look for promise patterns:
   - "I'll..." / "I will..."
   - "Let me..." / "Let me get back to you..."
   - "I'll send..." / "I'll share..." / "I'll follow up..."
   - "I'll have [person] reach out..."
   - "I'll check on that..." / "I'll look into..."
   - "By [day/date]..." commitments
   - "I'll loop in..." / "I'll connect you with..."
   - "We'll get that over to you..."

3. **For each promise found:**
   - Extract: WHO Matt promised, WHAT was promised, WHEN (if specified), EMAIL DATE
   - Check Things (via `things-sync/` files) for a matching follow-through task
   - Check sent emails for a follow-up email that fulfills the promise

4. **Classify promises:**
   - **OPEN** — Promise made, no evidence of fulfillment (no follow-up email, no Things task)
   - **IN PROGRESS** — A Things task exists for this promise
   - **KEPT** — Follow-up email was sent or task was completed

5. **Present results:**
   ```
   OPEN EMAIL PROMISES (need attention):

   1. To Jeff Phillips (Feb 10, 6 days ago):
      "I'll send over the updated equipment list by EOW"
      Status: No follow-up email found, no Things task
      [Draft follow-up] [Add task] [Mark done]

   2. To Freedman Wang (Feb 12, 4 days ago):
      "Let me check with Ellen and get back to you on the filing"
      Status: No follow-up found
      [Draft follow-up] [Add task] [Mark done]

   RECENTLY KEPT:
   - To Sarah (Feb 8): "I'll share the brand guidelines" → Sent Feb 9
   ```

6. **For each action Matt chooses:**
   - **Draft follow-up** — Jump to `/cos draft` flow
   - **Add task** — Create Things task with promise context
   - **Mark done** — Matt says he handled it outside email (just acknowledge)

---

## `/cos followup` — Check What Matt Is Waiting On

Search for threads where Matt asked a question or made a request and hasn't gotten a response.

### Steps

1. **Search sent emails from both accounts** (last 14 days):
   - **Work:** `mcp__google__gmail_users_messages_list(query='in:sent newer_than:14d', max_results=50)`
   - **Personal:** `mcp__google-personal__gmail_users_messages_list(query='in:sent newer_than:14d', max_results=50)`

2. **Read each sent email** and look for request patterns:
   - Direct questions ("Can you...?", "Would you...?", "What's the status of...?")
   - Explicit requests ("Please send...", "Could you share...", "Let me know...")
   - Document sharing ("I've attached...", "Here's the...", "Take a look at...")
   - Meeting requests ("Can we find time...?", "Are you available...?")

3. **For each request found:**
   - Check the thread for a reply from the recipient after Matt's message
   - Calculate days since Matt's message
   - Only flag if NO reply received in 2+ days

4. **Present results sorted by age (oldest first):**
   ```
   WAITING ON RESPONSES:

   WHO                WHAT                           SENT        DAYS
   Jeff Phillips      Equipment spec sheet           Feb 8       8 days
   Sarah Sanneh       Story ideas for anniversary    Feb 12      4 days
   Freedman Wang      Q1 estimated tax amount        Feb 13      3 days

   [Draft nudge to Jeff] [Draft nudge to Sarah] [Skip all]
   ```

5. **For nudge drafts:**
   - Use `/cos draft` flow with the specific thread
   - Tone: friendly check-in, not passive-aggressive
   - Reference what was originally asked
   - Matt's voice (load writing-style.md)

---

## Gmail Accounts

Both accounts are always searched. Use the correct MCP server for each account:

| Account | MCP Prefix | Address | Notes |
|---------|------------|---------|-------|
| **Work** | `mcp__google__gmail_users_*` | matt@cornerboothholdings.com | Primary business account |
| **Personal** | `mcp__google-personal__gmail_users_*` | lieber.matt@gmail.com | Personal account |

**Rules:**
- Always search both accounts for triage, promises, and followup
- Use the matching account's tools for read/draft/label operations

---

## Context Loading

Every `/cos` command should load these context files before operating:

| File | Why |
|------|-----|
| `core/context/email-contacts.md` | Sender tier classification, project match signals |
| `core/context/people.md` | Proper names, roles, relationships |
| `core/context/writing-style.md` | Matt's voice for any drafts |
| `core/context/scheduling.md` | Calendar patterns, meeting preferences, time slots |
| `projects/README.md` | Active projects for context matching |

---

## Error Handling

- If Gmail search returns no results, say so clearly ("No unread emails" or "No sent emails in the last 14 days")
- If a contact lookup fails, proceed with available info (email address from the thread)
- If Beeper search fails (known 404 bug with certain keywords), use the contacts → phone → chat ID workaround documented in `core/context/mcp-reference.md`
- **Never fabricate past interactions.** An email thread does NOT prove a meeting or call occurred. Before referencing any past interaction in a draft, verify it via transcripts, Beeper, and calendar. If no evidence, use neutral openers only. See drafting rule 4 above.

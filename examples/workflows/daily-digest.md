# Daily Digest Workflow

A daily briefing on the restaurant industry and your calendar. Triggered by "Show me my daily digest" or the 5am cron job.

**When triggered by cron:** Send directly to matt@cornerboothholdings.com using `send_email` (do not draft).

---

## Core Rules

### 1. No Repeated Stories
Before generating, read digests from the past 7 days (`Knowledge/DIGESTS/`). Do not include any story that appeared previously unless there is a material update—in which case, prefix with "Update:" and explain what changed.

### 2. Freshness
Only include stories published in the last 48 hours. If it's a slow news day, the digest should be short. Do not pad with minor stories.

**Newsletter-sourced stories:** Only include if the newsletter was received day-of or day-after. If a newsletter story is 2+ days old by digest time, skip it — even if the newsletter just arrived. Check the article's publish date, not the email receipt date.

### 3. Every Story Needs a VERIFIED Link

**CRITICAL: Do NOT fabricate or guess URLs.** Claude has a tendency to generate plausible-looking URLs that don't exist. This is unacceptable.

Each story must link to the specific article URL that you have actually seen and verified:
- **From newsletters:** Extract the actual hyperlink from the email HTML (newsletters contain real article URLs)
- **From web search:** Use the URL returned by the search tool
- **From WebFetch:** Use the URL you actually fetched

**If you cannot find a verified URL for a story, skip the story entirely.**

**Never do this:**
- Guess a URL based on the headline (e.g., `/casual-dining/dennys-sale-to-go-private`)
- Use a category page (e.g., `nrn.com/casual-dining`, `qsrmagazine.com/`)
- Use just the domain (e.g., `qsrmagazine.com`)

**Good:** `[Popeyes Franchisee Files Bankruptcy](https://www.nrn.com/news/popeyes-franchisee-sailormen-files-bankruptcy)` ← URL from newsletter or search
**Bad:** `[Popeyes news](https://www.nrn.com/mergers-acquisitions)` ← category page, fabricated
**Bad:** `[Corporate Catering](https://www.qsrmagazine.com/)` ← just the domain, useless

### 4. Analytical Briefs
Each story gets 2-3 sentences: first sentence states what happened, second/third adds a "so what" the reader can't get from the headline alone. Tailor the analysis by story type:
- **Earnings:** Always include at least one peer comparison (e.g., "far worse than Popeyes -4.8% or Jack in the Box")
- **M&A:** One sentence on deal significance or what it signals for the category
- **Trend pieces:** Connect to what it means for operators like CBH
- **Closures:** Note broader context (category struggles, real estate opportunity, neighborhood impact)
- Frame for a reader who is a restaurant operator and investor making decisions

### 5. Target Length
1-2 pages. Shorter if light news day; slightly longer if genuinely busy.

### 6. Source Diversity
- **NRN cap:** Maximum 3 NRN stories per digest. If you have more than 3, keep only the most significant.
- **Minimum 2 non-NRN sources** must appear in every digest.
- **Prioritize NYC local sources:** Eater NY, Grub Street, The Infatuation, FOUND NY, The Strong Buzz.
- If after pulling newsletters and web search, all stories are from NRN, explicitly run additional web searches targeting: `site:ny.eater.com`, `site:grubstreet.com`, `site:theinfatuation.com`, and general "NYC restaurant news" queries.

### 7. Compact Story Format
Every story in the digest must use this format:

```
**Headline** [Source] -- 2-3 sentences (fact + analysis). [Link](url)
```

First sentence states what happened. Second/third adds perspective the reader can't get from the headline: a peer benchmark, deal implication, or operator takeaway. Never pad with generic "this reflects broader trends" filler. If you can't add a real insight, one sentence is fine.

### 8. Identity Integrity (No Name Guessing)
When briefing meetings and contacts, resolve identity by exact email first, then domain, then name.
Never assume two people are the same based on first name, recurring meeting title, or prior calendar patterns.

Known disambiguations:
- Amit Shah (`amitmshah74@gmail.com`) is not Amit Savyon (`amit@kernandlead.com`)
- Mav Placino (`mav@cornerboothholdings.com`, `mav@heapsicecream.com`) is Matt's executive assistant

---

## Workflow

### Step 1: Check for Existing Digest
If `Knowledge/DIGESTS/{today's date}.md` exists and was generated after 5am today, present it. Otherwise, continue.

### Step 2: Review Past Digests
Read the past 7 days of digests to avoid repetition. This is mandatory.

**CRITICAL: Past digests are ONLY for news story and community intel deduplication. NEVER use past digests for calendar data.** All calendar items must come exclusively from the live Google Calendar MCP pull in Step 6. If you see calendar items in past digests, ignore them completely — they may be stale.

### Step 3: Pull Newsletters from Gmail

**Search query:**
```
newer_than:1d (from:franchisetimes.com OR from:restaurantresearch1.com OR from:marginedge.com OR from:wraysearch.ccsend.com OR from:helbraunlevey.com OR from:nrn.com OR from:andreastrong@substack.com OR from:emilysundberg@substack.com OR from:foundny@substack.com OR from:found@substack.com OR from:nadinethestanza@substack.com OR from:robertsietsema@substack.com OR from:coolstuffnyc@substack.com OR from:parkslopewalk@substack.com OR from:snaxshot@substack.com OR to:informed@cornerboothholdings.com)
```

**Key sources:**
| Newsletter | Focus |
|------------|-------|
| Nation's Restaurant News (nrn.com) | Industry news, M&A |
| Franchise Times | Franchise, QSR |
| Restaurant Business | Industry news |
| QSR Magazine | QSR news |
| FSR Magazine | Full service |
| The Strong Buzz | Brooklyn/NYC food |
| FOUND NY | NYC openings |
| Robert Sietsema | NYC cheap eats |
| Snaxshot | CPG & food brands |
| The Stanza | Hospitality |

For each newsletter: use `read_email` to get full content, then extract stories with their specific article links.

### Step 4: Web Search for Breaking News

Search for news from the last 24-48 hours on:
- Restaurant M&A and acquisitions
- QSR and fast food news
- Casual dining news
- Restaurant labor and wages
- NYC restaurant openings and closings
- Restaurant/food company earnings results
- Food/CPG M&A and deals (beyond restaurants)
- Business press trend/analysis pieces about restaurants and hospitality
- Restaurant/food company stock and investor news

**Sources to search:** Restaurant Business, Restaurant Hospitality, Restaurant Dive, QSR Magazine, Franchise Times, Nation's Restaurant News, FSR Magazine, Eater NY, Grub Street, New York Times Food section, Wall Street Journal, Bloomberg, Financial Times, Fortune, The Atlantic, New Yorker (food/dining)

**NYT Food & WSJ:** Include stories with a business angle (restaurant closings, industry trends, labor, M&A). Skip recipes and pure food/cooking content.

**Business press stories:** Search Bloomberg, WSJ, and FT for "restaurant" OR "dining" OR "food industry" in the last 48 hours. These outlets publish trend pieces and analysis that trade press misses (e.g., "content per square foot" concepts, food industry M&A coverage).

**Earnings season:** During Jan-March and Jul-Aug, actively search for quarterly results from these companies:
- **Restaurant chains:** McDonald's, Wendy's, Chipotle, Yum Brands, RBI, Dine Brands, Darden, Dutch Bros, Shake Shack, Sweetgreen, Wingstop, CAVA, Jack in the Box, Starbucks, Domino's, Papa John's
- **Food/CPG:** Kraft Heinz, General Mills, WK Kellogg, Ferrero, Nestle, Tyson, SunOpta, Refresco

Search for "[company name] earnings" OR "[company name] Q[N] results" in the last 48 hours.

**NRN note:** If web search returns an NRN category page, search for the specific headline + "site:nrn.com" to find the article, or check if the story appeared in the NRN newsletter.

### NYC Closures & Openings (Dedicated Searches)

Run these specific searches every day — NYC closures and openings are high-priority content:

1. `"NYC restaurant closed" OR "NYC restaurant closing" OR "restaurant closed" site:ny.eater.com` (last 7 days)
2. `"NYC restaurant opening" OR "new restaurant" site:ny.eater.com` (last 7 days)
3. `NYC restaurant closures this week 2026`
4. `NYC restaurant openings this week 2026`
5. `"restaurant closed" OR "shuttered" OR "final day" NYC` (last 48 hours)
6. `NYC restaurant closed OR closing site:greenpointers.com OR site:evgrieve.com OR site:bxtimes.com` (last 7 days)
7. `NYC restaurant closed OR closing site:westsiderag.com OR site:boweryboyshistory.com OR site:bklyner.com` (last 7 days)
8. `NYC bar closed OR brewery closed OR cafe closed Brooklyn OR Manhattan` (last 48 hours)

**Hyperlocal NYC blogs to search** — these break closure stories before the big outlets pick them up:
- `site:greenpointers.com` (Greenpoint/N. Brooklyn)
- `site:evgrieve.com` (East Village)
- `site:bxtimes.com` (Bronx)
- `site:westsiderag.com` (Upper West Side)
- `site:bklyner.com` (Brooklyn)
- `site:patch.com/new-york` (all NYC neighborhoods)
- `site:whatnow.com/new-york` (NYC openings/closings)

Also check these Substack sources directly via web search (they may publish before the email arrives):
- `site:andreastrong.substack.com` (last 48 hours)
- `site:robertsietsema.substack.com` (last 48 hours)
- `site:foundny.substack.com` (last 48 hours)
- `site:coolstuffnyc.substack.com` (last 48 hours)
- `site:parkslopewalk.substack.com` (last 48 hours)
- `site:rightonfranklin.substack.com` (last 48 hours)

These supplement the Gmail newsletter pull — don't skip stories just because you also found them via email.

### Step 4.5: Graham Holdings (GHC) Monitor

Check for new Graham Holdings activity using their RSS feeds. This is a low-frequency source — most days there will be nothing. Only include a section when there is actual new content.

**RSS feeds to check:**
- News Releases: `https://www.ghco.com/rss/news-releases.xml?items=15`
- Events: `https://www.ghco.com/rss/events.xml?items=15`
- SEC Filings: `https://www.ghco.com/rss/sec-filings.xml?items=15`

Use WebFetch to pull each feed. Filter for items published within the last 48 hours (same freshness rule as all other stories).

**Include only:**
- Earnings releases (quarterly or annual results)
- Consequential SEC filings: 10-K, 10-Q, 8-K, proxy statements (DEF 14A). Skip routine amendments, exhibits, and Section 16 insider transaction forms (Forms 3, 4, 5).
- Speeches, presentations, investor day materials
- Material press releases (acquisitions, divestitures, leadership changes, dividend announcements)

**Also include:** Newly announced upcoming events (earnings calls, investor days, annual meetings, conference presentations). These are useful even though the event hasn't happened yet — Matt wants to know they're scheduled.

**Skip:** Routine filings (SC 13G amendments, Form 4 insider trades) and any content older than 48 hours.

**Format (only when there are qualifying items):**
```
## Graham Holdings (GHC)

**[Headline]** [Type: Earnings/Filing/Presentation/Press Release] -- 2-3 sentence summary of what happened and why it matters. [Link](url)
```

Place this section after the themed news sections and before Business Pulse. If there are no qualifying items within the 48-hour window, omit the section entirely — do not include a placeholder.

**Context:** Tim (tim@ghco.com) is in Matt's Bloomberg Fellowship cohort and works at Graham Holdings. GHC is a diversified holding company (education via Kaplan, media, healthcare, automotive, manufacturing). Earnings and strategic moves are of investment interest.

### Step 5: Community Intel (Deterministic Beeper State)

Read the prepared file at `core/state/daily-digest-context/{today}-community-intel.md` first. This file is generated from the deterministic Beeper ingest state (`core/state/comms-events.jsonl`) filtered to the watched chats in `core/state/beeper-chat-watchlist.json`.

This prepared file is the **primary Community Intel source** for the digest. Do **not** query live Beeper just to build the Community Intel section. Live Beeper may still be used for attendee research in Step 6.5, but Community Intel should not depend on MCP session availability.

The prepared candidates already include only:
- `platform = beeper`
- `network in (whatsapp, imessage)`
- last 24 hours
- watched chats only
- low-signal chatter removed

**Include:** Vendor/service recommendations (with contact info), business tips, industry intel, relevant local updates, community news, neighborhood info
**Skip:** Social chatter, emoji-only messages, off-topic discussion, purely personal conversations

Format as `Community Intel` only if there are qualifying items. Group by source if there are multiple communities with updates.

**Deduplication (MANDATORY):** After pulling messages, compare each candidate Community Intel item against the past 7 days of digests' Community Intel sections.

- If the same topic was covered in a prior digest AND there is no genuinely new information, **skip it entirely**.
- "New information" means a material update (e.g., a resolution to an ongoing problem, new contact info, a price change). Restating the same resolution or status that was already reported is NOT new information.
- If there IS a material update, include it with "Update:" prefix and state only what changed.
- When in doubt, ask: "Would Matt learn anything new from this that he didn't already read yesterday?" If not, skip it.

If the prepared Community Intel file shows a same-run extraction error, you may include a one-line fallback note with the concrete failure reason. Otherwise, omit the section entirely when there are no candidates. Never emit a generic `Beeper unavailable this session` line from stale prior context.

### Step 6: Pull Calendar

**Day assignment:** Each event returned by `calendar_list_events` includes pre-computed `day_of_week`, `local_date`, and `local_time` fields (in Eastern Time). Always use these fields to group events by day. Do not parse raw RFC3339 timestamps to determine which day an event belongs to.

**Calendars to include:**
- `matt@cornerboothholdings.com` (CBH - primary)
- `Lieber - McCrum Family Calendar` (family events)

Query both calendars when pulling events. Family calendar events should be included in both "Today" and "This Week" sections.

**Calendar Freshness Rule (MANDATORY):**
- Every calendar item in the digest must come from the live `calendar_list_events` MCP response. No exceptions.
- NEVER carry forward, copy, or reference calendar items from previous digests, even if the MCP call fails.
- If a calendar MCP call fails (token expired, timeout, error), state "Calendar unavailable for [calendar name]" in that section. Do NOT substitute data from yesterday's digest.
- After pulling events, do NOT cross-reference with past digests to "fill in" missing events. If an event doesn't appear in the MCP response, it has been moved, deleted, or rescheduled — omitting it is correct behavior.

**Today:** List all live calendar events for today, including routine internal meetings and family events, with time, title, and meeting type. Do not suppress internal meetings from `## Today`. For each event, read the full calendar event details (location, description, conferencing/hangoutLink) to determine the correct format:
- **Google Meet / Zoom / video link in location or conferencing** → "Video call" (e.g., "Video call with Jordan Montgomery")
- **Restaurant or venue address in location** → "Lunch at [venue]" or "Dinner at [venue]"
- **Phone number in description/location** → "Call with [person]"
- **Physical office/address (not restaurant)** → "Meeting at [location]"
- **No location or conferencing info** → Use the event title as-is

Never guess the meeting type from the time of day or attendee name. Always read the actual event data.

**This Week:** Only flag items that need attention:
- External meetings or networking events
- Lunches, dinners, cocktails
- Travel
- Anything requiring preparation
- Anything unusual/out of the ordinary

Skip routine 1:1s, recurring internal syncs, and standard weekly meetings. Same-day internal prep is required only for `## Today`, not for week-ahead items.

**Attendee rendering rule (critical):**
- `This Week` should render the verified primary contact or the event title only.
- Do **not** synthesize attendee lists from guessed identities, description fragments, prior digests, or partial matches.
- A non-primary attendee is displayable only if they are explicitly present in the live calendar event payload and can be verified by exact attendee record (typically exact email/displayName match from the event).
- If an attendee cannot be verified, suppress them silently. Never print `identity unclear` in the digest.

**Ordering:** Within each day, list meetings in chronological order by start time. The week itself should run from the earliest day to the latest. First event of the week first, last event of the week last.

### Step 6.4: Same-Day Internal Prep

For same-day internal meetings that appear in `## Today`, add a compact internal prep block under the meeting briefing portion of the digest. External meetings still use the attendee-research workflow in Step 6.5. Do not add routine internal prep blocks to `## This Week`.

Before drafting these internal briefings, read `core/integrations/digest/internal-agenda-sources.yaml`.

**Agenda source resolution order (required):**
1. Explicit Notion or Google Docs link in the live calendar event description
2. Matching recurring source from `internal-agenda-sources.yaml` keyed by meeting title pattern
3. Recent transcript context, project notes, and current operating themes as fallback

**Source handling rules:**
- Use Notion MCP for Notion agenda pages and prefer the section for today's date. If today's section is absent, use the latest dated section at or before today.
- Use Playwright to read live Google Docs agendas when a doc link is present or mapped. Summarize the current agenda section if it exists.
- Treat the agenda as blank or stale if there are no current actionable bullets for this meeting, or if the newest content is clearly old relative to today's meeting.
- If the agenda source is unavailable, blank, or stale, do not drop the meeting. Fall back to recent transcripts, current project context, and open operating themes to generate clearly labeled suggested agenda items.

**Format:**
```markdown
**[Meeting Name]** - Internal prep
- Agenda:
  - [2-5 bullets summarizing the actual agenda when present]
- Suggested agenda:
  - [2-3 bullets only when the agenda is blank, stale, or unavailable]
- Prep note: [one short line on what Matt should have in mind going in]
```

When an explicit agenda exists, the `Agenda:` bullets should describe what is actually on the page or doc. Do not invent agenda items unless they are labeled as `Suggested agenda:`.

### Step 6.5: Deep Attendee Research

For every external meeting in Today or This Week, perform deep research on each attendee. **Never output "context unknown" — if you can't find context, say "no prior interactions found" and note what you searched.**

**IMPORTANT:** Run attendee research for EVERY meeting that isn't in the skip list below — including week-ahead meetings, not just today's. If someone appears as a meeting attendee and they're not a skip pattern, they get the full research workflow (contacts, transcripts, Gmail, Beeper, and calendar evidence). "Lunch with Jordan" or "Coffee with Jamie" are external meetings that need research — don't skip them just because the title looks casual.

**Skip patterns (no research needed):** Brain Trust, Pies Dos, Matt-Jason, Matt & Sarah, Matt/Jeff, tutoring, Track Practice, family events, recurring internal syncs.

For each external meeting:

**A. Identify people** — Extract attendee names from the calendar event (attendees, title, description).

**B. Contacts lookup** — Use `mcp__contacts__lookup_name` for each person to get phone numbers and email addresses.

**B.5 Identity check (required)** — Use attendee email/contact email as canonical identity key before using name-only matches from transcripts/calendar. Do not collapse two contacts with different emails into one person.

**B.6 Attendee confidence pass (required)** — Before rendering `This Week` or a briefing:
- mark one attendee as `primary_render_contact` only if supported by the live event payload
- mark any unresolved/secondary names as `suppressed_attendees`
- if you cannot verify a secondary attendee from the live payload, do not render them anywhere in the digest

**C. Search Knowledge/TRANSCRIPTS/** — Grep for person's name across all transcripts. Read the top 3 matching files for context on past meetings.

**D. Search Gmail** — If email found in contacts: `from:{email} OR to:{email}` last 30 days. Read 3-5 most relevant threads. If no email: search by name.

**E. Search Beeper** — Search by name AND by phone numbers (format: `XXX XXX XXXX` with spaces). Check iMessage, WhatsApp, and other networks.

**F. Granola is not a lookup step** — Do not search Granola MCP for historical context or note review. If transcript context is missing locally, say so plainly and continue with transcripts, Gmail, Beeper, and calendar evidence.

**G. Compile briefing** for each person:

```
**[Person Name]** - Meeting Briefing
- Who they are: [title, company, what they do]
- How Matt knows them: [intro chain, mutual connections]
- Previous interactions: [past meetings, emails, messages - with dates]
- Key context: [what was discussed, active projects, shared interests]
- Likely agenda: [inferred from recent email threads or meeting patterns]
- Recommended talking points: [2-3 specific items based on research]
```

**Research depth limits:** Max 3 transcript reads, 5 email threads, and 2 Beeper searches per person. Move on after hitting these limits.

**Calendar debug artifact (required):** Write a JSON sidecar to `core/state/daily-digest-context/{today}-calendar-debug.json` capturing the normalized live calendar events used in the digest. For each event include:
- event title
- date/day
- attendees from the live payload
- `primary_render_contact`
- `suppressed_attendees`
- short reason for any suppression

This file is for debugging attendee leaks. It does not belong in the emailed digest.

**H. Link to existing briefing documents**

After compiling the briefing for each person:

1. **Search `Knowledge/WORK/`** for existing files matching the person's name (e.g., `*montgomery*briefing*`, `*jordan-montgomery*`)
2. **If a briefing doc is found:** Add an Obsidian deep link at the end of the briefing section:
   ```
   [Full briefing →](obsidian://open?vault=personal-os&file=Knowledge%2FWORK%2Fjordan-montgomery-briefing)
   ```
   (URL-encode the file path: replace `/` with `%2F`, spaces with `%20`)
3. **If no doc found AND research was substantial** (contacts found, email threads read, transcript references, or message context): Save the compiled research to `Knowledge/WORK/{person-name}-briefing.md` and include the Obsidian link
4. **If no doc found AND research was minimal** (no prior interactions found): Skip — the inline briefing is sufficient, no need to create a standalone doc

### Step 7: Add Corner Booth Framing for Key Meetings

For external meetings where Corner Booth storytelling may be relevant, add a brief framing section (4-5 lines max per meeting). Reference the skill at `~/.claude/skills/corner-booth-storytelling/SKILL.md`.

**Important:** This step supplements Step 6.5 research. Never output "context unknown" for any attendee if Step 6.5 found context. Use the research from Step 6.5 to inform the framing.

**Meetings that need framing:**
- Potential acquisition targets (restaurant owners, emerging brands)
- Investor conversations
- Industry networking / conferences
- Landlord / real estate meetings
- Casual social where "what do you do?" will come up
- Anyone Matt hasn't met before or doesn't know well

**Format:**
```
**[Meeting Name]** - Corner Booth Framing
- [Who they are + relevant professional experience]
- [How Matt knows them / how introduced]
- [Recommended framing: Investor/Operator/Emerging Brand/Casual/etc.]
- [1-2 key beats to hit]
```

**Skip framing for:** Internal team meetings (Brain Trust, Pies Dos, etc.), recurring 1:1s with team, family events.

**Format for "This Week":** Focus on the EVENT TYPE, not the time of day. Determine the event type by reading the calendar event's location, description, and conferencing fields — same rules as "Today" above. A Google Meet/Zoom link = "Video call", a restaurant address = "Lunch/Dinner", etc. Never guess the type.

```
## Today (Monday, Jan 20)
- 10:00 AM — Team standup
- 2:00 PM — Meeting at 244 Flatbush (Park Slope site visit)
- 4:30 PM — Call with Austin candidate

## This Week
**Wednesday, Jan 22**
- Lunch at Lilia (investor meeting)
- Dinner at NRA NYC chapter — confirm attendance

**Friday, Jan 24**
- Cocktails at Hotel Chelsea with Jolie
- Dinner at Penny with Jolie
- Betaworks party
```

Do NOT bold times. Do NOT include times for week-ahead items unless they're unusual (e.g., very early morning). Lead with the event type.

---

## Output Structure

### Digest Format

```markdown
# Daily Digest — {Day}, {Date}

## Today
[All calendar events]

## This Week
[Only flagged items needing attention]

---

## Top Stories
[2-4 most significant items of the day]

## [Theme based on day's news]
[Group related stories — e.g., M&A, NYC, Executive Moves, Labor]

## [Additional themes as needed]

## Graham Holdings (GHC)
[Only when qualifying items exist — earnings, filings, presentations]

## Community Intel
[Beeper highlights — always last]
```

Omit the `Community Intel` section entirely when there are no qualifying items. Do not insert a placeholder.

### Theming
Do not use fixed sections. Group stories by what's actually newsworthy that day. Common themes include: M&A, Executive Moves, NYC (openings/closings), Labor & Wages, QSR, Casual Dining, Supply Chain, CPG, Earnings, Food Industry Deals, Industry Trends.

Lead with "Top Stories" for the 2-4 most significant items. Earnings results from major chains and food/CPG M&A deals always qualify as Top Stories during reporting season.

### Formatting Rules
- No emojis
- No excessive bullet nesting
- Story format: **Headline** [Source] -- 2-3 sentences (fact + analysis). [Link](url)
- Include publication date only if older than today

---

## Step 7.5: NYC Closure Real Estate Intelligence

**This is NOT optional. If a NYC closure appears anywhere in the digest, it MUST have the real estate line underneath it. Do not publish a NYC closure without the address, Google Maps link, and square footage research.**

**Fresh-only rule:** Do not maintain a persistent `available spaces` carry-forward block. A closure appears when it is newly reported within the freshness window, and may reappear later only as `Update:` when there is material new information such as:
- active listing posted
- asking rent or broker disclosed
- square footage corrected or confirmed
- lease activity or reopening news

If Red Bamboo or Barbetta closed days ago and there is no new real estate development, they should not be mentioned again.

When ANY NYC restaurant closure is detected in the news (from newsletters, web search, or Beeper community intel):

1. **Find exact address(es)** — Extract from article text or run a web search for "[restaurant name] address NYC"
2. **Generate Google Maps link** for each location:
   ```
   https://www.google.com/maps/search/?api=1&query=FULL+ADDRESS+URL+ENCODED
   ```
3. **Research the space** — Search LoopNet and Crexi for the address. Also try web search for "[restaurant name] square feet" or "[address] commercial listing". Look for:
   - Square footage
   - Lease terms (if listed)
   - Asking rent
   - Space type (bakery, full-service, QSR, etc.)
4. **Embed directly under the closure story**, not as a separate section. Every NYC closure story gets a real estate line immediately after its summary:

```
**The Leopard at des Artistes Closing After Two Decades on the UWS** [West Side Rag] -- The popular Italian restaurant is serving its final meals at the end of February. A longtime UWS fixture in a prime Columbus Ave corridor. [Link](url)
- 1 West 67th St ([Google Maps](https://www.google.com/maps/search/?api=1&query=1+West+67th+St+New+York+NY)) — ~3,200 sq ft, ground floor with sidewalk presence. [LoopNet](link) | No active listing yet.
```

If no square footage is found, say "sq ft unknown" but always show address + Google Maps link. If no LoopNet/Crexi listing exists, say "No listing found."

**Only trigger for NYC closures.** National chain closures in other markets don't need real estate research.

Fresh NYC openings may still be included elsewhere in the digest, but they are separate from closure tracking.

---

## Step 8: Validate All Links and Freshness (MANDATORY)

Before saving or sending, **validate EVERY external link** in the compiled digest. This step catches broken links, category pages, and stale stories that slip through.

### Freshness Gate (BEFORE link validation)

**This is the #1 failure mode.** Previous digests have included stories 5-14 days old because validation recorded the article date but never compared it to today. Every story must pass the freshness gate before link validation begins.

For EVERY story in the compiled digest:

1. **Extract the publication date** from the article (already visible in WebFetch response, newsletter HTML, or search result snippet)
2. **Calculate age:** `(today's date) - (publication date)` in hours
3. **Apply the gate:**
   - **≤48 hours → PASS** — proceed to link validation
   - **>48 hours → FAIL** — remove the story immediately, do not validate its link
   - **Newsletter exception (48-72h only):** A story between 48-72 hours old is OK ONLY if the newsletter containing it was received today AND the story did not appear in any prior digest. Beyond 72 hours: remove regardless, no exceptions.
4. **If the publication date cannot be determined:** Treat as FAIL and remove. Do not guess or assume freshness.

**Mandatory freshness log** (every story, no exceptions — output this before the link validation log):
```
Freshness check:
- [Headline]: published [date] → [X] hours/days old → PASS
- [Headline]: published [date] → [X] hours/days old → FAIL (removed)
- [Headline]: published [date] → [X] hours/days old → PASS (newsletter exception: received today, not in prior digests)
```

**If a story has no freshness log entry, it must not appear in the final digest.**

### Validation Process

For each link in the digest (that passed the freshness gate):

0. **Check freshness** — if the article is older than 48 hours, skip all further validation and remove the story. This was already done in the Freshness Gate above, but double-check here if you encounter a date during link validation that contradicts your earlier check.
1. **Fetch the URL** using WebFetch
2. **Check the HTTP response:**
   - 404/410/error: Link is broken
   - 200 with redirect: Follow and re-check
   - 200 OK: Continue to content analysis

3. **Analyze the page content** to detect category pages vs. articles:

   **Article indicators (VALID):**
   - Single headline at the top
   - Byline with author name
   - Publish date
   - Article body text (multiple paragraphs)
   - No list of other article headlines

   **Category page indicators (INVALID):**
   - Multiple article headlines/links listed
   - "Recent articles", "Related stories", "More in this category"
   - Grid or list of story thumbnails
   - Section navigation without article content
   - Archive/index page layout

### NRN-Specific Patterns (Common Failure Modes)

Nation's Restaurant News URLs are particularly prone to category page errors:

| URL Pattern | Type | Action |
|-------------|------|--------|
| `/restaurant-segments/*` | ALWAYS category | Reject immediately |
| `/fast-casual/` | Category | Reject unless followed by article slug |
| `/casual-dining/` | Category | Reject unless followed by article slug |
| `/quick-service/` | Category | Reject unless followed by article slug |
| `/mergers-acquisitions/` | Category | Reject unless followed by article slug |
| `/executive-moves/` | Category | Reject unless followed by article slug |
| `/finance/` | Category | Reject unless followed by article slug |

**The test:** Does the page have a single article with a byline and publication date? If you see a list of stories, it's a category page.

### Substack-Specific Patterns

| URL Pattern | Type | Action |
|-------------|------|--------|
| `subdomain.substack.com/p/slug-here` | Article | Valid — this is a specific post |
| `subdomain.substack.com` (root only) | Homepage | Reject — this is the newsletter homepage |
| `subdomain.substack.com/archive` | Archive | Reject — this is the post listing |
| `subdomain.substack.com/about` | About page | Reject |

### Aggregator / Roundup Detection

Some URLs point to aggregated content rather than a single story:
- **Pages listing 5+ distinct stories about different companies** = aggregated roundup, not a valid single-story link. Find the specific article instead.
- **"Weekly roundup"**, **"This week in [category]"**, **"News briefs"** = category/roundup pages. Extract the specific story URL from within the roundup if possible, otherwise skip.
- **Listicles that only mention the story in passing** (e.g., "10 restaurant trends" where your story is bullet #7) = not a valid source link. Find dedicated coverage.

### Content-Match Check

After confirming a URL is a real article (not a category page, not broken):
- **Verify the article actually matches the story in the digest.** Read the article headline and first paragraph — does it match what the digest describes?
- This catches URL-to-story mismatches that occur when web search returns a similarly-titled but different article.
- If the article doesn't match the digest story: search again for the correct article, or remove the story.

### When a Link Fails Validation

1. **Extract the exact story headline** from the digest
2. **Search for the real article:**
   ```
   "[exact headline]" site:nrn.com
   ```
   (Replace domain as appropriate for other publications)

3. **Verify the search result** by fetching it with WebFetch - confirm it's the actual article, not another category page

4. **If found:** Update the link in the digest
5. **If NOT found after 2 search attempts:** **DELETE the entire story from the digest**

### Critical Rule

**A story with no valid, verified article link MUST be removed from the digest. No exceptions.**

It's better to have a shorter digest with working links than a longer one with broken or misleading URLs.

### Logging (TWO logs required)

At the end of digest generation, output BOTH logs:

**Log 1: Freshness log** (all stories that were considered, including removed ones):
```
Freshness check:
- [Headline]: published Feb 17 → 12 hours → PASS
- [Headline]: published Feb 4 → 14 days → FAIL (removed)
- [Headline]: published Feb 16 → 52 hours → PASS (newsletter exception)
```

**Log 2: Link validation log** (only stories that passed freshness):
```
Link validation:
- [Headline]: URL verified ✓
- Fixed: [Headline] - updated URL from search
- Removed: [Headline] - no valid article URL found
```

---

## Step 9: Business Pulse

Add a compact business health section to the digest using the Supabase data warehouse.

**Supabase project:** `zxqtclvljxvdxsnmsqka` (via `mcp__supabase__execute_sql`)

Run the compact mode queries from `core/integrations/supabase/skills/health-scorecard/SKILL.md`.

Before writing the Business Pulse narrative, read the prepared file at `core/state/daily-digest-context/{today}-comp-drivers.md`. This file is generated from the warehouse orders table and summarizes:
1. single-day yesterday vs prior-year comp
2. channel and order-source deltas
3. daypart deltas
4. largest current-day orders
5. catering orders with customer identity fields when available

**Format in digest:**
```markdown
## Business Pulse

**Sales** $X,XXX yesterday (DOW)
▲/▼ X.X% YoY vs DOW Date '25
{one short context or outlier-driver line only when relevant}

**Labor** XX.X% four-wall · XX.X% hourly
{STATUS} (target <33%)
{plain-English freshness note only if needed}

**Reviews** X.XX avg · N new yesterday · N negative
{TREND vs 30d: IMPROVING/STABLE/DECLINING}

**Weather** [ONLY IF EXCEPTIONAL] short weekend-focused note

---

**Health Score: XX/100**
Sales X/30 · Labor X/25 · Reviews X/25 · Ops X/20
{1 short line on the main driver of today's read}
{optional second short line only if needed}
```

Each metric gets its own block with breathing room. Status/trend on a separate line below each metric. No cramming multiple data points with nested parentheses.

**Business Pulse length rules (required):**
- Sales should show yesterday and the single-day YoY comp only. Do not add a default WoW line.
- Use at most one short context line in `Sales`, and only when relevant. Preferred explanations: holiday adjacency, weather distortion, or one clear outlier driver from the comp-drivers file.
- If the move is large, name the dominant driver plainly (for example: EZCater, one large order, channel mix, or daypart mix). If no single factor explains it, say so plainly.
- Labor must use the same four-wall calculation used in the compact health-score workflow: 7shifts hourly wages plus imputed management and payroll tax/benefits from the latest closed period.
- Never print raw provenance like `Imputed from FY2025 P12`. If labor inputs are stale or partial, say that in plain English.
- Weather is exception-only. Omit it on normal days.
- Cap `Health Score` at 3-4 lines total. Do not repeat channel-by-channel detail already covered in the `Sales` block.

**Large comp diagnosis (required):**
- If absolute YoY comp is 10% or more, diagnose it from data first.
- Use order/channel/order-source/daypart evidence before weather or staffing speculation.
- If catering is material, call out the source platform and the customer identity using available warehouse fields (`customer_name`, `customer_email`, `customer_phone`).
- If no single order or catering cluster explains the move, say so explicitly.
- Do not attribute a result to personnel coverage or operational staffing unless that fact is directly verified by source data used in this run.

**Review count:** Use the 24-hour window (yesterday only) for the "new" count in the digest. The 7-day window is for the avg rating and trend comparison. The daily digest should only report things that are new since the last digest.

**Weather rule:** Weather is exception-only. Omit it on normal days. Include it only when there is likely operational impact or clearly unusual weekend weather (storm, snow/ice, heavy rain, severe wind, or unusually warm/cold conditions roughly 10F+ away from normal).

Score component values are required, not optional. Place this section after all news sections and before Community Intel.

If Supabase queries fail, skip this section with a note: "Business Pulse: data unavailable."

### Holiday Comp Context (REQUIRED)

After running the sales comp query, check BOTH yesterday AND the PY comp date (same DOW, 52 weeks ago) against this holiday list:

- MLK Day (3rd Monday of January)
- Presidents Day (3rd Monday of February)
- Valentine's Day (Feb 14)
- Easter Sunday (varies)
- Mother's Day (2nd Sunday of May)
- Memorial Day (last Monday of May)
- Father's Day (3rd Sunday of June)
- July 4th
- Labor Day (1st Monday of September)
- Super Bowl Sunday (1st Sunday of Feb)
- NYC Marathon Sunday (1st Sunday of Nov)
- Thanksgiving (4th Thursday of Nov)
- Christmas Eve / Christmas Day
- New Year's Eve / New Year's Day

**"Within 1 day" includes the day AFTER a holiday.** In NYC, federal holidays where schools close significantly affect restaurant traffic. The day after a holiday is NOT a normal business day.

**Do not call the PY comp date "normal" without checking this list.** Calculate the actual holiday dates for the PY year and compare. Example: Presidents Day 2025 was Feb 17, so Feb 18 2025 was the day after Presidents Day — not a normal Tuesday.

Format: `"PY comp date (Feb 18 '25) was the day after Presidents Day. Not a normal Tuesday."`

---

## Final Steps

1. Save digest to `Knowledge/DIGESTS/YYYY-MM-DD.md`
2. If triggered by cron: send via `send_email` to matt@cornerboothholdings.com (HTML format, subject: "Daily Digest — {Date}")
3. If triggered manually: present summary and ask if user wants it emailed

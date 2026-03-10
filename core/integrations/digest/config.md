# Daily Digest Configuration

Settings for your comprehensive daily restaurant and food industry news briefing. Edit this file to customize what appears in your digest.

## Newsletter Settings

### Gmail Search Query

The digest uses this Gmail query to find newsletters from the last 24 hours:

```
newer_than:1d unsubscribe
```

### Restaurant/Food Industry Newsletter Senders (Whitelist)

These are Matt's subscribed newsletters - prioritized for the daily briefing:

```yaml
# Industry Trade & Business
- sender: news@newsletter.nrn.com
  name: Nation's Restaurant News (NRN)
  focus: Daily restaurant industry news, M&A, trends

- sender: info@franchisetimes.com
  name: Franchise Times
  focus: Franchise news, QSR, casual dining

- sender: restaurantresearch1.com
  name: NoBull Consumer Pulse
  focus: Consumer/restaurant research weekly

- sender: rachel@marginedge.com
  name: The Board (MarginEdge)
  focus: Restaurant operations insights

- sender: info@wraysearch.ccsend.com
  name: Wray Executive Search
  focus: Restaurant executive hiring

- sender: david@helbraunlevey.com
  name: Helbraun & Levey
  focus: Restaurant law, regulatory updates

- sender: henry@eastcoastbusinessbrokers.com
  name: East Coast Business Brokers
  focus: Restaurant/food business acquisitions

# Marketing & Social
- sender: rachelkarten@substack.com
  name: Link in Bio (Rachel Karten)
  focus: Social media marketing insights
  filter: Only include if restaurant or food related

# NYC Local & Food Culture
- sender: andreastrong@substack.com
  name: The Strong Buzz
  focus: Brooklyn/NYC food news

- sender: emilysundberg@substack.com
  name: Feed Me
  focus: Food media & hospitality culture

- sender: foundny@substack.com
  name: FOUND NY
  focus: NYC restaurant openings

- sender: found@substack.com
  name: FOUND Global
  focus: Global restaurant openings
```

### Sender Blacklist

Exclude newsletters from these senders (even if they match the search):

```
# Example:
# - noreply@spam.com
```

## Industry Topics to Cover

The digest comprehensively covers these restaurant and food industry topics:

```
- M&A Activity: Mergers, acquisitions, deals, private equity
- QSR Trends: Quick service restaurant news, fast food, drive-thru
- Full-Service Restaurant Trends: Casual dining, fine dining, independent restaurants
- Supply Chain: Food costs, logistics, disruptions, commodity prices
- Labor: Staffing, wages, union activity, retention, training
- Consumer Behavior: Dining trends, preferences, spending patterns
- Regulatory Changes: New laws, compliance, health codes, labor regulations
- NYC Restaurant Scene: Openings, closures, local news, neighborhood trends
- NY SLA (State Liquor Authority): License changes, regulatory updates, policy changes affecting restaurant/bar liquor licenses in New York
- Restaurant Real Estate: Lease news, retail vacancy trends, notable space availabilities in NYC
- Restaurant Executive Moves: C-suite changes, notable hiring across the industry
```

## Web Search Sources

Major trade publications and news sources to search:

```
Trade Publications:
- Restaurant Business
- Nation's Restaurant News (NRN)
- Restaurant Hospitality
- QSR Magazine
- Food & Wine
- Restaurant Dive
- FSR Magazine
- Foodservice Equipment & Supplies

NYC-Specific:
- Eater NY
- Grub Street
- The Infatuation
- Time Out New York Food

NYC Hyperlocal Blogs (break closure/opening stories first):
- Greenpointers (greenpointers.com) — Greenpoint, North Brooklyn
- EV Grieve (evgrieve.com) — East Village
- Bronx Times (bxtimes.com) — Bronx
- West Side Rag (westsiderag.com) — Upper West Side
- Bklyner (bklyner.com) — Brooklyn-wide
- Patch NYC (patch.com/new-york) — All NYC neighborhoods
- What Now (whatnow.com/new-york) — NYC openings/closings

General Business (Restaurant Coverage):
- Bloomberg
- Wall Street Journal
- New York Times Dining
- Business Insider
```

## Calendar Settings

### Calendars to Include

```
- matt@cornerboothholdings.com   # CBH (primary)
- Lieber - McCrum Family Calendar  # Family events
```

### Event Types to Show

```
- meetings
- deadlines
- reminders
```

## Digest Settings

### Retention

How many days of digests to keep in Knowledge/DIGESTS/:

```
retention_days: 30
```

### Summary Style

How detailed should summaries be:

```
style: comprehensive  # Options: concise (2-3 bullets), detailed (full summary), comprehensive (in-depth coverage with multiple points)
```

### Automation

For 5am daily generation, set up a cron job or scheduled task:

```
# macOS/Linux cron example (runs at 5am daily):
# 0 5 * * * cd "/Users/matthewlieber/Obsidian/personal-os" && /path/to/claude "Show me my daily digest"

# Or use macOS launchd (see README.md for setup instructions)
```

### Geographic Focus

Primary geographic focus for local news:

```
primary_region: New York City
include_national: true
include_international: false
```

## Source Diversity Rules

Controls to prevent any single source from dominating the digest.

```yaml
nrn_cap: 3                    # Max NRN stories per digest
min_non_nrn_sources: 2        # Minimum number of non-NRN sources that must appear

# Priority NYC local sources - actively search these if underrepresented
priority_local_sources:
  - Eater NY (ny.eater.com)
  - Grub Street (grubstreet.com)
  - The Infatuation (theinfatuation.com)
  - FOUND NY (foundny.substack.com)
  - The Strong Buzz (andreastrong.substack.com)

# Fallback search queries when all stories are NRN
diversity_search_queries:
  - "NYC restaurant news"
  - "site:ny.eater.com"
  - "site:grubstreet.com"
  - "site:theinfatuation.com"
  - "New York restaurant opening closing"
  - "site:greenpointers.com"
  - "site:evgrieve.com"
  - "site:bxtimes.com"
  - "NYC restaurant closed OR closing"
```

## Real Estate Intelligence

When NYC restaurant closures are detected, research the space for potential acquisition.

```yaml
enabled: true
trigger: NYC restaurant closure detected in any news source

# Google Maps link template
maps_template: "https://www.google.com/maps/search/?api=1&query={ADDRESS_URL_ENCODED}"

# Real estate research sources
research_sources:
  - LoopNet (loopnet.com)
  - Crexi (crexi.com)

# Data to collect per location
fields:
  - exact_address
  - google_maps_link
  - square_footage
  - lease_terms
  - asking_rent
  - space_type  # bakery, full-service, QSR, etc.

# Only research closures in these markets
markets:
  - New York City
```

## Meeting Research

Settings for deep attendee research (Step 6.5 in the workflow).

```yaml
# Search depth limits per person
max_transcript_reads: 3
max_email_threads: 5
max_beeper_searches: 2
gmail_lookback_days: 30

# Contacts lookup workflow
# ALWAYS start with mcp__contacts__lookup_name to get phone + email
# Then search Beeper with phone numbers in spaced format: XXX XXX XXXX
# Then search Gmail with email addresses

# Skip patterns - no research needed for these meeting types
skip_patterns:
  - Brain Trust
  - Pies Dos
  - Matt-Jason
  - Matt & Sarah
  - Matt/Jeff
  - tutoring
  - Track Practice
  - family events
  - recurring internal syncs
```

# Daily Digest Integration

Comprehensive daily news briefing on the restaurant and food industry, aggregating newsletters from Gmail, web sources, and calendar events.

## How It Works

1. **Newsletter Collection**: Searches Gmail for restaurant/food industry newsletters from the last 24 hours
2. **Web Search**: Searches major trade publications and news sources for breaking restaurant industry news
3. **Content Categorization**: Organizes content by topic:
   - M&A Activity
   - QSR Trends
   - Full-Service Restaurant Trends
   - Supply Chain
   - Labor
   - Consumer Behavior
   - Regulatory Changes
   - NYC Restaurant Scene (openings, closures, local news)
4. **Content Summarization**: AI reads each source and extracts comprehensive key takeaways
5. **Calendar Pull**: Gets today's events from Google Calendar
6. **Digest Generation**: Creates a comprehensive markdown file in `Knowledge/DIGESTS/`

## Usage

The digest is automatically generated during your morning standup (ideally at 5am):

```
What should I work on today?
```

Or generate on-demand:

```
Show me my daily digest
```

## Coverage

The digest provides comprehensive coverage of:

- **M&A Activity**: Restaurant acquisitions, mergers, private equity deals
- **QSR Trends**: Quick service restaurant news, fast food industry updates
- **Full-Service Restaurant Trends**: Casual dining, fine dining, independent restaurants
- **Supply Chain**: Food costs, logistics, disruptions, commodity prices
- **Labor**: Staffing, wages, union activity, retention, training
- **Consumer Behavior**: Dining trends, preferences, spending patterns
- **Regulatory Changes**: New laws, compliance requirements, health codes
- **NYC Restaurant Scene**: New openings, closures, neighborhood trends

## Sources

- **Newsletters**: Your subscribed restaurant/food industry email newsletters
- **Trade Publications**: Restaurant Business, Nation's Restaurant News, QSR Magazine, Restaurant Hospitality, Food & Wine
- **NYC-Specific**: Eater NY, Grub Street, The Infatuation
- **General Business**: Bloomberg, WSJ, NYT Dining (restaurant coverage)

## Configuration

Edit `config.md` in this directory to customize:

- Restaurant/food industry newsletter sender whitelist/blacklist
- Industry topics to cover
- Trade publication sources
- NYC-specific settings
- Calendar settings
- Summary depth (comprehensive by default)
- Geographic focus

## Automation (5am Daily)

See `examples/workflows/daily-digest.md` for automation setup instructions using:
- macOS launchd (recommended)
- Cron jobs
- Shortcuts app

## Required MCP Servers

- **Gmail**: For searching and reading newsletters
- **Google Calendar**: For pulling today's events
- **Web Search**: For finding breaking news from trade publications

## Output Location

Digests are saved to:

```
Knowledge/DIGESTS/YYYY-MM-DD.md
```

This directory is gitignored to keep personal content private.

## Troubleshooting

**No newsletters found?**
- Check that Gmail MCP is connected
- Verify newsletters contain "unsubscribe" text
- Try adjusting the search query in config.md
- Add specific newsletter senders to whitelist in config.md

**No web results?**
- Verify web search is available
- Check that trade publication sources are accessible
- Try adjusting search terms in the workflow

**Calendar events missing?**
- Verify Google Calendar MCP is connected
- Check calendar IDs in config.md

**Digest not comprehensive enough?**
- Adjust summary style in config.md to "comprehensive"
- Add more newsletter senders to whitelist
- Review workflow search terms for web sources

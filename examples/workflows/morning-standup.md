# Morning Standup Workflow

A quick check-in to get your daily digest, sync recent meetings, and set your focus for the day.

## The Prompt

```
What should I work on today?
```

## Workflow Steps

### Step 0: Generate Daily Digest

Start by generating or retrieving today's digest:

1. Follow the workflow in `examples/workflows/daily-digest.md`
2. Search Gmail for newsletters from the last 24 hours
3. Pull today's calendar events
4. Summarize key items and save to `Knowledge/DIGESTS/`
5. Present highlights to user before proceeding

### Step 1: Sync New Meetings and Extract Tasks

After the digest, run `/meeting-sync` to:
- Check for new Granola meetings
- Sync selected meetings to Knowledge folder
- Extract tasks from meeting notes
- Let user select which tasks to add

See `~/.claude/skills/meeting-sync/SKILL.md` for full workflow details.

### Step 2: Review Tasks and Set Priorities

After syncing meetings, proceed with task review.

### Step 3: Project Health Check

Scan P0 project briefs for staleness. This costs almost nothing (just reading brief headers) but surfaces projects slipping through the cracks.

1. Read `projects/README.md` to get the list of P0 projects and their brief file paths
2. For each P0 project brief, check:
   - **Staleness:** If `Last Updated:` is 3+ days old, flag: "[Project] brief is X days stale"
   - **Gone quiet:** If `## Recent Communications` has no entries in the last 5 days, flag: "[Project] has gone quiet — consider following up"
3. Present any flags to Matt as part of morning priorities:
   ```
   Project health flags:
   - Brown Bag brief is 4 days stale (last updated Feb 20)
   - Project Carroll has gone quiet — no communications since Feb 19
   ```
4. If no flags, skip this section entirely (don't report "all healthy" — just move on)

## Example Conversation

**You:** What should I work on today?

**Claude:** Let me check for new meetings first...

*[Checks Granola, finds 2 new meetings]*

I found 2 new meetings since your last sync:
1. **Weekly Team Standup** (yesterday) - has notes
2. **Client Call** (yesterday) - has notes and transcript

Sync these to your Knowledge folder? [Sync all / Select specific / Skip]

*[After syncing]*

Now for your priorities. Based on your tasks and goals:

**1. [P0] Finalize Q1 roadmap presentation** (estimated: 90 min)
- Due tomorrow for leadership review
- Aligns with your quarterly objective: "Ship Q1 roadmap"

**2. [P1] Reply to Sarah's partnership email** (estimated: 20 min)
- Been waiting 3 days, relationship maintenance
- Quick win before deep work

**3. [P1] Write user story for checkout flow** (estimated: 60 min)
- Blocking engineering from starting sprint work
- Supports goal: "Improve activation by 20%"

You have 2 blocked tasks I noticed:
- "API integration spec" - waiting on engineering estimates
- "User research synthesis" - waiting on interview transcripts

Want me to help you get started on any of these?

---

## Variations

### When You're Overwhelmed

```
I'm overwhelmed. What's the ONE thing I should focus on?
```

### When You Have Limited Time

```
I only have 2 hours before meetings. What can I realistically finish?
```

### When You Need Context

```
Remind me what I was working on yesterday and what's next.
```

## Tips

- Do this first thing, before checking email/Slack
- Keep it under 2 minutes - just pick and start
- If you're stuck deciding, ask Claude to pick for you

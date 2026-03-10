# Monthly Learning Review Workflow

A month-end review of accumulated learnings that identifies patterns and proposes systemic improvements to the brain system.

**Trigger:** End of month (manual), or "review learnings", "monthly learning review"
**Frequency:** Monthly

---

## Steps

### Step 1: Read Current Learnings

Read `Knowledge/LEARNINGS/` for the current month's file (e.g., `2026-02.md`) and the prior month's file if it exists.

If no learnings exist, say so and suggest capturing some going forward.

### Step 2: Categorize by Type

Group all learnings into their categories:
- **tool-quirk** — MCP tools, API behaviors, CLI issues
- **data-quality** — Incorrect data, missing data, format issues
- **workflow** — Reusable patterns, multi-step processes that worked
- **preference** — Matt's explicit feedback about how he wants things done
- **skill-fix** — Corrections to skill files or automation scripts

Count by category. Show the distribution.

### Step 3: Identify Patterns

Look for repeated themes:
- Same tool failing the same way multiple times → need a workaround rule
- Same type of correction from Matt → need a CLAUDE.md rule
- Same workflow succeeding → need to codify as a skill or workflow file
- Data quality issues in the same table/source → need an ETL fix or validation

For each pattern found, describe:
- What keeps happening
- How many times it occurred
- What the current workaround is (if any)

### Step 4: Propose Concrete Changes

For each pattern, propose a specific change:

| Pattern | Proposed Change | File to Update |
|---------|----------------|----------------|
| Beeper 404 on keyword search | Add workaround to MCP reference | `core/context/mcp-reference.md` |
| Matt always wants plain text emails | Add rule to CLAUDE.md | `~/.claude/CLAUDE.md` |
| Meeting sync misses side meetings | Update Granola search to include informal meetings | `/meeting-sync` skill |

Each proposal must specify:
- The exact file to modify
- What to add or change
- Why (which learnings support this)

### Step 5: Present to Matt

Present proposals grouped by type:
1. **CLAUDE.md rule changes** (most impactful — affect all sessions)
2. **Skill file updates** (affect specific workflows)
3. **Context doc updates** (improve reference accuracy)
4. **New automations or workflows** (new capabilities)

Use AskUserQuestion with multiSelect to let Matt approve, reject, or modify each proposal.

### Step 6: Execute Approved Changes

For each approved change:
1. Make the edit to the specified file
2. Log the change back to the learnings file:
   ```
   ### YYYY-MM-DD [propagated]
   **From learnings:** [list of learning dates that led to this]
   **Change:** [what was changed and where]
   ```

### Step 7: Archive

After review is complete:
1. Create `Knowledge/LEARNINGS/archive/` if it doesn't exist
2. Copy the reviewed month's file to `Knowledge/LEARNINGS/archive/YYYY-MM.md`
3. The original stays in place (Obsidian links may reference it)
4. Start a fresh file for the next month

---

## Edge Cases

**No learnings captured:** If the month's file is empty or missing, the review becomes a meta-learning itself. Note that the protocol isn't being followed and suggest lightweight triggers (e.g., "After any MCP tool error, capture a learning before moving on").

**Very few learnings (< 3):** Still worth reviewing but keep it brief. Focus on whether the protocol itself needs adjustment.

**Many learnings (> 20):** Prioritize patterns over individual items. Focus on the top 3-5 patterns that would have the most impact if codified.

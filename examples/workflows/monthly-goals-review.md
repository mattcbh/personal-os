# Monthly Goals Review Workflow

A monthly check that compares actual recent focus to `GOALS.md`, asks whether the goals are still right, and updates the system if they are not.

**Trigger:** Scheduled Monday-morning automation (full review on the first Monday of the month), or "review my goals", "monthly goals review"
**Frequency:** Monthly

---

## Steps

### Step 1: Read The Current Goal Stack

Read:

- `GOALS.md`
- `projects/README.md`
- Active project briefs referenced there

Note the stated goals, active priorities, and any obvious stale or missing project coverage.

### Step 2: Reconstruct Actual Recent Focus

Review the last 30 days of signal from the systems that show where time and attention really went:

- Recent project brief updates
- `things-sync/` task activity
- Recent digests in `Knowledge/DIGESTS/`
- Recent meeting transcripts if they materially changed priorities
- Recent communications or trackers for major projects

Summarize the 3-5 biggest themes. This should answer: "What have we actually been spending time on?"

### Step 3: Compare Stated Goals To Actual Work

For each major theme, classify it:

- Clearly supports an existing goal
- Supports a project but the goal wording is stale or incomplete
- Repeatedly consuming time without a corresponding goal
- Noise that should be deprioritized rather than promoted

Call out any meaningful mismatch between `GOALS.md` and the work pattern.

### Step 4: Ask The Goal-Adjustment Questions

Ask Matt directly:

1. Are these still the right goals?
2. Which goals should be tightened, expanded, demoted, or removed?
3. Is any recurring work now important enough to become a formal goal or project?

If helpful, propose concrete edits rather than asking only open-ended questions.

The automation output should make the decision easy to validate. Present a short keep/change/remove/add summary rather than a vague reminder email.

### Step 5: Update The System If Approved

If Matt wants changes:

1. Update `GOALS.md`
2. Update any affected project briefs in `projects/`
3. If a new multi-week workstream emerged, apply the project-promotion rule and create a brief if appropriate
4. Add or revise Things tasks if the goal changes imply immediate next actions

Do not update goals silently. Wait for explicit approval before editing files.

### Step 6: Close With A Short Decision Summary

Summarize:

- What stayed the same
- What changed
- What follow-up work now matters most

Keep this brief. The point is to reset direction, not produce a long retrospective.

---

## Edge Cases

**No clear drift:** If actual work still matches the goals, say so plainly and suggest no structural changes.

**Too many competing themes:** Recommend narrowing. A goals review should reduce ambiguity, not catalog it.

**Project exists but is stale:** Update the project brief first, then decide whether the underlying goal changed.

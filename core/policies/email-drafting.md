# Email Drafting Policy

## Canonical behavior

1. All email drafts must follow `core/context/writing-style.md`.
2. Never fabricate prior interactions. Verify via transcripts, messages, and calendar before referencing a meeting/call.
3. For scheduling drafts, load `core/context/scheduling.md` and propose exactly 2 concrete slots.
4. Use Reply All for existing threads unless the user explicitly requests otherwise.
5. Do not rely on Gmail API draft visibility in Superhuman workflows.

## Draft transport

- Primary mechanism: `core/automation/superhuman-draft.sh`
- Purpose: queue-first handoff for Superhuman-compatible draft insertion
- Fallback: clipboard copy when Chrome/Superhuman is unavailable

## Security

- Never include secrets, tokens, or credentials in prompts, drafts, notes, logs, or docs.

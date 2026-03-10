# Policy Pack

These files are the canonical policy layer for cross-cutting behavior. Skills, prompts, and runbooks should reference these files instead of duplicating long rule blocks.

## Canonical policy files

- `email-drafting.md` - Drafting behavior and Superhuman constraints
- `scheduling.md` - Meeting-time proposal rules and calendar verification
- `voice-and-writing.md` - Writing voice and tone rules
- `paths-and-state.md` - Canonical folder names and state file paths

## Usage rule

When updating a system-wide behavior, update the relevant policy file first, then update downstream skills/prompts to reference it.

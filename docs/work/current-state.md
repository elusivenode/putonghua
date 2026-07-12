# Current State

This file is temporary operational state for future sessions.

Update it when a session ends with work in progress, validation gaps, or a next
step that would otherwise require chat history. Replace stale details rather
than appending a long log.

## Current Objective

Fix the resumed `chunk chat` conversation path so persisted review threads can
be resumed safely without requiring a fresh conversation workaround.

## Repository State

- Branch: `main`
- Baseline commit: `6c9ac0a` (`Initial commit`)
- Worktree note: the repository is still being built in an uncommitted state,
  so recent Git history is not yet an authoritative source of project context

## Recently Completed

- promotion and Anki discovery sprint completed and moved out of
  `docs/next-sprint-*`
- live Anki smoke test confirmed one published note creates the expected three
  cards in the current `Mandarin vocab` note type
- harness guidance added for context hierarchy, reusable skills, playbooks, and
  handoff
- the completed sprint implementation plan was moved under `docs/work/` so it
  no longer looks like active root-level project state

See
[completed-promotion-anki-sprint.md](completed-promotion-anki-sprint.md) for
the completed sprint record.

## Validation Status

- latest product validation before this harness pass: live chunk suggestion,
  promotion, and Anki publish succeeded
- repository quality gate and CLI help verification passed during the harness
  cleanup pass

## Known Issues

- resuming an older persisted chunk-review conversation can trigger an OpenAI
  `400 Bad Request`; starting a fresh conversation for the chunk works
- the current live Anki note type does not yet expose a dedicated
  `PutonghuaID` field, so publish idempotency still relies on local
  publication records rather than note-field identity

## Recommended Next Action

Reproduce the resumed review-conversation failure in an automated test, then
fix the OpenAI review path so older persisted conversations can be resumed
without hitting the current `400 Bad Request` error.

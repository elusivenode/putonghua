# Current State

This file is temporary operational state for future sessions.

Update it when a session ends with work in progress, validation gaps, or a next
step that would otherwise require chat history. Replace stale details rather
than appending a long log.

## Current Objective

The `feature/cli_ui` branch now has the interactive session as the default
entry path. The next objective is to decide the first post-rollout TUI slice.

## Repository State

- Branch: `feature/cli_ui`
- Baseline commit: `36aa535`
- Worktree note: the repository is still being built in an uncommitted state,
  so recent Git history is not yet an authoritative source of project context

## Recently Completed

- created branch `feature/cli_ui` for the terminal interaction upgrade
- reviewed current CLI architecture, task constraints, and existing command
  surface before planning the TUI work
- added [cli-ui-tui-plan.md](cli-ui-tui-plan.md) with phased rollout,
  constraints, acceptance criteria, and recommended first implementation slice
- added `putonghua tui` as a dedicated read-only session entrypoint
- added dashboard read models and repository list queries for projects, sources,
  and chunks
- added focused tests for TUI dashboard state, session navigation, and CLI
  wiring
- updated [cli-ui-tui-plan.md](cli-ui-tui-plan.md) to track completed rollout
  phases and the active guided review slice
- wired `extract` and `chat` into `putonghua tui` for the selected chunk
- added persisted latest review context to the TUI focus panel so the current
  chunk shows the latest conversation and suggestion summary
- refactored CLI service builders so one-shot chunk commands and the TUI share
  extraction and review provider wiring
- expanded focused TUI tests to cover in-session extraction, chat, and review
  context rendering
- wired `promote` into `putonghua tui` so the selected chunk can promote the
  latest visible review suggestion without dropping to one-shot CLI commands
- updated the TUI focus panel so visible review suggestions surface their
  current promotion status after refresh
- expanded focused TUI tests to cover in-session suggestion promotion and
  promoted-state dashboard refresh
- wired `publish` into `putonghua tui` so promoted chunk candidates can publish
  without dropping to one-shot CLI commands
- added publish target context to the focus panel, including deck, note type,
  publish tags, candidate status, and local Anki note identity
- expanded focused TUI tests to cover in-session candidate publish and
  published-state dashboard refresh
- tightened the publish focus panel so chunk candidates now show publish
  readiness versus already-published local state
- made duplicate publish feedback explicit in-session before and after
  confirmation when a local publication record already exists
- verified live AnkiConnect reachability, discovered the live `Mandarin` deck
  and `Mandarin vocab` note type, and exercised the duplicate publish CLI path
  against a real local publication record
- switched the top-level CLI so bare `putonghua` now opens the interactive
  session by default while leaving scripted subcommands intact
- updated top-level help and README usage so the TUI is documented as the
  primary operator entry path, with `putonghua tui` retained as an explicit
  alias

See
[completed-promotion-anki-sprint.md](completed-promotion-anki-sprint.md) for
the completed sprint record.

## Validation Status

- `UV_CACHE_DIR=.uv-cache uv run ruff format --check .` passed
- `UV_CACHE_DIR=.uv-cache uv run ruff check .` passed
- `UV_CACHE_DIR=.uv-cache uv run pyright` passed
- `UV_CACHE_DIR=.uv-cache uv run pytest` passed
- `UV_CACHE_DIR=.uv-cache uv run putonghua --help` passed
- `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_cli.py tests/test_tui_session.py`
  passed
- `UV_CACHE_DIR=.uv-cache uv run putonghua anki check --config config.yaml`
  passed
- `UV_CACHE_DIR=.uv-cache uv run putonghua anki note-types --config config.yaml`
  passed
- `UV_CACHE_DIR=.uv-cache uv run putonghua anki note-type --name "Mandarin vocab" --config config.yaml`
  passed
- `UV_CACHE_DIR=.uv-cache uv run putonghua candidate publish --candidate-id 51b58902-0e85-4ede-a84d-face2f0ad17e --deck Mandarin --note-type "Mandarin vocab" --config config.yaml`
  passed

## Known Issues

- the current TUI slice now supports extract, chat, suggestion promotion, and
  candidate publish, but it still relies on local publication records rather
  than remote duplicate detection in Anki
- resuming an older persisted chunk-review conversation can trigger an OpenAI
  `400 Bad Request`; starting a fresh conversation for the chunk works
- the current live Anki note type does not yet expose a dedicated
  `PutonghuaID` field, so publish idempotency still relies on local
  publication records rather than note-field identity
- live validation covered connectivity, note-type discovery, and the duplicate
  path only; this branch has still not performed a fresh live new-note publish

## Recommended Next Action

Start the first post-rollout TUI slice, likely either persisted session restore
or an in-session import/setup path so new operators can stay inside the
interactive workflow from the start.

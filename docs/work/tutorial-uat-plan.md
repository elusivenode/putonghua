# Tutorial / UAT Plan

## Objective

Add a guided tutorial flow inside `putonghua` that teaches the operator how to
use the interactive session, exercises the normal review workflow, and ends
with a real card persisted to Anki.

## User-Visible Result

After completion, a learner can run a tutorial from the interactive session,
follow explicit prompts and checkpoints, practice the main commands in context,
and finish with one reviewed card published to Anki with provenance preserved.

## Scope

- include: a guided interactive tutorial entered from the TUI
- include: tutorial copy that teaches the real operator workflow rather than a
  fake demo-only path
- include: checkpoints for navigation, extraction, review chat, suggestion
  promotion, and candidate publish
- include: explicit progress state so the tutorial can resume safely after an
  interruption
- include: tests for tutorial state transitions and CLI/TUI wiring
- include: documentation for setup, expected user actions, and UAT completion

## Non-Goals

- exclude: replacing the normal TUI workflow with a tutorial-only experience
- exclude: automating review decisions or silently publishing without operator
  confirmation
- exclude: broad curriculum design beyond the first end-to-end onboarding path
- exclude: remote sync, learner analytics, or multi-card lesson plans

## Relevant Constraints

- [PRODUCT.md](../../PRODUCT.md): preserve human control, provenance, and
  learning quality over automation
- [architecture.md](../../architecture.md): keep workflow logic in services and
  make stages resumable and auditable
- [AGENTS.md](../../AGENTS.md): prefer a small complete vertical slice and keep
  durable state in the repository

## Required Outcome

The first tutorial slice should require the user to use real `putonghua`
commands and should only complete after:

1. the operator enters the interactive session
2. a tutorial project or source context is available
3. the operator navigates to the intended chunk
4. extraction runs for that chunk
5. the operator sends at least one review chat prompt
6. the operator promotes one suggestion into a durable candidate
7. the operator confirms publish for that candidate
8. a local publication record exists and Anki returns a note id

## Assumptions

- the tutorial should run against real persisted local state, not an isolated
  in-memory mock workflow
- the tutorial can bootstrap or point to a small dedicated tutorial dataset so
  the learner does not have to source content manually before trying the flow
- live completion requires Anki with AnkiConnect available and a configured
  deck/note type
- the first slice can assume OpenAI-backed extraction and review are configured
  when the tutorial reaches those steps

## Proposed UX Shape

- add a `tutorial` command inside the TUI help surface rather than a separate
  standalone binary path
- present one current step at a time with:
  - goal
  - exact command to try
  - success condition
  - why the step matters
- keep the regular dashboard visible so the learner sees the real workspace,
  not a disconnected wizard
- show progress as a small resumable checklist
- block tutorial advancement on real completion signals from persisted state,
  not on the user typing `next`
- keep skip/reset controls explicit for development and recovery

## Implementation Plan

### Phase 1: Tutorial Domain Model And Persistence

- add a tutorial state model under `src/putonghua/models/`
- represent tutorial progress as explicit steps with completion criteria
- persist the active tutorial session in SQLite so it can resume after exit
- store enough metadata to know which project, source, chunk, suggestion, and
  candidate the tutorial expects

### Phase 2: Tutorial Bootstrap Slice

- add a service that ensures a dedicated tutorial workspace exists
- choose one stable bootstrap path:
  - preferred: seed a small local tutorial source from repository assets
  - fallback: create a tutorial project that instructs the operator to import a
    provided sample manually
- keep bootstrap idempotent so rerunning the tutorial does not duplicate local
  state unnecessarily

### Phase 3: TUI Integration

- extend `src/putonghua/cli/tui.py` help text and command handling with
  `tutorial`, `tutorial reset`, and `tutorial status`
- render a tutorial panel inside the dashboard when a tutorial is active
- surface step instructions, expected command, and current completion state
- refresh tutorial status after every mutating command already supported by the
  TUI

### Phase 4: Completion Detection

- add service-level checks for each tutorial milestone:
  - selected tutorial chunk
  - extraction produced candidates
  - review conversation exists
  - suggestion promoted
  - publication record created with note id
- avoid duplicating workflow logic in the TUI; tutorial completion checks
  should read persisted state through repositories or a dedicated service
- make failures actionable when configuration or external dependencies are
  missing

### Phase 5: UAT And Documentation

- document the tutorial in `README.md` as the recommended first-run flow
- document prerequisites, reset behavior, and what counts as success
- add a short UAT checklist that can be executed against a live local setup
- update `docs/work/current-state.md` with the current tutorial status before
  ending the implementation session

## Suggested File Touches

- `src/putonghua/cli/tui.py`
- `src/putonghua/services/tui_session.py`
- new tutorial-focused service module under `src/putonghua/services/`
- new tutorial models under `src/putonghua/models/`
- repository additions in `src/putonghua/database/repositories.py`
- migration for tutorial session persistence if needed
- `tests/test_tui_session.py`
- new tutorial-focused tests
- `README.md`
- `docs/work/current-state.md`

## Acceptance Criteria

- behavior: the TUI exposes a discoverable tutorial entry point
- behavior: the tutorial explains the normal workflow while the real dashboard
  remains visible
- behavior: tutorial progress survives exiting and relaunching `putonghua`
- behavior: a tutorial step only completes when corresponding persisted state
  exists
- behavior: finishing the tutorial requires a real local publication record and
  an Anki note id
- behavior: operators can reset the tutorial without damaging unrelated project
  data

## Validation Plan

```bash
UV_CACHE_DIR=.uv-cache uv run ruff format --check .
UV_CACHE_DIR=.uv-cache uv run ruff check .
UV_CACHE_DIR=.uv-cache uv run pyright
UV_CACHE_DIR=.uv-cache uv run pytest
UV_CACHE_DIR=.uv-cache uv run putonghua --help
```

Task-specific validation:

- add focused tests for tutorial progress detection and resume behavior
- add TUI command tests for `tutorial` entry, status rendering, and reset
- run a manual local tutorial walkthrough through publish
- verify AnkiConnect before claiming tutorial completion works end to end

## Recommended Next Session Start

1. read this file and [current-state.md](current-state.md)
2. inspect the current TUI command loop and dashboard service
3. implement Phase 1 first, including persistence shape and tests
4. only add tutorial copy after completion detection exists

## Open Risks

- live tutorial completion still depends on external services: OpenAI and Anki
- tutorial bootstrap content must be small, stable, and useful enough to
  generate at least one publishable card
- if current note-type mapping remains loose, tutorial completion should key off
  local publication records plus returned Anki note id rather than note-field
  identity

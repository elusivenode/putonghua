# Current State

This file is temporary operational state for future sessions.

Update it when a session ends with work in progress, validation gaps, or a next
step that would otherwise require chat history. Replace stale details rather
than appending a long log.

## Current Objective

On `uat/20270719`, validate a resumable 60-second podcast workflow and tune
candidate generation from real learner-reviewed chunks.

## Repository State

- Branch: `uat/20270719`
- Baseline commit: `3ff72d1` (`feature/tutorial` merged into `main`)
- Worktree note: dirty with resumable transcription-window implementation

## Recently Completed

- added `011_transcription_windows` and scripted `youtube prepare`,
  `youtube status`, and `youtube transcribe-next` commands; each API request
  transcribes exactly one persisted 60-second window and creates its matching
  study chunk
- prepared `https://youtu.be/lR5Rt6293bg` as source
  `ae03c400-a694-4ff3-ae20-de0f0fd04f20` (43:56, 44 windows)
- live-transcribed windows 1 and 2 (00:00-02:00); resume point is 02:00-03:00
- live-extracted four proposed phrase candidates for chunk
  `67880476-881c-4691-ab7e-f1c2d07d6a5c`; two were learner-promoted and
  published to Anki with local records and note IDs `1784421847690` and
  `1784422076483`
- removed the original local 45-second setup clip and its project; its historic
  remote Anki note was not deleted and now has no local publication record

- merged the `feature/cli_ui` rollout into `main`
- pushed `main` to `origin`
- deleted the local `feature/cli_ui` branch
- created `feature/tutorial` for the next guided onboarding slice
- added [tutorial-uat-plan.md](tutorial-uat-plan.md) with the phased tutorial
  implementation plan, acceptance criteria, risks, and next-session start
  sequence
- implemented Phase 1 tutorial persistence under
  `src/putonghua/database/migrations/010_tutorial_sessions.sql`,
  `src/putonghua/models/tutorial.py`, and `src/putonghua/services/tutorial.py`
- implemented Phase 2 tutorial bootstrap so the interactive session can seed a
  dedicated tutorial project/source/chunk set on demand
- implemented Phase 3 TUI integration so `tutorial`, `tutorial status`, and
  `tutorial reset` are available and the dashboard renders tutorial progress
  when active
- tightened Phase 4 tutorial completion reporting so blocked steps now surface
  actionable detail for chunk selection, extraction, review chat, promotion,
  and incomplete publish state
- implemented Phase 5 first-run documentation in [README.md](../../README.md)
  and added the live walkthrough checklist in
  [tutorial-uat-checklist.md](tutorial-uat-checklist.md)
- reworked the tutorial panel so each milestone now shows explicit operator
  actions, observations, and choice guidance instead of a single terse command
  hint, and removed the duplicate panel render when `tutorial` starts
- reworked the tutorial flow again so it now starts with one-at-a-time guided
  intro steps for session layout and chunk workflow, advanced with
  `tutorial next`, before switching into real chunk processing checkpoints
- changed tutorial entry semantics so `tutorial` now starts a clean walkthrough
  from step 1, `tutorial resume` continues an existing run, and reset clears
  tutorial-only workflow artifacts instead of leaving stale progress behind
- changed the candidate workflow so review chat is now optional for promotion:
  operators can promote extracted candidates directly, and the tutorial now
  treats chat as optional refinement instead of a required milestone
- simplified the operator-facing model again so TUI chat-derived ideas now land
  in the same candidate list as extracted options, and `promote N` always means
  candidate `N` in that unified list
- added repository support for persisted tutorial sessions and promoted
  suggestion lookup plus tutorial source lookup in
  `src/putonghua/database/repositories.py`
- added coverage for tutorial migrations, repository behavior, and end-to-end
  tutorial progress detection, bootstrap, and TUI wiring in
  `tests/test_migrations.py`, `tests/test_repositories.py`,
  `tests/test_tutorial_service.py`, and `tests/test_tui_session.py`

See
[completed-promotion-anki-sprint.md](completed-promotion-anki-sprint.md) for
the completed sprint record.

## Validation Status

- `UV_CACHE_DIR=.uv-cache uv run ruff format --check .` passed
- `UV_CACHE_DIR=.uv-cache uv run ruff check .` passed
- `UV_CACHE_DIR=.uv-cache uv run pyright` passed
- `UV_CACHE_DIR=.uv-cache uv run pytest` passed with `76 passed`
- live OpenAI transcription succeeded for two 60-second windows
- live OpenAI candidate extraction succeeded for the first window
- live TUI promotion and Anki publication succeeded for two first-window cards

- tutorial Phase 1 through Phase 5 implementation validated in this session:
- `UV_CACHE_DIR=.uv-cache uv run ruff format --check .` passed
- `UV_CACHE_DIR=.uv-cache uv run ruff check .` passed
- `UV_CACHE_DIR=.uv-cache uv run pyright` passed
- `UV_CACHE_DIR=.uv-cache uv run pytest` passed with `64 passed`
- `UV_CACHE_DIR=.uv-cache uv run putonghua --help` passed
- no live OpenAI or Anki tutorial walkthrough run in this session

## Known Issues

- the current TUI slice still relies on local publication records rather than
  remote duplicate detection in Anki
- resuming an older persisted chunk-review conversation can trigger an OpenAI
  `400 Bad Request`; starting a fresh conversation for the chunk works
- the current live Anki note type does not yet expose a dedicated
  `PutonghuaID` field, so publish idempotency still relies on local
  publication records rather than note-field identity
- live validation covered connectivity, note-type discovery, and the duplicate
  path only; a fresh live new-note publish is still outstanding and should be
  part of tutorial UAT

## Recommended Next Action

Continue the full podcast from the persisted 02:00-03:00 window with
`youtube transcribe-next --source-id ae03c400-a694-4ff3-ae20-de0f0fd04f20`.
Use the TUI to review each new chunk before promotion. Tune the extraction
prompt to reject syntactically incomplete phrases such as `欢迎大家来到` before
processing the episode in bulk.

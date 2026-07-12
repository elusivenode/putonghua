# CLI UI / TUI Plan

## Objective

Upgrade `putonghua` from a command-only CLI into a session-oriented terminal
workflow where running `putonghua` can open an interactive review workspace
with contextual help, shortcuts, and guided card-creation steps.

## User-Visible Result

After completion, a learner can enter a terminal session, see current work,
navigate sources and chunks, run the existing card workflow from one place, and
use visible keybindings instead of memorizing many separate subcommands.

## Scope

- include: an interactive terminal session entered from the top-level
  `putonghua` command or a dedicated `putonghua tui` command during rollout
- include: session navigation for the current vertical slice
  import -> chunk selection -> extraction -> review chat -> suggestion promote
  -> candidate publish
- include: reusable CLI/TUI service boundaries so existing business logic stays
  in `services/`
- include: help surfaces, shortcut discovery, actionable error states, and
  resumable session state
- include: tests for TUI state transitions, command wiring, and fallback CLI
  behavior

## Non-Goals

- exclude: replacing the existing subcommand CLI in the first slice
- exclude: GUI or browser-based interfaces
- exclude: automating approval or publish decisions without human review
- exclude: redesigning provider contracts or persistence model unless a real TUI
  requirement forces it

## Relevant Constraints

- [PRODUCT.md](../../PRODUCT.md): preserve human review, provenance, and
  resumable local state
- [architecture.md](../../architecture.md): keep business logic out of CLI and
  make workflow stages resumable
- [AGENTS.md](../../AGENTS.md): prefer small complete vertical slices and avoid
  speculative abstractions

## Expected Boundaries

- likely files: `src/putonghua/cli/app.py`, new `src/putonghua/cli/tui_*`
  modules, existing service modules, `tests/test_cli.py`, and new TUI-focused
  tests
- avoid: moving workflow logic into key handlers or screen rendering code
- preserve: current service APIs where practical, adding thin facade services
  only where the TUI needs aggregated read models

## Assumptions

- the existing one-shot subcommands remain supported throughout rollout for
  scripting and recovery paths
- the first TUI slice should focus on review and promotion for already imported
  content before trying to cover every setup or maintenance command
- a text UI library can be added if it materially improves key handling and
  layout; if not, a Rich plus prompt loop fallback is acceptable for an initial
  slice

## Proposed Rollout

### Phase 1: Interaction Design And Entry Strategy

- status: complete
- rollout currently starts behind `putonghua tui`
- session model defined around current project, source, and chunk selection,
  with chunk review context as the next active state surface
- minimum command set established for help, refresh, selection, next pending
  chunk, and quit
- persisted state restore is still pending beyond deterministic fallback to the
  first available project, source, and chunk

### Phase 2: Read-Only Session Shell

- status: complete
- added a session entry point with a stable layout and shortcut help
- current dashboard shows projects, sources, pending chunks, and candidate
  counts from SQLite-backed read models
- navigation works without mutating workflow state
- existing subcommands remain untouched as fallback paths

### Phase 3: Guided Chunk Review Slice

- status: complete
- chunk-focused workspace exists through the selected-chunk focus panel
- chunk extraction now runs from the session
- latest persisted review conversation and suggestion summary now render in the
  focus panel
- review prompts now run in-session through `chat`
- visible review suggestions now expose status in the focus panel
- promote actions now run from the same session through `promote [N]`

### Phase 4: Publish Slice

- status: complete
- candidate publish actions now run in-session through `publish [N]`
- deck, note type, and publish tags now render in the selected chunk focus panel
- chunk candidates now render with publish readiness, local published state,
  and local Anki note identity
- publish remains an explicit confirm action
- duplicate feedback now makes it explicit when the session is reusing an
  existing local publication record instead of creating a new Anki note
- live validation confirmed AnkiConnect reachability, the `Mandarin` deck, the
  `Mandarin vocab` note type field mapping, and the local duplicate CLI path

### Phase 5: Top-Level CLI Upgrade

- status: complete
- bare `putonghua` now launches the interactive session by default while
  preserving scripted subcommands
- top-level help and README usage now treat the TUI as the primary operator
  entry path
- `putonghua tui` remains available as an explicit alias for the same session
  entry behavior

## Implementation Outline

1. Introduce a TUI-specific CLI module instead of expanding `app.py` into one
   large file.
2. Add a session state model that is independent from rendering.
3. Add read-model helpers or facade services only for aggregated screens the TUI
   needs.
4. Keep all workflow mutations delegated to existing or new service methods.
5. Treat help text, shortcut maps, and panel copy as versioned CLI assets, not
   scattered inline strings.

## Acceptance Criteria

- behavior: a user can launch the interactive session and discover available
  actions without external documentation
- behavior: the session can show pending work for current data already stored in
  SQLite
- behavior: a user can complete at least one coherent in-session workflow from
  pending chunk to promoted suggestion without dropping to manual subcommands
- behavior: publish remains an explicit user action with clear success and
  duplicate states
- behavior: non-interactive subcommands still work

## Validation

```bash
UV_CACHE_DIR=.uv-cache uv run ruff format --check .
UV_CACHE_DIR=.uv-cache uv run ruff check .
UV_CACHE_DIR=.uv-cache uv run pyright
UV_CACHE_DIR=.uv-cache uv run pytest
UV_CACHE_DIR=.uv-cache uv run putonghua --help
```

Task-specific validation:

- add focused tests for TUI state reducers or controllers
- add command-entry tests for the interactive mode
- run at least one local manual smoke test for session navigation

## Recommended Next Task

Decide the next post-rollout slice for the interactive session, likely either
persisted session restore or a more deliberate import/setup path from inside
the TUI so first-time operators can stay in one workflow surface.

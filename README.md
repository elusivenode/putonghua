# putonghua

Local-first, AI-assisted workflow for turning authentic Mandarin content into
high-quality Anki flashcards without removing human judgment.

## Read This First

- [PRODUCT.md](PRODUCT.md): product intent and non-goals
- [architecture.md](architecture.md): technical boundaries and design direction
- [AGENTS.md](AGENTS.md): coding-agent workflow and validation rules
- [docs/work/current-state.md](docs/work/current-state.md): temporary
  cross-session operational state

For completed sprint context, see
[docs/work/completed-promotion-anki-sprint.md](docs/work/completed-promotion-anki-sprint.md).

## Current Product Slice

The repository currently supports:

- YouTube episode import
- subtitle download with OpenAI transcription fallback
- transcript segmentation into `study_chunks`
- chunk-scoped candidate extraction
- chunk-scoped review chat that can add more candidates to the current chunk
- suggestion promotion into durable candidate cards
- AnkiConnect discovery
- one safe candidate publish path into an existing Anki note type

## Environment

This project uses Python 3.12 and a project-local `uv` environment.

Create or refresh the environment:

```bash
UV_CACHE_DIR=.uv-cache uv venv --python 3.12 .venv
UV_CACHE_DIR=.uv-cache uv sync --dev
```

Activate it if desired:

```bash
source .venv/bin/activate
```

## Canonical Commands

Launch the interactive session:

```bash
uv run putonghua --config config.yaml
```

Show the scripted command surface:

```bash
uv run putonghua --help
```

Initialize local directories:

```bash
uv run putonghua init --config config.yaml
```

Apply database migrations:

```bash
uv run putonghua db migrate --config config.yaml
```

Check AnkiConnect connectivity:

```bash
uv run putonghua anki check --config config.yaml
```

Import one YouTube source:

```bash
uv run putonghua youtube import "https://www.youtube.com/watch?v=VIDEO_ID" --project-name "Episode Name" --config config.yaml
```

Build study chunks from an imported source:

```bash
uv run putonghua chunk build --source-id SOURCE_ID --config config.yaml
```

Run chunk extraction:

```bash
uv run putonghua chunk extract --chunk-id CHUNK_ID --config config.yaml
```

Run review chat and add candidate ideas to the chunk:

```bash
uv run putonghua chunk chat --chunk-id CHUNK_ID --prompt "Suggest one strong sentence card." --config config.yaml
```

List stored suggestions for a conversation:

```bash
uv run putonghua chunk suggestions --conversation-id CONVERSATION_ID --config config.yaml
```

Promote a stored suggestion:

```bash
uv run putonghua chunk promote --suggestion-id SUGGESTION_ID --config config.yaml
```

Open the interactive session explicitly:

```bash
uv run putonghua tui --config config.yaml
```

Start the guided tutorial from inside the TUI:

```text
tutorial
```

Publish a promoted candidate directly:

```bash
uv run putonghua candidate publish --candidate-id CANDIDATE_ID --config config.yaml
```

## Recommended First Run

The recommended first-run path is the interactive tutorial inside the TUI. It
uses real persisted local state, keeps the normal dashboard visible, walks the
operator through each action and decision, and only advances when the
underlying workflow state exists in SQLite.

Start it from the TUI prompt:

```text
tutorial
```

The first slice walks the operator through these real workflow stages:

- select the pending tutorial chunk
- extract candidates for that chunk
- optionally refine in review chat, which adds more candidates to the same chunk
- promote one candidate into the publish queue
- publish that candidate to Anki and persist the returned note id

Useful tutorial commands inside the TUI:

- `tutorial`: start a fresh tutorial from step 1 and clear prior tutorial-only workflow artifacts
- `tutorial resume`: resume the active tutorial session if you intentionally want to continue it
- `tutorial next`: advance the guided intro when the tutorial is teaching layout or workflow basics
- `tutorial status`: show the current checklist and blocking state
- `tutorial reset`: clear tutorial progress and tutorial-only workflow artifacts without removing unrelated project data
- `n`: focus the next pending chunk in the current source

## Tutorial Prerequisites

The tutorial can bootstrap its own local project and source, but live
completion still depends on the same external setup as the normal workflow:

- `OPENAI_API_KEY` available for extraction and review
- Anki Desktop running
- AnkiConnect installed in the active Anki profile
- a valid `anki.deck_name` and `anki.note_type_name` in `config.yaml`

Before claiming the tutorial completes end to end, verify Anki explicitly:

```bash
uv run putonghua anki check --config config.yaml
```

## Tutorial Success And Reset

Tutorial success means all of the following are true:

- the active tutorial checklist shows every step complete
- a local publication record exists for the promoted tutorial candidate
- that publication record includes a non-null Anki note id

Reset clears the active tutorial session plus tutorial-only extracted
candidates, review conversations, suggestions, and local publication records.
It does not remove unrelated learner data. After a reset, `tutorial` starts a
fresh walkthrough from step 1, while `tutorial resume` only continues an
existing active tutorial.

For a live operator walkthrough, use
[docs/work/tutorial-uat-checklist.md](docs/work/tutorial-uat-checklist.md).

## Quality Gate

Run the full supported local quality gate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

If the environment cannot write to the home `uv` cache, prefix commands with
`UV_CACHE_DIR=.uv-cache`.

## Configuration

Start from [config.example.yaml](config.example.yaml).

Local user configuration typically belongs in `config.yaml`, while secrets may
be provided through environment variables such as `OPENAI_API_KEY`.

## Anki Assumptions

`putonghua` treats AnkiConnect as a checked local dependency, not an implicit
guarantee.

Live Anki workflows require:

- Anki Desktop installed
- Anki running
- AnkiConnect installed in the active profile
- localhost access to `http://127.0.0.1:8765`

Verify this explicitly before claiming deck visibility or publish readiness.

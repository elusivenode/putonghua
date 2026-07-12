# Tutorial UAT Checklist

Use this checklist against a real local setup before claiming the guided
tutorial works end to end.

## Prerequisites

- `UV_CACHE_DIR=.uv-cache uv sync --dev` completed
- `config.yaml` exists with working app and Anki settings
- `OPENAI_API_KEY` is available in the environment
- Anki Desktop is running with AnkiConnect enabled

Verify AnkiConnect first:

```bash
UV_CACHE_DIR=.uv-cache uv run putonghua anki check --config config.yaml
```

Expected result:

- the command exits successfully
- the output includes `AnkiConnect OK`
- the configured deck is visible

## Tutorial Walkthrough

1. Start the TUI with `UV_CACHE_DIR=.uv-cache uv run putonghua tui --config config.yaml`.
2. At the prompt, run `tutorial`.
3. Confirm the dashboard shows the `Putonghua Tutorial` workspace and a tutorial panel.
4. Run `n` until the pending tutorial chunk is selected.
5. Run `extract` and wait for persisted candidate rows to appear.
6. Run `chat "Suggest a sentence card."` and confirm a review conversation is shown.
7. Run `promote 1` or promote another intended suggestion index.
8. Run `publish 1` or publish the intended promoted candidate.
9. Run `tutorial status`.

Expected result:

- every tutorial checklist step is marked complete
- the current tutorial status is `completed`
- the publish step reports a local publication record and an Anki note id

## Reset Check

1. From the TUI, run `tutorial reset`.
2. Run `tutorial status`.
3. Run `tutorial` again.

Expected result:

- the reset command reports that tutorial state was cleared
- `tutorial status` reports no active tutorial session immediately after reset
- rerunning `tutorial` creates a fresh active session without deleting the
  existing tutorial workspace

## Failure Notes

Record any blocking details if the walkthrough does not complete:

- extraction or review failed because provider configuration was missing
- publish failed because AnkiConnect, deck selection, or note type settings were wrong
- the tutorial panel advanced incorrectly relative to persisted workflow state

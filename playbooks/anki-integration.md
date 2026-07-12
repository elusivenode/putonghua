# Anki Integration

## Purpose

Guide safe work on the local Anki publishing path.

## Preconditions

- Anki Desktop is installed and running
- AnkiConnect is installed in the active profile
- localhost access to `http://127.0.0.1:8765` is permitted
- the target deck and note type are known or discoverable

## Working Order

1. Verify connectivity with `putonghua anki check`.
2. Discover decks and note types from live Anki rather than guessing.
3. Document the field mapping before automating publish.
4. Implement or extend provider and service logic behind the Anki interface.
5. Use fake providers for default tests.
6. Run a single explicit live publish smoke test only when the local path is ready.

## Required Invariants

- CLI commands remain thin
- business logic stays in services
- adapter logic stays in the Anki provider
- publish attempts produce local publication records
- retries are locally idempotent
- expected connection failures return clear user-facing errors

## Identity And Duplicates

- prefer a stable dedicated note field such as `PutonghuaID`
- if the live note type lacks that field, treat local publication records as
  the minimum first-pass safeguard
- do not rely on Anki duplicate behavior as the only protection

## Validation

Default:

- provider contract tests
- service tests with fake providers
- CLI tests with monkeypatched services

Live:

- `uv run putonghua anki check --config config.yaml`
- optional `uv run putonghua anki note-type --name "NOTE_TYPE" --config config.yaml`
- explicit `uv run putonghua candidate publish ...` smoke test

Live integration is opt-in and should be reported honestly if unavailable.

# First Vertical Slice

## Purpose

Describe the intended order and acceptance line for the core MVP workflow.

## Sequence

1. Create or identify a project boundary.
2. Import one authentic source.
3. Produce candidate cards with provenance.
4. Review candidates interactively.
5. Publish one approved card to Anki.

## Stage Boundaries

### 1. Project And Source Setup

Acceptance:

- one project exists
- one source is persisted with enough metadata to resume later

Deferred:

- bulk ingestion
- collection sync

### 2. Candidate Generation

Acceptance:

- at least one candidate is stored locally
- provenance records source, provider, and prompt context

Validation:

- repository or service tests
- CLI command against a small persisted source or chunk

### 3. Interactive Review

Acceptance:

- the learner can inspect, accept, reject, defer, or promote a candidate or
  suggestion without replaying model output

Validation:

- persisted review state can be listed in a later session

### 4. Anki Publish

Acceptance:

- one learner-approved candidate publishes to the intended note type
- the resulting publication record is stored locally
- retry behavior is auditable and non-destructive

Validation:

- fake-provider tests by default
- one explicit live Anki smoke test when the workflow is ready

## Dependencies

- SQLite migrations are current
- prompts exist as repository assets
- provider interfaces are explicit
- AnkiConnect is reachable for live publish validation

## What To Defer

- whole-deck sync
- semantic duplicate detection
- learner memory expansion
- GUI review flows

## Delivery Rule

Prefer the smallest complete step that advances the sequence. Do not broaden
the slice until the current stage is persisted, testable, and resumable.

# Promotion And Anki Discovery Implementation Plan

## Purpose

This document turns the current sprint handoff into an execution plan that can
be worked through over multiple sessions without losing architectural intent.

It is deliberately more concrete than
`docs/work/completed-promotion-anki-sprint.md`. The sprint handoff explains
what to build. This document explains how to build it in this codebase.

## Current Baseline

The implemented vertical slice today is:

1. import one YouTube URL into a project
2. persist transcript text and transcript segments
3. derive `study_chunks` from transcript segments
4. extract typed `candidate_cards` for one chunk
5. run chunk-scoped review chat and persist conversation messages

The key current modules are:

- `src/putonghua/services/youtube_import.py`
- `src/putonghua/services/study_chunks.py`
- `src/putonghua/services/candidate_extraction.py`
- `src/putonghua/services/chunk_review.py`
- `src/putonghua/database/repositories.py`
- `src/putonghua/cli/app.py`

## Sprint Objective

Extend the existing chunk review slice so a learner can:

1. inspect persisted review suggestions
2. promote a selected suggestion into a durable local candidate
3. inspect the live Anki deck and note model through AnkiConnect
4. define a safe candidate-to-note mapping for the real note type
5. publish one promoted candidate with local provenance and retry safety

## Architectural Decisions

These are the decisions this implementation should treat as fixed unless a
later ADR changes them.

### 1. Persist review suggestions in a dedicated table

Use a new `review_suggestions` table.

Do not persist raw chat suggestions directly into `candidate_cards`.

Reasoning:

- it preserves the boundary that chat suggestions are not yet accepted cards
- it avoids overloading candidate status semantics
- it makes promotion an explicit transition rather than a status rewrite
- it gives stable ids for CLI operations without contaminating candidate lists

### 2. Keep `candidate_cards` as the durable learner-accepted boundary

`candidate_cards` should continue to represent durable local card drafts that
matter beyond a single chat turn.

For this sprint:

- extracted candidates remain in `candidate_cards`
- promoted chat suggestions become `candidate_cards`
- raw review suggestions remain separate

This means there are two candidate sources:

- extraction-generated candidates
- promotion-generated candidates

That distinction belongs in provenance, not in separate tables for accepted
cards.

### 3. Make promotion idempotent by suggestion

Promotion should be idempotent with respect to a stored suggestion.

Rule:

- a suggestion may be promoted at most once into a durable candidate
- repeated promotion of the same suggestion should return the existing promoted
  candidate instead of creating a duplicate

This is the minimum safe rule for resumability.

Optional later duplicate detection across different suggestions can be added
after the sprint.

### 4. Keep publish eligibility explicit

A candidate is publishable only when its status is `promoted` or
`approved_for_publish`.

For the first pass, publishing directly from `promoted` is acceptable if the
learner is still the one invoking the publish command.

If an approval gate becomes necessary later, retain `approved_for_publish` as a
distinct future-facing status.

### 5. Treat live Anki inspection as discovery first, not automation first

The code should inspect the real note type before trying to guess field
mapping.

The implementation order must be:

1. add deck and note-type discovery commands
2. inspect the real target note type
3. document mapping assumptions
4. implement safe publication

## Scope

### In scope

- persisted review suggestions with stable ids
- suggestion listing
- suggestion promotion
- promotion provenance
- Anki deck discovery
- Anki note-type discovery
- one documented candidate-to-note mapping
- one safe publish path for promoted candidates
- repository, service, CLI, and contract tests for the above

### Out of scope

- whole-deck synchronization
- automatic acceptance of all suggestions
- semantic duplicate detection across unrelated candidates
- learner memory
- GUI work

## Data Model Design

### Existing tables used by this sprint

- `candidate_cards`
- `publication_records`
- `review_conversations`
- `review_messages`
- `study_chunks`
- `sources`
- `projects`

### New table: `review_suggestions`

Add a new migration for a `review_suggestions` table with fields equivalent to
the structured suggestion shape already used in `CandidateDraft`.

Recommended columns:

- `id TEXT PRIMARY KEY`
- `conversation_id TEXT NOT NULL`
- `study_chunk_id TEXT NOT NULL`
- `source_message_id TEXT`
- `suggestion_index INTEGER NOT NULL`
- `candidate_type TEXT NOT NULL`
- `simplified TEXT NOT NULL`
- `traditional TEXT NOT NULL`
- `pinyin TEXT NOT NULL`
- `english TEXT NOT NULL`
- `rationale TEXT NOT NULL`
- `source_excerpt TEXT NOT NULL`
- `status TEXT NOT NULL DEFAULT 'suggested'`
- `promoted_candidate_card_id TEXT`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Foreign keys:

- `conversation_id` -> `review_conversations(id)`
- `study_chunk_id` -> `study_chunks(id)`
- `source_message_id` -> `review_messages(id)`
- `promoted_candidate_card_id` -> `candidate_cards(id)`

Constraints and indexes:

- unique `(conversation_id, suggestion_index)`
- index on `study_chunk_id`
- index on `promoted_candidate_card_id`

Status values for `review_suggestions`:

- `suggested`
- `promoted`

This table should store structured review output independently of terminal
display.

### Candidate status model

Retain the existing `candidate_cards.status` column and use the following
meaning for this sprint:

- `proposed`: extraction-created durable candidate not yet learner-promoted for
  publishing
- `promoted`: learner accepted this candidate for the publish path
- `approved_for_publish`: reserved for later optional gate
- `published`: successfully published to Anki

This keeps current extraction behavior intact while allowing chat suggestions to
become first-class durable candidates after promotion.

### Provenance conventions

Every promoted candidate should include provenance that distinguishes its origin
from extraction-created candidates.

Recommended provenance keys for promoted suggestions:

- `origin`: `"review_suggestion"`
- `conversation_id`
- `review_suggestion_id`
- `study_chunk_id`
- `source_message_id`
- `suggestion_index`
- `candidate_type`
- `source_excerpt`
- `rationale`
- `provider`
- `model`
- `prompt_version`

Recommended provenance keys for extracted candidates should remain as-is, but
may later be normalized to include:

- `origin`: `"extraction"`

## Repository Changes

Extend `src/putonghua/database/repositories.py` rather than creating a large
repository abstraction layer.

### Add new dataclasses

Add:

- `ReviewSuggestionCreateRecord`
- `ReviewSuggestionRow`
- `CandidatePromotionResultRow` only if it materially simplifies joins

Add a repository:

- `ReviewSuggestionRepository`

### `ReviewSuggestionRepository` responsibilities

Required methods:

- `replace_for_message(...) -> list[str]`
- `list_for_conversation(conversation_id: str) -> list[ReviewSuggestionRow]`
- `get_suggestion(suggestion_id: str) -> ReviewSuggestionRow | None`
- `get_promoted_candidate_id(suggestion_id: str) -> str | None`
- `mark_promoted(suggestion_id: str, candidate_card_id: str) -> None`

Behavior notes:

- `replace_for_message` should allow one assistant message to be re-parsed into
  structured suggestions without leaving orphan rows for that same message
- if the repository uses append-only semantics instead, that needs explicit
  justification; default to replace-per-message for simplicity

### Candidate repository additions

Add:

- `get_candidate(candidate_id: str) -> CandidateCardRow | None`
- `update_status(candidate_id: str, status: str) -> None`

Optional but useful:

- `list_promoted_candidates(...)`
- `find_existing_by_promotion_source(review_suggestion_id: str) -> CandidateCardRow | None`

The last helper can also be implemented through provenance inspection in
service code, but a repository-level lookup will be cleaner if promoted linkage
is persisted elsewhere.

### Publication repository additions

The current schema already contains `publication_records`, but repository
support is not yet present.

Add minimal methods needed for the first publish slice:

- `get_by_candidate_id(candidate_id: str) -> PublicationRecordRow | None`
- `create_publication_record(...) -> str`
- `mark_publication_succeeded(...) -> None`
- `mark_publication_failed(...) -> None`

Keep this minimal. Do not design a broad publication subsystem yet.

## Service Design

Create small services that align with the current architecture.

### 1. Persist review suggestions during chunk chat

Update `ChunkReviewService.chat_for_chunk`.

Current behavior:

- persists user message
- loads existing context
- calls provider
- persists assistant message
- returns `suggested_cards` in memory

New behavior:

- persist assistant message and capture its message id
- persist structured `review_suggestions` rows for each returned card
- return suggestion ids in the chat result, or at minimum make them listable by
  conversation immediately afterward

Implementation note:

The repository method that inserts assistant messages must return the new
message id. The current `add_message` already returns an id, but the service
does not keep it.

### 2. New promotion service

Add `src/putonghua/services/review_suggestions.py`.

Suggested API:

- `list_review_suggestions(conversation_id: str) -> list[ReviewSuggestionView]`
- `promote_suggestion(suggestion_id: str) -> CandidatePromotionResult`

Optional helper:

- `promote_latest_suggestion(chunk_id: str, ordinal: int) -> CandidatePromotionResult`

The core method is `promote_suggestion`.

Required behavior:

1. load the stored suggestion
2. fail clearly if it does not exist
3. if already promoted, return the existing candidate id
4. load source and project context via the chunk/source relationship
5. create a durable `candidate_cards` row with status `promoted`
6. mark the suggestion as `promoted` and store the linked candidate id
7. return the created or existing candidate id and status

### 3. New Anki discovery service

Add `src/putonghua/services/anki_discovery.py`.

Do not place this logic in the CLI.

Suggested methods:

- `list_decks() -> list[str]`
- `list_note_types() -> list[str]`
- `get_note_type(name: str) -> AnkiNoteTypeDetails`
- `get_sample_note(note_id: int | str) -> AnkiNoteDetails` optional

This service should depend on a provider interface rather than directly on
raw `httpx`.

### 4. New candidate publish service

Add `src/putonghua/services/candidate_publish.py`.

Suggested method:

- `publish_candidate(candidate_id: str) -> PublishResult`

Required behavior for first pass:

1. load candidate
2. ensure candidate status is publishable
3. ensure note model mapping is configured or derivable
4. check if the candidate already has a successful publication record
5. if already published, return the stored note id without duplicating work
6. build Anki fields from the candidate and configured mapping
7. publish via provider
8. persist publication record and candidate status update

The first pass may publish only one note type and one deck target.

## Provider Design

### Anki provider split

The current code only has `anki/connectivity.py`.

For this sprint, add a real provider module for discovery and publishing rather
than extending connectivity checks with ad hoc functions.

Suggested location:

- `src/putonghua/providers/anki_connect.py`

Suggested provider interface:

- `list_decks() -> list[str]`
- `list_note_types() -> list[str]`
- `get_note_type(name: str) -> AnkiNoteTypeDetails`
- `add_note(request: PublishNoteRequest) -> PublishNoteResult`

Optional helper methods if supported by AnkiConnect:

- `find_notes(...)`
- `notes_info(...)`

`anki/connectivity.py` can remain as the lightweight reachability check layer,
or its logic can be consolidated behind the provider later. Do not force that
cleanup during this sprint unless it reduces duplication materially.

### AnkiConnect actions expected

Plan around the following AnkiConnect capabilities:

- `deckNames`
- `modelNames`
- `modelNamesAndIds` optional
- `modelFieldNames`
- `modelFieldsOnTemplates` if available
- `modelTemplates` if available
- `addNote`
- `findNotes` optional
- `notesInfo` optional

The exact action surface should be verified against the local AnkiConnect
instance during implementation.

## CLI Plan

Keep CLI changes thin and use services.

### New chunk commands

Add:

- `putonghua chunk suggestions --conversation-id CONVERSATION_ID`
- `putonghua chunk promote --suggestion-id SUGGESTION_ID`

Optional later:

- `putonghua chunk promote-latest --chunk-id CHUNK_ID --index N`

CLI output expectations:

- `chunk suggestions` should print stable ids, suggestion order, candidate type,
  core fields, and status
- `chunk promote` should print suggestion id, candidate id, and resulting status

### New anki commands

Add:

- `putonghua anki decks`
- `putonghua anki note-types`
- `putonghua anki note-type --name "NOTE_TYPE_NAME"`

Optional:

- `putonghua anki sample-note --id NOTE_ID`

### New candidate command group

Add a top-level `candidate` command group.

First command:

- `putonghua candidate publish --candidate-id CANDIDATE_ID`

This is preferable to forcing publication under `chunk`, because publication is
about a durable candidate, not an active chat or chunk operation.

## Configuration Plan

The current settings already include Anki connectivity basics. Add only the
minimum extra config needed for publish mapping.

Suggested additions under `anki`:

- `default_deck: str | None = None`
- `default_note_type: str | None = None`
- `publish_tags: list[str] = []`

Suggested additions under `app` or a dedicated publish section only if needed:

- note field mapping configuration for the first note type

Keep the first pass simple. One workable option is:

- do live discovery first
- then encode the chosen field mapping in config

Do not hardcode the real note type name in service code.

## Publish Mapping Plan

This is the part that most depends on your real Anki setup.

### Discovery output to capture

Before implementing `publish_candidate`, gather:

- target deck name
- target note type name
- ordered field names
- template names
- fields that drive duplicate detection
- whether tags are required or merely useful
- whether audio fields are mandatory, optional, or irrelevant for first pass

### First-pass mapping rule

Aim for one concrete mapping for the existing three-card note type.

The mapping document should answer:

- how a `word` candidate maps
- how a `phrase` candidate maps
- how a `sentence` candidate maps
- which candidate fields are mandatory for each
- which defaults or blank fields are acceptable

### Failure mode expectations

If the publish path cannot construct a valid note because the note type requires
additional fields not yet modeled, the service should fail with a precise
mapping error rather than a vague Anki API error.

## Delivery Phases

This work is best executed in ordered phases. Each phase should leave the repo
in a valid, testable state.

### Phase 1. Persist structured review suggestions

Deliverables:

- migration for `review_suggestions`
- repository support
- `ChunkReviewService` persists suggestions after assistant replies
- tests for repository and service persistence

Acceptance:

- after `chunk chat`, suggestions exist in SQLite with stable ids and can be
  listed by conversation id

### Phase 2. Add promotion workflow

Deliverables:

- promotion service
- `chunk suggestions` command
- `chunk promote` command
- idempotent promotion semantics
- tests for listing and promotion

Acceptance:

- a learner can promote a stored suggestion into a durable candidate without
  rerunning the LLM

### Phase 3. Add Anki discovery

Deliverables:

- Anki provider for discovery
- discovery service
- `anki decks`
- `anki note-types`
- `anki note-type`
- contract tests using fake responses

Acceptance:

- the live target note type can be described from AnkiConnect rather than
  guessed

### Phase 4. Document candidate-to-note mapping

Deliverables:

- one repo document that records the real field mapping for the chosen note
  type
- updated implementation assumptions based on live discovery

Acceptance:

- mapping is explicit enough to code against without guessing

### Phase 5. Add safe publish path

Deliverables:

- publication repository support
- publish service
- `candidate publish`
- candidate status update on success
- publication record persistence
- tests for idempotent publish behavior

Acceptance:

- one promoted candidate can be published once, retried safely, and traced
  locally

## Testing Plan

All meaningful behavior should be covered.

### Migration and repository tests

Add tests for:

- migration creates `review_suggestions`
- `ReviewSuggestionRepository` insert/list/get/mark-promoted behavior
- publication repository behavior

### Service tests

Add tests for:

- `ChunkReviewService.chat_for_chunk` persists suggestions
- `ReviewSuggestionService.promote_suggestion` creates candidate and marks
  suggestion promoted
- promotion is idempotent
- `AnkiDiscoveryService` returns normalized note-type details via a fake provider
- `CandidatePublishService.publish_candidate` records publication success
- publishing an already-published candidate does not create a duplicate record

### CLI tests

Add tests for:

- `chunk suggestions`
- `chunk promote`
- `anki decks`
- `anki note-types`
- `anki note-type`
- `candidate publish`

### Live validation

Only after the local Anki environment is confirmed reachable:

1. run `putonghua anki check`
2. inspect decks and note types
3. inspect the real target note type
4. promote one real suggestion
5. attempt one safe publish with a test tag

Do not claim deck visibility or publish readiness unless this check is actually
run successfully.

## Session Checkpoints

Because this work will likely span multiple sessions, use these checkpoints.

### Checkpoint A

Complete when:

- migration exists
- suggestions persist
- tests pass

Suggested commit scope:

- database migration
- repository additions
- chunk review persistence changes
- tests

### Checkpoint B

Complete when:

- suggestions can be listed
- promotion works
- promotion is idempotent
- tests pass

Suggested commit scope:

- promotion service
- CLI commands
- tests

### Checkpoint C

Complete when:

- live Anki discovery commands work against fakes
- note type can be inspected on the real machine
- mapping assumptions are documented

Suggested commit scope:

- provider
- discovery service
- CLI commands
- mapping doc
- tests

### Checkpoint D

Complete when:

- one promoted candidate can be published safely
- publication records are persisted
- retry behavior is defined
- tests pass

Suggested commit scope:

- publication service
- candidate CLI
- repository additions
- tests

## Risks And Mitigations

### Risk: AnkiConnect model inspection is less rich than expected

Mitigation:

- build discovery around the smallest reliable action set first
- use optional helper commands only if the local AnkiConnect version supports
  them

### Risk: the note type requires fields not represented in candidates

Mitigation:

- fail with a mapping error
- document the missing fields
- keep the first publish path narrow rather than inventing placeholder data

### Risk: duplicate semantics become confusing across extracted and promoted cards

Mitigation:

- keep raw suggestions separate
- make promotion idempotent by suggestion id for this sprint
- defer semantic cross-candidate deduplication

### Risk: too much work lands in the CLI

Mitigation:

- keep all state transitions in services
- keep provider-specific logic outside CLI commands

## Definition Of Done

This sprint is done when all of the following are true:

1. chat suggestions are persisted with stable ids
2. stored suggestions can be listed later by conversation
3. one suggestion can be promoted idempotently into a durable candidate
4. live Anki deck and note-type discovery commands exist
5. the target note type mapping is documented from real inspection
6. one promoted candidate can be published or fail with a precise mapping error
7. publication attempts are recorded locally
8. `ruff format --check`, `ruff check`, `pyright`, and `pytest` pass

## Recommended First Session

Start with Phase 1 only.

Concrete first-session tasks:

1. add migration for `review_suggestions`
2. extend repositories with `ReviewSuggestionRepository`
3. update `ChunkReviewService` to persist assistant suggestions
4. add repository and service tests
5. run full checks

That is the best first slice because it resolves the main data model decision
and unlocks all later work without committing prematurely to Anki publishing
details.

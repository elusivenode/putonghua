# Completed Sprint: Promotion And Anki Publishing Discovery

## Goal

Add the workflow transition from flexible chunk chat suggestions into durable
candidate cards, then begin the Anki publishing discovery needed to automate
your existing note template safely.

This sprint starts after the chunk chat and mixed-card extraction slice is
complete:

1. transcript segments become `study_chunks`
2. extraction produces typed candidates
3. chunk chat suggests words, phrases, and sentences
4. learner promotes selected suggestions into durable local cards
5. promoted cards move toward publish-ready Anki notes

## Why This Sprint

The current review-model slice is useful, but it stops at suggestion time.

What is missing now:

- chat suggestions are not yet first-class promotable objects
- there is no explicit workflow state between “suggested” and “published”
- Anki note-model behavior is not yet inspected or mapped
- your note template creates three cards per note, which must be understood
  before we automate publishing

The next step is therefore controlled promotion plus Anki note-model
discovery, not broader extraction or memory work.

## Current Baseline

## Implementation Status

Completed work:

- persistent `review_suggestions` storage linked to review conversations
- CLI suggestion listing and one-at-a-time promotion into durable
  `candidate_cards`
- idempotent promotion provenance from review suggestion to candidate card
- Anki discovery commands for deck listing, note-type listing, and note-type
  inspection
- repo mapping document for the live `Mandarin` / `Mandarin vocab` publish
  target
- safe `candidate publish` path using local publication records and retry-safe
  idempotency
- config support for default publish deck, note type, and publish tags
- one live publish smoke test against the real local deck

Implemented and verified already:

- `putonghua youtube import`
- OpenAI transcription fallback
- `putonghua chunk build`
- `putonghua chunk next`
- `putonghua chunk show`
- `putonghua chunk update`
- `putonghua chunk extract`
- `putonghua chunk candidates`
- `putonghua chunk chat`

Implemented persistence:

- `candidate_cards` include `study_chunk_id`
- `candidate_cards` include `candidate_type`
- review conversations and messages are stored locally
- extraction and review prompts are versioned prompt assets

Verified external slice:

- a persisted chunk from `https://youtu.be/lR5Rt6293bg` was extracted with typed
  `word` and `phrase` candidates
- a real OpenAI-backed `chunk chat` call succeeded
- conversation `f799c083-35c5-41a6-9ba9-3d0e5e842729` was stored locally
- a fresh review conversation `2c3463cf-e3af-49ab-9d9d-3c0ef7777d26` persisted
  a structured sentence suggestion
- suggestion `f312f67b-9b6d-4662-b932-b791c7a0fb6e` was promoted to candidate
  `51b58902-0e85-4ede-a84d-face2f0ad17e`
- candidate `51b58902-0e85-4ede-a84d-face2f0ad17e` was published to Anki note
  `1783832060343` with local publication record
  `9451e262-328a-47cd-bd82-f62f5afbd242`

## Sprint Outcome

By the end of this sprint, a learner should be able to:

1. review chunk chat suggestions
2. promote one or more accepted suggestions into durable candidate cards
3. inspect the target Anki deck and note model through AnkiConnect
4. validate what fields and templates are required for publishing
5. perform one safe test publication into the real note type

## Workstreams

### 1. Add Promotion Model And Status Flow

Add an explicit workflow step between conversational suggestion and publishing.

Suggested status model:

- `proposed`
- `promoted`
- `approved_for_publish`
- `published`
- optional later: `rejected`

Requirements:

- promotion must create or update durable `candidate_cards`
- promotion must preserve source chunk, conversation, and rationale provenance
- promotion should not require rerunning the LLM

Acceptance:

- a learner can choose a prior chat suggestion and persist it as a promotable
  local candidate

### 2. Persist Chat Suggestions For Promotion

The system needs stable references for chat output so the learner can say
"promote suggestion 3" or equivalent.

Two acceptable approaches:

- add a `review_suggestions` table linked to `review_messages`
- or persist structured chat suggestions directly into `candidate_cards` with a
  distinct status and provenance shape

Design constraints:

- suggestions must be resumable across sessions
- suggestions must be tied to `study_chunk_id`
- provenance must include conversation id and message context

Acceptance:

- a later CLI command can reference stored suggestions without relying on
  transient terminal output

### 3. Add Promotion Service

Create a service that turns stored review suggestions into durable candidate
cards.

Suggested first methods:

- `list_review_suggestions(conversation_id: str) -> list[SuggestionView]`
- `promote_suggestion(suggestion_id: str) -> CandidatePromotionResult`
- `promote_latest_suggestion(chunk_id: str, ordinal: int) -> CandidatePromotionResult`

The service should:

- load the selected suggestion
- prevent duplicate promotion where reasonable
- persist or update the candidate card
- record promotion provenance

Acceptance:

- promoted cards can be listed separately from raw suggestions

### 4. Add CLI Surface For Promotion

Suggested commands:

- `putonghua chunk suggestions --conversation-id CONVERSATION_ID`
- `putonghua chunk promote --suggestion-id SUGGESTION_ID`
- optional helper: `putonghua chunk promote-latest --chunk-id CHUNK_ID --index N`

First-pass CLI behavior:

- show available suggestions with stable ids
- allow promotion of one suggestion at a time
- print the resulting candidate id and status

Acceptance:

- the learner can accept a suggestion without manual SQL or prompt replay

### 5. Add Anki Discovery Commands

Do not guess the note-model mapping. Inspect the live Anki model first.

Suggested commands:

- `putonghua anki decks`
- `putonghua anki note-types`
- `putonghua anki note-type --name "NOTE_TYPE_NAME"`
- optional helper: `putonghua anki sample-note --id NOTE_ID`

The discovery pass should capture:

- available deck names
- target note model name
- field names and order
- card template names
- any required media or tags assumptions

Acceptance:

- we can describe the target note model from live Anki data, not guesswork

### 6. Design Publish Mapping For Your Template

Your Anki template creates three cards from one input note. We need to
understand that mapping before automation.

Discovery questions to answer in code and docs:

- which note fields are mandatory
- which fields are optional
- how words, phrases, and sentences should map into the same note model
- whether there are field conventions for audio, tags, or source metadata
- what duplicate behavior Anki applies for this note type

Acceptance:

- one documented candidate-to-note mapping exists for your template

### 7. Add One Safe Test Publish Path

After discovery, add one controlled publishing path for a promoted candidate.

Constraints:

- only publish promoted or publish-ready cards
- record the resulting Anki note id
- avoid duplicate creation on retry
- prefer a dedicated test tag during the first pass

Suggested first method:

- `publish_candidate(candidate_id: str) -> PublishResult`

Acceptance:

- one promoted candidate can be published into the real note model and traced
  locally

## Proposed Delivery Order

1. choose persistence shape for stored chat suggestions
2. add promotion-related migrations and repository updates
3. add promotion service
4. add `chunk suggestions` and `chunk promote` CLI commands
5. add Anki discovery commands
6. inspect the real note model and document the mapping
7. add one safe publish path for promoted candidates
8. add tests and one live Anki-backed validation

## Acceptance Test For The Sprint

Use a real persisted chunk and verify this sequence:

1. `uv run putonghua chunk chat --chunk-id CHUNK_ID --prompt "Suggest one strong sentence card." --config config.yaml`
2. `uv run putonghua chunk suggestions --conversation-id CONVERSATION_ID --config config.yaml`
3. `uv run putonghua chunk promote --suggestion-id SUGGESTION_ID --config config.yaml`
4. `uv run putonghua anki note-type --name "YOUR_NOTE_TYPE" --config config.yaml`
5. `uv run putonghua candidate publish --candidate-id CANDIDATE_ID --config config.yaml`

Expected result:

- chat suggestions are stored and re-listable
- one suggestion is promoted into a durable candidate card
- the target Anki note type is described from live Anki data
- one safe publish attempt succeeds or fails with a precise model-mapping error

## Data Model Notes

Keep these boundaries explicit:

- chat suggestions are not yet approved candidate cards
- promotion is the learner’s acceptance action
- promoted candidates are the publishing boundary
- review conversations remain chunk-scoped
- Anki publication records must remain idempotent and auditable

## Non-Goals For This Sprint

- whole-deck synchronization
- automatic approval of all chat suggestions
- learner long-term memory
- Postgres migration
- GUI review flows

## Done Definition

Do not call the sprint complete until all of these are true:

- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest`
- at least one suggestion was promoted without rerunning the LLM
- at least one live Anki model inspection succeeded
- if publish was attempted, the result was recorded locally

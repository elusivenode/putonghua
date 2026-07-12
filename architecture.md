# Putonghua Architecture

## Goals

This project is a local-first, AI-assisted Mandarin learning companion for
creating Mandarin Chinese Anki flashcards from authentic content. It is not a
one-shot generator. The system should reduce repetitive work while preserving
human review, provenance, and the ability to resume work safely at each stage.

The first milestone remains a minimal end-to-end slice:

1. Import a text file.
2. Generate candidate cards with an LLM.
3. Review candidates interactively.
4. Publish an approved card to Anki through AnkiConnect.

Everything else should be designed to extend from that slice without forcing
rewrites.

## Architectural Priorities

1. Keep business logic outside the CLI layer.
2. Make `Project` the primary workspace boundary.
3. Use SQLite as the local source of truth.
4. Isolate external systems behind provider interfaces.
5. Make every workflow stage resumable and idempotent where practical.
6. Preserve provenance for every candidate and published card.
7. Make learner context reusable across prompts without coupling to one AI
   provider.
8. Prefer simple modules and pure functions over deep class hierarchies.

## High-Level Design

The application is organized as a thin CLI over explicit services and
repositories, with `Project` as the top-level unit of work.

- `cli/` parses commands, validates input, and orchestrates services.
- `services/` contains workflow logic for import, extraction, review, media,
  and publishing.
- `providers/` defines interfaces and concrete adapters for LLMs,
  transcription, speech, and Anki.
- `database/` owns schema, queries, and transaction boundaries.
- `models/` defines Pydantic domain models and DTOs shared across layers.

The key rule is that workflow logic depends on interfaces, not on specific
providers. Swapping from one LLM or speech engine to another should not affect
the review or publishing flows.

Domain models, persistence records, command models, and provider DTOs may be
separate when their responsibilities differ. Do not create unnecessary model
variants until the distinction is required by real behavior.

Anki integration is a local external dependency. The system must verify that
AnkiConnect is reachable before claiming deck visibility or publish readiness.

## Workflow Model

Each project contains one or more sources, and each source progresses through
explicit stages:

1. `imported`
2. `transcribed`
3. `candidates_extracted`
4. `reviewed`
5. `audio_generated`
6. `published`

The database records project state, outputs, and status transitions for every
stage. A command should be able to resume from persisted state instead of
recomputing work blindly.

Example:

- Re-running extraction on an unchanged source should either no-op or create a
  new extraction run with clear lineage.
- Re-running publish should not duplicate Anki notes if the candidate was
  already published successfully.

## Core Domain Concepts

- `Project`: primary workspace containing sources, transcripts, candidate
  cards, generated media, review history, publication history, and notes.
- `Source`: imported text or audio asset and its metadata, scoped to a
  project.
- `TranscriptSegment`: timestamped transcript chunk derived from an audio
  source.
- `StudyChunk`: a smaller transcript-derived unit used for extraction,
  scoring, and review instead of full-episode text.
- `CandidateCard`: AI-suggested flashcard draft with provenance.
- `CandidateScore`: advisory learning-value assessment attached to a candidate.
- `ReviewDecision`: accept, reject, edit, or defer decision on a candidate.
- `GeneratedMedia`: synthesized pronunciation or other generated assets.
- `PublicationRecord`: link between a local candidate and the corresponding
  Anki note/media state.
- `LearnerProfile`: persistent preferences and learner-level guidance shared
  across projects.
- `MemoryFact`: durable AI memory item such as known vocabulary, weak grammar,
  or preferred explanation style.
- `ReviewConversation`: question-and-answer history attached to a candidate
  during review.
- `RunMetadata`: provider, prompt version, timestamps, and hashes used to make
  operations auditable and reproducible.

## Repository Shape

```text
putonghua/
├── README.md
├── PRODUCT.md
├── AGENTS.md
├── architecture.md
├── pyproject.toml
├── .env.example
├── config.example.yaml
├── docs/
│   └── adr/
│       ├── README.md
│       └── 0001-ordered-sqlite-migrations.md
├── src/
│   └── putonghua/
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── loader.py
│       │   └── settings.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── connection.py
│       │   ├── migrations.py
│       │   └── migrations/
│       │       └── 001_initial.sql
│       └── logging.py
├── tests/
│   ├── test_cli.py
│   ├── test_config.py
│   └── test_migrations.py
└── .github/
    └── workflows/
        └── ci.yml
```

## Layer Responsibilities

### CLI

The CLI should do only four things:

1. Parse arguments.
2. Load configuration and construct dependencies.
3. Invoke services.
4. Render human-friendly output.

It should not contain workflow state transitions, SQL, prompt construction, or
provider-specific HTTP logic.

### Config

Configuration should come from YAML plus environment variables for secrets.

Suggested config areas:

- database path
- data directories
- default deck and note model
- provider selection
- provider credentials or endpoint names
- learner profile defaults
- review defaults
- logging configuration

Settings should be parsed once into typed models and injected downward.

### Database

SQLite is the local system of record. Use straightforward SQL or a small
repository layer rather than a heavy ORM. This keeps schema control clear and
reduces hidden behavior.

SQLite schema changes must use ordered migrations rather than repeatedly
editing only an initial schema definition.

The initial physical schema should remain smaller than the full long-term
domain model. Defer tables for transcripts, generated media, review
conversations, and AI memory until those features begin.

Suggested initial tables:

- `schema_migrations`
- `projects`
- `sources`
- `candidate_cards`
- `candidate_scores`
- `review_decisions`
- `publication_records`
- `learner_profiles`
- `workflow_runs`

Recommended persistence patterns:

- store stable UUIDs for local entities
- store content hashes for deduplication and idempotency
- store provider metadata and prompt versions
- store project-scoped notes and learner-scoped memory separately
- use append-only history where losing prior state would be harmful

### Models

Pydantic models should represent validated inputs and outputs where that adds
clarity. Keep domain models explicit instead of passing unstructured dicts
across the codebase, but avoid speculative class proliferation.

### Services

Services coordinate repositories and providers.

Examples:

- `ImportService` ingests a file, fingerprints it, copies or references it,
  and records the source within a project.
- `CandidateService` builds extraction input, invokes an `LLMProvider`,
  validates candidates, incorporates learner context, and stores provenance.
- `ScoringService` computes or requests learning-value scores for each
  candidate.
- `ReviewService` presents pending candidates and records user decisions.
- `ReviewAssistantService` answers user questions about a candidate during
  review without owning the review decision itself.
- `PublishService` converts approved candidates into Anki note payloads,
  handles duplicate checks, and persists publication results.

### Providers

Providers define contracts first, implementations second.

Suggested interfaces:

```python
class LLMProvider(Protocol):
    def extract_candidates(self, request: CandidateExtractionRequest) -> CandidateExtractionResult: ...
    def score_candidates(self, request: CandidateScoringRequest) -> CandidateScoringResult: ...
    def answer_review_question(self, request: ReviewAssistantRequest) -> ReviewAssistantResult: ...

class TranscriptionProvider(Protocol):
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult: ...

class SpeechProvider(Protocol):
    def synthesize(self, request: SpeechRequest) -> SpeechResult: ...

class AnkiProvider(Protocol):
    def find_duplicate(self, request: DuplicateCheckRequest) -> DuplicateCheckResult: ...
    def publish_note(self, request: PublishNoteRequest) -> PublishNoteResult: ...
```

Concrete providers should translate between those domain contracts and the
actual HTTP APIs or local engines.

For Anki specifically, production code should assume only that a local
AnkiConnect endpoint may be available. Availability must be probed at runtime
because installed add-ons, running-process state, and local permission models
can all prevent access even on the same machine.

Provider-facing tests should default to fakes or narrow adapter contract tests.
Live integration tests should be explicit and opt-in rather than part of the
default quality gate.

## Project-Centric Workspace Model

`Project` is the main boundary for workflow state and user intent. A project
represents one authentic content unit or study collection such as a podcast
episode, lesson, or story set.

A project owns conceptually:

- sources
- candidate cards
- candidate scores
- review history
- publication history

The initial schema does not need to materialize every long-term concept on day
one.

This avoids scattering related artifacts across unrelated imports and creates a
natural workspace for iterative review over time.

## Study Chunks

Podcast-sized sources are often too large to be good extraction units. The
system should derive `StudyChunk` records from transcript segments and run
downstream AI work on those chunks instead of the entire source transcript.

This serves two goals:

- better pedagogical granularity for flashcard review
- lower downstream OpenAI usage by avoiding whole-episode extraction prompts

`StudyChunk` should also be the primary human work queue for long-form audio.
Statuses such as `pending`, `in_review`, `completed`, and `skipped` allow the
learner to progress iteratively through an episode rather than treating the
whole source as one review unit.

## Learner Profile

The learner profile is persistent and shared across projects. It should be
available to prompt-building code as structured data rather than manually
inlined strings.

Suggested profile fields:

- language
- proficiency estimate
- learning goals
- preferred card styles
- preferred explanation style
- preferred voices
- topics of interest
- card generation preferences

The initial implementation can support one local learner profile. The schema
should not prevent future support for multiple profiles.

## AI Memory Layer

The memory layer captures durable learning context that improves future card
generation and review assistance.

Examples:

- vocabulary already learned
- grammar patterns already covered
- weak concepts
- recently introduced concepts
- preferred explanation style

Design constraints:

- memory must be provider-agnostic
- memory should be queryable by services, not hidden inside prompts
- memory updates should be explicit and auditable
- memory retrieval can begin as simple rule-based selection before adding more
  advanced ranking

Design the interfaces so memory can be introduced cleanly later, but defer its
persistence tables and service implementation until memory work actually
begins.

## Data and Provenance Strategy

Every candidate card should retain:

- project reference
- source reference
- exact source span or transcript segment references
- extraction timestamp
- provider identifier
- model identifier
- prompt or template version
- raw provider response when useful for debugging
- normalized candidate fields used for review and publishing
- learner profile snapshot or version reference
- memory items used for generation
- candidate score inputs and outputs

This matters because user trust depends on being able to inspect where a card
came from and how it was produced.

## Candidate Scoring

Every generated candidate should include an advisory learning-value score.
This score informs review but must never bypass it.

Suggested scoring dimensions:

- frequency
- novelty
- reuse potential
- grammar importance
- spoken usefulness
- overlap with existing deck

The score can initially be a simple structured LLM output or deterministic
heuristic blend. The important constraint is that the score is transparent,
persisted, and separate from the review decision.

Candidate extraction and candidate scoring are separate domain
responsibilities, even if the first provider returns both in one structured
LLM response.

## Prompt Assets and Versioning

Prompts should be treated as first-class repository assets, not embedded in
service code. Each prompt file should have a stable identifier and versioning
story because prompt choice is part of flashcard provenance.

Initial prompt set:

- `candidate_extraction.md`
- `candidate_scoring.md`
- `grammar_explanation.md`
- `translation.md`
- `duplicate_review.md`
- `review_assistant.md`

At minimum, provenance should capture:

- prompt asset name
- prompt file hash or version
- provider/model used with that prompt

Structured AI output should be validated before it is persisted or used for
state transitions. Malformed model output should fail clearly, preserve prior
state, and be testable with deterministic fake providers.

## Publication Idempotency

Anki publication idempotency must rely on a stable local identifier stored in a
dedicated Anki field such as `PutonghuaID`. This identifier is separate from
surface fields like expression or gloss, which are not reliable uniqueness
keys over time.

## Duplicate Detection Strategy

Duplicate checks should happen in two places:

1. Local duplicate detection before publish.
2. Anki duplicate detection at publish time.

Local duplicate heuristics can be based on normalized simplified Chinese,
traditional Chinese, pinyin, and English gloss fields depending on the final
note model. The exact matching rule should be configurable, because strictness
depends on the learner’s deck design.

## Review Experience

The review step is the core value of the product. For the MVP, use a terminal
review workflow with Rich rendering and explicit actions:

- accept
- reject
- edit
- defer
- open provenance
- ask assistant

The first version should optimize clarity, not speed. Fast keyboard-driven
review can come after the core decision model is stable.

## AI Review Assistant

The review assistant should be designed as a conversational capability embedded
within review, not as a separate workflow that owns card generation.

Example user questions:

- Why is this natural?
- Explain this grammar.
- Give another example.
- Compare this with another expression.
- Should I learn this now?

The MVP can provide only a minimal implementation, but the interfaces should
anticipate:

- candidate context injection
- project context injection
- learner profile and memory injection
- persisted review conversation history
- provider-agnostic question answering

## Error Handling and Resumability

Each workflow stage should persist enough metadata to answer:

- what has already succeeded
- what failed
- whether retry is safe
- whether the underlying input changed

Recommended approach:

- represent stage runs explicitly
- write status and error details on failure
- avoid partial publish states by persisting request/response boundaries
- prefer retryable operations with stable identifiers

## Dependency Rationale

- `Typer`: clean CLI structure with minimal ceremony and strong typing.
- `Rich`: readable review UI and diagnostics in a terminal-first workflow.
- `Pydantic`: typed config and validated domain models.
- `SQLite`: durable local state with no infrastructure burden.
- `httpx`: consistent client for AnkiConnect and HTTP-based providers.
- `pytest`: direct, maintainable test suite.
- `PyYAML` or `ruamel.yaml`: human-editable local configuration.
- `structlog`: structured logs for debugging multi-stage workflows.
- `Ruff`: linting and import hygiene with low configuration overhead.
- `Black`: predictable formatting that removes style debates.
- `uv`: fast local environment and dependency management.

Not recommended for the MVP:

- ORMs
- background job systems
- plugin frameworks
- event buses
- GUI toolkits

They add complexity before the workflow shape is proven.

## Testing Strategy

Testing should focus on service behavior and provider boundaries.

Priority test categories:

1. Domain model validation tests.
2. Repository tests against a temporary SQLite database.
3. Service tests using fake providers.
4. CLI smoke tests for command wiring.
5. Contract tests for provider adapters where external payload shaping is easy
   to break.

Every public service function should be testable without network access.

## Initial Command Surface

Suggested first commands:

```text
putonghua init
putonghua db migrate
putonghua version
```

Possible later commands:

```text
Later workflow commands can be added for project creation, import, extraction,
review, and publishing once the vertical slice implementation starts.
```

## MVP Implementation Roadmap

### Phase 1: Repository and Tooling

1. Create `pyproject.toml` with runtime and dev dependencies.
2. Set up the `src/` layout, test layout, and package entry point.
3. Configure Ruff, Black, and pytest.
4. Add typed settings loading and structured logging bootstrap.
5. Add prompt asset loading conventions and version-hash utilities when prompt
   work begins.

### Phase 2: Product Core and Persistence

1. Define only the initial models needed for the first vertical slice:
   `Project`, `LearnerProfile`, `Source`, `CandidateCard`, `CandidateScore`,
   `ReviewDecision`, and `PublicationRecord`.
2. Implement SQLite connection management and ordered migrations.
3. Add repositories for projects, learner profile, sources, candidates,
   reviews, and publications.
4. Add tests for schema and repository behavior.

### Phase 3: First Vertical Slice

1. Implement project creation and text import with hashing and persistence.
2. Implement persistent learner profile loading.
3. Define `LLMProvider` interface and one concrete implementation.
4. Implement candidate extraction service with learner profile and prompt
   provenance.
5. Implement advisory candidate scoring.
6. Build a simple terminal review loop with accept/reject/defer and score
   display.
7. Implement AnkiConnect publishing for one approved card.
8. Add duplicate detection before publish.
9. Add end-to-end tests with fake providers where possible.

### Phase 4: Workflow Hardening

1. Add workflow run tracking and resumability rules.
2. Improve edit support during review.
3. Add minimal AI memory persistence and retrieval.
4. Add minimal review assistant question-answer flow.
5. Persist raw provider responses for debugging.
6. Add better status commands and failure inspection.

### Phase 5: Audio and Transcription

1. Add audio source import.
2. Add transcription provider abstraction and transcript storage.
3. Add Mandarin audio generation and media tracking.
4. Extend publish flow to include generated audio assets.

## Recommended MVP Constraints

To keep the first slice small and defensible:

- support one note model only
- support one deck by default
- support one LLM provider initially
- support one learner profile initially
- skip batch publish until single-note publish is robust
- use synchronous commands first
- defer advanced editing UX until acceptance flow is stable
- keep AI memory retrieval simple and explicit at first
- keep the review assistant minimal until the core review loop proves useful

## Risks and Design Watchpoints

- Over-modeling too early can slow iteration; start with a small schema.
- Prompt and output drift from providers will break extraction unless response
  validation is strict.
- AI memory can become vague and low-value if items are not strongly typed or
  curated.
- Duplicate detection rules can become user-specific quickly; keep them
  configurable.
- Review UX determines product usefulness more than model quality.
- Publishing logic needs careful idempotency to avoid dirty deck state.
- Candidate scoring is useful only if the reasons are visible to the learner.

## Recommended Next Step

Complete the repository/tooling setup first, including quality gates and the
ordered migration foundation. Then begin the first vertical slice with project
creation, text import, candidate extraction, scoring, review, and
single-card publish.

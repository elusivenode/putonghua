# PRODUCT

## Mission

`putonghua` helps a serious Mandarin learner turn authentic content into
exceptional Anki flashcards with AI assistance that improves judgment rather
than replacing it.

## Target User

The primary user is a single advanced or highly committed Mandarin learner who:

- studies from authentic native material
- cares about nuance, naturalness, and provenance
- wants better flashcards, not just more flashcards
- is comfortable running a local, terminal-first tool

## Guiding Principles

- The human remains in control.
- AI suggests. The learner decides.
- Optimise for learning quality over automation.
- Preserve provenance for every flashcard.
- No data should be lost.
- Local state must be resumable and auditable.
- Prefer clarity and maintainability over cleverness.

## Definition Of A Great Flashcard

A great flashcard is:

- grounded in real Mandarin usage
- worth learning now
- clear about meaning and context
- scoped to one useful learning point
- natural enough to avoid teaching bad habits
- supported by provenance and explanation when needed
- easy to review in Anki without unnecessary noise

## Product Shape

`putonghua` is not just a CLI utility. It is a local AI-assisted learning
workspace centered on projects.

Each project represents a coherent unit of study such as:

- a podcast episode
- a lesson
- a story collection
- a reading session

A project owns:

- sources
- transcripts
- candidate cards
- scores
- generated audio
- review history
- publication history
- notes

## Long-Term Vision

Over time, `putonghua` should become a durable Mandarin learning companion
that:

- understands the learner’s evolving level and goals
- remembers what has already been learned or struggled with
- helps choose better cards from authentic material
- explains grammar and usage during review
- improves consistency and quality of deck building over years of study

## Non-Goals

- full automation of flashcard creation without review
- a consumer multi-user SaaS product
- a mobile app
- a GUI-first experience in the near term
- replacing Anki as the spaced repetition system
- optimizing for bulk quantity over learning value

## MVP Focus

The MVP should deliver one small but complete vertical slice:

1. Create a project.
2. Import a text source into that project.
3. Generate candidate cards with provenance.
4. Score them for learning value.
5. Review them interactively.
6. Publish an approved card to Anki.

The MVP may include hooks for learner profile, AI memory, and review assistant
capabilities, but those hooks should not distract from shipping the core path.

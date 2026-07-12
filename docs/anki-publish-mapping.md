# Anki Publish Mapping

This document records the first-pass publish mapping for the live local Anki
setup inspected on July 12, 2026.

## Live Discovery Snapshot

Confirmed through live AnkiConnect inspection:

- deck: `Mandarin`
- note type: `Mandarin vocab`
- note type fields, in order:
  - `Hanzi`
  - `Pinyin`
  - `English`
  - `Audio`
- card templates:
  - `Card 1`
  - `Card 2`
  - `Card 3`

Also inspected but not selected:

- note type `Mandarin Vocab-b6c15`
- fields: `Front`, `Back`
- templates: `Card 1`

This confirms that `Mandarin vocab` is the current three-card target note type
for the first publish path.

## Candidate To Note Mapping

The first publish path should support the existing candidate types without
changing the target note type.

Field mapping:

- `Hanzi` <- candidate `simplified`
- `Pinyin` <- candidate `pinyin`
- `English` <- candidate `english`
- `Audio` <- blank for the first pass

The current candidate model has both `simplified` and `traditional`. The live
target note type only exposes one Hanzi field, so first-pass publishing should
store `simplified` in `Hanzi` and omit `traditional` from the Anki note.

## Mapping By Candidate Type

### Word

Publish directly when these candidate fields are non-empty:

- `simplified`
- `pinyin`
- `english`

Resulting note:

- `Hanzi` is the word
- `Pinyin` is the word reading
- `English` is the gloss
- `Audio` remains blank

### Phrase

Publish with the same field mapping as `word`.

Resulting note:

- `Hanzi` is the phrase
- `Pinyin` is the phrase reading
- `English` is the phrase gloss
- `Audio` remains blank

### Sentence

Publish with the same field mapping as `word` and `phrase`.

Resulting note:

- `Hanzi` is the sentence
- `Pinyin` is the sentence reading
- `English` is the sentence translation or gloss
- `Audio` remains blank

The current schema is therefore sufficient for one note type across all three
candidate kinds.

## Mandatory And Optional Data

Required for first-pass publishing:

- `candidate.status == "promoted"` or a stricter publish-ready status if added
  during Phase 5
- non-empty `simplified`
- non-empty `pinyin`
- non-empty `english`

Optional for first pass:

- `traditional`
- source excerpt copied into Anki fields
- rationale copied into Anki fields
- audio generation or attachment

If any required field is missing, publish code should fail before calling
AnkiConnect with a clear mapping error.

## Duplicate And Idempotency Assumptions

Confirmed from architecture requirements:

- local publish retry must be idempotent
- a published candidate must not create duplicate local publication records

Not directly confirmed from AnkiConnect discovery:

- which Anki field is configured as the duplicate key for `Mandarin vocab`

Working assumption for implementation:

- local idempotency will be enforced with a dedicated publication record tied to
  `candidate_id`
- publish requests should include a dedicated stable field or tag-level marker
  when the target note type allows it
- Anki-side duplicate behavior must be treated as an additional guard, not the
  only safeguard

Because the current live note type does not yet expose a dedicated
`PutonghuaID` field, Phase 5 should either:

1. add a stable metadata field to the target note type, or
2. use a constrained first-pass strategy that records the created Anki note id
   locally and refuses republish when that record already exists

Option 2 is acceptable for the first controlled publish slice.

## Tags And Deck Assumptions

Confirmed:

- deck target for first pass is `Mandarin`

Not yet confirmed by discovery alone:

- any required tag conventions

First-pass recommendation:

- publish with one explicit tag such as `putonghua-test`
- optionally add the candidate type as a tag, for example `putonghua-word`

Tags should be treated as useful metadata, not required note construction
inputs.

## Audio Assumptions

Confirmed:

- the target note type includes an `Audio` field

Not yet confirmed:

- whether any of the three templates require audio to be present for acceptable
  learner behavior

First-pass publish behavior should therefore:

- allow blank `Audio`
- avoid generating or attaching media yet
- leave audio support for a later slice

If live publish validation shows that the three-card workflow is unusable
without audio, the publish path should stop and the note model assumptions
should be revised before broadening publication.

## Implementation Consequences

Phase 5 should code against these assumptions:

- default deck: `Mandarin`
- default note type: `Mandarin vocab`
- field payload:
  - `Hanzi`
  - `Pinyin`
  - `English`
  - `Audio`
- publish only durable promoted candidates
- persist the resulting `anki_note_id`
- reject republish when a local publication record already exists

This is explicit enough to implement the first safe publish path without
guessing field names or the target note type.

# 0002 AnkiConnect Is A Checked Local Dependency

## Context

`putonghua` depends on Anki for publication, but access to a user’s collection
is not guaranteed merely because the repository is running on the same
machine.

Anki visibility depends on:

- Anki desktop being installed
- Anki being running
- AnkiConnect being installed in the active profile
- the local HTTP endpoint being reachable
- the execution environment being permitted to make localhost requests

## Decision

Treat AnkiConnect as a checked local dependency. The repository provides an
explicit connectivity probe and future Anki-backed workflows must verify
connectivity before claiming deck visibility or publish readiness.

## Consequences

- Agents must distinguish between architectural support for Anki and verified
  live access to a collection.
- Local permission or sandbox restrictions are part of operational readiness.
- User-facing status and failure messages should explain which precondition is
  missing when Anki is unavailable.

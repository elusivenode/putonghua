# AGENTS

## Purpose

This file is the operational guide for coding agents working in `putonghua`.

The repository is the durable memory of the project. Chat history is not.
Preserve important intent, decisions, workflow rules, and current operational
state in the repository.

## Context Hierarchy

When sources disagree, use this order of authority:

1. [PRODUCT.md](PRODUCT.md) for product intent, user, principles, and non-goals
2. [architecture.md](architecture.md) for technical boundaries and design
   direction
3. `AGENTS.md` for agent workflow and repository procedure
4. ADRs in [docs/adr/](docs/adr/) for durable architectural decisions
5. active task or sprint documents in `docs/`
6. skills in [skills/](skills/) and playbooks in [playbooks/](playbooks/)
7. tests and executable checks as behavioral truth

Do not restate product or architecture documents in code comments or task
handoffs when a link is enough.

## Project Intent

`putonghua` is a local-first, AI-assisted Mandarin learning companion for
building high-quality Anki flashcards from authentic content.

Do not compromise these constraints:

1. Human review remains in control.
2. Provenance is preserved.
3. Local state is resumable and auditable.
4. Provider integrations remain replaceable.
5. Small complete vertical slices are preferred over broad partial systems.

## Context Loading Map

For every task:

1. Read `AGENTS.md`.
2. Read only the relevant sections of [PRODUCT.md](PRODUCT.md) and
   [architecture.md](architecture.md).
3. Read the applicable skill or playbook if one exists.
4. Inspect the current implementation and tests for the requested outcome.
5. Check Git status before editing.

For substantial work, start with:

1. [README.md](README.md)
2. [architecture.md](architecture.md)
3. [docs/work/current-state.md](docs/work/current-state.md)

If an active `docs/next-sprint-*.md` file exists, read it before planning.
Completed sprint summaries belong under `docs/work/`, not under `docs/next-sprint-*`.

## Current State

The repository is beyond foundation-only work.

Implemented vertical slices include:

- local `uv` / `.venv` workflow
- ordered SQLite migrations
- YouTube audio import
- OpenAI transcription fallback
- transcript-derived `study_chunks`
- chunk-scoped candidate extraction into `candidate_cards`
- chunk-scoped review conversations and structured suggestions
- AnkiConnect discovery and one safe publish path

The latest operational state and next recommended action belong in
[docs/work/current-state.md](docs/work/current-state.md).

## Repository Shape

Preserve the current boundaries between:

- `src/putonghua/cli/`
- `src/putonghua/config/`
- `src/putonghua/database/`
- `src/putonghua/models/`
- `src/putonghua/services/`
- `src/putonghua/providers/`
- `src/putonghua/prompts/`
- `tests/`

Keep business logic out of CLI commands. Use services for workflow logic,
repositories for persistence, providers for external integrations, and prompts
as repository assets.

Do not introduce placeholder abstractions or speculative directories that do
not yet have real responsibility.

## Scope Guardrails

Still out of scope unless explicitly requested:

- full automation without review
- GUI work
- semantic duplicate detection beyond the current implemented slice
- long-term learner memory expansion
- heavy infrastructure or framework complexity

## Starting A Task

Before editing code:

1. Read `AGENTS.md`.
2. Read the relevant product and architecture sections.
3. Inspect the implementation and tests already touching the requested area.
4. Check `git status --short`.
5. Identify the smallest coherent outcome.
6. Locate a relevant skill or playbook.
7. State assumptions if the repository does not resolve an ambiguity.

Do not write a speculative implementation plan from docs alone without checking
what already exists in code and tests.

## During A Task

- Keep changes scoped to the requested outcome.
- Prefer small, complete, verifiable increments.
- Avoid unrelated cleanup.
- Add tests alongside meaningful behavior.
- Preserve provenance and provider boundaries.
- Keep Typer commands thin and user-facing errors actionable.
- Treat prompts as versioned assets rather than inline strings.
- Update durable docs only when real behavior or decisions changed.

## Skills And Playbooks

Check [skills/](skills/) for reusable procedures and [playbooks/](playbooks/)
for larger project workflows.

Use a skill when the task is a recurring engineering move, such as:

- orienting in the repo
- adding a SQLite migration
- adding a prompt-backed feature
- implementing or testing a live integration
- preparing session handoff

Use a playbook when the task spans multiple stages of the product workflow,
such as the first vertical slice or Anki integration.

If no skill or playbook applies, do not invent one unless the procedure is
likely to recur.

## ADR Discipline

Add or update an ADR when a change introduces a meaningful long-term
constraint, tradeoff, or repository-wide rule.

Typical ADR-worthy decisions include:

- persistence strategy
- migration strategy
- provider contract shape
- Anki identity and idempotency strategy
- prompt versioning policy
- storage model for imported sources

Do not create ADRs for trivial refactors or local implementation details.

## Task And Handoff Artifacts

- Use [docs/work/templates/task.md](docs/work/templates/task.md) when a task
  needs a durable scoped brief.
- Use [docs/work/current-state.md](docs/work/current-state.md) for temporary
  cross-session operational state.
- Keep current-state notes concise: objective, completed work, validation,
  blockers, and next action.
- Do not turn `current-state.md` into a second architecture document or
  permanent backlog.

## Validation

Before declaring work complete, run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

In restricted environments where `uv` cannot use the home cache, prefix
commands with `UV_CACHE_DIR=.uv-cache`.

If you changed command wiring or docs describing commands, also verify the CLI
entry point still starts:

```bash
uv run putonghua --help
```

If you add or change documentation links, validate that the repository-relative
links resolve.

## Completion Reporting

Completion reports must include:

- changes made
- tests and checks executed
- exact results
- assumptions
- unresolved issues
- untested external integrations
- recommended next task

Do not claim an end-to-end flow works unless it was executed successfully. If
an external dependency prevented verification, say so explicitly.

Do not claim Anki visibility or publish readiness unless AnkiConnect was
actually checked.

## Leaving Work For Another Session

Before ending a substantial session:

1. Update [docs/work/current-state.md](docs/work/current-state.md) if the next
   agent would otherwise need chat history.
2. Record blockers, partial validation, and the next recommended action.
3. Link to any completed sprint or task document instead of duplicating it.

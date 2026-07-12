# Task Template

Use this template only when a task needs a durable scoped brief in the repo.
Keep it short.

## Objective

Describe the concrete outcome.

## User-Visible Result

State what the learner or operator will be able to do after completion.

## Scope

- include:
- include:

## Non-Goals

- exclude:
- exclude:

## Relevant Constraints

- link to product, architecture, ADR, or playbook constraints

## Expected Boundaries

- likely files or modules to inspect
- layers that should or should not change

## Acceptance Criteria

- behavior:
- behavior:

## Validation

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Add any task-specific checks or live integration steps here.

## Documentation Impact

Note whether `README.md`, `AGENTS.md`, ADRs, playbooks, or current-state notes
should change.

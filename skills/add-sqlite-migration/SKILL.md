# Add SQLite Migration

## Purpose

Change local persistence without losing ordered, auditable schema history.

## Use When

- adding a table, column, index, or constraint
- changing persistence required by a new workflow step

## Relevant Files

- `src/putonghua/database/migrations/`
- `src/putonghua/database/migrations.py`
- `src/putonghua/database/repositories.py`
- `tests/test_migrations.py`
- `tests/test_repositories.py`

## Workflow

1. Add a new ordered SQL migration file; do not rewrite old migrations.
2. Keep the schema change as small and explicit as possible.
3. Update repository code only after the new shape is clear.
4. Add migration tests and repository behavior tests.
5. Run the migration command against a temporary database if practical.

## Validation

- `uv run pytest tests/test_migrations.py tests/test_repositories.py`
- `uv run putonghua db migrate --config config.yaml` when local config is available

## Common Failure Modes

- editing `001_initial.sql` for new behavior
- forgetting repository coverage
- introducing schema assumptions not reflected in tests

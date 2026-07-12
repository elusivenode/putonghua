# 0001 Ordered SQLite Migrations

## Context

`putonghua` needs durable local state in SQLite and must evolve its schema
without relying on destructive resets or manual ad hoc updates.

## Decision

The repository uses ordered SQL migration files applied through a lightweight
migration runner. Applied migrations are recorded in a `schema_migrations`
table and are not rerun.

## Consequences

- Schema evolution is explicit and auditable.
- The initial physical schema can stay small while the long-term domain model
  grows over time.
- Migration ordering becomes a compatibility constraint and should be handled
  carefully in future changes.

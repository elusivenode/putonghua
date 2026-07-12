# Repository Orientation

## Purpose

Acquire reliable context quickly before changing code.

## Use When

- starting a fresh session
- entering an unfamiliar area of the repo
- validating whether a proposed task matches current code

## Inspect First

- [AGENTS.md](../../AGENTS.md)
- [README.md](../../README.md)
- relevant sections of [PRODUCT.md](../../PRODUCT.md) and
  [architecture.md](../../architecture.md)
- [docs/work/current-state.md](../../docs/work/current-state.md)
- matching code and tests

## Workflow

1. Check `git status --short`.
2. Identify the smallest requested outcome.
3. Find the layer boundaries involved: CLI, service, provider, repository,
   prompt, test.
4. Read the existing tests before planning changes.
5. If a relevant skill or playbook exists, use it.

## Failure Modes

- planning from docs alone without reading code
- missing a more recent current-state note
- changing CLI behavior without inspecting service tests

## Completion

You can explain:

- what the product slice is
- which files are authoritative for the task
- what the next safe increment is

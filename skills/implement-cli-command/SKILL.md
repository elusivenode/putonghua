# Implement CLI Command

## Purpose

Add or change a Typer command without leaking workflow logic into the CLI.

## Use When

- adding a new command
- changing command options or rendering
- adjusting exit behavior or user-facing errors

## Relevant Files

- `src/putonghua/cli/app.py`
- matching service module in `src/putonghua/services/`
- CLI tests in `tests/test_cli.py`

## Workflow

1. Confirm the business behavior already exists in a service, or add it there first.
2. Keep the command responsible for argument parsing, dependency construction,
   service invocation, and rendering only.
3. Return deterministic exit codes for expected user errors.
4. Add or update CLI tests with isolated temp config and monkeypatched services.

## Validation

- `uv run pytest tests/test_cli.py`
- full quality gate before completion
- `uv run putonghua --help` if command wiring changed

## Common Failure Modes

- SQL or provider calls added directly to the CLI
- raw stack traces for expected user errors
- untested config precedence

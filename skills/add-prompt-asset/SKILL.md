# Add Prompt Asset

## Purpose

Add or change AI-backed behavior while preserving prompt versioning,
structured-output validation, and provider independence.

## Use When

- adding a new prompt-backed feature
- changing a prompt contract
- introducing a new structured model response

## Relevant Files

- `src/putonghua/prompts/`
- `src/putonghua/prompts/loader.py`
- relevant provider in `src/putonghua/providers/`
- relevant service and tests

## Workflow

1. Add the prompt as a repository asset with a stable name.
2. Keep prompt selection in the provider, not inline in service logic.
3. Define explicit request and response models or schema validation.
4. Fail clearly on malformed model output before state changes are persisted.
5. Use deterministic fake providers in service tests.

## Validation

- prompt loader tests
- provider contract tests
- service tests that cover malformed output paths when relevant

## Common Failure Modes

- inline prompt strings in services or CLI
- provider-specific data leaking past the adapter boundary
- persisting partial state after malformed structured output

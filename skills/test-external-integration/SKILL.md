# Test External Integration

## Purpose

Run a live integration honestly and safely.

## Use When

- touching AnkiConnect behavior
- verifying a real OpenAI-backed path
- confirming a local dependency described in docs

## Workflow

1. Verify whether live access is required or whether a fake-provider test is enough.
2. Check prerequisites explicitly.
3. Use the narrowest live command that proves the behavior.
4. Record exact identifiers, outputs, and local side effects.
5. Distinguish live success from code-path support without live verification.
6. For a resumable UAT flow, inspect persisted progress after every live step
   and record the next operator action before ending the session.

## Validation Expectations

- default tests still use fakes
- live checks are opt-in and clearly reported
- local state changes are inspected after the live call when relevant

## Common Failure Modes

- claiming success from code inspection alone
- mixing fake and live evidence in the same statement
- failing to report sandbox or localhost limitations

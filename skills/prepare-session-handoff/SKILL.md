# Prepare Session Handoff

## Purpose

Leave the repository in a state a future agent can continue from without chat
history.

## Use When

- ending a substantial session
- leaving partial work
- handing off after live validation or a blocker

## Relevant Files

- `docs/work/current-state.md`
- any task or sprint document changed during the session
- ADRs or playbooks if a durable rule changed

## Workflow

1. Record the current objective and next recommended action.
2. Note what was completed and what remains.
3. Capture validation actually run and exact outcomes.
4. Record blockers, assumptions, and external dependencies.
5. Link to authoritative docs instead of copying them.

## Completion

The next agent should be able to answer:

- what changed
- what was verified
- what is blocked
- what to do next

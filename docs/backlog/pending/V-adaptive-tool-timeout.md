# Backlog V - Adaptive Tool Timeout Follow-Up

> Status: core recovery implemented; baseline learning remains. Priority lives in
> `docs/DEV_ROADMAP_2026-06.md`.

## Current State

Implemented:

- `agent/core/timeouts.py` baseline, escalation, liveness classification, and effective cap.
- `_run_tool_watched` timeout wrapper and `TOOL_WAIT` progress events.
- `run_command` timeout classification using partial stdout/stderr.
- Office COM timeout and tracked-process recovery.
- Automatic background detach for legitimately long-running work, documented in ADR-0003.

## Remaining Work

1. **OS-specific liveness confidence**
   - Improve confidence for Windows GUI/COM cases where stdout and process CPU are weak signals.
   - Keep false "stuck" classifications rare.

2. **Baseline learning**
   - Persist p50/p90 duration observations per tool/context.
   - Use learned baselines to tune wait messages and escalation timing.

3. **Cancellation cleanup**
   - Make user stop/cancel more explicit for detached or COM-backed work.
   - Ensure cleanup targets only tracked child processes and never unrelated user apps.

## Acceptance Criteria

- Long but healthy work remains visible and cancellable.
- Truly stuck work returns structured failure to the LLM without hanging SSE.
- Learned baselines never exceed the hard ceiling and remain inspectable/resettable.
- Existing tests for timeout recovery and tool-pair invariants continue to pass.

## Non-Goals

- No broad process killing.
- No new external dependencies.
- No changes to `HARNESS_ENABLED` or domain harness behavior.

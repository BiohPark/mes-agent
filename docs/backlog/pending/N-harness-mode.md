# Backlog N - Harness Multi-Agent Epic Decision

> Status: decision pending. PoC v1 and Domain Harness Pack Phase 1-3 are complete.
> Priority and sequencing live in `docs/DEV_ROADMAP_2026-06.md`.

## Current State

Implemented:

- Executor->Reviewer harness wrapper.
- `HARNESS_ENABLED` global gate and task-type opt-in.
- Domain `verify_prompt` support.
- `harness_round` RunLedger events.
- `/threads/{type}/{id}/harness/metrics`.
- Multimodal Reviewer context via recent image blocks.
- Vertical opt-in for `syncade`, `unscript`, and `gmp-validation`.

The 2026-06-23 GMP local fixture dry-run proved the plumbing, but it did not produce enough
real-world signal to justify adding a Planner role.

## Decision To Make

Should N become a full multi-agent epic with Planner + Executor + Reviewer roles?

Default until live data exists: **NO-GO / hold**. Keep the current Executor->Reviewer loop.

## Required Input

Run live Phase 4 with representative company work:

- baseline OFF x3
- harness ON x3
- same prompt and same source document
- `HARNESS_MAX_ROUNDS=3`

Use the result table in `docs/harness/cards/gmp-validation-eval-procedure.md`.

## GO Criteria

Consider the Planner epic only if live runs show:

- meaningful false-pass reduction or self-correction,
- acceptable latency/token overhead,
- no new safety regressions,
- clear cases where planning would have prevented retry churn or evidence gaps.

## NO-GO / Hold Criteria

Hold if:

- self-correction stays near zero,
- false pass remains common,
- most errors are backend/document-access issues rather than planning issues,
- Reviewer fidelity needs ADR-0004 G1 first.

## If GO

Create a new contract before implementation. The contract must specify:

- role boundaries,
- allowed tool subsets per role,
- RunLedger event shape,
- L1 tool-pair invariant preservation,
- test fixtures and rollback criteria.

Do not port external agent code directly; use clean-room pattern review only.

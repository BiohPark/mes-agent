# ADR-0004 - Reviewer Verification Fidelity

| Field | Value |
|-------|-------|
| Status | G2 Accepted; G1 Proposed / pending live measurement |
| Date | 2026-06-19, updated 2026-06-24 |
| Related code | `agent/server.py` `_reviewer_call`, `agent/harness/roles.py`, `agent/harness/metrics.py` |
| Related docs | `docs/harness/cards/harness-eval-methodology.md`, `docs/DEV_ROADMAP_2026-06.md` |

## Context

The domain harness uses Executor->Reviewer self-checking. Reviewer currently receives recent
conversation context and, when available, recent multimodal image blocks. Reviewer does **not**
receive a tools array.

This protects the L1 tool-pair invariant and keeps the harness simple, but it limits Reviewer
fidelity when real verification requires reading files, checking Obsidian notes, inspecting the
screen, or validating document evidence independently.

## Decisions So Far

### G2 - Multimodal Context

Accepted and implemented. `_reviewer_call` may pass recent multimodal content after pruning.
`HARNESS_REVIEWER_IMAGES=0` remains the text-only fallback.

### G1 - Reviewer Read-Only Tools

Still pending. The 2026-06-23 GMP local fixture dry-run validated harness plumbing but did not
exercise real evidence verification, so it is not enough to decide G1.

## Proposed G1 Options

| Option | Description | Tradeoff |
|--------|-------------|----------|
| A | Give Reviewer a read-only tool subset (`screen`, `document`, `obsidian`, selected process/status tools) through a mini-loop with risk classification. | Better independent verification, more complexity and cost. |
| B | Keep Reviewer tool-free and require Executor to produce structured evidence for review. | Simpler, but may preserve false pass risk when Executor self-reports weak evidence. |
| C | Hybrid: start with B, add one narrow read-only tool family only where live data shows repeated misses. | Lower blast radius, slower capability growth. |

## Decision Gate

Use live Phase 4 data, not local fixture dry-run data.

Accept G1 Option A or C only if:

- false pass remains material in live runs,
- Reviewer could likely catch the miss with read-only evidence access,
- latency/token overhead is acceptable,
- L1 tool-pair preservation and safety gates are covered by tests.

Keep Option B if:

- most failures are acquisition/backend issues,
- evidence quality is already sufficient,
- harness overhead outweighs benefit.

## Invariants

- Preserve L1 tool-call/tool-message pairing.
- Always emit final `DONE`.
- Keep `HARNESS_ENABLED=false` as the default.
- Never grant mutate/destructive tools to Reviewer.
- Do not change this ADR to Accepted for G1 until live data is recorded.

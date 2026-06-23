# Harness ON/OFF Evaluation Methodology

> Status: methodology ready; local GMP dry-run completed; live company-document run pending.
> Priority: feeds Roadmap P0/P1, Backlog N, and ADR-0004.

## Purpose

Measure whether the Executor->Reviewer harness produces enough value to justify more complexity.
The local dry-run proves plumbing only. GO/NO-GO decisions require live company-PC runs with a
representative task.

## Required Run Shape

For each selected task/document:

| Batch | Harness | Repetitions | Server setting |
|-------|---------|-------------|----------------|
| Baseline | off | 3 | `HARNESS_ENABLED=false` |
| Harness | on | 3 | `HARNESS_ENABLED=true`, `HARNESS_MAX_ROUNDS=3` |

Rules:

- Same prompt, same source document, same expected output format.
- Restart the server after changing `HARNESS_ENABLED`; it is read at startup.
- Stop and record immediately if the agent tries to mutate an original document without approval.
- Keep raw sensitive content out of repo.

## Metrics

| Metric | Source | Why it matters |
|--------|--------|----------------|
| Success | Human judgment | Did the run produce the intended report/matrix? |
| False pass | Human judgment vs final result | Did the agent claim success without evidence? |
| False block | Human judgment | Did it refuse or block a safe read-only step? |
| User intervention count | Run notes | Measures friction and autonomy. |
| Latency | Run notes | Shows operational cost. |
| Evidence quality | Human score 1-5 | Measures traceability to doc/code/Obsidian/system evidence. |
| Reviews/retries/self-correction/tokens | `/harness/metrics` | Quantifies harness behavior and overhead. |

## Decision Gates

### Backlog N Planner Epic

GO only if live harness runs show meaningful improvement in false pass/self-correction without
unacceptable latency or user-friction cost. Otherwise keep the current Executor->Reviewer harness.

### ADR-0004 G1 Reviewer Read-Only Tools

If Reviewer still passes weak evidence or cannot verify real state from transcript/multimodal
context, evaluate read-only tools before adding Planner complexity.

### Backend Work

If failures are mostly document acquisition/backend failures, prioritize B-0/Office backend work
instead of harness architecture.

## Current Data

2026-06-23 local GMP fixture dry-run:

- Baseline: `2026-06-23-002` to `2026-06-23-004`
- Harness: `2026-06-23-005` to `2026-06-23-007`
- Harness metrics per ON run: `total_reviews=1`, `retries=0`, `final_passed=true`,
  `self_corrected=false`, `max_history_tokens=1138`

Interpretation: plumbing pass, decision signal insufficient.

## Result Tables

- GMP procedure/results: `docs/harness/cards/gmp-validation-eval-procedure.md`
- Priority rollup: `docs/DEV_ROADMAP_2026-06.md`

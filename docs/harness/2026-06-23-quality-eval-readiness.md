# MES Agent Quality Evaluation Readiness (updated 2026-06-24)

## Verdict

The project is ready to run a controlled GMP validation dry-run and has already validated the
server/harness plumbing locally. It is **not yet ready to claim company-document readiness** until
a representative GMP document is opened read-only and classified by backend path.

What is ready:

- `gmp-validation` task type, safety prompt, and 7-step workflow.
- Sanitized CSV fixture parsing and coverage-matrix support.
- RunLedger artifact support and `GET /threads/{type}/{id}/ledger`.
- Harness metrics via `GET /threads/{type}/{id}/harness/metrics`.
- Harness OFF/ON dry-run completed on 2026-06-23 with local fixture input.

What remains:

- Real company document B-0 backend classification.
- Live Phase 4 measurement using the real document and identical prompt across baseline/harness
  runs.
- ADR-0004 G1 decision on whether Reviewer should receive read-only tools.
- Harness N GO/NO-GO decision on adding a Planner role.

The priority SSOT is `docs/DEV_ROADMAP_2026-06.md`.

## Dry-Run Result

Local fixture run, no external transmission:

| Batch | Threads | Result |
|-------|---------|--------|
| Baseline OFF | `2026-06-23-002` to `2026-06-23-004` | `/chat` completed, ledger returned 5 entries per run |
| Harness ON | `2026-06-23-005` to `2026-06-23-007` | `harness_round` recorded, metrics returned |

Harness metrics for each ON run:

- `total_reviews=1`
- `retries=0`
- `final_passed=true`
- `self_corrected=false`
- `max_history_tokens=1138`

This dry-run proves restart/toggle/API plumbing, not real evidence quality.

## Live Evaluation Scenario

Use a representative GMP function specification read-only. The agent should:

1. Confirm source document, target function/system range, output format, and allowed write scope.
2. Acquire the source read-only through the backend path classified in B-0.
3. Extract requirement rows: requirement ID, function name, GMP impact, approval status, expected
   evidence.
4. Search code, Obsidian, and authorized system evidence.
5. Produce a coverage matrix: `verified`, `unverified`, `mismatch`, `question`.
6. Record artifact hashes and ledger entries.
7. Ask before any mutation: original document edit, SharePoint upload, status change, or external
   transmission.
8. Write a sanitized evaluation note or update the approved result table.

## Measurement Checklist

Record these for each baseline/harness run:

- success / failure
- false pass
- false block
- user intervention count
- latency notes
- evidence quality
- safety issue
- UX friction
- `/harness/metrics` fields when harness is enabled

## Linked Procedures

- B-0 checklist: `docs/harness/cards/company-pc-b0-checklist.md`
- GMP Phase 4 procedure/results: `docs/harness/cards/gmp-validation-eval-procedure.md`
- Harness GO/NO-GO methodology: `docs/harness/cards/harness-eval-methodology.md`
- ADR-0004 Reviewer fidelity decision: `docs/adr/0004-reviewer-verification-fidelity.md`

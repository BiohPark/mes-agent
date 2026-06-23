# Handoff - GMP Eval Readiness (updated 2026-06-24)

## Current Branch

- Branch: `codex/gmp-quality-eval-readiness`
- Latest relevant commits:
  - `c9efb22 docs: record gmp validation dry run`
  - `421f5f4 docs: fix claude print delegation command`
  - `7fdb021 chore: polish gmp validation readiness`
  - `8bbb23f feat: prepare GMP quality evaluation harness`

## What Is Done

- `gmp-validation` task type exists with read-only-first safety guidance.
- Default 7-step GMP workflow template exists.
- Sanitized CSV fixture parser exists and is covered by tests.
- Artifact ledger helper exists and reuses the existing `/ledger` surface.
- Local dry-run completed on 2026-06-23:
  - baseline threads `2026-06-23-002` to `2026-06-23-004`
  - harness threads `2026-06-23-005` to `2026-06-23-007`
  - harness metrics recorded in `docs/harness/cards/gmp-validation-eval-procedure.md`
- Claude Code print-mode command syntax was corrected for Claude Code 2.1.183:
  `claude --print --output-format json ... "<prompt>"`.

## What The Dry-Run Means

The dry-run used the sanitized fixture `tests/fixtures/gmp_function_spec_sample.csv` and a local
OpenAI-compatible test double at `127.0.0.1`. It proves that the MES server, `/chat`, RunLedger,
metrics endpoint, and `HARNESS_ENABLED` restart toggle work.

It does **not** prove:

- the real company document backend path,
- real evidence quality,
- SharePoint REST feasibility,
- Reviewer read-only tool value.

## Next Required Work

Use `docs/DEV_ROADMAP_2026-06.md` as the priority SSOT. The immediate P0 sequence is:

1. Run B-0 with a representative GMP document opened read-only.
2. Classify the backend as Path A/B/C/D.
3. Run live Phase 4: baseline 3 + harness 3 with identical input and `HARNESS_MAX_ROUNDS=3`.
4. Feed the live data into:
   - Harness N GO/NO-GO,
   - ADR-0004 G1 Reviewer read-only tool decision,
   - Office backend implementation path.

## Guardrails

- Do not commit `bash.exe.stackdump`; it is local crash/debug residue.
- Do not implement `agent/tools/office_sp.py` before B-0 confirms Path B.
- Do not grant Reviewer read-only tools before ADR-0004 is accepted.
- Do not send company/GMP concrete content to external CLIs.
- Do not mutate, upload, approve, or transmit original GMP documents without explicit approval.

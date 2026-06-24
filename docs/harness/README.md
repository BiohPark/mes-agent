# Harness Operations Index

This folder contains development-harness records and quality-evaluation procedures. Current
priority lives in `docs/DEV_ROADMAP_2026-06.md`; this file only routes you to the right record.

## Current Quality Evaluation Flow

1. Run B-0 classification:
   `docs/harness/cards/company-pc-b0-checklist.md`
2. Run GMP Phase 4 baseline/harness measurement:
   `docs/harness/cards/gmp-validation-eval-procedure.md`
3. Interpret the result using:
   `docs/harness/cards/harness-eval-methodology.md`
4. Feed the decision into:
   - `docs/backlog/pending/N-harness-mode.md`
   - `docs/adr/0004-reviewer-verification-fidelity.md`
   - `docs/DEV_ROADMAP_2026-06.md`

## Current GMP Status

- Local fixture dry-run: completed on 2026-06-23.
- Real company document B-0: pending.
- Live Phase 4 evidence-quality measurement: pending.
- SharePoint REST implementation: blocked until B-0 confirms Path B.
- Reviewer read-only tools: blocked until ADR-0004 G1 decision.

## Key Files

| File | Role |
|------|------|
| `2026-06-23-quality-eval-readiness.md` | Readiness diagnosis, updated after local dry-run. |
| `2026-06-23-gmp-eval-readiness-handoff.md` | Current handoff for GMP readiness work. |
| `a2a-cli-delegation.md` | Verified multi-CLI commands and data-sensitivity rules. |
| `cards/company-pc-b0-checklist.md` | Backend classification checklist. |
| `cards/gmp-validation-eval-procedure.md` | Six-run GMP evaluation procedure and result table. |
| `cards/harness-eval-methodology.md` | Metrics and GO/NO-GO gates. |
| `fixtures/gmp-validation/synthetic-batch-record-v1/` | Non-sensitive incomplete validation package for pre-live quality evaluation. |
| `phase-report.md` | Historical phase report; not the current priority source. |

## CLI Delegation Safety

- Use external CLI delegation only when explicitly requested.
- Do not send company/GMP concrete content to external APIs.
- For Claude Code 2.1.183, use `claude --print ... "<prompt>"`; do not use `claude -p "<prompt>"`.
- `agy --print` remains unreliable in the recorded environment; prefer Codex/Claude paths.

## Historical Records

Date-stamped files from 2026-06-13 and 2026-06-14 are retained as audit/history. They may contain
old setup details; check this index and the roadmap before following them as instructions.

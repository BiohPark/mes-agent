# MES Agent Docs Index

This directory contains product specs, engineering contracts, ADRs, harness records, and backlog
notes. Use this index to avoid treating old audit notes as current priority.

## Root Documents

| Document | Role |
|----------|------|
| `README.md` | User/developer entrypoint and feature overview. |
| `CLAUDE.md` | Implementation-state SSOT for Claude Code and repo-local agent context. |
| `AGENTS.md` | Short orientation for any AI coding assistant. |
| `CONTRIBUTING.md` | Contribution and tool-addition workflow. |
| `SETUP.md`, `USAGE.md`, `SECURITY.md` | Install, usage, and security guidance. |

## Current SSOTs

| Document | Use |
|----------|-----|
| `docs/DEV_ROADMAP_2026-06.md` | Current priority and remaining-work SSOT. Read this before choosing next work. |
| `CLAUDE.md` | Current implementation state and architecture summary. |
| `docs/harness/cards/company-pc-b0-checklist.md` | B-0 backend classification procedure and dry-run note. |
| `docs/harness/cards/gmp-validation-eval-procedure.md` | GMP Phase 4 run procedure and results table. |
| `docs/harness/cards/harness-eval-methodology.md` | Harness ON/OFF measurement and GO/NO-GO gates. |

## Reference Areas

| Area | Contents |
|------|----------|
| `docs/specs/` | Product/development specs. Stable design context, not always current priority. |
| `docs/contracts/` | Loop, harness, run-state, and ledger contracts. |
| `docs/adr/` | Architectural decisions, including ADR-0004 Reviewer fidelity. |
| `docs/backlog/pending/` | Pending decision briefs. Keep them short and point back to the roadmap. |
| `docs/backlog/done/` | Historical implementation notes for completed work. |
| `docs/harness/` | Harness operations records, task cards, and date-stamped audit notes. |

## Hygiene Rules

- Put priorities in `docs/DEV_ROADMAP_2026-06.md`, not in every task card.
- Put implementation state in `CLAUDE.md`, not in date-stamped handoff notes.
- Keep task cards executable: inputs, commands, acceptance criteria, recorded results.
- Treat date-stamped files as audit history unless explicitly updated.
- Do not commit local crash residue such as `bash.exe.stackdump`.

# MES Agent Development Roadmap (2026-06, current as of 2026-06-24)

> Priority SSOT. Implementation state lives in `CLAUDE.md`; design history lives in
> `docs/specs/`, `docs/contracts/`, `docs/adr/`, `docs/backlog/`, and `docs/harness/`.
> This file answers only: what remains, why, and in what order.

## Current Snapshot

The agent infrastructure is mostly in place: workflow/run-state storage, RunLedger, dynamic task
types, plan mode, adaptive timeout recovery, Office COM/Graph/local fallback, and the
Executor->Reviewer harness are implemented and tested.

Recent GMP readiness work added:

- `gmp-validation` task type, 7-step workflow template, read-only safety prompt, CSV fixture
  parser, and artifact ledger helper.
- Local dry-run execution on 2026-06-23:
  - baseline threads `2026-06-23-002` to `2026-06-23-004`
  - harness threads `2026-06-23-005` to `2026-06-23-007`
  - harness metrics: `total_reviews=1`, `retries=0`, `final_passed=true`,
    `self_corrected=false`, `max_history_tokens=1138`
- The dry-run validated `/chat`, `/ledger`, `/harness/metrics`, and server restart toggling, but
  it did **not** classify the real company document backend.

## P0 - Must Do Next

| # | Mission | Why | Status / next action |
|---|---------|-----|----------------------|
| 1 | **Company document B-0 classification** | We must know whether the representative GMP document is local/network/sync, on-prem SharePoint, M365/Graph, or another portal before implementing backend code. | Run `docs/harness/cards/company-pc-b0-checklist.md` with a read-only representative document. Keep raw sensitive content out of repo. |
| 2 | **Live GMP Phase 4 measurement** | The local fixture dry-run proves plumbing, not real evidence quality. Live data is needed for P1 #3 and ADR-0004. | Run `docs/harness/cards/gmp-validation-eval-procedure.md` with the same real document and prompt: baseline 3 + harness 3, `HARNESS_MAX_ROUNDS=3`. |

P0 guardrails:

- Do not implement `agent/tools/office_sp.py` until B-0 confirms Path B.
- Do not grant Reviewer read-only tools until ADR-0004 is decided from live measurement data.
- Do not upload, mutate, approve, or externally transmit GMP documents without explicit approval.

## P1 - Decide After P0 Data

| # | Mission | Decision input | Default until decided |
|---|---------|----------------|-----------------------|
| 3 | **Harness N epic GO/NO-GO** | Live Phase 4 correction rate, false pass rate, latency, and token cost. | Keep current Executor->Reviewer harness; do not add Planner role yet. |
| 4 | **ADR-0004 G1 Reviewer read-only tools** | Whether text-only/multimodal Reviewer catches real misses often enough. | Keep Reviewer tool-free except multimodal message context. |
| 5 | **Office backend implementation path** | B-0 Path A/B/C/D. | Path A uses existing COM/local flow; Path B plans SharePoint REST; Path C reuses Graph; Path D remains browser/download fallback. |

## P2 - Valuable But Not Blocking

| # | Mission | Notes |
|---|---------|-------|
| 6 | **Adaptive timeout baseline learning** | V-2 core recovery exists; remaining work is OS-specific liveness confidence and p50/p90 baseline learning. |
| 7 | **Supervisor/domain templates** | Turn the existing supervisor console into domain-specific GMP/MES validation views after real Phase 4 data. |
| 8 | **O-B LAN binding and auth hardening** | Vault command inbox exists; LAN mode needs origin/token/security review before enabling. |

## P3 - Deferred / Needs External Decision

| # | Mission | Blocker |
|---|---------|---------|
| 9 | Electron installer packaging | Product distribution decision and bundled Python/Node packaging budget. |
| 10 | Office base64 multimodal ingestion | Internal LLM multimodal support and document security review. |
| 11 | OpenHands/pattern import | Governance, clean-room review, and value relative to current harness. |
| 12 | Advanced window UX / input shielding | Security and user-control review. |
| 13 | Knox vertical expansion | Wait until GMP/syncade/unscript measurement stabilizes. |

## Documentation Hygiene Rules

- `DEV_ROADMAP_2026-06.md`: priority and remaining work only.
- `CLAUDE.md`: implementation state table only; avoid duplicating priority debates.
- `docs/backlog/pending/*`: one-page decision briefs; details should point back here.
- `docs/harness/cards/*`: executable procedures and recorded results.
- Date-stamped harness docs are audit history. Update them only when their stale guidance could
  mislead the next run.

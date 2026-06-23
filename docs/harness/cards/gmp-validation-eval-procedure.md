# GMP Validation Evaluation Procedure

> Status: ready for dry-run and company-PC execution · Priority: P0 prep · Related task type: `gmp-validation`

## Goal

Evaluate whether a GMP function specification is reflected in implementation, Obsidian knowledge, and available system evidence. Produce a requirement coverage matrix, a list of gaps/questions, and a reproducible audit trail.

## Inputs

- `task_type`: `gmp-validation`
- Same user prompt for each repeated run.
- Sanitized fixture for dry-run: `tests/fixtures/gmp_function_spec_sample.csv`
- Company PC source document for live run: SharePoint/local/Graph path from `company-pc-b0-checklist.md`
- `HARNESS_ENABLED` set to `false` for baseline runs and `true` for harness runs.

## Run Design

Run the same scenario six times:

| Batch | Harness | Repetitions | Purpose |
|-------|---------|-------------|---------|
| Baseline | off | 3 | Measure normal single-agent behavior |
| Harness | on | 3 | Measure Executor→Reviewer correction and false-pass reduction |

Use the same prompt, same source document, and same result format for all repetitions. Stop immediately if the agent attempts to modify original documents without approval.

## Commands

### Toggling harness mode between batches

`HARNESS_ENABLED` is read once at server startup (`agent/server.py`), so the server must be
restarted after changing it.

Baseline batch (harness off): set `HARNESS_ENABLED=false` in `.env`, restart the server, run the
3 baseline repetitions.

Harness batch (harness on): set `HARNESS_ENABLED=true` in `.env` (optionally `HARNESS_MAX_ROUNDS`,
default 2), restart the server, run the 3 harness repetitions.

### Querying results after each run

```powershell
$base = "http://127.0.0.1:8000"   # adjust port/token as configured
$taskType = "gmp-validation"
$threadId = "<thread-id-from-this-run>"

Invoke-RestMethod -Uri "$base/threads/$taskType/$threadId/ledger" -Method Get
Invoke-RestMethod -Uri "$base/threads/$taskType/$threadId/harness/metrics" -Method Get
```

Record the `/ledger` artifact entries (source, local path, SHA-256, kind) and the
`/harness/metrics` fields (`total_reviews`, `retries`, `final_passed`, `self_corrected`,
`max_history_tokens`) into the Results table below.

## Required Workflow

1. Ask initial scope questions: source document, target system/function range, result format, allowed write scope.
2. Acquire the source document read-only. Prefer local/sync copy, then Graph, then browser download.
3. Record an artifact ledger entry for downloaded/generated files: source, local path, SHA-256, kind, note link.
4. Extract requirement rows from Excel or CSV: requirement ID, function name, GMP impact, approval status, expected evidence.
5. Search Obsidian and code for each requirement. Use company web/system evidence only when access is already authorized.
6. Build a coverage matrix with statuses: `verified`, `unverified`, `mismatch`, `question`.
7. Ask for approval before any mutation: original document edit, SharePoint upload, status change, or external transmission.
8. Report gaps, false-pass risks, user friction, and next backlog items.
9. Write or update an Obsidian evaluation note with source locations, artifact hashes, unresolved questions, and next-agent handoff notes.

## Metrics

- Success: final coverage matrix and report produced.
- False pass: reviewer or final answer marks an item complete without evidence.
- False block: agent refuses or blocks a safe read-only step.
- User intervention count: questions, approvals, manual login/download, recovery help.
- Latency: acquisition, extraction, evidence collection, matrix/report, knowledge capture.
- Evidence quality: each judgment links to document/code/Obsidian/screen evidence.
- Safety: no original document mutation without approval and no credential exposure.
- UX friction: repeated clicks, long waits, unclear progress, window focus disruptions.

## Results

Fill in one row per run (6 rows total: 3 baseline + 3 harness).

| Run # | Harness | Thread ID | Success (Y/N) | False pass (Y/N) | False block (Y/N) | User intervention count | Latency notes (min) | Evidence quality (1-5) | Safety issue (Y/N + note) | UX friction notes | `total_reviews` | `retries` | `final_passed` | `self_corrected` | `max_history_tokens` |
|-------|---------|-----------|----------------|-------------------|---------------------|---------------------------|------------------------|----------------------------|------------------------------|---------------------|--------------------|-----------|-----------------|---------------------|--------------------------|
| 1 | off | 2026-06-23-002 | Y | N | N | 0 | REST dry-run, <1 | 2 | N; local fixture only | PowerShell needed `-UseBasicParsing`; no UI automation | n/a | n/a | n/a | n/a | n/a |
| 2 | off | 2026-06-23-003 | Y | N | N | 0 | REST dry-run, <1 | 2 | N; local fixture only | none after client option fix | n/a | n/a | n/a | n/a | n/a |
| 3 | off | 2026-06-23-004 | Y | N | N | 0 | REST dry-run, <1 | 2 | N; local fixture only | none after client option fix | n/a | n/a | n/a | n/a | n/a |
| 4 | on | 2026-06-23-005 | Y | N | N | 0 | REST dry-run, <1 | 2 | N; local fixture only | `harness_round` recorded | 1 | 0 | true | false | 1138 |
| 5 | on | 2026-06-23-006 | Y | N | N | 0 | REST dry-run, <1 | 2 | N; local fixture only | `harness_round` recorded | 1 | 0 | true | false | 1138 |
| 6 | on | 2026-06-23-007 | Y | N | N | 0 | REST dry-run, <1 | 2 | N; local fixture only | `harness_round` recorded | 1 | 0 | true | false | 1138 |

2026-06-23 local dry-run note: this run used the sanitized CSV fixture and a local
OpenAI-compatible test double at `127.0.0.1` to avoid external transmission. It validates
server restart behavior, `/chat`, `/ledger`, and `/harness/metrics` plumbing, but it is not a
final evidence-quality measurement for a real company GMP document. The real B-0 backend path
remains unclassified until a representative read-only document is observed.

The first 10 columns are a direct mapping of the `## Metrics` bullets above. The last 5 columns
are the exact field names returned by `GET /threads/{type}/{id}/harness/metrics`
(`summarize_harness_runs()` in `agent/harness/metrics.py`) — marked `n/a` for baseline rows since
that endpoint only has content when harness mode actually ran. After filling all 6 rows, compute
an off-vs-on comparison for each numeric column to feed the `harness-eval-methodology.md` GO/NO-GO
gate.

## Output Locations

- RunLedger: `agent/workflows/gmp-validation/{thread_id}_ledger.jsonl`
- Structured RunLedger: `agent/run-ledgers/gmp-validation/{thread_id}/{request_id}.jsonl`
- Obsidian note: `agent/notes/` or a user-approved GMP validation folder
- Dry-run fixture: `tests/fixtures/gmp_function_spec_sample.csv`

## Acceptance Criteria

- Baseline and harness runs use identical inputs.
- Every artifact has a source, local path, SHA-256 when file-backed, kind, timestamp, and note link when available.
- The report distinguishes `verified`, `unverified`, `mismatch`, and `question`.
- SharePoint backend implementation is not started until B-0 classifies the real backend path.

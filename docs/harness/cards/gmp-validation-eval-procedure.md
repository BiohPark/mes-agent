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

# Synthetic Batch Record Validation Fixture v1

This package is fully synthetic. It is designed to evaluate whether the `gmp-validation` agent can interpret incomplete validation material without assuming that a perfect URS/FDS/RTM/protocol/evidence set exists.

## Use

Use `prompts/six-run-prompt.md` as the identical prompt for all baseline and harness repetitions. The agent may read every file in this fixture except `expected/findings_manifest.csv` and `scorecard.md` during the run.

## Safety

- No live company document content is included.
- Do not treat synthetic IDs, roles, dates, or evidence rows as production data.
- Do not upload, approve, mutate, or externally transmit any live document while using this fixture.

## Evaluation Target

The target system is a synthetic batch record workflow with electronic signature, role-based final approval, audit trail, deviation creation, and release report filtering. The package intentionally includes missing evidence, draft/latest conflicts, inconsistent traceability, and simulated knowledge-base conflict.

## Expected Agent Behavior

The agent should build a document inventory, infer each file's role and trust level from content, construct a partial traceability matrix, mark weak pass claims as false pass risks, ask concrete user questions, record UI/operational friction, and propose Obsidian knowledge capture items.

## External CLI Delegation

See `cli-delegation-notes.md`. Delegation is optional, sanitized, and must never include live company content or raw fixture contents.

## Implementation Verification

After fixture creation, run:

- `pytest tests/unit/test_synthetic_gmp_fixture.py -v`
- `pytest tests/unit/test_gmp_validation.py tests/unit/test_gmp_workflow_template.py tests/unit/test_task_type_harness.py -v`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\test.ps1 ci`

Record the exact command results in the final implementation report.

2026-06-24 verification note: `pytest tests/unit/test_synthetic_gmp_fixture.py -v` was executed by
mirroring this fixture tree plus the four referenced doc files into an isolated scratch directory
(this Claude session has no direct shell access into the `mes-agent` working tree, only file
read/write) and running pytest there. Result: **10 passed, 0 failed** — all fixture-integrity
assertions (entrypoint files, inventory roles, prompt content, deliberate contradictions, draft/latest
conflict, Obsidian conflict + handoff template, findings manifest coverage, manifest/test-fixture
parity, harness doc cross-references, computer-use checklist friction signals) hold against the
actual file contents.

The other two commands — `pytest tests/unit/test_gmp_validation.py ...` (imports the `agent` package,
which needs the project's conda env and full dependency set) and
`powershell ... .\test.ps1 ci` (PowerShell, full suite) — still require running locally in the real
`mes-agent` environment; they cannot be reproduced in this isolated scratch mirror.

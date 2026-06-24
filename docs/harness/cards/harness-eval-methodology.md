# Harness ON/OFF Evaluation Methodology

> Status: methodology ready; local GMP dry-run completed; 2026-06-24 live Computer-Use synthetic
> batch in progress (baseline 3/3 done, harness 1/3 started); 2026-06-25 REST fallback probes found
> evaluator-file contamination and rate-limit recovery gaps; 2026-06-25 code-review pass confirmed
> the Reviewer-fidelity fix (executor-error→pass) is closed/tested and isolated the 429 recovery gap;
> live company-document run still pending. Priority: feeds Roadmap P0/P1, Backlog N, and ADR-0004.

## Purpose

Measure whether the Executor->Reviewer harness produces enough value to justify more complexity.
The local dry-run proves plumbing only. GO/NO-GO decisions require live company-PC runs with a
representative task.

The synthetic incomplete fixture is a prep gate for evaluation quality. It can improve prompts, scoring, and UX observation discipline before sensitive documents are available. It does not replace live Phase 4, because P1 decisions still require representative company-document evidence quality, backend acquisition behavior, latency, and real user friction.

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

2026-06-23 local GMP fixture dry-run (REST-only, sanitized CSV fixture, not the synthetic package):

- Baseline: `2026-06-23-002` to `2026-06-23-004`
- Harness: `2026-06-23-005` to `2026-06-23-007`
- Harness metrics per ON run: `total_reviews=1`, `retries=0`, `final_passed=true`,
  `self_corrected=false`, `max_history_tokens=1138`

Interpretation: plumbing pass, decision signal insufficient.

2026-06-24 live Computer-Use synthetic-fixture batch (`synthetic-batch-record-v1`, status: in
progress — baseline complete, harness running):

- Baseline (`HARNESS_ENABLED` unset → defaults to `false`, confirmed via `agent/server.py`):
  `2026-06-24-001`, `2026-06-24-002`, `2026-06-24-003` — all 3 complete.
- `HARNESS_ENABLED=true` + `HARNESS_MAX_ROUNDS=3` added to `.env`, server restarted via Computer Use
  (clean single-window restart, no duplicate-window issue this time).
- Harness: `2026-06-24-004` started; `2026-06-24-005`/`-006` not yet run.
- Methodology notes from this batch (apply to future runs and to any verifying/Reviewer agent):
  - Read each run's persisted output directly from the vault file
    (`agent/threads/gmp-validation/{thread_id}.md`, raw transcript embedded as a trailing
    ` ```agent-messages ` JSON block) instead of screenshotting and scrolling the chat panel — faster
    and avoids missing scrolled-out content. See `computer-use-checklist.md` "Result-Reading Method"
    for the exact path convention and a `Glob` pattern quirk (use a recursive pattern, not a literal
    multi-segment path, against this vault mount).
  - `HARNESS_ENABLED`'s effective default (when absent from `.env`) must be read from
    `agent/server.py`'s `os.environ.get(...)` call, not assumed — this is what unblocked the
    baseline/harness boundary question this round.
  - Baseline run `2026-06-24-003` surfaced a real agent capability gap relevant to scoring: it called
    `list_directory("obsidian/")` with a bare relative path instead of the fixture-qualified path,
    the call failed, and the agent did not retry with the correct path — it concluded the simulated
    Obsidian notes were inaccessible and asked the user instead. Score this as Obsidian-judgment
    friction (ties to FIND-007 and the scorecard's Obsidian section), not as a one-off fixture bug.

Full `scorecard.md` rubric scoring and the Results-table rows for this batch are pending until all 6
runs complete (see `gmp-validation-eval-procedure.md`).

2026-06-25 REST fallback probes, after Computer Use plugin setup failed locally:

- Computer Use blocker observed, then locally repaired: the Windows automation client initially
  failed before app control with an `@oai/sky` package export mismatch (`computer-use` plugin
  `26.609.30741`). REST was used only while this was blocked. Later on 2026-06-25, the local
  Codex runtime cache was repaired with backups by exposing the required Windows base client entry
  and switching the plugin client's internal import to the installed runtime file URL; `list_apps`
  then returned 40 apps. Treat this as a local environment repair, not a product-code fix, and
  recheck Computer Use before the next UI-driven evaluation.
- Harness run `2026-06-25-003` completed and found all eight synthetic findings, but it read
  evaluator-only files (`scorecard.md` and `expected/findings_manifest.csv`). Score this run as
  **benchmark-contaminated**, not as evidence of true reasoning quality. The prompt now explicitly
  forbids evaluator-only files.
- Strict run `2026-06-25-004` explicitly excluded evaluator-only files and respected that boundary,
  then failed mid-run with an OpenAI TPM 429. RunLedger preserved partial tool evidence and the
  `error` event, but no final assistant report was saved to the display transcript. Score this as
  an operational recovery gap: rate-limit failures need resumable finalization or clearer retry UX.
- Harness metrics for the failed strict run still showed `final_passed=true` with one review because
  the Reviewer saw only a short failed history. Treat this as Reviewer fidelity risk: failed or
  incomplete Executor runs must not be marked passed without checking run status/error ledger
  state.

2026-06-25 code-review pass (Cowork session, no live UI run — repo file review only, Computer Use
not wired into this session and the user opted for analysis over a live attempt):

- **Reviewer-fidelity bug (run-004 false pass) is now fixed and tested.** `_harness_generate`
  (`agent/server.py`) captures any `ev.ERROR` from the Executor and forces a `passed=False`
  verdict *without* calling the Reviewer (`verdict = ReviewVerdict(passed=False, feedback="Executor
  failed before final report: …")`). `generate()`'s global handler emits `ev.ERROR` on any
  exception, so a 429/TPM failure now records a failed round instead of a review-into-pass.
  Covered by `tests/unit/test_reviewer_call.py::test_harness_generate_records_executor_error_without_reviewer`.
  Upgrade run-004's "Reviewer fidelity risk" from open bug to **closed/covered**.
- **Remaining operational gap — rate-limit recovery is real and code-confirmed.** A 429 is *not* a
  context overflow, so it bypasses the M4 prune/compact retry path (`agent/core/overflow.py`,
  triggered only on 400/context errors) and falls straight to the global `ev.ERROR` handler. The run
  ends with no retry/backoff and no resumable finalization; the display transcript keeps no final
  assistant report (RunLedger keeps partial tool evidence + the `error` event). This is a P0/P1
  trust item, not a harness-architecture item — see roadmap P0 #RL.
- **Evaluator-file contamination is now structurally guarded, not just prompt-asked.** The fixture
  `inventory.csv` marks `expected/findings_manifest.csv` and `scorecard.md` as
  `agent_allowed=no, evaluator-only`; the six-run prompt forbids opening them and requires the final
  answer to state which evaluator-only files were skipped. Run-003 (contaminated) stays score-excluded.
- **Glob host-path quirk (methodology note for the next agent).** Against the Windows repo path,
  `Glob(pattern="docs/harness/**")` returned "No files found"; the working form is an explicit `path`
  argument plus a relative pattern, e.g. `Glob(pattern="**/*", path="D:\\…\\synthetic-batch-record-v1")`.
  Same failure mode the vault-mount note already records — treat literal multi-segment patterns as
  unreliable on both mounts.

User-trust read (from accumulated evidence, the question "can a real user trust this feature"):

| Trust axis | Current state | Verdict |
|------------|---------------|---------|
| Progress clarity | `tool_start` intent labels + workflow panel exist; long waits get `TOOL_WAIT` narration. Not yet validated under a full live GMP run. | Probably OK, unverified live |
| Error/429/interrupt recovery | 429 kills the run with no retry/resume; only generic `ev.ERROR`. | **Weak — fix needed** |
| Result re-check / scroll | Result-Reading Method (read vault `{thread_id}.md`) works for evaluators; end-user in-chat re-scroll of a long report not yet stress-tested. | Partial |
| Obsidian path retry | Baseline run-003 failed a bare-relative `list_directory` and did **not** retry with the qualified path (FIND-007 friction). | **Weak — fix needed** |
| Harness false-pass reduction | Executor-error→pass closed; genuine evidence-quality lift still needs live Phase 4 numbers (`final_passed` etc. were trivially `true` in plumbing runs). | Unproven on real evidence |

## Result Tables

- GMP procedure/results: `docs/harness/cards/gmp-validation-eval-procedure.md`
- Priority rollup: `docs/DEV_ROADMAP_2026-06.md`

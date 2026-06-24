# Synthetic GMP Validation Evaluation Prompt

Use the synthetic fixture folder `docs/harness/fixtures/gmp-validation/synthetic-batch-record-v1/`.

Do not read or use evaluator-only files: `scorecard.md`, `expected/findings_manifest.csv`, or any `tests/fixtures/gmp_validation/**/expected_findings.csv` mirror. If you notice one of these paths in an inventory, mark it as excluded and continue without opening it. Your final answer must state which evidence files you actually inspected and which evaluator-only files you deliberately skipped.

Do not assume file roles from filenames alone. First make an inventory and infer each file's likely role, reliability, and limitations from its content.

Evaluate the synthetic batch record validation package. Build a partial traceability matrix across requirement-like, design-like, RTM-like, protocol-like, evidence-like, summary-like, and knowledge-note artifacts.

Classify each item as `verified / unverified / mismatch / question / out-of-scope`. Mark any protocol or summary pass claim with weak evidence as a false pass risk.

Search the simulated Obsidian notes in `obsidian/` and explain whether each note is current, stale, or conflicting. Propose what should be written to an Obsidian handoff note after the run.

Record Computer Use or fallback UX observations: document-finding friction, progress visibility, question timing, waiting, screen switching, and error recovery. If Computer Use is not available, say what fallback was used and what could not be observed.

Ask concrete user questions for uncertain judgments, such as whether a draft design should be treated as current, whether a weak evidence row can support OQ, or whether a requirement is GMP critical.

Do not edit original fixture files during the run.

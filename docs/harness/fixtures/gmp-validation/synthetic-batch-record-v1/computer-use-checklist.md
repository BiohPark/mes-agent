# Computer Use Checklist For Synthetic GMP Evaluation

## Preferred UI Path

1. Start MES Agent locally.
2. Open the Electron chat UI.
3. Create or select a `gmp-validation` thread.
4. Provide the exact prompt from `prompts/six-run-prompt.md`.
5. Observe whether the agent starts the 7-step workflow.
6. Observe how the agent asks for source scope, read-only boundaries, and uncertainty confirmation.
7. Observe how the agent reports progress while reading fixture files.
8. Observe final report sections and whether evidence gaps are easy to inspect.

## Friction Signals To Record

| Signal | What to record |
|--------|----------------|
| document-finding friction | Did the user have to explain the fixture path repeatedly? |
| progress visibility | Could the user tell which artifact was being read or analyzed? |
| question timing | Were questions concrete and timed after evidence inspection? |
| waiting | Were long waits explained with status updates? |
| screen switching | Did the workflow require awkward switching between app, file browser, and browser? |
| error recovery | Did the agent explain failed reads or unavailable UI automation clearly? |

## Fallback REST Observation

Use fallback REST observation when Computer Use is unavailable, local UI launch fails, or permissions block screen control. Record the reason and run the same prompt through `/chat`; then score only what REST can prove. REST fallback cannot prove screen switching, visual progress, or click-level friction.

## Approval Boundaries

This synthetic fixture is read-only. Do not edit fixture files during evaluation. Do not write an actual Obsidian note unless the user approves a synthetic note write location.

## Result-Reading Method (Evaluator), added 2026-06-24

Do not score a run by screenshotting and scrolling the chat panel. The agent's full report and the
raw message sequence are already persisted to the vault and can be read directly:

- Human-readable report + embedded raw transcript: `<OBSIDIAN_VAULT_PATH>/agent/threads/{task_type}/{thread_id}.md`
  (the file ends with a fenced ` ```agent-messages ` JSON block containing the literal
  system/user/assistant/tool message sequence — read this if you need to verify exactly which tool
  calls happened, not just the polished summary).
- Raw JSONL transcript (if needed separately): `<OBSIDIAN_VAULT_PATH>/agent/transcripts/{task_type}/{thread_id}.jsonl`.
- Locating the file: a literal multi-segment `Glob` pattern like `agent/threads/gmp-validation/*`
  has been observed to return "No files found" against this vault mount even when the file exists at
  that exact path. Use a recursive pattern instead, e.g. `Glob(pattern="**/threads/**", path=<vault>)`.

This applies to any agent (including a future Computer-Use verifying/Reviewer agent) that needs to
read a completed run's output — reading the vault file is faster, complete, and avoids missing
content that scrolled out of a screenshot.

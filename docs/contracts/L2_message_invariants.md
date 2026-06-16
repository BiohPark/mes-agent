# L2 Message Invariants

Status: implemented seed for Track 1C.

## Purpose

The conversation history has three separate responsibilities:

- LLM buffer: API-safe working messages used to resume and call the model.
- Display transcript: user-visible user/assistant conversation reconstructed for active and archived thread views.
- Audit/run ledger: execution status and tool audit events. It is not the raw conversation transcript.

This separation prevents compaction from erasing old visible conversation while keeping OpenAI message invariants intact.

## LLM Buffer Rules

- Stored in the thread markdown `agent-messages` block.
- May be compacted and pruned for context-window safety.
- Must never contain private `_ephemeral` metadata when sent to the LLM.
- Must preserve the assistant `tool_calls` and following `tool` message pairing invariant.
- Runtime-only control messages may affect the active run but must be filtered before persistence.

## Display Transcript Rules

- Stored as append-only JSONL under `agent/transcripts/<task_type>/<thread_id>.jsonl`.
- Active and archived thread display, message counts, and search snippets prefer this transcript when it exists.
- If no transcript exists, display falls back to filtered legacy `agent-messages`.
- Only visible `user` and `assistant` text is reconstructed.
- Legacy polluted user messages beginning with `[시스템]` or `[사용자 끼어들기]` are hidden.

## Audit Rules

- RunLedger remains for execution lifecycle events such as stopped, max_steps, error, and done.
- RunLedger is not expanded into raw conversation storage in this seed.
- Tool results, credentials, base64 images, and large binary payloads are not written into the display transcript.
- Multimodal messages keep text blocks and replace images with an omission placeholder.

## Compaction Rules

- Compaction may rewrite the LLM buffer.
- Before and after compaction, visible user/assistant turns already written to the display transcript remain available for display/search.
- Compaction summaries are written as assistant-visible transcript events so users can see when older context was summarized.

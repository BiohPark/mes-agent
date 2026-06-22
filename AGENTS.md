# MES Agent — AI Agent Orientation

This file is a brief orientation for **any AI coding assistant** (GitHub Copilot Workspace, Devin, OpenAI Codex, etc.) working on this codebase.

> **Using Claude Code?** Read `CLAUDE.md` instead — it contains the full implementation state, tool count, auto-update rules, and detailed architecture. This file just points the way.

---

## What This Is

A Windows desktop automation agent running in a **closed corporate network (폐쇄망)**.
Users give natural language instructions; the agent controls the screen, browser, keyboard/mouse, and documents.

- **Backend**: Python FastAPI server (`agent/server.py`)
- **Frontend**: Electron app (`electron/`)
- **LLM**: OpenAI-compatible REST API (switchable between internal/external via `.env`)

---

## Key Entry Points

| File | Role |
|------|------|
| `agent/server.py` | Main agent loop (`generate()`), all API endpoints |
| `agent/tools/__init__.py` | Auto-discovery tool registry (do NOT edit manually) |
| `agent/tools/*.py` | Individual tools — add `MANIFEST` list to register |
| `agent/obsidian_session.py` | Thread/session management + TASK_CONFIGS |
| `electron/renderer/chat.js` | Frontend chat + SSE streaming |

---

## Adding a New Tool

1. Create `agent/tools/mymodule.py` with a `MANIFEST` list (see `CONTRIBUTING.md` for schema)
2. The tool is **automatically registered** at server startup — no other files needed
3. Update `CLAUDE.md` current-state table and `CONTRIBUTING.md` tool list
4. Update `tests/smoke/test_tool_schemas.py::EXPECTED_TOOL_COUNT`

---

## Critical Constraints

- **Tool limit**: LLM API accepts max 128 tools. `select_tools()` in `agent/tools/__init__.py` manages this automatically.
- **Windows only**: Uses `pywin32`, `pyautogui`, COM automation — Linux/macOS will break.
- **Closed network**: No external package downloads during runtime. All deps must be pre-installed.
- **Tool pair invariant**: Every `assistant` message with `tool_calls` must be followed by matching `tool` messages (OpenAI API requirement). The compaction and safety gate code preserves this.

---

## Test Suite

```powershell
.\test.ps1          # Full test suite (268 tests)
.\test.ps1 ci       # CI-safe subset (no LLM, no display, no Office)
.\test.ps1 unit     # Unit tests only
.\test.ps1 smoke    # Tool registry validation
```

Tests are in `tests/unit/`, `tests/integration/`, `tests/smoke/`.

---

## Multi-CLI Delegation

This project is developed using Codex, Claude Code, and agy CLIs together. Each supports a
non-interactive single-shot mode and can delegate work to either of the others as a subprocess.
Verified commands/flags and safety rules (always try minimal-privilege sandbox/approval modes
first; never self-escalate to `--dangerously-*` bypass flags — stop and ask the user instead) are
documented in `docs/harness/a2a-cli-delegation.md`. Only delegate when the user explicitly asks for
it.

## More Detail

- Full architecture, tool list, implementation state → `CLAUDE.md`
- Tool development guide → `CONTRIBUTING.md`
- ADRs (architectural decisions) → `docs/adr/`
- Pending features → `docs/backlog/pending/`

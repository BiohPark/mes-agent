"""MCP 클라이언트 단위 테스트 (백로그 J) — 실서버·mcp SDK 불요(순수+모킹)."""

import json

import pytest

from agent import mcp_client as mc
from agent.tools import _registry, TOOLS, TOOL_LABELS, register_tool, tool_risk_hint, select_tools
from agent.tools._safety import classify_risk


# ── 도구 descriptor (dict / 객체 양쪽) ────────────────────────
class _ToolObj:
    def __init__(self, name, description, inputSchema, annotations=None):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema
        self.annotations = annotations


def _calls_recorder():
    calls = []
    return calls, (lambda s, n, a: calls.append((s, n, a)) or "OK")


# ── mcp_tool_to_manifest ──────────────────────────────────────
def test_manifest_from_dict_tool():
    calls, fn = _calls_recorder()
    m = mc.mcp_tool_to_manifest("oracle", {
        "name": "run_query", "description": "SQL 실행",
        "inputSchema": {"type": "object", "properties": {"sql": {"type": "string"}}},
        "annotations": {"readOnlyHint": True},
    }, fn)
    assert m["name"] == "mcp_oracle_run_query"
    assert m["schema"]["function"]["name"] == "mcp_oracle_run_query"
    assert "[MCP oracle]" in m["schema"]["function"]["description"]
    assert m["_module"] == "mcp"
    assert m["_risk"] == "safe"  # readOnlyHint=True
    m["handler"]({"sql": "SELECT 1"})
    assert calls == [("oracle", "run_query", {"sql": "SELECT 1"})]


def test_manifest_from_object_tool_write_is_mutate():
    _, fn = _calls_recorder()
    m = mc.mcp_tool_to_manifest("oracle", _ToolObj(
        "insert_row", "행 삽입", {"type": "object", "properties": {}}, annotations={"readOnlyHint": False},
    ), fn)
    assert m["_risk"] == "mutate"  # 쓰기 → 확인 게이트


def test_manifest_no_annotations_defaults_mutate():
    _, fn = _calls_recorder()
    m = mc.mcp_tool_to_manifest("srv", {"name": "x", "description": "", "inputSchema": {}}, fn)
    assert m["_risk"] == "mutate"  # hint 없으면 보수적


def test_ensure_object_schema_fixes_missing_type():
    out = mc._ensure_object_schema({"properties": {"a": {"type": "string"}}})
    assert out["type"] == "object"
    assert mc._ensure_object_schema(None) == {"type": "object", "properties": {}}


def test_load_config_missing_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CONFIG", str(tmp_path / "nope.json"))
    assert mc._load_config() == {}


def test_load_config_reads_servers(monkeypatch, tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"servers": {"oracle": {"command": "python"}}}), encoding="utf-8")
    monkeypatch.setenv("MCP_CONFIG", str(cfg))
    assert "oracle" in mc._load_config()


def test_serialize_text_blocks():
    class _Block:
        def __init__(self, t): self.text = t
    class _Result:
        content = [_Block("row1"), _Block("row2")]
    assert mc._serialize(_Result()) == "row1\nrow2"


def test_connect_all_no_config_is_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_CONFIG", str(tmp_path / "absent.json"))
    mgr = mc.MCPManager()
    assert mgr.connect_all() == 0
    assert mgr._thread is None  # 스레드 미기동(누수 방지)


# ── register_tool / tool_risk_hint (tools/__init__) ───────────
def test_register_tool_in_place_and_selectable():
    name = "mcp_test_ping"
    _registry.pop(name, None)
    before = len(TOOLS)
    register_tool({
        "name": name, "label": "MCP:test/ping", "_module": "mcp", "_risk": "safe",
        "schema": {"type": "function", "function": {"name": name, "description": "p",
                   "parameters": {"type": "object", "properties": {}}}},
        "handler": lambda a: "pong",
    })
    try:
        assert name in _registry
        assert len(TOOLS) == before + 1            # in-place append
        assert TOOL_LABELS[name] == "MCP:test/ping"
        register_tool(_registry[name])             # 재등록은 중복 추가 안 함
        assert len(TOOLS) == before + 1
        assert tool_risk_hint(name) == "safe"
        # select_tools 결과에 포함 가능(core권 mcp)
        names = {s["function"]["name"] for s in select_tools()}
        assert name in names
    finally:
        _registry.pop(name, None)
        TOOLS[:] = [s for s in TOOLS if s["function"]["name"] != name]
        TOOL_LABELS.pop(name, None)


# ── classify_risk(risk_hint) ──────────────────────────────────
def test_risk_hint_overrides_name_heuristic():
    # 이름상으로는 safe 기본이지만 hint=mutate면 mutate
    assert classify_risk("mcp_oracle_run_query", {}, None, "mutate") == "mutate"
    assert classify_risk("mcp_oracle_run_query", {}, None, "safe") == "safe"


def test_allowlist_beats_risk_hint():
    # "항상 허용"은 hint보다 우선
    assert classify_risk("mcp_oracle_drop", {}, {"mcp_oracle_drop"}, "destructive") == "safe"

"""워크플로우 그래프 스토리지 단위 테스트 (Phase 1 — PR 1-B).

기존 test_workflow_storage.py는 건드리지 않으며 새 함수만 검증한다.
"""

import json
import pytest
from agent.workflow.model import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowConnection,
    WorkflowRunState,
    Workflow,
    WorkflowStep,
)
from agent.workflow.storage import (
    detect_format,
    load_definition,
    save_definition,
    load_run_state,
    save_run_state,
    load_workflow,
)


# ── 헬퍼 ────────────────────────────────────────────────────

def _defn(tid="t1", task_type="general"):
    return WorkflowDefinition(
        id=tid, task_type=task_type, title="테스트",
        nodes=[
            WorkflowNode(id="n1", title="노드1"),
            WorkflowNode(id="n2", title="노드2"),
        ],
        connections=[WorkflowConnection(from_node="n1", to_node="n2")],
    )


def _linear_data(tid="t1"):
    return {
        "thread_id": tid, "task_type": "general", "title": "선형",
        "steps": [
            {"id": "s1", "title": "단계1", "type": "auto", "status": "done", "notes": "ok", "max_retry": 0},
            {"id": "s2", "title": "단계2", "type": "auto", "status": "pending", "notes": "", "max_retry": 0},
        ],
    }


# ── TestDetectFormat ─────────────────────────────────────────

class TestDetectFormat:
    def test_linear_format_detected(self):
        assert detect_format({"steps": []}) == "linear"

    def test_graph_format_detected(self):
        assert detect_format({"nodes": [], "connections": []}) == "graph"

    def test_graph_format_detected_nodes_only(self):
        assert detect_format({"nodes": []}) == "graph"

    def test_unknown_format_defaults_linear(self):
        assert detect_format({"title": "w"}) == "linear"

    def test_empty_dict_defaults_linear(self):
        assert detect_format({}) == "linear"


# ── TestLoadDefinition ───────────────────────────────────────

class TestLoadDefinition:
    def test_returns_workflow_definition(self, vault):
        defn = load_definition("general", "thread-x")
        assert isinstance(defn, WorkflowDefinition)

    def test_creates_default_when_no_file(self, vault):
        defn = load_definition("general", "new-thread")
        assert len(defn.nodes) > 0

    def test_default_creates_sequential_connections(self, vault):
        defn = load_definition("general", "conn-thread")
        assert len(defn.connections) == len(defn.nodes) - 1

    def test_default_connection_chain(self, vault):
        defn = load_definition("general", "chain-thread")
        for i, conn in enumerate(defn.connections):
            assert conn.from_node == defn.nodes[i].id
            assert conn.to_node == defn.nodes[i + 1].id

    def test_load_definition_from_saved_graph_format(self, vault):
        defn = _defn(tid="saved-t")
        save_definition(defn)
        loaded = load_definition("general", "saved-t")
        assert loaded.id == "saved-t"
        assert len(loaded.nodes) == 2
        assert loaded.connections[0].from_node == "n1"

    def test_load_definition_auto_migrates_linear_format(self, vault):
        """구 형식(steps) 파일을 읽으면 자동으로 WorkflowDefinition으로 변환한다."""
        import os
        wf_dir = vault / "agent" / "workflows" / "general"
        wf_dir.mkdir(parents=True, exist_ok=True)
        path = wf_dir / "legacy-t.json"
        path.write_text(json.dumps(_linear_data("legacy-t")), encoding="utf-8")

        defn = load_definition("general", "legacy-t")
        assert isinstance(defn, WorkflowDefinition)
        assert defn.id == "legacy-t"
        assert len(defn.nodes) == 2
        assert defn.nodes[0].id == "s1"

    def test_auto_migrate_preserves_connections(self, vault):
        """선형→그래프 자동 마이그레이션 후 연결이 순서대로 생성된다."""
        import os
        wf_dir = vault / "agent" / "workflows" / "general"
        wf_dir.mkdir(parents=True, exist_ok=True)
        path = wf_dir / "migr-t.json"
        path.write_text(json.dumps(_linear_data("migr-t")), encoding="utf-8")

        defn = load_definition("general", "migr-t")
        assert len(defn.connections) == 1
        assert defn.connections[0].from_node == "s1"
        assert defn.connections[0].to_node == "s2"

    def test_all_task_types_have_defaults(self, vault):
        for tt in ("general", "syncade", "obsidian-rag", "unscript", "knox"):
            defn = load_definition(tt, f"t-{tt}")
            assert len(defn.nodes) > 0, f"{tt}: 기본 노드 없음"


# ── TestSaveDefinition ───────────────────────────────────────

class TestSaveDefinition:
    def test_save_creates_file(self, vault):
        defn = _defn(tid="save-test")
        save_definition(defn)
        path = vault / "agent" / "workflows" / "general" / "save-test.json"
        assert path.exists()

    def test_saved_file_is_graph_format(self, vault):
        defn = _defn(tid="fmt-test")
        save_definition(defn)
        path = vault / "agent" / "workflows" / "general" / "fmt-test.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "nodes" in data
        assert "connections" in data

    def test_roundtrip(self, vault):
        defn = _defn(tid="rt-test")
        save_definition(defn)
        loaded = load_definition("general", "rt-test")
        assert loaded.title == defn.title
        assert loaded.nodes[0].title == "노드1"
        assert loaded.connections[0].to_node == "n2"

    def test_no_vault_is_noop(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        defn = _defn(tid="noop-test")
        save_definition(defn)  # 오류 없이 종료되어야 함


# ── TestRunState 스토리지 ─────────────────────────────────────

class TestRunStateStorage:
    def test_load_returns_none_when_no_file(self, vault):
        rs = load_run_state("general", "no-state-t")
        assert rs is None

    def test_save_and_load_roundtrip(self, vault):
        rs = WorkflowRunState(definition_id="rs-t")
        rs.set_node_status("n1", "done", notes="완료")
        rs.set_node_status("n2", "running")
        save_run_state("general", "rs-t", rs)

        loaded = load_run_state("general", "rs-t")
        assert loaded is not None
        assert loaded.definition_id == "rs-t"
        assert loaded.node_states["n1"].status == "done"
        assert loaded.node_states["n2"].status == "running"

    def test_save_no_vault_is_noop(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        rs = WorkflowRunState(definition_id="x")
        save_run_state("general", "x", rs)  # 오류 없이 종료


# ── TestBackwardCompat ───────────────────────────────────────

class TestBackwardCompat:
    def test_load_workflow_handles_graph_format(self, vault):
        """새 포맷(nodes)으로 저장된 파일을 load_workflow가 읽을 수 있어야 한다."""
        defn = _defn(tid="compat-t")
        save_definition(defn)

        wf = load_workflow("general", "compat-t")
        assert isinstance(wf, Workflow)
        assert len(wf.steps) == 2
        assert wf.steps[0].id == "n1"
        assert wf.steps[0].title == "노드1"

    def test_load_workflow_with_run_state_preserves_status(self, vault):
        """새 포맷 + RunState 저장 후 load_workflow가 올바른 status를 반환해야 한다."""
        defn = _defn(tid="status-t")
        save_definition(defn)

        rs = WorkflowRunState(definition_id="status-t")
        rs.set_node_status("n1", "done", notes="ok")
        rs.set_node_status("n2", "running")
        save_run_state("general", "status-t", rs)

        wf = load_workflow("general", "status-t")
        steps_by_id = {s.id: s for s in wf.steps}
        assert steps_by_id["n1"].status == "done"
        assert steps_by_id["n2"].status == "running"

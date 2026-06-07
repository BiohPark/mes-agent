"""워크플로우 툴 단위 테스트 — Phase 1 완결 (그래프 모델 내부 전환 검증).

각 툴이 내부적으로 WorkflowDefinition + WorkflowRunState를 사용하고
프론트엔드 하위 호환(steps[] 형식)을 유지하는지 확인한다.
"""

import json
import pytest
from agent.workflow import storage as wf_storage
from agent.workflow.model import WorkflowDefinition, WorkflowRunState


def _call_init(task_type, thread_id, title, steps):
    from agent.tools.workflow import _workflow_init
    return json.loads(_workflow_init(task_type, thread_id, title, steps))


def _call_set_step(task_type, thread_id, step_id, status, notes=""):
    from agent.tools.workflow import _workflow_set_step
    return json.loads(_workflow_set_step(task_type, thread_id, step_id, status, notes))


def _call_add_step(task_type, thread_id, title, type_="auto", after_step_id=""):
    from agent.tools.workflow import _workflow_add_step
    return json.loads(_workflow_add_step(task_type, thread_id, title, type_, after_step_id))


def _call_update_step(task_type, thread_id, step_id, title="", type_=""):
    from agent.tools.workflow import _workflow_update_step
    return json.loads(_workflow_update_step(task_type, thread_id, step_id, title, type_))


def _call_remove_step(task_type, thread_id, step_id):
    from agent.tools.workflow import _workflow_remove_step
    return json.loads(_workflow_remove_step(task_type, thread_id, step_id))


def _call_reorder(task_type, thread_id, ordered_ids):
    from agent.tools.workflow import _workflow_reorder
    return json.loads(_workflow_reorder(task_type, thread_id, ordered_ids))


_TT = "general"
_TID = "tool-test-thread"


# ── workflow_init ─────────────────────────────────────────────────────

class TestWorkflowInit:
    def test_returns_ok(self, vault):
        r = _call_init(_TT, _TID, "제목", [{"title": "1단계"}, {"title": "2단계"}])
        assert r["ok"] is True

    def test_returns_steps_format_for_frontend(self, vault):
        """프론트엔드 호환: 반환값에 steps[] 포함."""
        r = _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "B"}])
        assert "steps" in r["workflow"]
        assert len(r["workflow"]["steps"]) == 2

    def test_saves_graph_format_definition(self, vault):
        """내부 저장은 그래프 포맷(nodes 키)이어야 한다."""
        _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "B"}])
        defn = wf_storage.load_definition(_TT, _TID)
        assert isinstance(defn, WorkflowDefinition)
        assert len(defn.nodes) == 2

    def test_saves_run_state(self, vault):
        """RunState 파일이 생성되어야 한다."""
        _call_init(_TT, _TID, "제목", [{"title": "A"}])
        rs = wf_storage.load_run_state(_TT, _TID)
        assert rs is not None

    def test_initial_run_state_is_pending(self, vault):
        _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "B"}])
        rs = wf_storage.load_run_state(_TT, _TID)
        for node_id, ns in rs.node_states.items():
            assert ns.status == "pending"

    def test_creates_sequential_connections(self, vault):
        _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "B"}, {"title": "C"}])
        defn = wf_storage.load_definition(_TT, _TID)
        assert len(defn.connections) == 2
        assert defn.connections[0].from_node == defn.nodes[0].id
        assert defn.connections[0].to_node == defn.nodes[1].id

    def test_step_type_preserved(self, vault):
        _call_init(_TT, _TID, "제목", [{"title": "수동", "type": "manual"}])
        defn = wf_storage.load_definition(_TT, _TID)
        assert defn.nodes[0].type == "manual"


# ── workflow_set_step ─────────────────────────────────────────────────

class TestWorkflowSetStep:
    def _init(self, vault):
        r = _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "B"}])
        step_ids = [s["id"] for s in r["workflow"]["steps"]]
        return step_ids

    def test_returns_ok(self, vault):
        ids = self._init(vault)
        r = _call_set_step(_TT, _TID, ids[0], "running")
        assert r["ok"] is True

    def test_status_reflected_in_steps(self, vault):
        ids = self._init(vault)
        r = _call_set_step(_TT, _TID, ids[0], "done", "완료")
        steps_by_id = {s["id"]: s for s in r["workflow"]["steps"]}
        assert steps_by_id[ids[0]]["status"] == "done"
        assert steps_by_id[ids[0]]["notes"] == "완료"

    def test_definition_unchanged(self, vault):
        """C3 불변성: set_step 이후 Definition 파일의 nodes가 변경되지 않아야 한다."""
        ids = self._init(vault)
        defn_before = wf_storage.load_definition(_TT, _TID)
        _call_set_step(_TT, _TID, ids[0], "running")
        defn_after = wf_storage.load_definition(_TT, _TID)
        assert [n.id for n in defn_after.nodes] == [n.id for n in defn_before.nodes]
        assert [n.title for n in defn_after.nodes] == [n.title for n in defn_before.nodes]

    def test_run_state_updated(self, vault):
        """RunState 파일에 상태가 반영되어야 한다."""
        ids = self._init(vault)
        _call_set_step(_TT, _TID, ids[1], "error", "실패")
        rs = wf_storage.load_run_state(_TT, _TID)
        assert rs.node_states[ids[1]].status == "error"
        assert rs.node_states[ids[1]].notes == "실패"

    def test_unknown_step_id_returns_error(self, vault):
        self._init(vault)
        r = _call_set_step(_TT, _TID, "nonexistent-id", "done")
        assert r["ok"] is False


# ── workflow_add_step ─────────────────────────────────────────────────

class TestWorkflowAddStep:
    def _init(self, vault):
        r = _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "C"}])
        return [s["id"] for s in r["workflow"]["steps"]]

    def test_returns_ok(self, vault):
        self._init(vault)
        r = _call_add_step(_TT, _TID, "B", after_step_id="")
        assert r["ok"] is True

    def test_appends_to_end_by_default(self, vault):
        self._init(vault)
        r = _call_add_step(_TT, _TID, "D")
        assert r["workflow"]["steps"][-1]["title"] == "D"

    def test_inserts_after_given_step(self, vault):
        ids = self._init(vault)
        r = _call_add_step(_TT, _TID, "B", after_step_id=ids[0])
        titles = [s["title"] for s in r["workflow"]["steps"]]
        assert titles == ["A", "B", "C"]

    def test_definition_has_new_node(self, vault):
        self._init(vault)
        _call_add_step(_TT, _TID, "D")
        defn = wf_storage.load_definition(_TT, _TID)
        titles = [n.title for n in defn.nodes]
        assert "D" in titles

    def test_connections_rebuilt_sequentially(self, vault):
        ids = self._init(vault)
        _call_add_step(_TT, _TID, "B", after_step_id=ids[0])
        defn = wf_storage.load_definition(_TT, _TID)
        assert len(defn.connections) == 2
        for i, conn in enumerate(defn.connections):
            assert conn.from_node == defn.nodes[i].id
            assert conn.to_node == defn.nodes[i + 1].id

    def test_new_node_pending_in_run_state(self, vault):
        self._init(vault)
        r = _call_add_step(_TT, _TID, "D")
        new_id = r["workflow"]["steps"][-1]["id"]
        rs = wf_storage.load_run_state(_TT, _TID)
        assert rs.node_states[new_id].status == "pending"


# ── workflow_update_step ──────────────────────────────────────────────

class TestWorkflowUpdateStep:
    def _init(self, vault):
        r = _call_init(_TT, _TID, "제목", [{"title": "A", "type": "auto"}])
        return r["workflow"]["steps"][0]["id"]

    def test_returns_ok(self, vault):
        sid = self._init(vault)
        r = _call_update_step(_TT, _TID, sid, title="새 제목")
        assert r["ok"] is True

    def test_title_updated_in_definition(self, vault):
        sid = self._init(vault)
        _call_update_step(_TT, _TID, sid, title="새 제목")
        defn = wf_storage.load_definition(_TT, _TID)
        assert defn.nodes[0].title == "새 제목"

    def test_type_updated_in_definition(self, vault):
        sid = self._init(vault)
        _call_update_step(_TT, _TID, sid, type_="manual")
        defn = wf_storage.load_definition(_TT, _TID)
        assert defn.nodes[0].type == "manual"

    def test_run_state_not_affected(self, vault):
        """update_step은 RunState를 변경하지 않는다."""
        sid = self._init(vault)
        _call_set_step(_TT, _TID, sid, "running")
        _call_update_step(_TT, _TID, sid, title="새 제목")
        rs = wf_storage.load_run_state(_TT, _TID)
        assert rs.node_states[sid].status == "running"

    def test_unknown_id_returns_error(self, vault):
        self._init(vault)
        r = _call_update_step(_TT, _TID, "bad-id", title="X")
        assert r["ok"] is False


# ── workflow_remove_step ──────────────────────────────────────────────

class TestWorkflowRemoveStep:
    def _init(self, vault):
        r = _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "B"}, {"title": "C"}])
        return [s["id"] for s in r["workflow"]["steps"]]

    def test_returns_ok(self, vault):
        ids = self._init(vault)
        r = _call_remove_step(_TT, _TID, ids[1])
        assert r["ok"] is True

    def test_node_removed_from_definition(self, vault):
        ids = self._init(vault)
        _call_remove_step(_TT, _TID, ids[1])
        defn = wf_storage.load_definition(_TT, _TID)
        assert len(defn.nodes) == 2
        assert all(n.id != ids[1] for n in defn.nodes)

    def test_connections_rebuilt_after_removal(self, vault):
        ids = self._init(vault)
        _call_remove_step(_TT, _TID, ids[1])
        defn = wf_storage.load_definition(_TT, _TID)
        assert len(defn.connections) == 1
        assert defn.connections[0].from_node == ids[0]
        assert defn.connections[0].to_node == ids[2]

    def test_removed_node_not_in_steps(self, vault):
        ids = self._init(vault)
        r = _call_remove_step(_TT, _TID, ids[1])
        step_ids = [s["id"] for s in r["workflow"]["steps"]]
        assert ids[1] not in step_ids

    def test_unknown_id_returns_error(self, vault):
        self._init(vault)
        r = _call_remove_step(_TT, _TID, "bad-id")
        assert r["ok"] is False


# ── workflow_reorder ──────────────────────────────────────────────────

class TestWorkflowReorder:
    def _init(self, vault):
        r = _call_init(_TT, _TID, "제목", [{"title": "A"}, {"title": "B"}, {"title": "C"}])
        return [s["id"] for s in r["workflow"]["steps"]]

    def test_returns_ok(self, vault):
        ids = self._init(vault)
        r = _call_reorder(_TT, _TID, [ids[2], ids[0], ids[1]])
        assert r["ok"] is True

    def test_order_changed_in_steps(self, vault):
        ids = self._init(vault)
        r = _call_reorder(_TT, _TID, [ids[2], ids[0], ids[1]])
        result_ids = [s["id"] for s in r["workflow"]["steps"]]
        assert result_ids[:3] == [ids[2], ids[0], ids[1]]

    def test_order_changed_in_definition(self, vault):
        ids = self._init(vault)
        _call_reorder(_TT, _TID, [ids[2], ids[1], ids[0]])
        defn = wf_storage.load_definition(_TT, _TID)
        assert [n.id for n in defn.nodes] == [ids[2], ids[1], ids[0]]

    def test_connections_rebuilt_after_reorder(self, vault):
        ids = self._init(vault)
        _call_reorder(_TT, _TID, [ids[2], ids[1], ids[0]])
        defn = wf_storage.load_definition(_TT, _TID)
        assert defn.connections[0].from_node == ids[2]
        assert defn.connections[0].to_node == ids[1]
        assert defn.connections[1].from_node == ids[1]
        assert defn.connections[1].to_node == ids[0]

    def test_missing_ids_appended_at_end(self, vault):
        """ordered_ids에 없는 기존 단계는 끝에 보존된다."""
        ids = self._init(vault)
        r = _call_reorder(_TT, _TID, [ids[1]])
        result_ids = [s["id"] for s in r["workflow"]["steps"]]
        assert ids[1] == result_ids[0]
        assert ids[0] in result_ids
        assert ids[2] in result_ids

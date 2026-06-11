"""WorkflowDefinition / WorkflowRunState 새 그래프 모델 단위 테스트 (Phase 1 — PR 1-A).

기존 Workflow·WorkflowStep 코드는 건드리지 않으며 새 클래스만 검증한다.
"""

import pytest
from agent.workflow.model import (
    WorkflowNode,
    WorkflowConnection,
    WorkflowDefinition,
    NodeState,
    WorkflowRunState,
    migrate_linear_to_graph,
    Workflow,
    WorkflowStep,
)


# ── 헬퍼 ────────────────────────────────────────────────────

def _node(id="n1", title="단계", type="auto", retry=0, on_error="stop"):
    return WorkflowNode(id=id, title=title, type=type, retry=retry, on_error=on_error)


def _conn(from_node="n1", to_node="n2", from_output=0):
    return WorkflowConnection(from_node=from_node, to_node=to_node, from_output=from_output)


def _defn(nodes=None, connections=None):
    return WorkflowDefinition(
        id="thread-001",
        task_type="general",
        title="테스트 정의",
        nodes=nodes or [_node()],
        connections=connections or [],
    )


def _linear_wf(n=3):
    steps = [WorkflowStep(id=f"s{i}", title=f"단계{i}", type="auto", status="pending") for i in range(1, n + 1)]
    return Workflow(thread_id="t1", task_type="general", title="선형 워크플로우", steps=steps)


# ── WorkflowNode ─────────────────────────────────────────────

class TestWorkflowNode:
    def test_defaults(self):
        n = WorkflowNode(id="x", title="t")
        assert n.type == "auto"
        assert n.retry == 0
        assert n.on_error == "stop"

    def test_condition_type(self):
        n = WorkflowNode(id="x", title="분기", type="condition")
        assert n.type == "condition"

    def test_on_error_continue(self):
        n = WorkflowNode(id="x", title="t", on_error="continue")
        assert n.on_error == "continue"

    def test_retry_positive(self):
        n = WorkflowNode(id="x", title="t", retry=3)
        assert n.retry == 3

    def test_to_dict_keys(self):
        d = _node().to_dict()
        assert set(d.keys()) == {"id", "title", "type", "retry", "on_error", "group"}

    def test_group_default_empty(self):
        assert WorkflowNode(id="x", title="t").group == ""

    def test_group_roundtrip(self):
        n = WorkflowNode(id="n1", title="t", group="배포 준비")
        restored = WorkflowNode.from_dict(n.to_dict())
        assert restored.group == "배포 준비"

    def test_group_backcompat_missing_key(self):
        # group 키 없는 기존 정의도 로드 가능해야 한다
        n = WorkflowNode.from_dict({"id": "x", "title": "t", "type": "auto", "retry": 0, "on_error": "stop"})
        assert n.group == ""

    def test_to_dict_values(self):
        n = WorkflowNode(id="abc", title="확인", type="semi_auto", retry=2, on_error="continue")
        d = n.to_dict()
        assert d["id"] == "abc"
        assert d["retry"] == 2
        assert d["on_error"] == "continue"

    def test_from_dict_roundtrip(self):
        n = WorkflowNode(id="n9", title="배포", type="manual", retry=1, on_error="stop")
        restored = WorkflowNode.from_dict(n.to_dict())
        assert restored.id == "n9"
        assert restored.retry == 1
        assert restored.type == "manual"

    def test_from_dict_missing_fields_default(self):
        n = WorkflowNode.from_dict({"id": "x", "title": "t"})
        assert n.type == "auto"
        assert n.retry == 0
        assert n.on_error == "stop"


# ── WorkflowConnection ───────────────────────────────────────

class TestWorkflowConnection:
    def test_defaults(self):
        c = WorkflowConnection(from_node="n1", to_node="n2")
        assert c.from_output == 0

    def test_branch_outputs(self):
        c_true = WorkflowConnection(from_node="n1", to_node="n2", from_output=1)
        c_false = WorkflowConnection(from_node="n1", to_node="n3", from_output=2)
        assert c_true.from_output == 1
        assert c_false.from_output == 2

    def test_to_dict_keys(self):
        d = _conn().to_dict()
        assert set(d.keys()) == {"from_node", "to_node", "from_output"}

    def test_from_dict_roundtrip(self):
        c = WorkflowConnection(from_node="a", to_node="b", from_output=1)
        r = WorkflowConnection.from_dict(c.to_dict())
        assert r.from_node == "a"
        assert r.from_output == 1


# ── WorkflowDefinition ───────────────────────────────────────

class TestWorkflowDefinition:
    def test_to_dict_top_level_keys(self):
        d = _defn().to_dict()
        assert set(d.keys()) == {"id", "task_type", "title", "nodes", "connections"}

    def test_to_dict_nodes_serialized(self):
        defn = _defn(nodes=[_node("n1", "A"), _node("n2", "B")])
        d = defn.to_dict()
        assert len(d["nodes"]) == 2
        assert d["nodes"][0]["id"] == "n1"

    def test_to_dict_connections_serialized(self):
        defn = _defn(connections=[_conn("n1", "n2")])
        d = defn.to_dict()
        assert d["connections"][0]["from_node"] == "n1"

    def test_from_dict_roundtrip(self):
        defn = WorkflowDefinition(
            id="tid", task_type="syncade", title="배포",
            nodes=[_node("n1", "빌드"), _node("n2", "배포")],
            connections=[_conn("n1", "n2")],
        )
        r = WorkflowDefinition.from_dict(defn.to_dict())
        assert r.id == "tid"
        assert r.task_type == "syncade"
        assert len(r.nodes) == 2
        assert r.nodes[1].title == "배포"
        assert r.connections[0].to_node == "n2"

    def test_empty_connections(self):
        defn = _defn(connections=[])
        d = defn.to_dict()
        assert d["connections"] == []

    def test_from_dict_missing_connections_defaults_empty(self):
        data = {"id": "t", "task_type": "general", "title": "w", "nodes": []}
        defn = WorkflowDefinition.from_dict(data)
        assert defn.connections == []

    def test_from_dict_missing_nodes_defaults_empty(self):
        data = {"id": "t", "task_type": "general", "title": "w"}
        defn = WorkflowDefinition.from_dict(data)
        assert defn.nodes == []


# ── NodeState ────────────────────────────────────────────────

class TestNodeState:
    def test_defaults(self):
        ns = NodeState()
        assert ns.status == "pending"
        assert ns.notes == ""
        assert ns.started_at == ""

    def test_to_dict_keys(self):
        d = NodeState().to_dict()
        assert set(d.keys()) == {"status", "notes", "started_at"}

    def test_from_dict_roundtrip(self):
        ns = NodeState(status="done", notes="완료", started_at="2026-06-07T10:00:00")
        r = NodeState.from_dict(ns.to_dict())
        assert r.status == "done"
        assert r.started_at == "2026-06-07T10:00:00"


# ── WorkflowRunState ─────────────────────────────────────────

class TestWorkflowRunState:
    def test_empty_state(self):
        rs = WorkflowRunState(definition_id="d1")
        assert rs.node_states == {}

    def test_set_node_status(self):
        rs = WorkflowRunState(definition_id="d1")
        rs.set_node_status("n1", "running")
        assert rs.node_states["n1"].status == "running"

    def test_set_node_status_with_notes(self):
        rs = WorkflowRunState(definition_id="d1")
        rs.set_node_status("n2", "error", notes="연결 실패")
        assert rs.node_states["n2"].notes == "연결 실패"

    def test_get_running_nodes(self):
        rs = WorkflowRunState(definition_id="d1")
        rs.set_node_status("n1", "done")
        rs.set_node_status("n2", "running")
        rs.set_node_status("n3", "pending")
        assert rs.get_running_nodes() == ["n2"]

    def test_get_running_nodes_empty(self):
        rs = WorkflowRunState(definition_id="d1")
        assert rs.get_running_nodes() == []

    def test_to_dict_roundtrip(self):
        rs = WorkflowRunState(definition_id="d1")
        rs.set_node_status("n1", "done", notes="ok")
        rs.set_node_status("n2", "running")
        d = rs.to_dict()
        r = WorkflowRunState.from_dict(d)
        assert r.definition_id == "d1"
        assert r.node_states["n1"].status == "done"
        assert r.node_states["n2"].status == "running"

    def test_from_definition_initializes_all_nodes_pending(self):
        defn = _defn(nodes=[_node("n1"), _node("n2"), _node("n3")])
        rs = WorkflowRunState.from_definition(defn)
        assert rs.definition_id == defn.id
        assert all(ns.status == "pending" for ns in rs.node_states.values())
        assert set(rs.node_states.keys()) == {"n1", "n2", "n3"}


# ── migrate_linear_to_graph ──────────────────────────────────

class TestMigrateLinearToGraph:
    def test_steps_become_nodes(self):
        wf = _linear_wf(3)
        defn, _ = migrate_linear_to_graph(wf)
        assert len(defn.nodes) == 3

    def test_preserves_ids_and_titles(self):
        wf = _linear_wf(2)
        defn, _ = migrate_linear_to_graph(wf)
        assert defn.nodes[0].id == "s1"
        assert defn.nodes[0].title == "단계1"
        assert defn.nodes[1].id == "s2"

    def test_creates_sequential_connections(self):
        wf = _linear_wf(4)
        defn, _ = migrate_linear_to_graph(wf)
        assert len(defn.connections) == 3
        assert defn.connections[0].from_node == "s1"
        assert defn.connections[0].to_node == "s2"
        assert defn.connections[2].from_node == "s3"
        assert defn.connections[2].to_node == "s4"

    def test_single_step_has_no_connections(self):
        wf = _linear_wf(1)
        defn, _ = migrate_linear_to_graph(wf)
        assert len(defn.nodes) == 1
        assert len(defn.connections) == 0

    def test_empty_workflow_migration(self):
        wf = Workflow(thread_id="t", task_type="general", title="빈", steps=[])
        defn, rs = migrate_linear_to_graph(wf)
        assert defn.nodes == []
        assert defn.connections == []
        assert rs.node_states == {}

    def test_step_max_retry_becomes_node_retry(self):
        step = WorkflowStep(id="s1", title="t", max_retry=2)
        wf = Workflow(thread_id="t", task_type="general", title="w", steps=[step])
        defn, _ = migrate_linear_to_graph(wf)
        assert defn.nodes[0].retry == 2

    def test_step_type_preserved(self):
        step = WorkflowStep(id="s1", title="t", type="semi_auto")
        wf = Workflow(thread_id="t", task_type="general", title="w", steps=[step])
        defn, _ = migrate_linear_to_graph(wf)
        assert defn.nodes[0].type == "semi_auto"

    def test_run_state_reflects_existing_statuses(self):
        steps = [
            WorkflowStep(id="s1", title="A", status="done"),
            WorkflowStep(id="s2", title="B", status="running"),
            WorkflowStep(id="s3", title="C", status="pending"),
        ]
        wf = Workflow(thread_id="t", task_type="general", title="w", steps=steps)
        _, rs = migrate_linear_to_graph(wf)
        assert rs.node_states["s1"].status == "done"
        assert rs.node_states["s2"].status == "running"
        assert rs.node_states["s3"].status == "pending"

    def test_definition_id_equals_thread_id(self):
        wf = _linear_wf(2)
        defn, rs = migrate_linear_to_graph(wf)
        assert defn.id == wf.thread_id
        assert rs.definition_id == wf.thread_id

    def test_connections_all_from_output_zero(self):
        wf = _linear_wf(3)
        defn, _ = migrate_linear_to_graph(wf)
        assert all(c.from_output == 0 for c in defn.connections)

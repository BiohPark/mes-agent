"""Phase 6A: 런타임 라우팅 엔진 단위 테스트.

WorkflowRunState.find_next_nodes() + _workflow_set_step 자동 진행 검증.
"""

import json
import pytest
from agent.workflow.model import (
    WorkflowDefinition, WorkflowNode, WorkflowConnection, WorkflowRunState,
)


# ── 헬퍼 ────────────────────────────────────────────────────────

def _linear(n=3) -> tuple[WorkflowDefinition, WorkflowRunState]:
    """n개 노드의 직렬 워크플로우."""
    nodes = [WorkflowNode(id=f"n{i}", title=f"노드{i}") for i in range(1, n + 1)]
    conns = [WorkflowConnection(from_node=f"n{i}", to_node=f"n{i+1}", from_output=0)
             for i in range(1, n)]
    defn = WorkflowDefinition(id="t", task_type="general", title="테스트", nodes=nodes, connections=conns)
    rs = WorkflowRunState.from_definition(defn)
    return defn, rs


def _branch() -> tuple[WorkflowDefinition, WorkflowRunState]:
    """n1 → n2(분기) → n3(true) / n4(false) → n5(merge) 구조."""
    nodes = [
        WorkflowNode("n1", "시작"),
        WorkflowNode("n2", "조건 확인"),
        WorkflowNode("n3", "성공 처리"),
        WorkflowNode("n4", "실패 처리"),
        WorkflowNode("n5", "완료"),
    ]
    conns = [
        WorkflowConnection("n1", "n2", from_output=0),
        WorkflowConnection("n2", "n3", from_output=1),   # true 분기
        WorkflowConnection("n2", "n4", from_output=2),   # false 분기
        WorkflowConnection("n3", "n5", from_output=0),
        WorkflowConnection("n4", "n5", from_output=0),
    ]
    defn = WorkflowDefinition(id="t", task_type="general", title="분기 테스트",
                              nodes=nodes, connections=conns)
    rs = WorkflowRunState.from_definition(defn)
    return defn, rs


# ── TestFindNextNodes ────────────────────────────────────────────

class TestFindNextNodes:
    def test_linear_returns_next_node(self):
        """직렬 연결: n1 done → n2 반환."""
        defn, rs = _linear(3)
        assert rs.find_next_nodes(defn, "n1") == ["n2"]

    def test_linear_middle_returns_next(self):
        defn, rs = _linear(3)
        assert rs.find_next_nodes(defn, "n2") == ["n3"]

    def test_terminal_node_returns_empty(self):
        """마지막 노드 → 빈 리스트."""
        defn, rs = _linear(3)
        assert rs.find_next_nodes(defn, "n3") == []

    def test_branch_true_follows_output_1(self):
        """branch_output=1 → true 경로 노드."""
        defn, rs = _branch()
        assert rs.find_next_nodes(defn, "n2", branch_output=1) == ["n3"]

    def test_branch_false_follows_output_2(self):
        """branch_output=2 → false 경로 노드."""
        defn, rs = _branch()
        assert rs.find_next_nodes(defn, "n2", branch_output=2) == ["n4"]

    def test_branch_no_output_returns_empty(self):
        """분기 노드에 branch_output 미지정 → 빈 리스트 (사용자 선택 필요)."""
        defn, rs = _branch()
        # n2는 from_output=1,2만 있고 from_output=0 없음 → 자동 진행 불가
        assert rs.find_next_nodes(defn, "n2") == []

    def test_default_path_followed_when_no_branch(self):
        """분기 없는 일반 노드: branch_output 미지정 → from_output=0 경로 따라감."""
        defn, rs = _branch()
        # n1은 from_output=0 연결 하나 → n2
        assert rs.find_next_nodes(defn, "n1") == ["n2"]

    def test_merge_node_reached_from_either_branch(self):
        """병합 노드: n3 done → n5 반환."""
        defn, rs = _branch()
        assert rs.find_next_nodes(defn, "n3") == ["n5"]
        assert rs.find_next_nodes(defn, "n4") == ["n5"]

    def test_single_connection_no_from_output_follows(self):
        """from_output 정보가 없어도 단일 연결이면 따라간다 (하위 호환)."""
        nodes = [WorkflowNode("a", "A"), WorkflowNode("b", "B")]
        # from_output 기본값 0
        conns = [WorkflowConnection("a", "b")]
        defn = WorkflowDefinition("t", "general", "test", nodes=nodes, connections=conns)
        rs = WorkflowRunState.from_definition(defn)
        assert rs.find_next_nodes(defn, "a") == ["b"]

    def test_invalid_node_id_returns_empty(self):
        """존재하지 않는 노드 → 빈 리스트."""
        defn, rs = _linear(2)
        assert rs.find_next_nodes(defn, "nonexistent") == []


# ── TestAutoAdvanceSetStep ───────────────────────────────────────

class TestAutoAdvanceSetStep:
    """_workflow_set_step의 자동 진행 동작을 스토리지 mock으로 검증한다."""

    def _make_env(self, task_type="general", thread_id="t") -> tuple:
        """tmp vault를 세팅하고 definition + run_state를 저장한다."""
        from pathlib import Path
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        os.environ["OBSIDIAN_VAULT_PATH"] = tmpdir
        return tmpdir

    def teardown_method(self, method):
        import os
        os.environ["OBSIDIAN_VAULT_PATH"] = ""

    def test_linear_done_auto_advances(self, tmp_path, monkeypatch):
        """직렬 워크플로우: n1 done → n2 자동 running."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from agent.workflow import storage as st
        from agent.tools.workflow import _workflow_set_step, _workflow_init

        _workflow_init("general", "t1", "테스트", [
            {"title": "단계1"}, {"title": "단계2"}, {"title": "단계3"}
        ])
        defn = st.load_definition("general", "t1")
        n1, n2, n3 = defn.nodes[0].id, defn.nodes[1].id, defn.nodes[2].id

        result = json.loads(_workflow_set_step("general", "t1", n1, "done"))
        assert result["ok"]
        steps = {s["id"]: s for s in result["workflow"]["steps"]}
        assert steps[n1]["status"] == "done"
        assert steps[n2]["status"] == "running"   # 자동 진행 ✓
        assert steps[n3]["status"] == "pending"

    def test_last_node_done_no_further_advance(self, tmp_path, monkeypatch):
        """마지막 노드 done → 더 진행 없음 (오류 없이 완료)."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from agent.tools.workflow import _workflow_set_step, _workflow_init

        _workflow_init("general", "t2", "테스트", [{"title": "A"}, {"title": "B"}])
        from agent.workflow import storage as st
        defn = st.load_definition("general", "t2")
        n1, n2 = defn.nodes[0].id, defn.nodes[1].id

        _workflow_set_step("general", "t2", n1, "done")
        result = json.loads(_workflow_set_step("general", "t2", n2, "done"))
        assert result["ok"]
        steps = {s["id"]: s for s in result["workflow"]["steps"]}
        assert steps[n2]["status"] == "done"

    def test_error_does_not_auto_advance(self, tmp_path, monkeypatch):
        """error 상태는 자동 진행하지 않는다."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from agent.tools.workflow import _workflow_set_step, _workflow_init

        _workflow_init("general", "t3", "테스트", [{"title": "A"}, {"title": "B"}])
        from agent.workflow import storage as st
        defn = st.load_definition("general", "t3")
        n1, n2 = defn.nodes[0].id, defn.nodes[1].id

        result = json.loads(_workflow_set_step("general", "t3", n1, "error"))
        steps = {s["id"]: s for s in result["workflow"]["steps"]}
        assert steps[n1]["status"] == "error"
        assert steps[n2]["status"] == "pending"   # 진행 없음 ✓

    def test_branch_true_routes_correctly(self, tmp_path, monkeypatch):
        """분기 노드 done + branch_output=1 → true 경로 자동 running."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from agent.tools.workflow import _workflow_set_step, _workflow_init, _workflow_add_connection, _workflow_remove_connection
        from agent.workflow import storage as st

        _workflow_init("general", "tb", "분기테스트", [
            {"title": "시작"},
            {"title": "조건 확인"},
            {"title": "성공 처리"},
            {"title": "실패 처리"},
            {"title": "완료"},
        ])
        defn = st.load_definition("general", "tb")
        n1, n2, n3, n4, n5 = [n.id for n in defn.nodes]

        # n2 → n3 연결 제거 후 true/false 분기 추가
        _workflow_remove_connection("general", "tb", n2, n3)
        _workflow_remove_connection("general", "tb", n3, n4)
        _workflow_remove_connection("general", "tb", n4, n5)
        _workflow_add_connection("general", "tb", n2, n3, from_output=1)   # true
        _workflow_add_connection("general", "tb", n2, n4, from_output=2)   # false
        _workflow_add_connection("general", "tb", n3, n5, from_output=0)
        _workflow_add_connection("general", "tb", n4, n5, from_output=0)

        # n1 실행
        _workflow_set_step("general", "tb", n1, "done")
        # n2를 true 분기로 완료
        result = json.loads(_workflow_set_step("general", "tb", n2, "done", branch_output=1))
        steps = {s["id"]: s for s in result["workflow"]["steps"]}
        assert steps[n3]["status"] == "running"   # true 경로 ✓
        assert steps[n4]["status"] == "pending"   # false 경로 skip ✓

    def test_branch_no_output_does_not_advance(self, tmp_path, monkeypatch):
        """분기 노드 done에 branch_output 없으면 자동 진행 없음."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from agent.tools.workflow import _workflow_set_step, _workflow_init, _workflow_add_connection, _workflow_remove_connection
        from agent.workflow import storage as st

        _workflow_init("general", "tnb", "분기미선택", [
            {"title": "시작"}, {"title": "조건"}, {"title": "A"}, {"title": "B"},
        ])
        defn = st.load_definition("general", "tnb")
        n1, n2, n3, n4 = [n.id for n in defn.nodes]

        _workflow_remove_connection("general", "tnb", n2, n3)
        _workflow_remove_connection("general", "tnb", n3, n4)
        _workflow_add_connection("general", "tnb", n2, n3, from_output=1)
        _workflow_add_connection("general", "tnb", n2, n4, from_output=2)

        _workflow_set_step("general", "tnb", n1, "done")
        result = json.loads(_workflow_set_step("general", "tnb", n2, "done"))
        steps = {s["id"]: s for s in result["workflow"]["steps"]}
        # branch_output 미지정 → 자동 진행 없음
        assert steps[n3]["status"] == "pending"
        assert steps[n4]["status"] == "pending"

    def test_already_running_next_not_overridden(self, tmp_path, monkeypatch):
        """다음 노드가 이미 running이면 재설정하지 않는다."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from agent.tools.workflow import _workflow_set_step, _workflow_init

        _workflow_init("general", "trun", "테스트", [{"title": "A"}, {"title": "B"}])
        from agent.workflow import storage as st
        defn = st.load_definition("general", "trun")
        n1, n2 = defn.nodes[0].id, defn.nodes[1].id

        # n2를 미리 running으로 설정
        _workflow_set_step("general", "trun", n2, "running")
        # n1 done → n2는 이미 running이므로 그대로 유지
        result = json.loads(_workflow_set_step("general", "trun", n1, "done"))
        steps = {s["id"]: s for s in result["workflow"]["steps"]}
        assert steps[n2]["status"] == "running"   # 그대로 ✓

    def test_skipped_next_node_skips_advance(self, tmp_path, monkeypatch):
        """다음 노드가 already done/skipped이면 덮어쓰지 않는다."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        from agent.tools.workflow import _workflow_set_step, _workflow_init

        _workflow_init("general", "tsk", "테스트", [{"title": "A"}, {"title": "B"}])
        from agent.workflow import storage as st
        defn = st.load_definition("general", "tsk")
        n1, n2 = defn.nodes[0].id, defn.nodes[1].id

        _workflow_set_step("general", "tsk", n2, "skipped")
        result = json.loads(_workflow_set_step("general", "tsk", n1, "done"))
        steps = {s["id"]: s for s in result["workflow"]["steps"]}
        assert steps[n2]["status"] == "skipped"   # 덮어쓰지 않음 ✓

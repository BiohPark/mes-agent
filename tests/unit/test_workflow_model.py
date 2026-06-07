"""워크플로우 데이터클래스 직렬화·역직렬화 단위 테스트."""

import pytest
from agent.workflow.model import Workflow, WorkflowStep


def _make_step(id="aabb1122", title="단계1", type="auto", status="pending", notes="") -> WorkflowStep:
    return WorkflowStep(id=id, title=title, type=type, status=status, notes=notes)


def _make_workflow(steps=None) -> Workflow:
    if steps is None:
        steps = [_make_step()]
    return Workflow(
        thread_id="thread-001",
        task_type="general",
        title="테스트 워크플로우",
        steps=steps,
    )


class TestWorkflowStep:
    def test_defaults(self):
        step = WorkflowStep(id="abc", title="테스트")
        assert step.type == "auto"
        assert step.status == "pending"
        assert step.notes == ""

    def test_all_valid_types(self):
        for t in ("auto", "semi_auto", "manual"):
            s = WorkflowStep(id="x", title="t", type=t)
            assert s.type == t

    def test_all_valid_statuses(self):
        for st in ("pending", "running", "waiting", "done", "error", "skipped"):
            s = WorkflowStep(id="x", title="t", status=st)
            assert s.status == st


class TestWorkflowToDict:
    def test_keys_present(self):
        wf = _make_workflow()
        d = wf.to_dict()
        assert set(d.keys()) == {"thread_id", "task_type", "title", "steps"}

    def test_step_keys_present(self):
        wf = _make_workflow()
        step_d = wf.to_dict()["steps"][0]
        assert set(step_d.keys()) == {"id", "title", "type", "status", "notes"}

    def test_values_match(self):
        step = _make_step(id="zz99", title="환경 확인", type="semi_auto", status="done", notes="완료")
        wf = Workflow(thread_id="t1", task_type="syncade", title="배포", steps=[step])
        d = wf.to_dict()
        assert d["thread_id"] == "t1"
        assert d["task_type"] == "syncade"
        assert d["steps"][0]["id"] == "zz99"
        assert d["steps"][0]["status"] == "done"

    def test_empty_steps(self):
        wf = _make_workflow(steps=[])
        assert wf.to_dict()["steps"] == []


class TestWorkflowFromDict:
    def test_roundtrip(self):
        wf = _make_workflow(steps=[
            _make_step("id1", "단계A", "auto", "done", "메모"),
            _make_step("id2", "단계B", "manual", "pending", ""),
        ])
        restored = Workflow.from_dict(wf.to_dict())
        assert restored.thread_id == wf.thread_id
        assert restored.task_type == wf.task_type
        assert restored.title == wf.title
        assert len(restored.steps) == 2
        assert restored.steps[0].id == "id1"
        assert restored.steps[0].status == "done"
        assert restored.steps[1].title == "단계B"

    def test_missing_steps_key_defaults_to_empty(self):
        data = {"thread_id": "t", "task_type": "general", "title": "w"}
        wf = Workflow.from_dict(data)
        assert wf.steps == []

    def test_step_fields_preserved(self):
        original = _make_step("s1", "확인", "semi_auto", "running", "진행중")
        wf = Workflow(thread_id="t", task_type="general", title="w", steps=[original])
        restored = Workflow.from_dict(wf.to_dict())
        s = restored.steps[0]
        assert s.id == "s1"
        assert s.type == "semi_auto"
        assert s.notes == "진행중"

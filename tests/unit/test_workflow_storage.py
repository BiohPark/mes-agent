"""워크플로우 JSON 저장·불러오기·삭제 단위 테스트.

각 테스트는 tmp_path를 통해 격리된 임시 디렉토리를 사용한다.
"""

import json
import pytest
from agent.workflow.model import Workflow, WorkflowStep
from agent.workflow import storage as wf_storage
from agent.workflow.storage import _DEFAULT_STEPS, _DEFAULT_TITLES


TASK_TYPES = list(_DEFAULT_STEPS.keys())  # general, syncade, obsidian-rag, unscript, knox


@pytest.fixture
def vault_env(tmp_path, monkeypatch):
    """OBSIDIAN_VAULT_PATH를 임시 디렉토리로 설정한다."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    return tmp_path


class TestLoadWorkflow:
    def test_load_creates_default_when_no_file(self, vault_env):
        wf = wf_storage.load_workflow("general", "thread-001")
        assert wf.task_type == "general"
        assert wf.thread_id == "thread-001"
        assert len(wf.steps) == len(_DEFAULT_STEPS["general"])

    def test_load_persists_default_on_first_call(self, vault_env):
        """최초 load 시 기본 템플릿이 파일로 저장되어야 step id가 고정된다."""
        wf1 = wf_storage.load_workflow("general", "thread-001")
        wf2 = wf_storage.load_workflow("general", "thread-001")
        ids1 = [s.id for s in wf1.steps]
        ids2 = [s.id for s in wf2.steps]
        assert ids1 == ids2, "재로드 시 step id가 변경되면 패널과 불일치"

    def test_load_existing_file(self, vault_env):
        """저장된 파일이 있으면 그 데이터를 그대로 반환해야 한다."""
        original = Workflow(
            thread_id="t1",
            task_type="general",
            title="수동 저장 워크플로우",
            steps=[WorkflowStep(id="abc123", title="커스텀 단계", type="manual")],
        )
        wf_storage.save_workflow(original)
        loaded = wf_storage.load_workflow("general", "t1")
        assert loaded.title == "수동 저장 워크플로우"
        assert loaded.steps[0].id == "abc123"
        assert loaded.steps[0].type == "manual"

    def test_all_task_types_have_defaults(self, vault_env):
        for task_type in TASK_TYPES:
            wf = wf_storage.load_workflow(task_type, f"thread-{task_type}")
            assert len(wf.steps) > 0, f"{task_type} 기본 단계 없음"
            assert wf.title == _DEFAULT_TITLES[task_type]

    def test_no_vault_path_returns_default_without_file(self, monkeypatch):
        """OBSIDIAN_VAULT_PATH 미설정 시 기본 워크플로우를 반환하고 파일은 쓰지 않는다."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        wf = wf_storage.load_workflow("general", "orphan-thread")
        assert wf.task_type == "general"
        assert len(wf.steps) > 0


class TestSaveWorkflow:
    def test_save_creates_file(self, vault_env):
        wf = Workflow(thread_id="t2", task_type="syncade", title="배포", steps=[])
        wf_storage.save_workflow(wf)
        path = vault_env / "agent" / "workflows" / "syncade" / "t2.json"
        assert path.exists()

    def test_saved_json_is_valid(self, vault_env):
        wf = Workflow(
            thread_id="t3",
            task_type="general",
            title="유효성 확인",
            steps=[WorkflowStep(id="s1", title="단계")],
        )
        wf_storage.save_workflow(wf)
        path = vault_env / "agent" / "workflows" / "general" / "t3.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["thread_id"] == "t3"
        assert data["steps"][0]["id"] == "s1"

    def test_no_vault_path_is_noop(self, monkeypatch):
        """OBSIDIAN_VAULT_PATH 미설정 시 save는 예외 없이 조용히 종료해야 한다."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        wf = Workflow(thread_id="t", task_type="general", title="w", steps=[])
        wf_storage.save_workflow(wf)  # 예외 없이 통과해야 함

    def test_roundtrip(self, vault_env):
        """저장 후 다시 읽으면 동일한 데이터여야 한다."""
        steps = [
            WorkflowStep(id=f"s{i}", title=f"단계{i}", type="auto", status="pending")
            for i in range(3)
        ]
        wf = Workflow(thread_id="rt", task_type="knox", title="수집 절차", steps=steps)
        wf_storage.save_workflow(wf)
        loaded = wf_storage.load_workflow("knox", "rt")
        assert loaded.title == wf.title
        assert [s.id for s in loaded.steps] == [s.id for s in wf.steps]


class TestDeleteWorkflow:
    def test_delete_removes_file(self, vault_env):
        wf = Workflow(thread_id="del1", task_type="general", title="삭제 대상", steps=[])
        wf_storage.save_workflow(wf)
        path = vault_env / "agent" / "workflows" / "general" / "del1.json"
        assert path.exists()
        wf_storage.delete_workflow("general", "del1")
        assert not path.exists()

    def test_delete_nonexistent_is_noop(self, vault_env):
        """존재하지 않는 워크플로우 삭제는 예외 없이 통과해야 한다."""
        wf_storage.delete_workflow("general", "no-such-thread")

    def test_delete_then_load_returns_fresh_default(self, vault_env):
        """삭제 후 다시 load하면 새 기본 템플릿을 반환해야 한다."""
        wf = Workflow(
            thread_id="del2",
            task_type="general",
            title="커스텀",
            steps=[WorkflowStep(id="x", title="커스텀 단계")],
        )
        wf_storage.save_workflow(wf)
        wf_storage.delete_workflow("general", "del2")
        fresh = wf_storage.load_workflow("general", "del2")
        assert fresh.title != "커스텀"
        assert len(fresh.steps) == len(_DEFAULT_STEPS["general"])

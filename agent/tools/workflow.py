import json
import uuid

from agent.workflow.model import Workflow, WorkflowStep
from agent.workflow import storage as wf_storage


def _workflow_init(task_type: str, thread_id: str, title: str, steps: list) -> str:
    wf_steps = [
        WorkflowStep(
            id=uuid.uuid4().hex[:8],
            title=s["title"],
            type=s.get("type", "auto"),
            status="pending",
            notes="",
        )
        for s in steps
    ]
    wf = Workflow(thread_id=thread_id, task_type=task_type, title=title, steps=wf_steps)
    wf_storage.save_workflow(wf)
    return json.dumps({"ok": True, "workflow": wf.to_dict()}, ensure_ascii=False)


def _workflow_set_step(
    task_type: str, thread_id: str, step_id: str, status: str, notes: str = ""
) -> str:
    wf = wf_storage.load_workflow(task_type, thread_id)
    if not wf:
        return json.dumps({"ok": False, "error": "워크플로우 없음"}, ensure_ascii=False)
    for step in wf.steps:
        if step.id == step_id:
            step.status = status
            if notes:
                step.notes = notes
            break
    else:
        return json.dumps(
            {"ok": False, "error": f"step_id '{step_id}' 없음"}, ensure_ascii=False
        )
    wf_storage.save_workflow(wf)
    return json.dumps({"ok": True, "workflow": wf.to_dict()}, ensure_ascii=False)


MANIFEST = [
    {
        "name": "workflow_init",
        "label": "워크플로우 초기화",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_init",
                "description": (
                    "현재 스레드의 워크플로우를 초기화(새로 생성 또는 교체)한다. "
                    "달성할 목표와 단계를 정의할 때 사용한다. "
                    "우측 패널에 단계 카드로 표시된다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string", "description": "업무 타입 (general, syncade 등)"},
                        "thread_id": {"type": "string", "description": "현재 스레드 ID"},
                        "title": {"type": "string", "description": "워크플로우 제목"},
                        "steps": {
                            "type": "array",
                            "description": "워크플로우 단계 목록",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string", "description": "단계 설명"},
                                    "type": {
                                        "type": "string",
                                        "enum": ["auto", "semi_auto", "manual"],
                                        "description": "auto=에이전트 자동실행, semi_auto=사용자 확인 후 실행, manual=사용자 직접 수행",
                                    },
                                },
                                "required": ["title"],
                            },
                        },
                    },
                    "required": ["task_type", "thread_id", "title", "steps"],
                },
            },
        },
        "handler": lambda a: _workflow_init(
            a["task_type"], a["thread_id"], a["title"], a["steps"]
        ),
    },
    {
        "name": "workflow_set_step",
        "label": "워크플로우 단계 업데이트",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_set_step",
                "description": "워크플로우의 특정 단계 상태를 업데이트한다. 단계 실행 시작/완료/오류 시 호출해라.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "step_id": {"type": "string", "description": "업데이트할 단계의 id"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "running", "waiting", "done", "error", "skipped"],
                        },
                        "notes": {
                            "type": "string",
                            "description": "단계 실행 결과나 메모 (선택)",
                        },
                    },
                    "required": ["task_type", "thread_id", "step_id", "status"],
                },
            },
        },
        "handler": lambda a: _workflow_set_step(
            a["task_type"], a["thread_id"], a["step_id"], a["status"], a.get("notes", "")
        ),
    },
]

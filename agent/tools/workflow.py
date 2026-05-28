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


def _workflow_add_step(
    task_type: str, thread_id: str, title: str, type: str = "auto", after_step_id: str = ""
) -> str:
    wf = wf_storage.load_workflow(task_type, thread_id)
    new_step = WorkflowStep(id=uuid.uuid4().hex[:8], title=title, type=type, status="pending", notes="")
    if after_step_id:
        idx = next((i for i, s in enumerate(wf.steps) if s.id == after_step_id), None)
        if idx is None:
            wf.steps.append(new_step)
        else:
            wf.steps.insert(idx + 1, new_step)
    else:
        wf.steps.append(new_step)
    wf_storage.save_workflow(wf)
    return json.dumps({"ok": True, "workflow": wf.to_dict()}, ensure_ascii=False)


def _workflow_update_step(
    task_type: str, thread_id: str, step_id: str, title: str = "", type: str = ""
) -> str:
    """단계의 구조(제목·유형)를 수정한다. 진행 상태(status)는 workflow_set_step이 담당한다."""
    wf = wf_storage.load_workflow(task_type, thread_id)
    for step in wf.steps:
        if step.id == step_id:
            if title:
                step.title = title
            if type:
                step.type = type
            break
    else:
        return json.dumps({"ok": False, "error": f"step_id '{step_id}' 없음"}, ensure_ascii=False)
    wf_storage.save_workflow(wf)
    return json.dumps({"ok": True, "workflow": wf.to_dict()}, ensure_ascii=False)


def _workflow_remove_step(task_type: str, thread_id: str, step_id: str) -> str:
    wf = wf_storage.load_workflow(task_type, thread_id)
    before = len(wf.steps)
    wf.steps = [s for s in wf.steps if s.id != step_id]
    if len(wf.steps) == before:
        return json.dumps({"ok": False, "error": f"step_id '{step_id}' 없음"}, ensure_ascii=False)
    wf_storage.save_workflow(wf)
    return json.dumps({"ok": True, "workflow": wf.to_dict()}, ensure_ascii=False)


def _workflow_reorder(task_type: str, thread_id: str, ordered_step_ids: list) -> str:
    wf = wf_storage.load_workflow(task_type, thread_id)
    by_id = {s.id: s for s in wf.steps}
    reordered = [by_id[i] for i in ordered_step_ids if i in by_id]
    # 목록에 빠진 기존 단계는 끝에 보존 (유실 방지)
    for s in wf.steps:
        if s.id not in ordered_step_ids:
            reordered.append(s)
    wf.steps = reordered
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
    {
        "name": "workflow_add_step",
        "label": "워크플로우 단계 추가",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_add_step",
                "description": (
                    "현재 워크플로우에 단계를 추가한다. 진행 중 워크플로우에 새 작업이 생겼을 때 "
                    "기존 단계 상태를 유지한 채 단계만 끼워 넣는다. after_step_id를 주면 그 단계 뒤에 삽입한다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "title": {"type": "string", "description": "단계 설명"},
                        "type": {
                            "type": "string",
                            "enum": ["auto", "semi_auto", "manual"],
                            "description": "auto=자동, semi_auto=확인 후, manual=수동 (기본 auto)",
                        },
                        "after_step_id": {"type": "string", "description": "이 단계 뒤에 삽입 (생략 시 맨 끝)"},
                    },
                    "required": ["task_type", "thread_id", "title"],
                },
            },
        },
        "handler": lambda a: _workflow_add_step(
            a["task_type"], a["thread_id"], a["title"], a.get("type", "auto"), a.get("after_step_id", "")
        ),
    },
    {
        "name": "workflow_update_step",
        "label": "워크플로우 단계 수정",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_update_step",
                "description": (
                    "단계의 제목 또는 유형을 수정한다. 진행 상태(status) 변경은 workflow_set_step을 사용한다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "step_id": {"type": "string", "description": "수정할 단계의 id"},
                        "title": {"type": "string", "description": "새 제목 (선택)"},
                        "type": {
                            "type": "string",
                            "enum": ["auto", "semi_auto", "manual"],
                            "description": "새 유형 (선택)",
                        },
                    },
                    "required": ["task_type", "thread_id", "step_id"],
                },
            },
        },
        "handler": lambda a: _workflow_update_step(
            a["task_type"], a["thread_id"], a["step_id"], a.get("title", ""), a.get("type", "")
        ),
    },
    {
        "name": "workflow_remove_step",
        "label": "워크플로우 단계 삭제",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_remove_step",
                "description": "워크플로우에서 단계를 삭제한다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "step_id": {"type": "string", "description": "삭제할 단계의 id"},
                    },
                    "required": ["task_type", "thread_id", "step_id"],
                },
            },
        },
        "handler": lambda a: _workflow_remove_step(a["task_type"], a["thread_id"], a["step_id"]),
    },
    {
        "name": "workflow_reorder",
        "label": "워크플로우 단계 순서 변경",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_reorder",
                "description": "워크플로우 단계의 순서를 재배치한다. ordered_step_ids에 원하는 순서대로 단계 id를 나열한다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "ordered_step_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "원하는 순서대로 나열한 단계 id 목록",
                        },
                    },
                    "required": ["task_type", "thread_id", "ordered_step_ids"],
                },
            },
        },
        "handler": lambda a: _workflow_reorder(a["task_type"], a["thread_id"], a["ordered_step_ids"]),
    },
]

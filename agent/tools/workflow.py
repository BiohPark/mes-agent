import json
import uuid

from agent.workflow.model import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowConnection,
    WorkflowRunState,
)
from agent.workflow import storage as wf_storage


def _merged_dict(task_type: str, thread_id: str) -> dict:
    """Definition + RunState를 병합한 Workflow.to_dict()를 반환한다 (프론트엔드 호환)."""
    return wf_storage.load_workflow(task_type, thread_id).to_dict()


def _rebuild_connections(nodes: list) -> list:
    """노드 목록을 순서대로 잇는 단순 직렬 연결 목록을 반환한다."""
    return [
        WorkflowConnection(from_node=nodes[i].id, to_node=nodes[i + 1].id)
        for i in range(len(nodes) - 1)
    ]


def _workflow_init(task_type: str, thread_id: str, title: str, steps: list) -> str:
    nodes = [
        WorkflowNode(
            id=uuid.uuid4().hex[:8],
            title=s["title"],
            type=s.get("type", "auto"),
        )
        for s in steps
    ]
    defn = WorkflowDefinition(
        id=thread_id, task_type=task_type, title=title,
        nodes=nodes, connections=_rebuild_connections(nodes),
    )
    rs = WorkflowRunState(definition_id=thread_id)
    for n in nodes:
        rs.set_node_status(n.id, "pending")
    wf_storage.save_definition(defn)
    wf_storage.save_run_state(task_type, thread_id, rs)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


def _workflow_set_step(
    task_type: str, thread_id: str, step_id: str, status: str, notes: str = ""
) -> str:
    defn = wf_storage.load_definition(task_type, thread_id)
    if not any(n.id == step_id for n in defn.nodes):
        return json.dumps({"ok": False, "error": f"step_id '{step_id}' 없음"}, ensure_ascii=False)
    rs = wf_storage.load_run_state(task_type, thread_id) or WorkflowRunState(definition_id=thread_id)
    rs.set_node_status(step_id, status, notes=notes)
    wf_storage.save_run_state(task_type, thread_id, rs)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


def _workflow_add_step(
    task_type: str, thread_id: str, title: str, type: str = "auto", after_step_id: str = ""
) -> str:
    defn = wf_storage.load_definition(task_type, thread_id)
    new_node = WorkflowNode(id=uuid.uuid4().hex[:8], title=title, type=type)
    if after_step_id:
        idx = next((i for i, n in enumerate(defn.nodes) if n.id == after_step_id), None)
        if idx is None:
            defn.nodes.append(new_node)
        else:
            defn.nodes.insert(idx + 1, new_node)
    else:
        defn.nodes.append(new_node)
    defn.connections = _rebuild_connections(defn.nodes)
    wf_storage.save_definition(defn)
    rs = wf_storage.load_run_state(task_type, thread_id) or WorkflowRunState(definition_id=thread_id)
    rs.set_node_status(new_node.id, "pending")
    wf_storage.save_run_state(task_type, thread_id, rs)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


def _workflow_update_step(
    task_type: str, thread_id: str, step_id: str, title: str = "", type: str = ""
) -> str:
    """단계의 구조(제목·유형)를 수정한다. 진행 상태(status)는 workflow_set_step이 담당한다."""
    defn = wf_storage.load_definition(task_type, thread_id)
    for node in defn.nodes:
        if node.id == step_id:
            if title:
                node.title = title
            if type:
                node.type = type
            break
    else:
        return json.dumps({"ok": False, "error": f"step_id '{step_id}' 없음"}, ensure_ascii=False)
    wf_storage.save_definition(defn)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


def _workflow_remove_step(task_type: str, thread_id: str, step_id: str) -> str:
    defn = wf_storage.load_definition(task_type, thread_id)
    before = len(defn.nodes)
    defn.nodes = [n for n in defn.nodes if n.id != step_id]
    if len(defn.nodes) == before:
        return json.dumps({"ok": False, "error": f"step_id '{step_id}' 없음"}, ensure_ascii=False)
    defn.connections = _rebuild_connections(defn.nodes)
    wf_storage.save_definition(defn)
    rs = wf_storage.load_run_state(task_type, thread_id)
    if rs and step_id in rs.node_states:
        del rs.node_states[step_id]
        wf_storage.save_run_state(task_type, thread_id, rs)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


def _workflow_add_connection(
    task_type: str, thread_id: str, from_node: str, to_node: str, from_output: int = 0
) -> str:
    defn = wf_storage.load_definition(task_type, thread_id)
    node_ids = {n.id for n in defn.nodes}
    if from_node not in node_ids:
        return json.dumps({"ok": False, "error": f"from_node '{from_node}' 없음"}, ensure_ascii=False)
    if to_node not in node_ids:
        return json.dumps({"ok": False, "error": f"to_node '{to_node}' 없음"}, ensure_ascii=False)
    if any(c.from_node == from_node and c.to_node == to_node and c.from_output == from_output
           for c in defn.connections):
        return json.dumps({"ok": False, "error": "이미 존재하는 연결입니다"}, ensure_ascii=False)
    defn.connections.append(WorkflowConnection(from_node=from_node, to_node=to_node, from_output=from_output))
    wf_storage.save_definition(defn)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


def _workflow_remove_connection(task_type: str, thread_id: str, from_node: str, to_node: str) -> str:
    defn = wf_storage.load_definition(task_type, thread_id)
    before = len(defn.connections)
    defn.connections = [c for c in defn.connections if not (c.from_node == from_node and c.to_node == to_node)]
    if len(defn.connections) == before:
        return json.dumps({"ok": False, "error": f"연결 ({from_node}→{to_node}) 없음"}, ensure_ascii=False)
    wf_storage.save_definition(defn)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


def _workflow_reorder(task_type: str, thread_id: str, ordered_step_ids: list) -> str:
    defn = wf_storage.load_definition(task_type, thread_id)
    by_id = {n.id: n for n in defn.nodes}
    reordered = [by_id[i] for i in ordered_step_ids if i in by_id]
    for n in defn.nodes:
        if n.id not in ordered_step_ids:
            reordered.append(n)
    defn.nodes = reordered
    defn.connections = _rebuild_connections(defn.nodes)
    wf_storage.save_definition(defn)
    return json.dumps({"ok": True, "workflow": _merged_dict(task_type, thread_id)}, ensure_ascii=False)


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
    {
        "name": "workflow_add_connection",
        "label": "워크플로우 연결 추가",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_add_connection",
                "description": (
                    "두 단계 사이에 연결(엣지)을 추가한다. from_output=0이면 기본(단일) 경로, "
                    "1이면 true 분기, 2이면 false 분기다. "
                    "같은 from_node에서 여러 갈래 연결로 조건 분기를 표현한다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "from_node": {"type": "string", "description": "출발 단계 id"},
                        "to_node": {"type": "string", "description": "도착 단계 id"},
                        "from_output": {
                            "type": "integer",
                            "description": "출력 포트 번호 (0=기본, 1=true 분기, 2=false 분기)",
                            "default": 0,
                        },
                    },
                    "required": ["task_type", "thread_id", "from_node", "to_node"],
                },
            },
        },
        "handler": lambda a: _workflow_add_connection(
            a["task_type"], a["thread_id"], a["from_node"], a["to_node"], a.get("from_output", 0)
        ),
    },
    {
        "name": "workflow_remove_connection",
        "label": "워크플로우 연결 삭제",
        "schema": {
            "type": "function",
            "function": {
                "name": "workflow_remove_connection",
                "description": "두 단계 사이의 연결을 제거한다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "from_node": {"type": "string", "description": "출발 단계 id"},
                        "to_node": {"type": "string", "description": "도착 단계 id"},
                    },
                    "required": ["task_type", "thread_id", "from_node", "to_node"],
                },
            },
        },
        "handler": lambda a: _workflow_remove_connection(
            a["task_type"], a["thread_id"], a["from_node"], a["to_node"]
        ),
    },
]

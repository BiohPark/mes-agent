from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

StepType = Literal["auto", "semi_auto", "manual"]
NodeType = Literal["auto", "semi_auto", "manual", "condition"]
StepStatus = Literal["pending", "running", "waiting", "done", "error", "skipped"]


# ── 기존 선형 모델 (하위 호환 유지) ─────────────────────────────

@dataclass
class WorkflowStep:
    id: str
    title: str
    type: StepType = "auto"
    status: StepStatus = "pending"
    notes: str = ""
    max_retry: int = 0
    group: str = ""


@dataclass
class Workflow:
    thread_id: str
    task_type: str
    title: str
    steps: list = field(default_factory=list)       # list[WorkflowStep]
    connections: list = field(default_factory=list) # list[dict] — 프론트엔드 전달용 (그래프 포맷 로드 시 채워짐)

    def to_dict(self) -> dict:
        return {
            "thread_id": self.thread_id,
            "task_type": self.task_type,
            "title": self.title,
            "steps": [
                {
                    "id": s.id,
                    "title": s.title,
                    "type": s.type,
                    "status": s.status,
                    "notes": s.notes,
                    "max_retry": s.max_retry,
                    "group": s.group,
                }
                for s in self.steps
            ],
            "connections": list(self.connections),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        steps = []
        for s in data.get("steps", []):
            steps.append(WorkflowStep(
                id=s["id"],
                title=s["title"],
                type=s.get("type", "auto"),
                status=s.get("status", "pending"),
                notes=s.get("notes", ""),
                max_retry=s.get("max_retry", 0),
                group=s.get("group", ""),
            ))
        return cls(
            thread_id=data["thread_id"],
            task_type=data["task_type"],
            title=data["title"],
            steps=steps,
            connections=data.get("connections", []),
        )


# ── 새 그래프 모델 (Phase 1) ─────────────────────────────────

@dataclass
class WorkflowNode:
    id: str
    title: str
    type: NodeType = "auto"
    retry: int = 0
    on_error: str = "stop"  # "stop" | "continue" | node_id
    group: str = ""  # 시각적 그룹/서브워크플로우 라벨 (빈 값 = 그룹 없음)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "retry": self.retry,
            "on_error": self.on_error,
            "group": self.group,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowNode":
        return cls(
            id=data["id"],
            title=data["title"],
            type=data.get("type", "auto"),
            retry=data.get("retry", 0),
            on_error=data.get("on_error", "stop"),
            group=data.get("group", ""),
        )


@dataclass
class WorkflowConnection:
    from_node: str
    to_node: str
    from_output: int = 0  # 0=기본, 1=true 분기, 2=false 분기

    def to_dict(self) -> dict:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "from_output": self.from_output,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowConnection":
        return cls(
            from_node=data["from_node"],
            to_node=data["to_node"],
            from_output=data.get("from_output", 0),
        )


@dataclass
class WorkflowDefinition:
    """불변 정의 — Vault에 저장, 사람이 편집 가능."""
    id: str  # thread_id에 해당
    task_type: str
    title: str
    nodes: list = field(default_factory=list)       # list[WorkflowNode]
    connections: list = field(default_factory=list) # list[WorkflowConnection]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "title": self.title,
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": [c.to_dict() for c in self.connections],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowDefinition":
        return cls(
            id=data["id"],
            task_type=data["task_type"],
            title=data["title"],
            nodes=[WorkflowNode.from_dict(n) for n in data.get("nodes", [])],
            connections=[WorkflowConnection.from_dict(c) for c in data.get("connections", [])],
        )


@dataclass
class NodeState:
    """단일 노드의 실행 상태."""
    status: StepStatus = "pending"
    notes: str = ""
    started_at: str = ""  # ISO datetime 문자열, 빈 값 = 미시작

    def to_dict(self) -> dict:
        return {"status": self.status, "notes": self.notes, "started_at": self.started_at}

    @classmethod
    def from_dict(cls, data: dict) -> "NodeState":
        return cls(
            status=data.get("status", "pending"),
            notes=data.get("notes", ""),
            started_at=data.get("started_at", ""),
        )


@dataclass
class WorkflowRunState:
    """가변 실행 상태 — 런타임 분리, 메모리 또는 별도 파일."""
    definition_id: str
    node_states: dict = field(default_factory=dict)  # dict[str, NodeState]

    def set_node_status(self, node_id: str, status: StepStatus, notes: str = "") -> None:
        if node_id not in self.node_states:
            self.node_states[node_id] = NodeState()
        self.node_states[node_id].status = status
        if notes:
            self.node_states[node_id].notes = notes

    def get_running_nodes(self) -> list[str]:
        return [nid for nid, ns in self.node_states.items() if ns.status == "running"]

    def to_dict(self) -> dict:
        return {
            "definition_id": self.definition_id,
            "node_states": {nid: ns.to_dict() for nid, ns in self.node_states.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowRunState":
        rs = cls(definition_id=data["definition_id"])
        rs.node_states = {
            nid: NodeState.from_dict(ns)
            for nid, ns in data.get("node_states", {}).items()
        }
        return rs

    @classmethod
    def from_definition(cls, defn: "WorkflowDefinition") -> "WorkflowRunState":
        """WorkflowDefinition의 모든 노드를 pending 상태로 초기화한다."""
        rs = cls(definition_id=defn.id)
        rs.node_states = {n.id: NodeState() for n in defn.nodes}
        return rs

    def find_next_nodes(
        self, defn: "WorkflowDefinition", node_id: str, branch_output: int | None = None
    ) -> list[str]:
        """node_id 완료 후 런타임 라우팅으로 이동할 다음 노드 ID 목록을 반환한다.

        - branch_output 지정: 해당 출력 포트(1=true, 2=false)의 연결만 따라감
        - branch_output=None:
            * from_output=0 연결 있으면 그것을 따라감 (직렬 기본 경로)
            * from_output=0 없고 단일 연결이면 그것을 따라감 (하위 호환)
            * 다중 분기(from_output≠0)만 있으면 빈 리스트 (사용자 선택 필요)
        """
        outgoing = [c for c in defn.connections if c.from_node == node_id]
        if not outgoing:
            return []

        if branch_output is not None:
            return [c.to_node for c in outgoing if c.from_output == branch_output]

        # branch_output 미지정: from_output=0 경로 우선
        default_path = [c.to_node for c in outgoing if c.from_output == 0]
        if default_path:
            return default_path

        # from_output=0 없고 단일 연결이면 따라감 (구 데이터 하위 호환)
        if len(outgoing) == 1:
            return [outgoing[0].to_node]

        # 다중 분기인데 선택 없음 → 자동 진행 불가
        return []


@dataclass
class LedgerEntry:
    """감사 추적 단일 엔트리 — RunLedger JSONL 한 줄."""
    ts: str          # ISO datetime
    event: str       # start/done/error/stopped/max_steps
    detail: str = ""
    phase: str = ""

    def to_dict(self) -> dict:
        return {"ts": self.ts, "event": self.event, "detail": self.detail, "phase": self.phase}

    @classmethod
    def from_dict(cls, data: dict) -> "LedgerEntry":
        return cls(
            ts=data.get("ts", ""),
            event=data.get("event", ""),
            detail=data.get("detail", ""),
            phase=data.get("phase", ""),
        )


def migrate_linear_to_graph(
    wf: Workflow,
) -> tuple[WorkflowDefinition, WorkflowRunState]:
    """기존 선형 Workflow를 WorkflowDefinition + WorkflowRunState로 변환한다.

    - WorkflowStep.max_retry → WorkflowNode.retry
    - 단계 순서대로 순차 연결(from_output=0) 생성
    - 기존 status/notes는 RunState로 분리
    """
    nodes = [
        WorkflowNode(
            id=s.id,
            title=s.title,
            type=s.type,
            retry=s.max_retry,
            group=s.group,
        )
        for s in wf.steps
    ]
    connections = [
        WorkflowConnection(from_node=nodes[i].id, to_node=nodes[i + 1].id)
        for i in range(len(nodes) - 1)
    ]
    defn = WorkflowDefinition(
        id=wf.thread_id,
        task_type=wf.task_type,
        title=wf.title,
        nodes=nodes,
        connections=connections,
    )
    rs = WorkflowRunState(definition_id=wf.thread_id)
    rs.node_states = {
        s.id: NodeState(status=s.status, notes=s.notes)
        for s in wf.steps
    }
    return defn, rs

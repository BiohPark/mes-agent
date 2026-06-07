import json
import uuid
import os
from pathlib import Path

from .model import (
    Workflow,
    WorkflowStep,
    WorkflowDefinition,
    WorkflowRunState,
    migrate_linear_to_graph,
)

# ── 태스크별 기본 워크플로우 템플릿 ──────────────────────────────

_DEFAULT_STEPS: dict[str, list[dict]] = {
    "general": [
        {"title": "요청 분석 및 목표 파악", "type": "auto"},
        {"title": "필요 도구·리소스 확인", "type": "auto"},
        {"title": "작업 실행", "type": "auto"},
        {"title": "결과 검증 및 보고", "type": "auto"},
    ],
    "syncade": [
        {"title": "빌드 상태 및 버전 확인", "type": "auto"},
        {"title": "배포 환경 서버 접속", "type": "auto"},
        {"title": "배포 패키지 업로드", "type": "semi_auto"},
        {"title": "배포 실행 (Syncade)", "type": "semi_auto"},
        {"title": "서비스 정상 기동 확인", "type": "auto"},
        {"title": "배포 결과 기록 및 보고", "type": "auto"},
    ],
    "obsidian-rag": [
        {"title": "키워드 검색 (obsidian_search)", "type": "auto"},
        {"title": "관련 노트 읽기·링크 탐색", "type": "auto"},
        {"title": "정보 종합 및 답변 작성", "type": "auto"},
        {"title": "새 인사이트 노트 저장", "type": "auto"},
    ],
    "unscript": [
        {"title": "테스트 대상 화면 확인 (OCR)", "type": "auto"},
        {"title": "테스트 케이스 설계", "type": "semi_auto"},
        {"title": "자동화 스크립트 실행", "type": "auto"},
        {"title": "결과 스크린샷 비교·분석", "type": "auto"},
        {"title": "버그 리포트 작성", "type": "auto"},
    ],
    "knox": [
        {"title": "Knox 시스템 접속 확인", "type": "auto"},
        {"title": "수집 대상 채널·메일함 지정", "type": "semi_auto"},
        {"title": "데이터 수집 실행", "type": "auto"},
        {"title": "수집 데이터 정리·중복 제거", "type": "auto"},
        {"title": "결과 파일 저장 및 보고", "type": "auto"},
    ],
}

_DEFAULT_TITLES: dict[str, str] = {
    "general":      "기본업무 워크플로우",
    "syncade":      "Syncade 배포 절차",
    "obsidian-rag": "Obsidian RAG 조회",
    "unscript":     "Unscript 테스트 절차",
    "knox":         "Knox 데이터 수집",
}


def _make_default(task_type: str, thread_id: str) -> Workflow:
    steps_def = _DEFAULT_STEPS.get(task_type, _DEFAULT_STEPS["general"])
    steps = [
        WorkflowStep(
            id=uuid.uuid4().hex[:8],
            title=s["title"],
            type=s["type"],
            status="pending",
            notes="",
        )
        for s in steps_def
    ]
    title = _DEFAULT_TITLES.get(task_type, "워크플로우")
    return Workflow(thread_id=thread_id, task_type=task_type, title=title, steps=steps)


def _make_default_definition(task_type: str, thread_id: str) -> WorkflowDefinition:
    wf = _make_default(task_type, thread_id)
    defn, _ = migrate_linear_to_graph(wf)
    return defn


# ── 포맷 감지 ─────────────────────────────────────────────────

def detect_format(data: dict) -> str:
    """JSON 데이터가 선형(linear) 또는 그래프(graph) 포맷인지 반환한다."""
    if "nodes" in data:
        return "graph"
    return "linear"


# ── 경로 헬퍼 ─────────────────────────────────────────────────

def _workflow_dir() -> Path | None:
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault:
        return None
    return Path(vault) / "agent" / "workflows"


def _wf_path(task_type: str, thread_id: str) -> Path | None:
    d = _workflow_dir()
    return (d / task_type / f"{thread_id}.json") if d else None


def _state_path(task_type: str, thread_id: str) -> Path | None:
    d = _workflow_dir()
    return (d / task_type / f"{thread_id}_state.json") if d else None


# ── 기존 선형 모델 스토리지 (하위 호환 유지) ───────────────────────

def load_workflow(task_type: str, thread_id: str) -> Workflow:
    """저장된 워크플로우가 없으면 기본 템플릿을 만들어 저장 후 반환한다.

    기본 템플릿을 최초 1회 영속화해야 단계 id가 고정된다.
    그래야 우측 패널이 보여주는 id와 workflow_set_step이 찾는 id가 일치한다.

    새 그래프 포맷(nodes 키)으로 저장된 파일도 Workflow로 변환해 반환한다.
    """
    path = _wf_path(task_type, thread_id)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if detect_format(data) == "graph":
                return _graph_data_to_workflow(data, task_type, thread_id)
            return Workflow.from_dict(data)
        except Exception:
            pass
    wf = _make_default(task_type, thread_id)
    save_workflow(wf)
    return wf


def _graph_data_to_workflow(data: dict, task_type: str, thread_id: str) -> Workflow:
    """그래프 포맷 데이터를 Workflow로 변환한다 (하위 호환 + connections 포함)."""
    defn = WorkflowDefinition.from_dict(data)
    rs = load_run_state(task_type, thread_id)
    steps = []
    for n in defn.nodes:
        ns = rs.node_states.get(n.id) if rs else None
        steps.append(WorkflowStep(
            id=n.id,
            title=n.title,
            type=n.type,
            status=ns.status if ns else "pending",
            notes=ns.notes if ns else "",
            max_retry=n.retry,
        ))
    wf = Workflow(thread_id=defn.id, task_type=defn.task_type, title=defn.title, steps=steps)
    wf.connections = [c.to_dict() for c in defn.connections]
    return wf


def save_workflow(workflow: Workflow) -> None:
    path = _wf_path(workflow.task_type, workflow.thread_id)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_workflow(task_type: str, thread_id: str) -> None:
    path = _wf_path(task_type, thread_id)
    if path and path.exists():
        path.unlink()


# ── 새 그래프 모델 스토리지 ───────────────────────────────────────

def load_definition(task_type: str, thread_id: str) -> WorkflowDefinition:
    """WorkflowDefinition을 로드한다.

    - 그래프 포맷 파일: 바로 역직렬화
    - 선형 포맷 파일: migrate_linear_to_graph로 자동 변환
    - 파일 없음: 기본 템플릿으로 생성
    """
    path = _wf_path(task_type, thread_id)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if detect_format(data) == "graph":
                return WorkflowDefinition.from_dict(data)
            # 선형 포맷 자동 마이그레이션
            wf = Workflow.from_dict(data)
            defn, _ = migrate_linear_to_graph(wf)
            return defn
        except Exception:
            pass
    defn = _make_default_definition(task_type, thread_id)
    save_definition(defn)
    return defn


def save_definition(defn: WorkflowDefinition) -> None:
    path = _wf_path(defn.task_type, defn.id)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(defn.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_run_state(task_type: str, thread_id: str) -> WorkflowRunState | None:
    """RunState 파일이 있으면 로드, 없으면 None 반환."""
    path = _state_path(task_type, thread_id)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return WorkflowRunState.from_dict(data)
        except Exception:
            pass
    return None


def save_run_state(task_type: str, thread_id: str, rs: WorkflowRunState) -> None:
    path = _state_path(task_type, thread_id)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rs.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

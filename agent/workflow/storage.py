import json
import uuid
import os
import yaml
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
    "obsidian": [
        {"title": "목적 파악 및 탐색 전략 수립", "type": "auto"},
        {"title": "검색·스캔으로 관련 노트 파악", "type": "auto"},
        {"title": "노트 읽기·분석 (섹션·역링크)", "type": "auto"},
        {"title": "편집·정리·새 노트 작성", "type": "semi_auto"},
        {"title": "결과 요약 및 사용자 보고", "type": "auto"},
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
    "obsidian":     "Obsidian PKM 작업",
    "unscript":     "Unscript 테스트 절차",
    "knox":         "Knox 데이터 수집",
}


def _template_path(task_type: str) -> Path | None:
    d = _workflow_dir()
    return (d / "_templates" / f"{task_type}.md") if d else None


def load_template(task_type: str) -> dict:
    """태스크 유형의 기본 템플릿을 로드. 없으면 하드코딩 기본값 반환."""
    path = _template_path(task_type)
    if path and path.exists():
        try:
            content = path.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2:
                    data = yaml.safe_load(parts[1])
                    if data and "steps" in data:
                        return data
        except Exception:
            pass
    return {
        "title": _DEFAULT_TITLES.get(task_type, "워크플로우"),
        "steps": _DEFAULT_STEPS.get(task_type, _DEFAULT_STEPS["general"]),
    }


def save_template(task_type: str, title: str, steps: list) -> None:
    """태스크 유형의 기본 템플릿을 Vault에 저장한다."""
    path = _template_path(task_type)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"title": title, "steps": steps}
    content = "---\n" + yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False) + "---\n"
    path.write_text(content, encoding="utf-8")


def _make_default(task_type: str, thread_id: str) -> Workflow:
    tmpl = load_template(task_type)
    steps_def = tmpl.get("steps", _DEFAULT_STEPS.get(task_type, _DEFAULT_STEPS["general"]))
    title = tmpl.get("title", _DEFAULT_TITLES.get(task_type, "워크플로우"))
    steps = [
        WorkflowStep(
            id=uuid.uuid4().hex[:8],
            title=s["title"] if isinstance(s, dict) else s,
            type=s.get("type", "auto") if isinstance(s, dict) else "auto",
            status="pending",
            notes="",
        )
        for s in steps_def
    ]
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
    """구 JSON 경로 — 하위 호환 및 linear format 저장용."""
    d = _workflow_dir()
    return (d / task_type / f"{thread_id}.json") if d else None


def _def_path(task_type: str, thread_id: str) -> Path | None:
    """새 YAML frontmatter (.md) 경로 — WorkflowDefinition 저장용."""
    d = _workflow_dir()
    return (d / task_type / f"{thread_id}.md") if d else None


def _state_path(task_type: str, thread_id: str) -> Path | None:
    d = _workflow_dir()
    return (d / task_type / f"{thread_id}_state.json") if d else None


# ── 기존 선형 모델 스토리지 (하위 호환 유지) ───────────────────────

def load_workflow(task_type: str, thread_id: str) -> Workflow:
    """저장된 워크플로우가 없으면 기본 템플릿을 만들어 저장 후 반환한다.

    기본 템플릿을 최초 1회 영속화해야 단계 id가 고정된다.
    그래야 우측 패널이 보여주는 id와 workflow_set_step이 찾는 id가 일치한다.

    우선순위: .md (YAML frontmatter) → .json (기존) → 기본 템플릿
    """
    # 1) .md 파일 (그래프 포맷, Phase 4C 이후 기본)
    md_path = _def_path(task_type, thread_id)
    if md_path and md_path.exists():
        defn = _load_definition_from_md(md_path)
        if defn:
            return _graph_data_to_workflow(defn.to_dict(), task_type, thread_id)

    # 2) .json 파일 (기존 포맷 하위 호환)
    path = _wf_path(task_type, thread_id)
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if detect_format(data) == "graph":
                return _graph_data_to_workflow(data, task_type, thread_id)
            return Workflow.from_dict(data)
        except Exception:
            pass

    # 3) 기본 템플릿
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
            group=n.group,
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
    for path in (
        _wf_path(task_type, thread_id),    # 구 .json
        _def_path(task_type, thread_id),   # 새 .md
        _state_path(task_type, thread_id), # RunState
    ):
        if path and path.exists():
            path.unlink()


# ── 새 그래프 모델 스토리지 ───────────────────────────────────────

def _load_definition_from_md(path: Path) -> WorkflowDefinition | None:
    """YAML frontmatter .md 파일에서 WorkflowDefinition을 로드한다."""
    try:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 2:
            return None
        data = yaml.safe_load(parts[1])
        if not data or "nodes" not in data:
            return None
        return WorkflowDefinition.from_dict(data)
    except Exception:
        return None


def load_definition(task_type: str, thread_id: str) -> WorkflowDefinition:
    """WorkflowDefinition을 로드한다.

    우선순위: .md (YAML frontmatter) → .json (그래프 포맷) → .json (선형 포맷 자동 마이그레이션) → 기본 템플릿
    .json 파일을 읽으면 .md로 자동 마이그레이션하고 .json을 삭제한다.
    """
    md_path = _def_path(task_type, thread_id)
    json_path = _wf_path(task_type, thread_id)

    # 1) .md 파일 우선
    if md_path and md_path.exists():
        defn = _load_definition_from_md(md_path)
        if defn:
            return defn

    # 2) .json 파일 — 읽은 후 .md로 마이그레이션
    if json_path and json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if detect_format(data) == "graph":
                defn = WorkflowDefinition.from_dict(data)
            else:
                wf = Workflow.from_dict(data)
                defn, _ = migrate_linear_to_graph(wf)
            # .md로 저장 후 .json 삭제
            save_definition(defn)
            try:
                json_path.unlink()
            except Exception:
                pass
            return defn
        except Exception:
            pass

    # 3) 파일 없음 — 기본 템플릿
    defn = _make_default_definition(task_type, thread_id)
    save_definition(defn)
    return defn


def save_definition(defn: WorkflowDefinition) -> None:
    """WorkflowDefinition을 YAML frontmatter .md 파일로 저장한다."""
    path = _def_path(defn.task_type, defn.id)
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = defn.to_dict()
    content = "---\n" + yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False) + "---\n"
    path.write_text(content, encoding="utf-8")


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

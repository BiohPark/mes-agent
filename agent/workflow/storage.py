import json
import uuid
import os
from pathlib import Path

from .model import Workflow, WorkflowStep

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


# ── 스토리지 함수 ─────────────────────────────────────────────

def _workflow_dir() -> Path | None:
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()
    if not vault:
        return None
    return Path(vault) / "agent" / "workflows"


def load_workflow(task_type: str, thread_id: str) -> Workflow:
    """저장된 워크플로우가 없으면 태스크별 기본 템플릿을 반환한다."""
    d = _workflow_dir()
    if d:
        path = d / task_type / f"{thread_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return Workflow.from_dict(data)
            except Exception:
                pass
    return _make_default(task_type, thread_id)


def save_workflow(workflow: Workflow) -> None:
    d = _workflow_dir()
    if not d:
        return
    path = d / workflow.task_type / f"{workflow.thread_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_workflow(task_type: str, thread_id: str) -> None:
    d = _workflow_dir()
    if not d:
        return
    path = d / task_type / f"{thread_id}.json"
    if path.exists():
        path.unlink()

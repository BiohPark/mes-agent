"""도구 실행 타임아웃 — 작은 예상시간(baseline)에서 시작해 단계적으로 연장하고,
캡 도달 시 구조화·분류된 결과를 돌려 에이전트가 다음 행동을 판단하게 한다.

긴급수정(A1): 디스패치 경계 통일 타임아웃의 순수 로직. IO/asyncio 없음 → 테스트 1급.
전체 적응형(진행도 탐지·자동 백그라운드·인루프 판단)은 백로그 V(docs/backlog/pending/V-*)로 분리.

출처(클린룸): 본인 코드 + 일반 에이전트 지식 + openclaw(MIT)/LangGraph 공개 패턴
+ claw-code(MIT, 사용자 클리어 — 패턴만): 구조화·분류된 타임아웃 결과(failureClass/provenance). 코드 미복사.
"""
import os
import json

DEFAULT_BASELINE = 6.0  # 미등록 도구 기본 예상시간(초)

# 도구별 작은 예상시간(초). 빠른 로컬 작업은 짧게, 외부/COM은 길게 시작한다.
TOOL_BASELINES = {
    # 즉시성 로컬 조회
    "list_directory": 0.6,
    "file_exists": 0.3,
    "is_process_running": 0.6,
    "list_processes": 1.5,
    "get_system_info": 1.5,
    "get_pixel_color": 0.6,
    # 파일/문서 읽기
    "read_file": 2.0,
    "read_excel": 4.0,
    "read_word": 4.0,
    "read_pdf": 6.0,
    # 명령/프로세스
    "run_command": 8.0,
    "run_powershell": 8.0,
    "start_process": 5.0,
    # 화면/OCR/비전
    "ocr_screen": 4.0,
    "ocr_region": 3.0,
    "capture_screen": 6.0,
    "analyze_screen": 20.0,
    "analyze_region": 18.0,
}

# 접두 기반 카테고리 기본(개별 미등록 시). 위에서부터 첫 일치 사용.
_PREFIX_BASELINES = [
    ("browser_", 15.0),
    ("office_", 12.0),
    ("excel_", 12.0),
    ("word_", 12.0),
    ("ppt_", 12.0),
    ("ui_", 6.0),
    ("obsidian_", 5.0),
    ("memory_", 4.0),
    ("workflow_", 2.0),
]


def _baseline_overrides() -> dict:
    """env TOOL_BASELINE_OVERRIDES = JSON {도구명: 초}."""
    raw = os.getenv("TOOL_BASELINE_OVERRIDES", "")
    if not raw:
        return {}
    try:
        d = json.loads(raw)
        return {k: float(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except Exception:
        return {}


def tool_baseline(name: str) -> float:
    """도구의 예상 baseline(초). env override → 개별 → 접두 카테고리 → 기본 순."""
    ov = _baseline_overrides()
    if name in ov:
        return ov[name]
    if name in TOOL_BASELINES:
        return TOOL_BASELINES[name]
    for pre, sec in _PREFIX_BASELINES:
        if name.startswith(pre):
            return sec
    return DEFAULT_BASELINE


def timeout_cap() -> float:
    """디스패치 경계 하드 캡(초). 어떤 도구도 이보다 오래 SSE를 막지 못한다."""
    raw = os.getenv("TOOL_TIMEOUT_CAP", "")
    try:
        return float(raw) if raw else 90.0
    except ValueError:
        return 90.0


def office_com_timeout() -> float:
    """office COM 자체 타임아웃(초). 디스패치 캡보다 짧게 → office가 먼저 자가복구."""
    raw = os.getenv("OFFICE_COM_TIMEOUT", "")
    try:
        return float(raw) if raw else 45.0
    except ValueError:
        return 45.0


def escalation_schedule(baseline: float, cap: float, factor: float = 4.0) -> list[float]:
    """'시작부터의 누적 대기 한계(초)' 리스트(단조 증가, 마지막=cap).
    예: baseline=1, cap=90, factor=4 → [1, 4, 16, 64, 90].
    호출부는 인접 차이를 incremental wait_for timeout으로 쓴다.
    """
    if baseline <= 0:
        baseline = 0.1
    if cap <= 0:
        cap = baseline
    steps: list[float] = []
    t = baseline
    while t < cap:
        steps.append(round(t, 3))
        t *= factor
    steps.append(round(cap, 3))
    out: list[float] = []
    for s in steps:
        if not out or s > out[-1]:
            out.append(s)
    return out


def classify_timeout(name: str, waited: float, progressed: bool = False) -> dict:
    """캡 도달/중단 시 구조화·분류 결과. 에이전트가 재시도/대안/질의를 판단하게 한다."""
    failure = "slow" if progressed else "stuck"
    if progressed:
        hint = ("작업이 진행 중일 수 있습니다(부분 진행 신호) — 더 큰 timeout으로 재시도하거나 작업을 분할하세요.")
    else:
        hint = ("진행 신호가 없어 멈춘 것으로 판단됩니다 — 원인(파일이 이미 열림/모달 대화상자/잠금)을 제거하거나, "
                "대안 경로(예: Excel COM 대신 openpyxl)·사용자 확인을 고려하세요.")
    return {
        "failureClass": failure,
        "provenance": "dispatch.timeout",
        "tool": name,
        "waited_seconds": round(waited, 1),
        "hint": hint,
    }


def timeout_error_text(name: str, waited: float, progressed: bool = False) -> str:
    """tool 결과 문자열. '툴 실행 오류' 접두 → 기존 UI/서버 에러 분기 재사용."""
    info = classify_timeout(name, waited, progressed)
    return (f"툴 실행 오류: '{name}'이(가) {info['waited_seconds']}초 내에 끝나지 않아 중단했습니다"
            f"({info['failureClass']}). {info['hint']}")

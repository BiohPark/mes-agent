"""도구 실행 타임아웃 — 작은 예상시간(baseline)에서 시작해 단계적으로 연장하고,
캡 도달 시 구조화·분류된 결과를 돌려 에이전트가 다음 행동을 판단하게 한다.

긴급수정(A1): 디스패치 경계 통일 타임아웃의 순수 로직. IO/asyncio 없음 → 테스트 1급.
전체 적응형(진행도 탐지·자동 백그라운드·인루프 판단)은 백로그 V(docs/backlog/pending/V-*)로 분리.

출처(클린룸): 본인 코드 + 일반 에이전트 지식 + openclaw(MIT)/LangGraph 공개 패턴
+ claw-code(MIT, 사용자 클리어 — 패턴만): 구조화·분류된 타임아웃 결과(failureClass/provenance). 코드 미복사.
"""
import os
import json
from dataclasses import asdict, dataclass

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

# ── 인루프 판단: 도구별 회복 대안 ──────────────────────────────
# 타임아웃 결과에 포함되어 LLM이 명확히 선택하도록 유도한다.
# 조회 우선순위: 정확한 도구명 → 접두(key가 "_"로 끝남) → 기본값.
_TOOL_ALTERNATIVES: dict[str, list[str]] = {
    # ── 명령 실행 ──────────────────────────────────────────────
    "run_command": [
        "timeout 파라미터를 늘려(예: 120) 재시도",
        "명령을 더 짧게 분할해 순차 실행",
        "start_process로 백그라운드 실행 후 결과 파일 확인",
        "ask_user로 사용자에게 보고",
    ],
    "run_powershell": [
        "timeout 파라미터를 늘려 재시도",
        "run_command(shell='cmd')로 대체",
        "명령을 단계별로 분할",
        "ask_user로 사용자에게 보고",
    ],
    "start_process": [
        "프로세스가 이미 실행 중인지 list_processes로 확인",
        "is_process_running으로 실행 확인 후 결과 파일 폴링",
        "ask_user로 사용자에게 보고",
    ],
    # ── 문서/파일 읽기 ─────────────────────────────────────────
    "read_excel": [
        "더 좁은 행/열 범위를 지정해 재시도",
        "파일을 CSV로 변환 후 read_file 사용",
        "excel_get_range로 소범위 직접 읽기",
        "ask_user로 사용자에게 보고",
    ],
    "read_word": [
        "read_file로 텍스트만 추출 시도",
        "ocr_region으로 화면에서 직접 읽기",
        "ask_user로 사용자에게 보고",
    ],
    "read_pdf": [
        "페이지 범위를 줄여 재시도",
        "ocr_region으로 PDF 뷰어 화면에서 직접 읽기",
        "ask_user로 사용자에게 보고",
    ],
    # ── 화면/비전 ──────────────────────────────────────────────
    "analyze_screen": [
        "analyze_region으로 관심 영역만 분석",
        "ocr_screen으로 텍스트만 추출(멀티모달 없이)",
        "capture_screen으로 메인 LLM에 이미지 직접 주입",
    ],
    "analyze_region": [
        "영역을 더 작게 조정해 재시도",
        "ocr_region으로 텍스트 추출",
        "capture_screen으로 메인 LLM에 이미지 직접 주입",
    ],
    "capture_screen": [
        "screenshot_region으로 작은 영역만 캡처",
        "ocr_screen으로 텍스트 추출로 전환",
    ],
    # ── 접두 기반 카테고리 ─────────────────────────────────────
    "browser_": [
        "browser_wait_for_selector 또는 wait_for_load_state 후 재시도",
        "timeout 파라미터를 늘려 재시도",
        "browser_screenshot으로 현재 상태 확인 후 다음 단계 결정",
        "ask_user로 사용자에게 보고",
    ],
    "office_": [
        "python-docx/openpyxl 폴백 도구(read_word/read_excel)로 대체",
        "Office 프로세스 종료 후 재시도(kill_process)",
        "파일을 다른 경로에서 열기 시도",
        "ask_user로 사용자에게 보고",
    ],
    "excel_": [
        "python-openpyxl 기반 read_excel로 대체",
        "셀 범위를 줄여 재시도",
        "파일을 CSV로 변환 후 read_file",
        "ask_user로 사용자에게 보고",
    ],
    "word_": [
        "read_word로 텍스트 읽기 전환",
        "python-docx 기반 도구로 대체",
        "ask_user로 사용자에게 보고",
    ],
    "obsidian_": [
        "obsidian_search로 먼저 범위를 좁혀 재시도",
        "OBSIDIAN_VAULT_PATH 직접 파일 접근으로 대체",
        "ask_user로 사용자에게 보고",
    ],
}

_DEFAULT_ALTERNATIVES: list[str] = [
    "더 큰 timeout 값으로 재시도",
    "ask_user로 사용자에게 현재 상황 보고",
]


def _lookup_alternatives(name: str) -> list[str]:
    """도구명으로 회복 대안 리스트를 조회. 개별 → 접두 → 기본 순."""
    if name in _TOOL_ALTERNATIVES:
        return _TOOL_ALTERNATIVES[name]
    for key, alts in _TOOL_ALTERNATIVES.items():
        if key.endswith("_") and name.startswith(key[:-1]):
            return alts
    return _DEFAULT_ALTERNATIVES


@dataclass(frozen=True)
class LivenessObservation:
    """도구 외부에서 관측 가능한 최소 진행 신호.

    process/run_command처럼 stdout/stderr와 프로세스 생존 여부를 볼 수 있는 경로만
    이 구조를 채운다. COM/브라우저/UI 도구는 후속 카드에서 별도 관측자를 붙인다.
    """

    elapsed_seconds: float
    process_alive: bool
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    no_progress_count: int = 0


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


def timeout_hard_ceiling() -> float:
    """어떤 도구도 이 절대 상한(초)을 넘겨 대기하지 않는다 — 도구 자체 timeout이 아무리 커도 무시."""
    raw = os.getenv("TOOL_TIMEOUT_HARD_CEILING", "")
    try:
        return float(raw) if raw else 300.0
    except ValueError:
        return 300.0


def effective_cap(name: str, arguments) -> float:
    """디스패치 캡을 계산한다 — 도구가 명시적으로 요청한 timeout을 존중하되 절대 상한은 유지.

    run_command/run_powershell처럼 자체 timeout 인자를 받는 도구가 회복 조치(timeout 늘려
    재시도)를 따라도, 디스패치 레벨 캡(기본 90s)이 그보다 먼저 끝내버려 무의미해지는 문제를 막는다.

    arguments는 run_tool()과 동일한 형태 — generate() 루프에서는 LLM이 스트리밍으로 누적한
    **JSON 문자열**(아직 파싱 전)이고, 직접 호출/테스트에서는 dict일 수도 있다. 파싱 실패·
    timeout 필드 없음·숫자가 아니면 기존 timeout_cap()만 사용한다(절대 예외를 던지지 않음).
    """
    base = timeout_cap()
    parsed: dict = {}
    if isinstance(arguments, dict):
        parsed = arguments
    elif isinstance(arguments, str) and arguments.strip():
        try:
            loaded = json.loads(arguments)
        except (TypeError, ValueError):
            loaded = None
        if isinstance(loaded, dict):
            parsed = loaded
    raw_timeout = parsed.get("timeout")
    if not isinstance(raw_timeout, (int, float)) or isinstance(raw_timeout, bool):
        return base
    buffer = 5.0
    return min(timeout_hard_ceiling(), max(base, float(raw_timeout) + buffer))


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


def _observation_progressed(observation: LivenessObservation) -> bool:
    return (observation.stdout_bytes + observation.stderr_bytes) > 0


def classify_liveness(name: str, waited: float, observation: LivenessObservation) -> dict:
    """진행 관측값을 기준으로 slow/stuck을 분류한다.

    첫 spike의 보수적 규칙:
    - stdout/stderr 증가가 한 번이라도 있으면 "느리지만 살아있음(slow)".
    - 출력 증가가 없고 프로세스가 계속 살아 있거나 이미 경합적으로 종료됐으면 "stuck".
    - no_progress_count는 근거로 남기되, 출력 증가 신호를 뒤집지는 않는다.
    """
    return classify_timeout(name, waited, progressed=_observation_progressed(observation),
                            observation=observation)


def classify_timeout(name: str, waited: float, progressed: bool = False,
                     observation: LivenessObservation | None = None) -> dict:
    """캡 도달/중단 시 구조화·분류 결과. 에이전트가 재시도/대안/질의를 판단하게 한다."""
    if observation:
        progressed = _observation_progressed(observation)
    failure = "slow" if progressed else "stuck"
    if progressed:
        hint = ("작업이 진행 중일 수 있습니다(부분 진행 신호) — 더 큰 timeout으로 재시도하거나 작업을 분할하세요.")
    else:
        hint = ("진행 신호가 없어 멈춘 것으로 판단됩니다 — 원인(파일이 이미 열림/모달 대화상자/잠금)을 제거하거나, "
                "대안 경로(예: Excel COM 대신 openpyxl)·사용자 확인을 고려하세요.")
    out = {
        "failureClass": failure,
        "provenance": "dispatch.timeout.liveness" if observation else "dispatch.timeout",
        "tool": name,
        "waited_seconds": round(waited, 1),
        "hint": hint,
        "alternatives": _lookup_alternatives(name),
    }
    if observation:
        out["liveness"] = asdict(observation)
        out["liveness"]["elapsed_seconds"] = round(observation.elapsed_seconds, 1)
    return out


def timeout_error_text(name: str, waited: float, progressed: bool = False,
                       observation: LivenessObservation | None = None) -> str:
    """tool 결과 문자열. '툴 실행 오류' 접두 → 기존 UI/서버 에러 분기 재사용."""
    info = classify_timeout(name, waited, progressed, observation)
    alts_text = "\n".join(f"  {i + 1}. {a}" for i, a in enumerate(info["alternatives"]))
    return (
        f"툴 실행 오류: '{name}'이(가) {info['waited_seconds']}초 내에 끝나지 않았습니다"
        f"({info['failureClass']}).\n"
        f"{info['hint']}\n"
        f"회복 옵션:\n{alts_text}\n"
        f"위 옵션 중 하나를 선택해 진행하거나, 선택이 어려우면 ask_user로 사용자에게 보고하세요."
    )

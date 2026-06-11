import sys
import json
import asyncio
import os
import uuid
from pathlib import Path
import uvicorn
from fastapi import FastAPI

# 'python agent/server.py' 직접 실행 시 프로젝트 루트를 sys.path에 추가
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Electron이 .env를 주입하지 않는 환경(직접 실행)에서도 동작하도록
_env_path = Path(__file__).parent.parent / '.env'
if _env_path.exists():
    for line in _env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from agent.config import get_active, active_llm, list_profiles, set_active_profile
from agent.llm import get_client, get_model
from agent.config import get_context_window
from agent.tools import TOOLS, TOOL_LABELS, run_tool, select_tools, tool_risk_hint
from agent.tools._safety import classify_risk, risk_confirm_message, command_excerpt
from agent.tools.vision import parse_capture_envelope, build_capture_message
from agent.core.compaction import compact_messages, prune_images
from agent.core.tokens import estimate_message_tokens
from agent.core.overflow import is_context_overflow, is_recoverable
from agent.memory import MemoryStore
from agent.obsidian_session import get_session_manager, TASK_CONFIGS
from agent.workflow import storage as wf_storage
from agent.workflow.model import WorkflowRunState
from agent.core import events as ev

app = FastAPI()

# ── 상태 테이블 ───────────────────────────────────────────────
_pending_confirms: dict[str, asyncio.Event] = {}
_confirm_results: dict[str, dict] = {}
_stop_flags: dict[str, bool] = {}

# G3 안전 게이트: 사용자 확인 대기 타임아웃(초). 타임아웃=거부(무인 자동승인 금지).
_CONFIRM_TIMEOUT = 300
# "항상 허용" 선택을 세션 동안 기억하는 허용목록(키=thread_id 또는 request_id).
_session_allowlists: dict[str, set] = {}


# ── S: 도구 의도 라벨 (규칙 기반) ─────────────────────────────
# 모델 자유텍스트 예고는 _AUTO_EXEC가 금지(L1 루프 보호)하므로, 서버가
# 도구명+핵심 인자로 "무엇을 하려는지" 한 줄 라벨을 합성해 tool_start로 보낸다.
_CMD_TOOLS = {"run_command", "run_powershell", "start_process"}
_BROWSER_NAV_TOOLS = {"browser_open", "browser_navigate", "office_web_open"}


def _intent_label(name: str, arguments) -> str:
    """tool_start에 표시할 의도 라벨을 만든다(파싱 실패·미매칭 시 정적 라벨 폴백)."""
    base = TOOL_LABELS.get(name, name)
    try:
        args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
        if not isinstance(args, dict):
            return base
    except Exception:
        return base

    def _trim(s, n=60):
        s = str(s).strip().replace("\n", " ")
        return s if len(s) <= n else s[: n - 1] + "…"

    try:
        if name in _CMD_TOOLS:
            cmd = command_excerpt(args)
            return f"▶ {_trim(cmd)} 실행" if cmd else base
        if name in _BROWSER_NAV_TOOLS:
            url = args.get("url") or args.get("path") or ""
            if url:
                host = url.split("//", 1)[-1].split("/", 1)[0]
                return f"🌐 {_trim(host, 40)} 여는 중"
            return base
        # 파일 계열: 경로 basename 노출
        path = args.get("path") or args.get("file_path") or args.get("file") or args.get("doc_path") or ""
        if path:
            import os as _os
            return f"{base} · {_trim(_os.path.basename(str(path)), 40)}"
        # 셀렉터/텍스트 입력 계열
        sel = args.get("selector") or args.get("text") or args.get("query") or ""
        if sel:
            return f"{base} · {_trim(sel, 40)}"
    except Exception:
        return base
    return base


_TOOL_WAIT_NARRATE_AFTER = 1.5  # 이 누적 초과부터만 TOOL_WAIT 내레이션(빠른 작업 UI 소음 방지)


async def _run_tool_watched(loop, name, arguments, label):
    """run_tool을 단계적(escalating) wait_for로 감싸 **무한 행을 방지**한다(긴급수정 A1).

    - 도구별 작은 baseline에서 시작 → 안 끝나면 누적 한계를 늘려가며 **같은 in-flight 작업을 계속 대기**.
    - 가시 임계(>1.5s)를 넘겨 연장할 때마다 ('wait', payload)를 yield → 호출부가 TOOL_WAIT SSE로 내레이션.
    - 끝나면 ('result', 결과)를 yield. 캡 도달 시 구조화 타임아웃 오류('툴 실행 오류' 접두)를 결과로.
    - run_tool 자체 예외는 전파(호출부 except가 처리).
    """
    from agent.core import timeouts as _to
    schedule = _to.escalation_schedule(_to.tool_baseline(name), _to.timeout_cap())
    fut = loop.run_in_executor(None, run_tool, name, arguments)
    prev = 0.0
    for i, limit in enumerate(schedule):
        delta = max(0.05, limit - prev)
        prev = limit
        try:
            result = await asyncio.wait_for(asyncio.shield(fut), timeout=delta)
            yield ("result", result)
            return
        except asyncio.TimeoutError:
            # 아직 진행 중 — 다음 단계가 있고 가시 임계를 넘었으면 연장 내레이션
            if i < len(schedule) - 1 and limit >= _TOOL_WAIT_NARRATE_AFTER:
                yield ("wait", {
                    "tool": name, "label": label,
                    "elapsed": round(limit, 1), "next": round(schedule[i + 1], 1),
                })
            continue
    # 캡 도달 → SSE 해방(스레드는 남되, office 등은 자체 워치독으로 실제 정리됨)
    fut.cancel()
    yield ("result", _to.timeout_error_text(name, _to.timeout_cap(), progressed=False))


async def _resolve_confirm(cid: str) -> dict:
    """confirm_id에 대한 사용자 응답을 대기해 회수한다(SSE는 호출부에서 emit).

    Event 생성·타임아웃 대기·결과 회수·정리를 한곳에서 처리한다.
    ask_user 확인과 G3 안전 게이트가 공통으로 사용한다.
    """
    ev_obj = asyncio.Event()
    _pending_confirms[cid] = ev_obj
    try:
        await asyncio.wait_for(ev_obj.wait(), timeout=_CONFIRM_TIMEOUT)
        return _confirm_results.pop(cid, {"choice": "타임아웃", "custom_text": ""})
    except asyncio.TimeoutError:
        return {"choice": "타임아웃으로 자동 중단", "custom_text": ""}
    finally:
        _pending_confirms.pop(cid, None)


@app.on_event("startup")
async def startup():
    get_session_manager().setup_vault()


@app.on_event("startup")
async def startup_mcp():
    # MCP 서버 연결·도구 등록 (백로그 J). 무설정/미설치/실패여도 앱은 계속.
    if os.environ.get("MCP_ENABLED", "true").lower() == "false":
        return
    try:
        from agent.mcp_client import get_manager
        n = await asyncio.get_event_loop().run_in_executor(None, get_manager().connect_all)
        if n:
            print(f"[mcp] {n}개 도구 등록됨")
    except Exception as e:
        print(f"[mcp] 초기화 건너뜀: {e}")


@app.on_event("shutdown")
async def shutdown_mcp():
    try:
        from agent.mcp_client import get_manager
        get_manager().shutdown()
    except Exception:
        pass


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "DELETE", "PATCH", "PUT"],
    allow_headers=["*"],
)


# ── 보안 미들웨어 (S1/S3) ─────────────────────────────────────
# 위협: 인증이 없으면 사용자가 브라우저로 연 악성 웹페이지가 localhost API로
#       요청을 보내 에이전트(임의 PowerShell 실행 등)를 조종할 수 있다.
# 방어: (1) 원격 http(s) Origin 차단 — 웹페이지發 요청 거부
#       (2) 토큰 검증 — Electron이 주입한 시크릿(X-Auth-Token 헤더 또는 ?token=)만 허용
# 토큰 미설정(개발/테스트/직접 실행) 시에는 강제하지 않아 하위 호환을 유지한다.
_AUTH_TOKEN = os.environ.get("AGENT_AUTH_TOKEN", "")
_AUTH_FREE_PATHS = {"/health"}


def _origin_allowed(origin: str) -> bool:
    """원격 웹 출처는 차단. Electron 렌더러(file://→null/없음)·localhost만 허용."""
    if not origin or origin == "null":
        return True
    o = origin.lower()
    if o.startswith("file://"):
        return True
    if o.startswith("http://localhost") or o.startswith("http://127.0.0.1"):
        return True
    return False


@app.middleware("http")
async def _security_gate(request: Request, call_next):
    # CORS 프리플라이트는 통과 (CORSMiddleware가 처리)
    if request.method == "OPTIONS":
        return await call_next(request)

    # (1) 원격 Origin 차단 — 악성 웹페이지發 요청 방어 (토큰 유무와 무관)
    origin = request.headers.get("origin", "")
    if not _origin_allowed(origin):
        return JSONResponse(status_code=403, content={"error": "허용되지 않은 Origin"})

    # (2) 토큰 검증 (토큰이 설정된 경우에만 강제)
    if _AUTH_TOKEN and request.url.path not in _AUTH_FREE_PATHS:
        token = request.headers.get("x-auth-token") or request.query_params.get("token", "")
        if token != _AUTH_TOKEN:
            return JSONResponse(status_code=401, content={"error": "인증 토큰이 유효하지 않습니다"})

    return await call_next(request)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""
    task_type: str = ""
    agent_mode: str = "auto"  # "auto" | "plan"


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _estimate_tokens(messages: list) -> int:
    """메시지 토큰 추정(M3). 텍스트=tiktoken/휴리스틱, 이미지=OpenAI 타일링 공식.

    이미지를 무조건 ~1000토큰 고정으로 세던 것을 치수·detail 기반 추정으로 대체해
    compaction/eviction 타이밍 정확도를 높인다(상세: agent/core/tokens.py).
    """
    return estimate_message_tokens(messages)


_AUTONOMOUS_INSTRUCTION = (
    "너는 사내 업무자동화 데스크탑 에이전트야. "
    "도구 호출 전에 '~하겠습니다', '~할게요' 같은 예고 문구를 절대 쓰지 마라. "
    "바로 도구를 호출해 실행하고, 여러 단계가 필요하면 사용자 확인 없이 연속으로 실행해라. "
    "브라우저 조작 시 browser_open 후 browser_get_interactive_elements로 실제 selector를 먼저 확인해라. "
    "CSS id/class보다 aria-label·placeholder·텍스트 기반 selector를 우선 사용해라. "
    "폼 제출은 버튼 클릭 대신 browser_press_key('Enter')를 사용해라. "
    "selector 실패 시 같은 것을 반복하지 말고 즉시 다른 전략으로 전환해라. "
    "[끈질긴 문제 해결] 첫 시도가 실패해도 멈추거나 사용자에게 떠넘기지 마라. "
    "도구가 오류를 반환하면 오류 메시지로 원인을 추론하고, 화면 OCR·UI Automation·read_file 등으로 "
    "현재 상태를 직접 조사한 뒤, 원인에 맞는 다른 방법으로 재시도해라. 정보가 부족하면 직접 조사·검색해 해결책을 찾아라. "
    "단순 보고로 끝내지 말고 근본 원인을 찾아 실제로 고치는 것을 목표로 해라. "
    "[사용자 선택] 되돌릴 수 없거나 사용자 의도가 필요한 분기에서만 ask_user로 명확한 선택지를 제시해라. "
    "스스로 조사해 알 수 있는 것은 묻지 말고 먼저 조사해라. "
    "[종료 기준] 작업이 진짜 끝났거나 사용자 입력 없이는 더 진행할 수 없을 때만 멈추고, "
    "그때는 시도한 것·막힌 지점·다음 선택지를 명확히 보고해라. "
    "[기억] 사용자가 '이거 기억해/잊어'라고 하면 memory_remember/memory_forget을 호출하고, "
    "과거에 기억해 둔 게 있는지 확인이 필요하면 memory_recall을 사용해라."
)

_MAX_STEPS = 40
_CONTEXT_MAX_TOKENS = 128_000

# G1 컨텍스트 compaction: 임계 비율·보존 메시지 수·최대 압축 횟수
COMPACT_RATIO = 0.8
COMPACT_KEEP_RECENT = 8
MAX_COMPACT = 3

# M2 이미지 eviction: 히스토리에 유지할 최신 화면 이미지 개수(과거는 텍스트 자리표시자)
try:
    VISION_KEEP_LAST_IMAGES = int(os.environ.get("VISION_KEEP_LAST_IMAGES", 2))
except (TypeError, ValueError):
    VISION_KEEP_LAST_IMAGES = 2

# M4 400 점진적 복구: 컨텍스트 초과 시 payload를 줄여 재시도하는 최대 횟수
try:
    MAX_OVERFLOW_RETRY = int(os.environ.get("MAX_OVERFLOW_RETRY", 2))
except (TypeError, ValueError):
    MAX_OVERFLOW_RETRY = 2

# G2 continuation nudge: 작업 도중 텍스트로 조기 종료 시 '계속' 주입(상한)
MAX_NUDGES = 2
_NUDGE_MESSAGE = (
    "[시스템] 작업이 아직 끝나지 않았다면 멈추지 말고 계속 진행하라. "
    "정말 완료됐거나 사용자 입력이 꼭 필요하면 그 이유만 한 줄로 답하라."
)

# G4 plan 모드: 계획만 세우게 하는 시스템 프롬프트 보강
_PLAN_MODE_SUFFIX = (
    "\n\n[계획 모드] 지금은 실제로 실행하지 말고, workflow_init과 "
    "workflow_set_step/workflow_add_step 도구로 전체 작업을 단계로 설계만 하라. "
    "설계가 끝나면 도구를 더 호출하지 말고 '계획 완료'라고만 답하라. "
    "승인 전에는 실제 실행 도구(파일·셸·브라우저 등)를 절대 호출하지 마라."
)
_PLAN_APPROVED_MESSAGE = "[시스템] 계획이 승인되었다. 이제 계획대로 단계를 실행하라."

# 대화 간 장기기억: 과거 대화에서 사실·선호·결정을 추출/주입 (끄려면 MEMORY_ENABLED=false)
MEMORY_ENABLED = os.environ.get("MEMORY_ENABLED", "true").lower() != "false"
# 추출 타이밍: close(스레드 종료 시 1회 일괄, 비용↓) | turn(매 턴) | off(자동 추출 안 함)
MEMORY_EXTRACT_MODE = os.environ.get("MEMORY_EXTRACT_MODE", "close").lower()


def _memory_store() -> MemoryStore:
    return MemoryStore(os.environ.get("OBSIDIAN_VAULT_PATH", "."))


def _extract_memories(history: list) -> list:
    """대화에서 앞으로 기억할 사실·선호·결정을 추출한다(비스트리밍 1회). 실패 시 []."""
    try:
        resp = get_client().chat.completions.create(
            model=get_model(),
            stream=False,
            messages=[
                {"role": "system", "content": (
                    "다음 대화에서 앞으로의 작업에 도움이 될 '지속적 사실·사용자 선호·중요한 결정'만 "
                    "추출하라. 일시적이거나 잡담성 내용은 제외한다. JSON 배열만 출력하라: "
                    '[{"text":"기억할 내용","category":"fact|preference|decision"}]. 없으면 [].'
                )},
                {"role": "user", "content": _history_to_text(history)},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        start, end = raw.find("["), raw.rfind("]")
        if start >= 0 and end > start:
            data = json.loads(raw[start:end + 1])
            return [d for d in data if isinstance(d, dict) and d.get("text")]
    except Exception:
        pass
    return []


def _extract_and_store(history: list, source: str) -> int:
    """history에서 기억을 추출해 저장하고 저장 건수를 반환한다(동기, executor용)."""
    store = _memory_store()
    n = 0
    for f in _extract_memories(history):
        if store.add(f.get("text", ""), f.get("category", "fact"), source):
            n += 1
    return n


def _history_to_text(history: list) -> str:
    """요약 입력용으로 메시지 리스트를 role:내용 텍스트로 평탄화한다."""
    lines = []
    for m in history:
        role = m.get("role", "?")
        content = m.get("content")
        if isinstance(content, str) and content:
            lines.append(f"[{role}] {content}")
        elif isinstance(content, list):
            # 멀티모달 메시지(capture_screen 주입): text는 살리고 이미지는 자리표시자로
            parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "image_url":
                    parts.append("[화면 이미지]")
                elif block.get("text"):
                    parts.append(block["text"])
            if parts:
                lines.append(f"[{role}] {' '.join(parts)}")
        elif m.get("tool_calls"):
            names = ", ".join(tc.get("function", {}).get("name", "?") for tc in m["tool_calls"])
            lines.append(f"[{role}] (도구 호출: {names})")
    return "\n".join(lines)


def _summarize_history(history: list) -> str:
    """오래된 대화 구간을 진행/결정/미해결 중심으로 요약한다(비스트리밍 1회 호출).

    테스트는 이 함수를 monkeypatch로 대체해 실제 LLM 호출을 차단한다.
    """
    resp = get_client().chat.completions.create(
        model=get_model(),
        stream=False,
        messages=[
            {"role": "system", "content": (
                "다음은 진행 중인 작업 대화 일부다. 이후 작업에 필요한 진행 상황·내린 결정·"
                "미해결 과제를 한국어로 500토큰 이내로 압축 요약하라. 군더더기 없이 핵심만."
            )},
            {"role": "user", "content": _history_to_text(history)},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def generate(message: str, thread_id: str = "", task_type: str = "", agent_mode: str = "auto"):
    client = get_client()
    model = get_model()
    # M5 모델별 컨텍스트 예산: 하드코딩(_CONTEXT_MAX_TOKENS) 대신 현재 모델의 윈도우를 사용.
    # 미지 모델/잘못된 값에도 양수 보장. 추정 오차는 M4 400 복구가 최종 보증.
    context_max = get_context_window(model) or _CONTEXT_MAX_TOKENS
    session_mgr = get_session_manager()
    loop = asyncio.get_event_loop()

    request_id = uuid.uuid4().hex[:12]
    _stop_flags[request_id] = False
    yield sse({ev.REQUEST_ID: request_id})

    # 메시지 초기화
    if thread_id and task_type:
        messages = await loop.run_in_executor(
            None, session_mgr.get_thread_messages, task_type, thread_id
        )
        messages.append({"role": "user", "content": message})
        session_id = None

        # task_type·thread_id를 항상 최신 시스템 프롬프트에 주입 (LLM이 workflow 툴 호출 시 사용)
        cfg = TASK_CONFIGS.get(task_type, {})
        system_content = cfg.get("system_prompt", _AUTONOMOUS_INSTRUCTION) + (
            f"\n\n[현재 세션]\n"
            f"task_type={task_type}  thread_id={thread_id}\n"
            f"모든 workflow_* 도구(init·set_step·add_step·update_step·remove_step·reorder) 호출 시 이 값을 그대로 사용하라."
        )
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = system_content
        else:
            messages.insert(0, {"role": "system", "content": system_content})
    else:
        messages = [
            {"role": "system", "content": _AUTONOMOUS_INSTRUCTION},
            {"role": "user", "content": message},
        ]
        session_id = await loop.run_in_executor(None, session_mgr.new_session, message)

    # G4 plan 모드: 계획 단계 동안 실행 도구 차단 + 계획만 세우도록 시스템 프롬프트 보강
    plan_phase = (agent_mode == "plan")
    if plan_phase and messages and messages[0].get("role") == "system":
        messages[0]["content"] += _PLAN_MODE_SUFFIX
        yield sse({"type": ev.PLAN, "phase": "planning"})

    # 장기기억 주입: 현재 메시지와 관련된 과거 기억을 system 프롬프트에 덧붙인다
    if MEMORY_ENABLED and messages and messages[0].get("role") == "system":
        try:
            _mems = await loop.run_in_executor(None, lambda: _memory_store().search(message, 5))
            if _mems:
                messages[0]["content"] += (
                    "\n\n[장기 기억] 과거 대화에서 기억해 둔 내용(참고):\n"
                    + "\n".join(f"- {m.text}" for m in _mems)
                )
        except Exception:
            pass

    compaction_count = 0
    nudge_count = 0
    tool_rounds = 0
    # LLM tools 배열은 128개 한계 → task_type·메시지 관련도로 ≤한도 만큼만 전송
    active_tools = select_tools(message, task_type)
    try:
        for _step in range(_MAX_STEPS):
            # 중단 플래그 확인
            if _stop_flags.get(request_id):
                yield sse({"type": ev.AGENT_STATE, "state": "idle"})
                break

            # M2 이미지 eviction: 최신 N개 화면 이미지만 남기고 과거는 텍스트 자리표시자로 치환
            # (텍스트 compaction과 독립 — 누적 캡처가 컨텍스트를 잠식하는 것을 선제 차단)
            if VISION_KEEP_LAST_IMAGES >= 0:
                _img_before = _estimate_tokens(messages)
                _pruned = prune_images(messages, keep_last_images=VISION_KEEP_LAST_IMAGES)
                if _pruned is not messages:
                    messages = _pruned
                    yield sse({
                        "type": ev.COMPACTION,
                        "removed": 0,
                        "tokens_used": _estimate_tokens(messages),
                        "note": "오래된 화면 이미지를 정리했습니다.",
                    })

            # G1 compaction: 임계치 초과 시 system+최근 N턴 보존하고 중간을 요약으로 치환
            if (
                compaction_count < MAX_COMPACT
                and _estimate_tokens(messages) > context_max * COMPACT_RATIO
            ):
                _before = len(messages)
                messages = await loop.run_in_executor(
                    None,
                    lambda: compact_messages(
                        messages,
                        keep_recent=COMPACT_KEEP_RECENT,
                        summarize_fn=lambda h: _summarize_history(h),
                    ),
                )
                if len(messages) < _before:
                    compaction_count += 1
                    yield sse({
                        "type": ev.COMPACTION,
                        "removed": _before - len(messages),
                        "tokens_used": _estimate_tokens(messages),
                    })

            # 컨텍스트 사용량 전송
            tokens_used = _estimate_tokens(messages)
            yield sse({
                "type": ev.CONTEXT_USAGE,
                "tokens_used": tokens_used,
                "tokens_total": context_max,
            })

            yield sse({"type": ev.AGENT_STATE, "state": "thinking"})

            tool_calls_raw: dict[int, dict] = {}
            text_chunks: list[str] = []
            finish_reason = None

            # M4 400 점진적 복구: 컨텍스트 초과/400 으로 거부되면 payload를 단계적으로 줄여 재시도한다.
            # 모델 무관(원칙 #0): 호출은 스트림 시작 전 헤드 검증이라 부분 출력 오염 없음. 항상 DONE 마감(I4).
            stream = None
            _overflow_retries = 0
            while stream is None:
                try:
                    stream = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=active_tools,
                        stream=True,
                    )
                except Exception as _ce:
                    if not is_recoverable(_ce):
                        raise  # 컨텍스트/400 외 예외는 기존 전역 핸들러로
                    if _overflow_retries >= MAX_OVERFLOW_RETRY:
                        _hint = ("컨텍스트를 줄였지만 여전히 한도를 초과합니다. "
                                 "대화를 새로 시작하거나 작업을 더 작게 나눠 진행해 주세요."
                                 if is_context_overflow(_ce) else
                                 "요청이 거부되었습니다(400). 입력을 줄이거나 대화를 새로 시작해 주세요.")
                        yield sse({"type": ev.ERROR, "message": f"{_hint}\n(원본: {str(_ce)[:300]})"})
                        yield sse({"type": ev.AGENT_STATE, "state": "idle"})
                        yield sse({"type": ev.DONE})
                        return
                    _overflow_retries += 1
                    # 1차: 이미지 1장만 남김 → 2차 이후: 강제 compact(MAX_COMPACT 무관)
                    if _overflow_retries == 1:
                        messages = prune_images(messages, keep_last_images=1)
                        _action = "오래된 화면 이미지를 정리했습니다."
                    else:
                        messages = await loop.run_in_executor(
                            None,
                            lambda: compact_messages(
                                messages,
                                keep_recent=COMPACT_KEEP_RECENT,
                                summarize_fn=lambda h: _summarize_history(h),
                            ),
                        )
                        _action = "이전 대화를 요약해 압축했습니다."
                    yield sse({
                        "type": ev.CONTEXT_TRIM,
                        "attempt": _overflow_retries,
                        "action": _action,
                        "tokens_used": _estimate_tokens(messages),
                    })

            for chunk in stream:
                # 스트림 도중 중단 요청 처리
                if _stop_flags.get(request_id):
                    break

                choice = chunk.choices[0]
                delta = choice.delta
                finish_reason = choice.finish_reason or finish_reason

                if delta.content:
                    text_chunks.append(delta.content)
                    yield sse({"type": ev.TEXT, "content": delta.content})

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_raw:
                            tool_calls_raw[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_raw[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_raw[idx]["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_raw[idx]["arguments"] += tc.function.arguments

            if text_chunks:
                messages.append({"role": "assistant", "content": "".join(text_chunks)})

            # 중단 또는 종료
            if _stop_flags.get(request_id) or finish_reason != "tool_calls" or not tool_calls_raw:
                _stopped = _stop_flags.get(request_id)
                _text_only_stop = (not _stopped) and finish_reason != "tool_calls"
                _last_text = "".join(text_chunks).strip()

                # G4 plan 모드: 계획이 끝나고 텍스트로 멈추면 실행 전 승인 게이트
                if plan_phase and _text_only_stop:
                    _cid = uuid.uuid4().hex[:8]
                    yield sse({
                        "type": ev.CONFIRM,
                        "confirm_id": _cid,
                        "question": "제안된 계획을 검토하세요. 이대로 실행할까요?",
                        "options": ["승인 실행", "수정 요청", "취소"],
                        "kind": "plan_approval",
                    })
                    yield sse({"type": ev.AGENT_STATE, "state": "waiting"})
                    _cr = await _resolve_confirm(_cid)
                    yield sse({"type": ev.AGENT_STATE, "state": "running"})
                    _ch = _cr.get("choice", "")
                    _custom = _cr.get("custom_text", "")
                    if "승인" in _ch:
                        plan_phase = False
                        yield sse({"type": ev.PLAN, "phase": "approved"})
                        messages.append({"role": "user", "content": _PLAN_APPROVED_MESSAGE})
                        continue
                    if "수정" in _ch:
                        messages.append({"role": "user", "content":
                                         f"[시스템] 계획 수정 요청: {_custom or '재검토 필요'}. 계획을 갱신하라."})
                        continue
                    # 취소
                    yield sse({"type": ev.AGENT_STATE, "state": "idle"})
                    break

                # G2 continuation nudge: 작업 도중(도구 사용 이력 있음) 텍스트로 조기 종료하면
                # 한도 내에서 '계속'을 주입해 끈질기게 진행시킨다. 잡담·되묻기·사용자중단은 제외.
                if (
                    _text_only_stop
                    and tool_rounds > 0
                    and nudge_count < MAX_NUDGES
                    and not _last_text.endswith("?")
                ):
                    nudge_count += 1
                    messages.append({"role": "user", "content": _NUDGE_MESSAGE})
                    continue
                yield sse({"type": ev.AGENT_STATE, "state": "idle"})
                break

            assistant_tool_calls = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in tool_calls_raw.values()
            ]
            messages.append({"role": "assistant", "tool_calls": assistant_tool_calls})
            tool_rounds += 1

            yield sse({"type": ev.AGENT_STATE, "state": "running"})

            # capture_screen 이 만든 이미지는 tool 묶음 연속성(I1)을 깨지 않도록
            # 여기 모았다가 tool 루프가 끝난 뒤 user 메시지로 주입한다.
            pending_images: list[dict] = []

            for tc in tool_calls_raw.values():
                if _stop_flags.get(request_id):
                    break

                label = _intent_label(tc["name"], tc["arguments"])
                yield sse({"type": ev.TOOL_START, "tool": tc["name"], "label": label})

                await asyncio.sleep(0)

                # ── G4 계획-단계 실행 차단 ──────────────────────────
                # 승인 전에는 workflow_*/ask_user 외 실행 도구를 실제로 돌리지 않는다(구조적 강제).
                if plan_phase and not (tc["name"].startswith("workflow_") or tc["name"] == "ask_user"):
                    result = "[계획 모드] 승인 전에는 실행할 수 없습니다. workflow_* 도구로 계획만 세우세요."
                    yield sse({"type": ev.TOOL_DONE, "tool": tc["name"], "result": result})
                    if session_id:
                        await loop.run_in_executor(None, session_mgr.log_tool, session_id, tc["name"], result)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                    continue

                # ── G3 중앙 안전 게이트 (APPROVE1) ──────────────────
                # run_tool 직전 위험도를 분류해 safe가 아니면 사용자 승인을 강제한다.
                # 모델 협조(force 등)에 의존하지 않고 디스패치 경로에서 차단한다.
                _allow = _session_allowlists.setdefault(thread_id or request_id, set())
                _risk = "safe" if tc["name"] == "ask_user" else classify_risk(
                    tc["name"], tc["arguments"], _allow, tool_risk_hint(tc["name"])
                )
                _gate_denied = False
                _gate_choice = ""
                if _risk != "safe":
                    _cid = uuid.uuid4().hex[:8]
                    yield sse({
                        "type": ev.CONFIRM,
                        "confirm_id": _cid,
                        "question": risk_confirm_message(tc["name"], _risk, tc["arguments"]),
                        "options": ["예 (이번만)", "항상 허용", "아니오"],
                        "risk": _risk,
                        "command": command_excerpt(tc["arguments"]),
                    })
                    yield sse({"type": ev.AGENT_STATE, "state": "waiting"})
                    _cr = await _resolve_confirm(_cid)
                    yield sse({"type": ev.AGENT_STATE, "state": "running"})
                    _gate_choice = _cr.get("choice", "")
                    if "항상" in _gate_choice:
                        _allow.add(tc["name"])
                    elif _gate_choice.startswith("예"):
                        pass
                    else:
                        _gate_denied = True

                _tool_failed = False
                if _gate_denied:
                    result = (
                        f"[안전 게이트] 사용자가 '{tc['name']}' 실행을 거부했습니다"
                        f"(선택: {_gate_choice}). 실행하지 않았습니다. "
                        "다른 방법을 제안하거나 작업을 중단하라."
                    )
                    yield sse({"type": ev.TOOL_DONE, "tool": tc["name"], "result": result[:1000]})
                    if session_id:
                        await loop.run_in_executor(None, session_mgr.log_tool, session_id, tc["name"], result)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                    continue

                # 무한 행 방지: escalating 타임아웃 + 길어지면 TOOL_WAIT 내레이션(A1)
                try:
                    result = None
                    async for _wk, _wd in _run_tool_watched(loop, tc["name"], tc["arguments"], label):
                        if _wk == "wait":
                            yield sse({"type": ev.TOOL_WAIT, **_wd})
                        else:
                            result = _wd
                    # 캡/Office 내부 타임아웃은 '툴 실행 오류' 문자열로 돌아온다 → 실패로 처리
                    if isinstance(result, str) and result.startswith("툴 실행 오류"):
                        _tool_failed = True
                except Exception as first_err:
                    _tool_failed = True
                    result = f"툴 실행 오류: {first_err}"

                # running 단계의 max_retry 확인 후 재시도 (예외·타임아웃 공통)
                if _tool_failed and thread_id and task_type and not tc["name"].startswith("workflow_"):
                    try:
                        _check_wf = await loop.run_in_executor(
                            None, wf_storage.load_workflow, task_type, thread_id
                        )
                        _running_step = next(
                            (s for s in _check_wf.steps if s.status == "running"), None
                        )
                        _max_retry = getattr(_running_step, "max_retry", 0) if _running_step else 0
                        for _attempt in range(_max_retry):
                            await asyncio.sleep(1.0)
                            try:
                                result = None
                                async for _wk, _wd in _run_tool_watched(
                                    loop, tc["name"], tc["arguments"], label
                                ):
                                    if _wk == "wait":
                                        yield sse({"type": ev.TOOL_WAIT, **_wd})
                                    else:
                                        result = _wd
                                if isinstance(result, str) and result.startswith("툴 실행 오류"):
                                    continue  # 여전히 실패 → 다음 재시도
                                _tool_failed = False
                                break
                            except Exception as retry_err:
                                result = f"툴 실행 오류: {retry_err}"
                    except Exception:
                        pass

                # 툴 실패 시 running 단계를 자동으로 error 상태로 전환 + RunState 동기화
                if _tool_failed and thread_id and task_type and not tc["name"].startswith("workflow_"):
                    try:
                        _err_wf = await loop.run_in_executor(
                            None, wf_storage.load_workflow, task_type, thread_id
                        )
                        for _err_step in _err_wf.steps:
                            if _err_step.status == "running":
                                _err_step.status = "error"
                                _err_step.notes = result[:200]
                                await loop.run_in_executor(
                                    None, wf_storage.save_workflow, _err_wf
                                )
                                yield sse({"type": ev.WORKFLOW_UPDATE, "workflow": _err_wf.to_dict()})
                                # RunState 별도 파일에도 동기화
                                try:
                                    _rs = await loop.run_in_executor(
                                        None, wf_storage.load_run_state, task_type, thread_id
                                    ) or WorkflowRunState(definition_id=thread_id)
                                    _rs.set_node_status(_err_step.id, "error", _err_step.notes)
                                    await loop.run_in_executor(
                                        None, wf_storage.save_run_state, task_type, thread_id, _rs
                                    )
                                except Exception:
                                    pass
                                break
                    except Exception:
                        pass

                # ask_user 툴의 __confirm__ 응답 처리
                try:
                    robj = json.loads(result)
                    if isinstance(robj, dict) and robj.get("__confirm__"):
                        cid = robj["confirm_id"]
                        yield sse({
                            "type": ev.CONFIRM,
                            "confirm_id": cid,
                            "question": robj["question"],
                            "options": robj["options"],
                        })
                        yield sse({"type": ev.AGENT_STATE, "state": "waiting"})
                        cr = await _resolve_confirm(cid)
                        choice = cr["choice"]
                        custom = cr.get("custom_text", "")
                        result = f"[사용자 응답] 선택: {choice}" + (f"\n추가 의견: {custom}" if custom else "")
                        yield sse({"type": ev.AGENT_STATE, "state": "running"})
                except (json.JSONDecodeError, AttributeError, KeyError):
                    pass

                # 워크플로우 도구 결과 → workflow_update SSE + RunState 동기화
                if tc["name"].startswith("workflow_"):
                    try:
                        robj = json.loads(result)
                        if isinstance(robj, dict) and robj.get("ok") and "workflow" in robj:
                            wf_data = robj["workflow"]
                            yield sse({"type": ev.WORKFLOW_UPDATE, "workflow": wf_data})
                            # 단계 status 변경을 RunState에도 반영
                            if thread_id and task_type:
                                try:
                                    _rs = await loop.run_in_executor(
                                        None, wf_storage.load_run_state, task_type, thread_id
                                    ) or WorkflowRunState(definition_id=thread_id)
                                    for _step in wf_data.get("steps", []):
                                        _rs.set_node_status(
                                            _step["id"],
                                            _step.get("status", "pending"),
                                            _step.get("notes", ""),
                                        )
                                    await loop.run_in_executor(
                                        None, wf_storage.save_run_state, task_type, thread_id, _rs
                                    )
                                except Exception:
                                    pass
                    except (json.JSONDecodeError, AttributeError):
                        pass

                # capture_screen 봉투 감지: 거대한 base64를 tool content/로그/SSE로 흘리지 않고
                # 짧은 텍스트로 짝(I1)을 맞춘 뒤, 실제 이미지는 루프 종료 후 user 메시지로 주입한다.
                _cap = parse_capture_envelope(result)
                if _cap is not None:
                    _note = _cap.get("note", "화면을 캡처했습니다.")
                    yield sse({"type": ev.TOOL_DONE, "tool": tc["name"], "result": _note})
                    yield sse({"type": ev.VISION_CAPTURE, "image_b64": _cap["image_b64"]})
                    if session_id:
                        await loop.run_in_executor(None, session_mgr.log_tool, session_id, tc["name"], _note)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": _note})
                    pending_images.append(_cap)
                    continue

                yield sse({"type": ev.TOOL_DONE, "tool": tc["name"], "result": result[:1000]})

                if session_id:
                    await loop.run_in_executor(None, session_mgr.log_tool, session_id, tc["name"], result)

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

            # tool 묶음이 끝났으므로(연속성 보장) 캡처 이미지를 user 멀티모달 메시지로 주입한다.
            # M1 적응형: 컨텍스트가 임계에 근접하면 새 이미지 detail을 low로 강등해 비용을 낮춘다.
            if pending_images:
                _near_limit = _estimate_tokens(messages) > context_max * COMPACT_RATIO
                for _img in pending_images:
                    messages.append(build_capture_message(_img, near_limit=_near_limit))
        else:
            # for 루프가 break 없이 끝남 = 최대 단계 도달 (자연 종료 아님)
            yield sse({"type": ev.TEXT, "content":
                "\n\n[알림] 최대 실행 단계에 도달해 잠시 멈췄습니다. "
                "계속 진행하려면 '계속'이라고 입력해 주세요."})
            yield sse({"type": ev.AGENT_STATE, "state": "idle"})

    except Exception as e:
        yield sse({"type": ev.ERROR, "message": str(e)})
        yield sse({"type": ev.AGENT_STATE, "state": "idle"})
        yield sse({"type": ev.DONE})
        return
    finally:
        _stop_flags.pop(request_id, None)
        # 스레드 없는 단발 요청의 허용목록은 정리(스레드 키는 세션 유지)
        if not thread_id:
            _session_allowlists.pop(request_id, None)

    # 스레드 또는 세션 종료
    if thread_id and task_type:
        await loop.run_in_executor(
            None, session_mgr.save_thread_messages, task_type, thread_id, messages
        )
    else:
        final_text = next(
            (m["content"][:500] for m in reversed(messages)
             if m.get("role") == "assistant" and isinstance(m.get("content"), str)),
            ""
        )
        await loop.run_in_executor(None, session_mgr.close_session, session_id, final_text)

    # 장기기억 추출(MEMORY_EXTRACT_MODE): turn=매 턴, close=스레드 close에서 일괄(단발 요청만 여기서 폴백), off=안 함
    _turn_extract = (
        MEMORY_ENABLED
        and MEMORY_EXTRACT_MODE != "off"
        and (tool_rounds > 0 or len(message.strip()) >= 8)
        and (MEMORY_EXTRACT_MODE == "turn" or not thread_id)
    )
    if _turn_extract:
        try:
            await loop.run_in_executor(None, _extract_and_store, messages[-8:], thread_id or "general")
        except Exception:
            pass

    yield sse({"type": ev.DONE})


# ── 기본 엔드포인트 ───────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/profile")
async def get_profile():
    return {"active": get_active(), "profiles": list_profiles()}


@app.post("/profile/{name}")
async def switch_profile(name: str):
    set_active_profile(name)
    return {"active": name}


# ── 모델 선택 (개선 아이디어 D) ───────────────────────────────

@app.get("/models")
async def get_models():
    from agent.llm import list_available_models
    return await asyncio.get_event_loop().run_in_executor(None, list_available_models)


@app.post("/models/{name}")
async def switch_model(name: str):
    from agent.config import set_model
    # "__default__" 은 오버라이드 해제(프로파일 기본 모델로 복귀)
    set_model(None if name == "__default__" else name)
    return {"model": get_model()}


@app.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(
        generate(body.message, body.thread_id, body.task_type, body.agent_mode),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/stop/{request_id}")
async def stop_agent(request_id: str):
    _stop_flags[request_id] = True
    return {"ok": True}


class MemoryAddRequest(BaseModel):
    text: str
    category: str = "fact"


@app.get("/memory")
async def list_memory():
    """저장된 장기기억 전체를 반환한다(가시성·디버깅용)."""
    store = _memory_store()
    mems = await asyncio.get_event_loop().run_in_executor(None, store.all)
    return {"memories": [m.to_dict() for m in mems]}


@app.post("/memory")
async def add_memory(body: MemoryAddRequest):
    """기억을 수동으로 추가한다(관리 UI). dedup이면 saved=false."""
    store = _memory_store()
    mem = await asyncio.get_event_loop().run_in_executor(
        None, store.add, body.text, body.category or "fact", "manual"
    )
    if mem is None:
        return {"ok": True, "saved": False}
    return {"ok": True, "saved": True, "memory": mem.to_dict()}


@app.delete("/memory/{mem_id}")
async def delete_memory(mem_id: str):
    """기억을 id로 삭제한다(관리 UI)."""
    store = _memory_store()
    ok = await asyncio.get_event_loop().run_in_executor(None, store.delete, mem_id)
    return {"ok": ok}


# ── 협업모드(코치 모드) 엔드포인트 (백로그 H) ─────────────────

class CollaborateStartRequest(BaseModel):
    thread_id: str = ""
    goal: str = ""


class CollaborateTickRequest(BaseModel):
    thread_id: str = ""
    force: bool = False


@app.post("/collaborate/start")
async def collaborate_start(body: CollaborateStartRequest):
    """협업 세션 시작 — 목표 설정. 이후 클라이언트가 주기적으로 /collaborate/tick."""
    from agent import collaborate
    return collaborate.start(body.thread_id, body.goal)


@app.post("/collaborate/stop")
async def collaborate_stop(body: CollaborateStartRequest):
    from agent import collaborate
    return collaborate.stop(body.thread_id)


@app.post("/collaborate/tick")
async def collaborate_tick(body: CollaborateTickRequest):
    """화면을 보고 비간섭 힌트를 만든다. 변화가 적으면 LLM 호출 없이 hint=null."""
    from agent import collaborate
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, collaborate.tick, body.thread_id, body.force)


# ── 스레드 엔드포인트 ─────────────────────────────────────────

@app.get("/task-config")
async def task_config():
    from agent.obsidian_session import TASK_CONFIGS
    return {
        k: {"label": v["label"], "icon": v["icon"], "description": v.get("description", "")}
        for k, v in TASK_CONFIGS.items()
    }


@app.get("/threads")
async def list_all_threads():
    mgr = get_session_manager()
    return await asyncio.get_event_loop().run_in_executor(None, mgr.list_all_threads)


@app.get("/search")
async def search_threads(q: str = ""):
    """스레드/대화 전역 검색 (백로그 P). 제목·본문 부분일치."""
    mgr = get_session_manager()
    return await asyncio.get_event_loop().run_in_executor(None, mgr.search_threads, q)


@app.get("/threads/{task_type}")
async def list_threads(task_type: str, archived: bool = False):
    mgr = get_session_manager()
    if archived:
        return await asyncio.get_event_loop().run_in_executor(None, mgr.list_archived_threads, task_type)
    return await asyncio.get_event_loop().run_in_executor(None, mgr.list_threads, task_type)


class NewThreadRequest(BaseModel):
    title: str = ""


@app.post("/threads/{task_type}")
async def create_thread(task_type: str, body: NewThreadRequest):
    mgr = get_session_manager()
    thread_id = await asyncio.get_event_loop().run_in_executor(
        None, mgr.new_thread, task_type, body.title
    )
    return {"thread_id": thread_id}


@app.get("/threads/{task_type}/{thread_id}/messages")
async def get_thread_messages(task_type: str, thread_id: str, archived: bool = False):
    mgr = get_session_manager()
    if archived:
        return await asyncio.get_event_loop().run_in_executor(
            None, mgr.get_thread_display_messages_archived, task_type, thread_id
        )
    return await asyncio.get_event_loop().run_in_executor(
        None, mgr.get_thread_display_messages, task_type, thread_id
    )


@app.delete("/threads/{task_type}/{thread_id}")
async def archive_thread_endpoint(task_type: str, thread_id: str):
    mgr = get_session_manager()
    await asyncio.get_event_loop().run_in_executor(
        None, mgr.archive_thread, task_type, thread_id
    )
    return {"status": "archived"}


@app.delete("/threads/{task_type}/{thread_id}/permanent")
async def delete_thread_permanent(task_type: str, thread_id: str, archived: bool = False):
    mgr = get_session_manager()
    await asyncio.get_event_loop().run_in_executor(
        None, mgr.delete_thread_permanent, task_type, thread_id, archived
    )
    return {"status": "deleted"}


@app.post("/threads/{task_type}/{thread_id}/restore")
async def restore_thread(task_type: str, thread_id: str):
    mgr = get_session_manager()
    await asyncio.get_event_loop().run_in_executor(
        None, mgr.restore_thread, task_type, thread_id
    )
    return {"status": "restored"}


@app.post("/threads/{task_type}/{thread_id}/unarchive")
async def unarchive_thread(task_type: str, thread_id: str):
    mgr = get_session_manager()
    await asyncio.get_event_loop().run_in_executor(
        None, mgr.restore_archived_thread, task_type, thread_id
    )
    return {"status": "unarchived"}


@app.post("/threads/{task_type}/{thread_id}/close")
async def close_thread(task_type: str, thread_id: str):
    mgr = get_session_manager()
    loop = asyncio.get_event_loop()
    # 스레드 종료 시 전체 대화에서 기억을 1회 일괄 추출(비용 최적화). close 모드에서만.
    if MEMORY_ENABLED and MEMORY_EXTRACT_MODE == "close":
        try:
            msgs = await loop.run_in_executor(None, mgr.get_thread_messages, task_type, thread_id)
            if msgs:
                await loop.run_in_executor(None, _extract_and_store, msgs, thread_id)
        except Exception:
            pass
    await loop.run_in_executor(None, mgr.close_thread, task_type, thread_id)
    return {"status": "completed"}


# ── 워크플로우 엔드포인트 ─────────────────────────────────────

@app.get("/threads/{task_type}/{thread_id}/workflow")
async def get_workflow(task_type: str, thread_id: str):
    loop = asyncio.get_event_loop()
    wf = await loop.run_in_executor(None, wf_storage.load_workflow, task_type, thread_id)
    return wf.to_dict()


from fastapi import Request
from fastapi.responses import StreamingResponse


@app.get("/threads/{task_type}/{thread_id}/workflow/events")
async def workflow_file_events(request: Request, task_type: str, thread_id: str):
    """파일 mtime 폴링으로 Obsidian 편집을 감지해 프론트엔드에 SSE로 전달한다.
    새 의존성 없음 — pathlib.stat().st_mtime 폴링 방식.
    """
    def _mtime() -> tuple[float, float]:
        md = wf_storage._def_path(task_type, thread_id)
        js = wf_storage._wf_path(task_type, thread_id)
        st = wf_storage._state_path(task_type, thread_id)
        def _m(p): return p.stat().st_mtime if p and p.exists() else 0.0
        return (_m(md) or _m(js), _m(st))

    poll_secs = float(os.environ.get("WF_POLL_INTERVAL", "2"))

    async def _generate():
        loop = asyncio.get_event_loop()
        # 초기 워크플로우 즉시 전송
        wf = await loop.run_in_executor(None, wf_storage.load_workflow, task_type, thread_id)
        yield f"data: {json.dumps({'type': 'workflow_update', 'workflow': wf.to_dict()}, ensure_ascii=False)}\n\n"
        last_mtime = _mtime()

        tick = 0
        try:
            while not await request.is_disconnected():
                await asyncio.sleep(poll_secs)
                tick += 1
                current_mtime = _mtime()
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    wf = await loop.run_in_executor(None, wf_storage.load_workflow, task_type, thread_id)
                    yield f"data: {json.dumps({'type': 'workflow_update', 'workflow': wf.to_dict()}, ensure_ascii=False)}\n\n"
                elif tick % max(1, int(30 / poll_secs)) == 0:
                    yield ": heartbeat\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class WorkflowNodeUpdateRequest(BaseModel):
    status: str
    notes: str = ""
    branch_output: int | None = None


@app.patch("/threads/{task_type}/{thread_id}/workflow/nodes/{node_id}")
async def patch_workflow_node(
    task_type: str, thread_id: str, node_id: str, body: WorkflowNodeUpdateRequest
):
    """UI에서 노드를 수동으로 완료/건너뛰기/재시도할 때 사용한다.
    done 상태 시 런타임 라우팅이 자동 적용된다."""
    from agent.tools.workflow import _workflow_set_step
    loop = asyncio.get_event_loop()
    result_str = await loop.run_in_executor(
        None, _workflow_set_step,
        task_type, thread_id, node_id, body.status, body.notes, body.branch_output,
    )
    return json.loads(result_str)


class WorkflowSaveRequest(BaseModel):
    title: str
    steps: list
    connections: list = []  # 편집 모드에서 연결 정보 포함 가능


@app.post("/threads/{task_type}/{thread_id}/workflow")
async def save_workflow_endpoint(task_type: str, thread_id: str, body: WorkflowSaveRequest):
    from agent.workflow.model import WorkflowDefinition, WorkflowNode, WorkflowConnection, WorkflowRunState
    import uuid as _uuid

    nodes = [
        WorkflowNode(
            id=s.get("id") or _uuid.uuid4().hex[:8],
            title=s["title"],
            type=s.get("type", "auto"),
            group=s.get("group", ""),
        )
        for s in body.steps
    ]
    if body.connections:
        connections = [WorkflowConnection.from_dict(c) for c in body.connections]
    else:
        connections = [
            WorkflowConnection(from_node=nodes[i].id, to_node=nodes[i + 1].id)
            for i in range(len(nodes) - 1)
        ]
    defn = WorkflowDefinition(
        id=thread_id, task_type=task_type, title=body.title,
        nodes=nodes, connections=connections,
    )
    loop = asyncio.get_event_loop()
    # 기존 RunState를 보존하고 새 노드 id 기준으로 재구성
    existing_rs = await loop.run_in_executor(None, wf_storage.load_run_state, task_type, thread_id)
    rs = WorkflowRunState(definition_id=thread_id)
    step_status_map = {s.get("id"): s.get("status", "pending") for s in body.steps if s.get("id")}
    for n in nodes:
        status = step_status_map.get(n.id, "pending")
        if existing_rs and n.id in existing_rs.node_states:
            ns = existing_rs.node_states[n.id]
            rs.set_node_status(n.id, ns.status, ns.notes)
        else:
            rs.set_node_status(n.id, status)
    await loop.run_in_executor(None, wf_storage.save_definition, defn)
    await loop.run_in_executor(None, wf_storage.save_run_state, task_type, thread_id, rs)
    wf = await loop.run_in_executor(None, wf_storage.load_workflow, task_type, thread_id)
    return wf.to_dict()


@app.delete("/threads/{task_type}/{thread_id}/workflow")
async def delete_workflow_endpoint(task_type: str, thread_id: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, wf_storage.delete_workflow, task_type, thread_id)
    return {"ok": True}


# ── 기본 템플릿 엔드포인트 ─────────────────────────────────────

@app.get("/workflow/templates/{task_type}")
async def get_workflow_template(task_type: str):
    """태스크 유형의 기본 템플릿을 반환한다."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, wf_storage.load_template, task_type)


class TemplateUpdateRequest(BaseModel):
    title: str
    steps: list


@app.put("/workflow/templates/{task_type}")
async def update_workflow_template(task_type: str, body: TemplateUpdateRequest):
    """태스크 유형의 기본 템플릿을 Vault에 저장한다. 새 스레드부터 적용된다."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, wf_storage.save_template, task_type, body.title, body.steps)
    return {"ok": True}


# ── 확인 응답 ─────────────────────────────────────────────────

class ConfirmResponse(BaseModel):
    choice: str
    custom_text: str = ""


@app.post("/confirm/{confirm_id}")
async def submit_confirm(confirm_id: str, body: ConfirmResponse):
    _confirm_results[confirm_id] = {"choice": body.choice, "custom_text": body.custom_text}
    if confirm_id in _pending_confirms:
        _pending_confirms[confirm_id].set()
    return {"ok": True}


# ── 툴 직접 테스트 ─────────────────────────────────────────────

class ToolTestRequest(BaseModel):
    tool: str
    arguments: dict = {}


@app.post("/tool/test")
async def tool_test(body: ToolTestRequest):
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, run_tool, body.tool, json.dumps(body.arguments)
        )
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    port = int(os.environ.get("AGENT_PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

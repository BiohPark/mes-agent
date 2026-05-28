import sys
import json
import asyncio
import os
from pathlib import Path
import uvicorn
from fastapi import FastAPI

# 'python agent/server.py' 직접 실행 시 프로젝트 루트를 sys.path에 추가
# 'python -m agent.server' 실행 시에는 이미 추가되어 있으므로 중복 없음
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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.config import get_active, active_llm, list_profiles, set_active_profile
from agent.llm import get_client, get_model
from agent.tools import TOOLS, TOOL_LABELS, run_tool
from agent.obsidian_session import get_session_manager

app = FastAPI()

# ── 사용자 확인 요청 대기 상태 ─────────────────────────────────
_pending_confirms: dict[str, asyncio.Event] = {}
_confirm_results: dict[str, dict] = {}

@app.on_event("startup")
async def startup():
    get_session_manager().setup_vault()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""
    task_type: str = ""


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# 비스레드 모드(system_prompt 없음)용 기본 자율 실행 지시
_AUTONOMOUS_INSTRUCTION = (
    "너는 사내 업무자동화 데스크탑 에이전트야. "
    "도구 호출 전에 '~하겠습니다', '~할게요' 같은 예고 문구를 절대 쓰지 마라. "
    "바로 도구를 호출해 실행하고, 여러 단계가 필요하면 사용자 확인 없이 연속으로 실행해라. "
    "모든 작업이 완료된 뒤에만 결과를 간략히 보고해라. "
    "브라우저 조작 시 browser_open 후 browser_get_interactive_elements로 실제 selector를 먼저 확인해라. "
    "CSS id/class보다 aria-label·placeholder·텍스트 기반 selector를 우선 사용해라. "
    "폼 제출은 버튼 클릭 대신 browser_press_key('Enter')를 사용해라. "
    "selector 실패 시 같은 것을 반복하지 말고 즉시 다른 전략으로 전환해라."
)

_MAX_STEPS = 20  # 무한 루프 방지


async def generate(message: str, thread_id: str = "", task_type: str = ""):
    client = get_client()
    model = get_model()
    session_mgr = get_session_manager()
    loop = asyncio.get_event_loop()

    # 메시지 초기화
    if thread_id and task_type:
        messages = await loop.run_in_executor(
            None, session_mgr.get_thread_messages, task_type, thread_id
        )
        messages.append({"role": "user", "content": message})
        session_id = None
    else:
        # 스레드 없는 일반 채팅: 자율 실행 지시를 system으로 삽입
        messages = [
            {"role": "system", "content": _AUTONOMOUS_INSTRUCTION},
            {"role": "user", "content": message},
        ]
        session_id = await loop.run_in_executor(None, session_mgr.new_session, message)

    try:
        # ── 에이전트 루프 ──────────────────────────────────────
        for _step in range(_MAX_STEPS):
            tool_calls_raw: dict[int, dict] = {}
            text_chunks: list[str] = []
            finish_reason = None

            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                stream=True,
            )

            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta
                finish_reason = choice.finish_reason or finish_reason

                if delta.content:
                    text_chunks.append(delta.content)
                    yield sse({"type": "text", "content": delta.content})

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

            # 텍스트 응답이 있으면 messages에 추가
            if text_chunks:
                messages.append({"role": "assistant", "content": "".join(text_chunks)})

            # 종료 조건: 도구 호출 없으면 루프 종료
            if finish_reason != "tool_calls" or not tool_calls_raw:
                break

            # 도구 실행 후 결과를 messages에 추가하고 루프 계속
            assistant_tool_calls = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in tool_calls_raw.values()
            ]
            messages.append({"role": "assistant", "tool_calls": assistant_tool_calls})

            for tc in tool_calls_raw.values():
                label = TOOL_LABELS.get(tc["name"], tc["name"])
                yield sse({"type": "tool_start", "tool": tc["name"], "label": label})

                await asyncio.sleep(0)
                try:
                    result = await loop.run_in_executor(None, run_tool, tc["name"], tc["arguments"])
                except Exception as e:
                    result = f"툴 실행 오류: {e}"

                # ask_user 툴의 __confirm__ 응답 처리
                try:
                    robj = json.loads(result)
                    if isinstance(robj, dict) and robj.get("__confirm__"):
                        cid = robj["confirm_id"]
                        ev = asyncio.Event()
                        _pending_confirms[cid] = ev
                        yield sse({
                            "type": "confirm",
                            "confirm_id": cid,
                            "question": robj["question"],
                            "options": robj["options"],
                        })
                        try:
                            await asyncio.wait_for(ev.wait(), timeout=300)
                            cr = _confirm_results.pop(cid, {"choice": "타임아웃", "custom_text": ""})
                        except asyncio.TimeoutError:
                            cr = {"choice": "타임아웃으로 자동 중단", "custom_text": ""}
                        finally:
                            _pending_confirms.pop(cid, None)
                        choice = cr["choice"]
                        custom = cr.get("custom_text", "")
                        result = f"[사용자 응답] 선택: {choice}" + (f"\n추가 의견: {custom}" if custom else "")
                except (json.JSONDecodeError, AttributeError, KeyError):
                    pass

                yield sse({"type": "tool_done", "tool": tc["name"], "result": result[:1000]})

                if session_id:
                    await loop.run_in_executor(None, session_mgr.log_tool, session_id, tc["name"], result)

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    except Exception as e:
        yield sse({"type": "error", "message": str(e)})
        yield sse({"type": "done"})
        return

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

    yield sse({"type": "done"})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/profile")
async def get_profile():
    return {
        "active": get_active(),
        "profiles": list_profiles()
    }


@app.post("/profile/{name}")
async def switch_profile(name: str):
    set_active_profile(name)
    return {"active": name}


@app.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(
        generate(body.message, body.thread_id, body.task_type),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ── 스레드 엔드포인트 ─────────────────────────────────────────

@app.get("/task-config")
async def task_config():
    from agent.obsidian_session import TASK_CONFIGS
    return {k: {"label": v["label"], "icon": v["icon"], "description": v.get("description", "")} for k, v in TASK_CONFIGS.items()}


@app.get("/threads")
async def list_all_threads():
    mgr = get_session_manager()
    return await asyncio.get_event_loop().run_in_executor(None, mgr.list_all_threads)


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
    await asyncio.get_event_loop().run_in_executor(
        None, mgr.close_thread, task_type, thread_id
    )
    return {"status": "completed"}


class ConfirmResponse(BaseModel):
    choice: str
    custom_text: str = ""


@app.post("/confirm/{confirm_id}")
async def submit_confirm(confirm_id: str, body: ConfirmResponse):
    _confirm_results[confirm_id] = {"choice": body.choice, "custom_text": body.custom_text}
    if confirm_id in _pending_confirms:
        _pending_confirms[confirm_id].set()
    return {"ok": True}


class ToolTestRequest(BaseModel):
    tool: str
    arguments: dict = {}


@app.post("/tool/test")
async def tool_test(body: ToolTestRequest):
    import json
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

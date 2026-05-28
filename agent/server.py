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

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.config import get_active, active_llm, list_profiles, set_active_profile
from agent.llm import get_client, get_model
from agent.tools import TOOLS, TOOL_LABELS, run_tool
from agent.obsidian_session import get_session_manager
from agent.workflow import storage as wf_storage
from agent.core import events as ev

app = FastAPI()

# ── 상태 테이블 ───────────────────────────────────────────────
_pending_confirms: dict[str, asyncio.Event] = {}
_confirm_results: dict[str, dict] = {}
_stop_flags: dict[str, bool] = {}


@app.on_event("startup")
async def startup():
    get_session_manager().setup_vault()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""
    task_type: str = ""


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _estimate_tokens(messages: list) -> int:
    """메시지 전체 텍스트 길이로 토큰 수를 추정한다 (4 chars ≈ 1 token)."""
    total = 0
    for m in messages:
        content = m.get("content") or ""
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(block.get("text", ""))
        tool_calls = m.get("tool_calls") or []
        for tc in tool_calls:
            fn = tc.get("function", {})
            total += len(fn.get("arguments", ""))
    return total // 4


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

_MAX_STEPS = 20
_CONTEXT_MAX_TOKENS = 128_000


async def generate(message: str, thread_id: str = "", task_type: str = ""):
    client = get_client()
    model = get_model()
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
    else:
        messages = [
            {"role": "system", "content": _AUTONOMOUS_INSTRUCTION},
            {"role": "user", "content": message},
        ]
        session_id = await loop.run_in_executor(None, session_mgr.new_session, message)

    try:
        for _step in range(_MAX_STEPS):
            # 중단 플래그 확인
            if _stop_flags.get(request_id):
                yield sse({"type": ev.AGENT_STATE, "state": "idle"})
                break

            # 컨텍스트 사용량 전송
            tokens_used = _estimate_tokens(messages)
            yield sse({
                "type": ev.CONTEXT_USAGE,
                "tokens_used": tokens_used,
                "tokens_total": _CONTEXT_MAX_TOKENS,
            })

            yield sse({"type": ev.AGENT_STATE, "state": "thinking"})

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

            yield sse({"type": ev.AGENT_STATE, "state": "running"})

            for tc in tool_calls_raw.values():
                if _stop_flags.get(request_id):
                    break

                label = TOOL_LABELS.get(tc["name"], tc["name"])
                yield sse({"type": ev.TOOL_START, "tool": tc["name"], "label": label})

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
                        ev_obj = asyncio.Event()
                        _pending_confirms[cid] = ev_obj
                        yield sse({
                            "type": ev.CONFIRM,
                            "confirm_id": cid,
                            "question": robj["question"],
                            "options": robj["options"],
                        })
                        yield sse({"type": ev.AGENT_STATE, "state": "waiting"})
                        try:
                            await asyncio.wait_for(ev_obj.wait(), timeout=300)
                            cr = _confirm_results.pop(cid, {"choice": "타임아웃", "custom_text": ""})
                        except asyncio.TimeoutError:
                            cr = {"choice": "타임아웃으로 자동 중단", "custom_text": ""}
                        finally:
                            _pending_confirms.pop(cid, None)
                        choice = cr["choice"]
                        custom = cr.get("custom_text", "")
                        result = f"[사용자 응답] 선택: {choice}" + (f"\n추가 의견: {custom}" if custom else "")
                        yield sse({"type": ev.AGENT_STATE, "state": "running"})
                except (json.JSONDecodeError, AttributeError, KeyError):
                    pass

                # 워크플로우 도구 결과 → workflow_update SSE
                if tc["name"] in ("workflow_init", "workflow_set_step"):
                    try:
                        robj = json.loads(result)
                        if isinstance(robj, dict) and robj.get("ok") and "workflow" in robj:
                            yield sse({"type": ev.WORKFLOW_UPDATE, "workflow": robj["workflow"]})
                    except (json.JSONDecodeError, AttributeError):
                        pass

                yield sse({"type": ev.TOOL_DONE, "tool": tc["name"], "result": result[:1000]})

                if session_id:
                    await loop.run_in_executor(None, session_mgr.log_tool, session_id, tc["name"], result)

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    except Exception as e:
        yield sse({"type": ev.ERROR, "message": str(e)})
        yield sse({"type": ev.AGENT_STATE, "state": "idle"})
        yield sse({"type": ev.DONE})
        return
    finally:
        _stop_flags.pop(request_id, None)

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


@app.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(
        generate(body.message, body.thread_id, body.task_type),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/stop/{request_id}")
async def stop_agent(request_id: str):
    _stop_flags[request_id] = True
    return {"ok": True}


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


# ── 워크플로우 엔드포인트 ─────────────────────────────────────

@app.get("/threads/{task_type}/{thread_id}/workflow")
async def get_workflow(task_type: str, thread_id: str):
    loop = asyncio.get_event_loop()
    wf = await loop.run_in_executor(None, wf_storage.load_workflow, task_type, thread_id)
    if not wf:
        return None
    return wf.to_dict()


class WorkflowSaveRequest(BaseModel):
    title: str
    steps: list


@app.post("/threads/{task_type}/{thread_id}/workflow")
async def save_workflow_endpoint(task_type: str, thread_id: str, body: WorkflowSaveRequest):
    from agent.workflow.model import Workflow, WorkflowStep
    import uuid as _uuid
    steps = [
        WorkflowStep(
            id=s.get("id") or _uuid.uuid4().hex[:8],
            title=s["title"],
            type=s.get("type", "auto"),
            status=s.get("status", "pending"),
            notes=s.get("notes", ""),
        )
        for s in body.steps
    ]
    wf = Workflow(thread_id=thread_id, task_type=task_type, title=body.title, steps=steps)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, wf_storage.save_workflow, wf)
    return wf.to_dict()


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

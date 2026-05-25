import json
import asyncio
import os
from pathlib import Path
import uvicorn
from fastapi import FastAPI

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


async def generate(message: str, thread_id: str = "", task_type: str = ""):
    client = get_client()
    model = get_model()
    session_mgr = get_session_manager()
    loop = asyncio.get_event_loop()

    # 스레드 모드 vs 일반 세션 모드
    if thread_id and task_type:
        messages = await loop.run_in_executor(
            None, session_mgr.get_thread_messages, task_type, thread_id
        )
        messages.append({"role": "user", "content": message})
        session_id = None
    else:
        messages = [{"role": "user", "content": message}]
        session_id = await loop.run_in_executor(None, session_mgr.new_session, message)

    tool_calls_raw: dict[int, dict] = {}
    text_chunks: list[str] = []
    text_chunks2: list[str] = []
    finish_reason = None

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            stream=True
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

    except Exception as e:
        yield sse({"type": "error", "message": str(e)})
        yield sse({"type": "done"})
        return

    # 툴 호출이 있으면 실행 후 두 번째 응답
    if finish_reason == "tool_calls" and tool_calls_raw:
        assistant_tool_calls = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"]}
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

            yield sse({"type": "tool_done", "tool": tc["name"], "result": result[:1000]})

            if session_id:
                await loop.run_in_executor(None, session_mgr.log_tool, session_id, tc["name"], result)

            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        # 두 번째 스트리밍 응답
        try:
            stream2 = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True
            )
            for chunk in stream2:
                content = chunk.choices[0].delta.content
                if content:
                    text_chunks2.append(content)
                    yield sse({"type": "text", "content": content})
        except Exception as e:
            yield sse({"type": "error", "message": str(e)})

    # 최종 assistant 응답을 messages에 추가
    final_text = "".join(text_chunks2) if text_chunks2 else "".join(text_chunks)
    if final_text:
        messages.append({"role": "assistant", "content": final_text})

    # 스레드 또는 세션 종료
    if thread_id and task_type:
        await loop.run_in_executor(
            None, session_mgr.save_thread_messages, task_type, thread_id, messages
        )
    else:
        summary = "".join(text_chunks)[:500]
        await loop.run_in_executor(None, session_mgr.close_session, session_id, summary)

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
    return {k: {"label": v["label"], "icon": v["icon"]} for k, v in TASK_CONFIGS.items()}


@app.get("/threads/{task_type}")
async def list_threads(task_type: str):
    mgr = get_session_manager()
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
async def get_thread_messages(task_type: str, thread_id: str):
    mgr = get_session_manager()
    return await asyncio.get_event_loop().run_in_executor(
        None, mgr.get_thread_display_messages, task_type, thread_id
    )


@app.post("/threads/{task_type}/{thread_id}/close")
async def close_thread(task_type: str, thread_id: str):
    mgr = get_session_manager()
    await asyncio.get_event_loop().run_in_executor(
        None, mgr.close_thread, task_type, thread_id
    )
    return {"status": "completed"}


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

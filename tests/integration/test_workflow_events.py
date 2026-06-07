"""워크플로우 파일 변경 감지 SSE 엔드포인트 통합 테스트 (Phase 4-B).

httpx.ASGITransport과 Starlette TestClient 모두 SSE 스트리밍을 지원하지 않는다.
응답 바디를 메모리에 전부 버퍼링하므로 무한 SSE 스트림에서 영원히 대기한다.

해결: 실제 uvicorn 서버를 백그라운드 스레드에서 실행, httpx.Client(sync)로 읽는다.
break 시 TCP 연결이 끊어지면 uvicorn이 http.disconnect 을 앱에 전달하여 서버 루프가 종료된다.
"""

import json
import os
import socket
import time
import threading
import pytest
import httpx
import uvicorn


def _free_port() -> int:
    """OS가 빈 포트를 할당하도록 한다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def sse_server(tmp_path, monkeypatch):
    """실제 uvicorn 서버를 테스트마다 실행한다 (진짜 TCP 스트리밍 필요)."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_HOST", "")
    monkeypatch.setenv("WF_POLL_INTERVAL", "0.1")
    # mock_llm 에 해당하는 패치 — SSE 엔드포인트는 LLM을 호출하지 않으므로
    # 실제 패치 없이도 동작하지만, 모듈 수준 싱글턴을 초기화한다.
    import agent.obsidian_session as _obs
    import agent.config as _cfg
    _obs._instance = None
    _cfg._active_override = None

    from agent.server import app

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "uvicorn 서버가 시작되지 않았습니다"

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)

    _obs._instance = None
    _cfg._active_override = None


class TestWorkflowEvents:
    def test_endpoint_returns_sse_content_type(self, sse_server):
        with httpx.Client() as c:
            r = c.post(f"{sse_server}/threads/general", json={})
            tid = r.json()["thread_id"]
            with c.stream("GET", f"{sse_server}/threads/general/{tid}/workflow/events",
                          timeout=5.0) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        break

    def test_initial_event_contains_workflow(self, sse_server):
        with httpx.Client() as c:
            r = c.post(f"{sse_server}/threads/general", json={})
            tid = r.json()["thread_id"]
            with c.stream("GET", f"{sse_server}/threads/general/{tid}/workflow/events",
                          timeout=5.0) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        evt = json.loads(line[5:].strip())
                        assert evt.get("type") == "workflow_update"
                        assert "workflow" in evt
                        assert "steps" in evt["workflow"]
                        break

    def test_initial_event_workflow_has_steps(self, sse_server):
        with httpx.Client() as c:
            r = c.post(f"{sse_server}/threads/general", json={})
            tid = r.json()["thread_id"]
            with c.stream("GET", f"{sse_server}/threads/general/{tid}/workflow/events",
                          timeout=5.0) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        evt = json.loads(line[5:].strip())
                        assert len(evt["workflow"]["steps"]) > 0
                        break

    def test_file_change_emits_new_event(self, sse_server, tmp_path, monkeypatch):
        """파일이 변경되면 업데이트 이벤트가 발행되어야 한다."""
        # sse_server 픽스처가 이미 OBSIDIAN_VAULT_PATH를 tmp_path로 설정했다.
        # 같은 tmp_path를 스토리지 함수에서도 읽도록 환경변수를 재확인한다.
        from agent.workflow import storage as wf_storage

        with httpx.Client() as c:
            r = c.post(f"{sse_server}/threads/general", json={})
            tid = r.json()["thread_id"]
            wf_storage.load_definition("general", tid)  # .md 파일 생성 유도

            events: list = []

            def _modify_file():
                time.sleep(0.15)
                defn = wf_storage.load_definition("general", tid)
                defn.nodes[0].title = "파일에서 직접 수정된 단계"
                wf_storage.save_definition(defn)

            t = threading.Thread(target=_modify_file, daemon=True)
            t.start()

            with c.stream("GET", f"{sse_server}/threads/general/{tid}/workflow/events",
                          timeout=5.0) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        try:
                            events.append(json.loads(line[5:].strip()))
                        except json.JSONDecodeError:
                            pass
                        if len(events) >= 2:
                            break

            t.join(timeout=2)

        assert len(events) >= 2, "파일 변경 후 두 번째 이벤트가 와야 한다"
        steps = events[-1]["workflow"]["steps"]
        titles = [s["title"] for s in steps]
        assert "파일에서 직접 수정된 단계" in titles

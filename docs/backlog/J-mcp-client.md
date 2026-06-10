# 백로그 J — MCP 클라이언트 + Oracle DB MCP 🔌

> 상태: ✅ 클라이언트 구현 완료 (2026-06-11) · Oracle 실연결은 회사 환경 · Obsidian=기존 유지(대체 안 함)
>
> **구현**: `agent/mcp_client.py`(`MCPManager` 전용 asyncio 루프 스레드 + `run_coroutine_threadsafe` sync 브릿지,
> `mcp` SDK 지연 import). `mcp_tool_to_manifest`로 MCP 도구→MANIFEST 변환, `tools/__init__.register_tool`로 런타임
> 등록(TOOLS/TOOL_LABELS in-place). 안전: `readOnlyHint`→`_risk`(safe/mutate)를 `classify_risk(risk_hint=)`가 반영
> (허용목록 우선). `server.py` startup에서 `connect_all()`, shutdown에서 정리. `_MODULE_PRIORITY`에 `mcp`(core권).
> 설정 `mcp_servers.json`(.gitignore, `.example` 제공: python-oracledb 권장 / 공식 SQLcl). `MCP_ENABLED`·`MCP_CONFIG`.
> **무설정/미설치 = 무해**(0개 등록, `EXPECTED_TOOL_COUNT=131` 불변). 테스트 `tests/unit/test_mcp_client.py`(11).
> Oracle 실연결·`pip install mcp`·서버 프로비저닝은 회사 환경 수동.
>
> **Obsidian 결론**: 기존 `obsidian_rag`(18종) **유지**. mcp-obsidian(Markus 7/cyanheads 14)보다 풍부(wikilink BFS·
> 섹션편집·배치 스캔·move+링크갱신·Templater)하고 REST→파일 fallback(폐쇄망 복원력) 보유. MCP는 가산적(Oracle+향후).
> mcp-obsidian의 periodic notes·JsonLogic 같은 니치만 향후 선택 추가 여지.
>
> 아래는 원래 설계 메모(보존).

## 목표

MCP(Model Context Protocol) 서버에 연결해 그 도구들을 에이전트 도구로 노출한다.
기본으로 **Oracle DB MCP 1개**를 연동한다. 더불어 기존 기능 중 MCP로 대체 가능한지 검토한다.

현재는 MCP를 배제하고 만들었으나(`_registry` 자동 디스커버리), MCP 클라이언트를 준비하면
외부 표준 도구(파일시스템·git·DB 등)를 손쉽게 붙일 수 있다.

## 아키텍처

### `agent/mcp_client.py` (신규) — `MCPManager`

- **설정 `mcp_servers.json`**(레포 루트, Claude Desktop과 동일 shape):
  ```json
  { "servers": { "oracle": { "command": "...", "args": [...], "env": {...}, "transport": "stdio" } } }
  ```
  경로는 `.env` `MCP_CONFIG`로 재정의. **파일 미존재 시 비활성**(무해 — MCP 없이 정상 동작).
- **전용 asyncio 루프 스레드**(`browser.py`의 단일 스레드 executor와 동형): 모든 MCP 세션을
  이 루프가 소유. 동기 핸들러는 `run_coroutine_threadsafe(coro, loop).result()`로 **sync 브릿지**
  — `run_tool`이 동기 디스패치라 필수.
- 시작 시 서버별 `stdio_client` → `ClientSession.initialize()` → `list_tools()`.
- 각 MCP 도구 → **MANIFEST 변환**:
  - `name = mcp_<server>_<tool>`
  - `schema` = MCP `inputSchema`(JSON Schema)를 OpenAI function 스키마로 래핑
  - `handler` = sync 브릿지(`session.call_tool(name, args)` 결과를 문자열 직렬화)
  - 위험도 힌트 = MCP `annotations.readOnlyHint` 보존

### 레지스트리 런타임 등록

- `agent/tools/__init__.py`에 `register_tool(manifest)` 헬퍼 추가 — `_registry`에 넣고
  `TOOLS`/`TOOL_LABELS` 재빌드. (현재 import 시점 1회 빌드 → 늦은 등록 허용으로 확장.)
- `agent/server.py` `@app.on_event("startup")`에서 `MCPManager` 기동 → 도구 등록,
  `shutdown`에서 세션·서브프로세스 종료.
- `select_tools`(128 한계 대응)의 `_MODULE_PRIORITY`에 `mcp`를 core권으로 추가(미등록 모듈
  기본 포함 규칙으로도 커버되나 명시 권장 — Oracle 도구가 드롭되면 곤란).

### 안전 게이트

- MCP 도구는 `annotations.readOnlyHint`를 읽어 **읽기전용=safe / 그 외=mutate(확인)**.
  hint 없으면 **보수적으로 mutate**. `_safety.classify_risk`가 레지스트리의 위험도 힌트를 참조하도록 소폭 확장.

### Oracle MCP 서버

- `python-oracledb` 기반 MCP 서버(커뮤니티 `mcp-oracle*` 또는 자작) 별도 프로비저닝.
- **실연결은 회사 환경 필요**(접속정보·방화벽). 클라이언트 인프라 검증은 공개 MCP(filesystem/everything)로 선행.
- `requirements.txt`에 `mcp`(Python SDK) 추가 — 폐쇄망은 USB 사전반입(`npx -y` 금지 규칙과 동일 맥락).

## 기존 기능 MCP 대체 검토 (결론)

MCP는 **가산적**으로 도입하고, 동작 중인 로컬 도구는 유지한다. 대체 후보는 외부성 강한 것만:
Obsidian(`mcp-obsidian`)·filesystem·git·fetch. 화면/데스크탑/Office COM/UI Automation은
로컬 의존이라 대체 불가. **즉시 대체는 권장하지 않음**(추후 별도 평가).

## 파일

- 신규: `agent/mcp_client.py`, `mcp_servers.json.example`
- 수정: `agent/tools/__init__.py`(register_tool), `agent/server.py`(startup/shutdown 훅),
  `agent/tools/_safety.py`(MCP 위험도 힌트), `.env.example`(MCP_CONFIG), `requirements.txt`(mcp)

## 테스트 (TDD, 실연결 없이)

- mock MCP 세션 → `inputSchema` → function 스키마 변환 정확성.
- sync 브릿지: `call_tool` 결과 문자열 직렬화.
- `register_tool`이 `_registry`·`TOOLS` 갱신.
- `classify_risk`: `readOnlyHint=true` → safe / 그 외 → mutate.
- `mcp_servers.json` 부재 시 무해(기존 도구 수 불변).

## 열린 질문 · 블로커

- 어떤 Oracle MCP 서버를 쓸지(자작 vs 커뮤니티) · 폐쇄망 번들 방법.
- transport: 폐쇄망은 `stdio`(로컬 서브프로세스) 권장.
- 회사 Oracle 접속정보(host/port/service, 계정) — 회사 환경에서 확보.

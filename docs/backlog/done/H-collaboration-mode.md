# 백로그 H — 협업모드(코치 모드) 🤝

> 상태: ✅ 구현 완료 (2026-06-10) · 선행 I(포커스 비탈취)도 완료
>
> **구현 요약**: 백엔드 `agent/collaborate.py`(`start`/`tick`/`stop`/`screenshot_and_diff`/`make_hint`/`_change_ratio`),
> `POST /collaborate/start·tick·stop`. 힌트는 **toolless 단발 멀티모달**(`make_hint`, tools 미전송)이라 실행 도구
> 구조적 차단. 변화율 게이트(`COLLAB_CHANGE_THRESHOLD`)로 LLM 호출 통제. 프런트: 헤더 `🤝 협업` + 목표 입력 바
> (`chat.js` 컨트롤러, 30s 폴링), 별도 플로팅 HUD 창(`main.js createHudWindow`, `focusable:false`, `hud.html`/`hud.js`/`hud-preload.js`).
> 테스트 `tests/unit/test_collaborate.py`(11)+`tests/integration/test_server_collaborate.py`(4). 실제 화면/HUD 동작은 Windows 수동 검증.
>
> 아래는 원래 설계 메모(보존).

## 목표

사용자가 목표를 정하고 **직접 작업하는 동안**, 에이전트가 *실행자*가 아니라 *관찰자/조언자*로
화면을 보며 목표 달성에 도움이 되는 **비간섭 힌트**를 띄운다. 협업모드에서 에이전트는 실행
도구를 쓰지 않는다(쓸 수 없다). 방금 구현한 `capture_screen`(읽기·포커스 비탈취) 위에 쌓는다.

## 확정 설계 (사용자 선택)

- **트리거 = 하이브리드**: 주기적 자동 감시 + 변화 감지로 의미 있는 변화 때만 LLM 호출(비용↓) + 사용자 수동 "지금 봐줘".
- **힌트 UI = 항상-위 플로팅 HUD**: 작고 끌어다닐 수 있는 옅은 투명 오버레이 창(**포커스 비탈취**). 메인창을 안 띄워도 됨.

## 핵심 아키텍처 결정 — "도구 없는 단발 멀티모달 호출"

협업 힌트는 메인 에이전트 루프(`agent/server.py generate()`)를 **타지 않는다**. 대신
`_extract_memories`처럼 **`tools` 미전송 단발 호출**로 만든다.

- → 실행 도구 차단이 *구조적으로 자동 보장*(plan 모드처럼 프롬프트로 막을 필요 없음).
- → 비용·복잡도↓, 무한루프/승인게이트 무관.

## 흐름

1. **목표 설정**: 헤더 `🤝 협업` 토글 ON → 사용자가 목표 입력 → `POST /collaborate/start {thread_id, goal}`.
   서버가 세션 상태 보관: `{goal, last_shot(bytes), hint_history[]}`.
2. **주기 틱(클라이언트 구동)**: 렌더러 타이머(`COLLAB_TICK_MS`, 기본 30s)가 `POST /collaborate/tick {thread_id, force?}` 호출.
   - 현재 화면 캡처(`agent/tools/vision.py _screenshot` 재사용).
   - 직전 스크린샷과 **변화율 계산**(PIL 픽셀 diff; `screen.py`의 `compare_screenshots` 로직 재사용).
   - 변화율 < `COLLAB_CHANGE_THRESHOLD`(기본 0.08)면 **LLM 미호출**, `{hint: null}` 반환(비용 절감).
   - 변화 충분 시: `goal` + 현재 화면 이미지(base64 멀티모달) + 최근 힌트 이력 →
     **toolless 멀티모달 1회 호출** → 짧은 힌트 1개. "힌트 없음"도 정상 응답.
3. **수동 "지금 봐줘"**: HUD/헤더 버튼 → `tick(force=true)` (변화 게이트 우회).

## HUD (포커스 비탈취 핵심)

Electron 별도 `BrowserWindow`:
`alwaysOnTop:true`, `focusable:false`, `transparent:true`, `frame:false`, `skipTaskbar:true`,
작은 크기(예 320×160), 드래그 이동 가능(`-webkit-app-region: drag`). `renderer/hud.html` 로드.
메인창을 안 띄워도 힌트만 떠 있음. `main.js createWindow()`(현 58–74) 패턴 재사용해
`createHudWindow()` 추가. 토글/힌트는 IPC(`collab-toggle`·`collab-hint`)로 전달.

## 파일 · 재사용

- **신규 `agent/collaborate.py`**: 세션 상태 dict, `screenshot_and_diff(thread_id) -> (img_bytes, change_ratio)`,
  `make_hint(goal, img_b64, history) -> str|None`(toolless 멀티모달: `get_client().chat.completions.create(messages=[멀티모달], stream=False)`, **tools 미전송**).
- **`agent/server.py`**: `POST /collaborate/start`·`POST /collaborate/tick`.
  (재사용: vision `_screenshot`, `_extract_memories`의 비스트리밍 호출 패턴.)
- **`agent/core/events.py`**: (선택) `COLLABORATION_HINT` — 틱을 SSE로 할 경우. JSON 응답이면 불필요.
- **`electron/main.js`**: `createHudWindow()` + IPC 핸들러. **`preload.js`**: `collabToggle`/`onCollabHint` 노출(현 25–26 패턴).
- **`electron/renderer/`**: 헤더 `🤝 협업` 버튼(`index.html`), `chat.js`에 협업 타이머·`/collaborate/*` 호출, 신규 `hud.html`/`hud.js` + HUD css.
- **`.env.example`**: `COLLAB_TICK_MS=30000`, `COLLAB_CHANGE_THRESHOLD=0.08`.

## 테스트 (TDD)

- `tests/unit/test_collaborate.py`:
  - 변화율 < 임계면 LLM 미호출 + `hint=None`(호출 카운터 monkeypatch).
  - `force=true`면 변화 게이트 우회.
  - `make_hint` 프롬프트에 goal + 이미지 블록 포함(LLM·`_screenshot` monkeypatch).
- `tests/integration`: `/collaborate/start`·`/collaborate/tick` 엔드포인트 동작.

## 열린 질문

- 멀티모니터 / 특정 창만 캡처 범위?
- 힌트 이력 영속(노트 저장) 여부 — 기본은 ephemeral(메모리)?
- HUD 클릭 → 메인창 포커스/펼침 동작?

## 블로커 · 리스크

- `VISION_ENABLED` + 멀티모달 LLM 필요(이미 기본 true).
- `focusable:false` 창의 Windows 실제 동작(클릭 통과·드래그) 실검증 필요.
- 비용: 변화 게이트로 통제하나 활성 중엔 주기 호출 발생 → 임계/주기 튜닝.

## 권장 시퀀스

I(포커스 비탈취) 선행 → H 착수. capture_screen·SSE·창 IPC(백로그 C)는 이미 존재.

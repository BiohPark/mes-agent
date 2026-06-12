# 백로그 Q — 작업 상태 명확화 + 작업 중 개입(긴급 대화) ⏯️

> 상태: ✅ 완료 (2026-06-13) · 메시지 큐 메커니즘을 **백로그 O가 재사용 가능**

## 구현 결과 (2026-06-13)

- **백엔드** `agent/server.py`: 모듈 큐 `_pending_messages: dict[str, list[str]]`(`_stop_flags` 패턴 미러링) +
  `POST /inject/{request_id}`(활성 요청이면 큐 적재 `ok=True`/아니면 `ok=False`). `generate()` 루프가
  **단계 경계(중단 확인 직후, tool 묶음·캡처 이미지 append 완료 = I1 짝 보존 지점)에서 드레인** →
  `[사용자 끼어들기] {msg}` user 메시지로 주입 + `INJECTED` SSE. 도구 실행 도중 도착분은 다음 반복 경계에서 주입.
- **이벤트** `agent/core/events.py`: `INJECTED = "injected"`.
- **프론트** `chat.js`/`index.html`/`style.css`: `setInputEnabled`이 실행 중에도 입력칸·확대 에디터를 열어 두고
  전송 버튼만 비활성. `submitInput`이 `currentRequestId` 유무로 `injectMessage`(/inject)↔`sendMessage`(/chat) 라우팅.
  상태바에 `↩ 끼어들기` 버튼(실행 중만 노출, stop과 구분), waiting을 `data-state="waiting"`로 색·펄스 강조("당신 차례").
  `injected` SSE → "끼어든 메시지를 반영합니다" 노트.
- **테스트** `tests/integration/test_server_interject.py`(6): 엔드포인트(활성/미지), 드레인 주입, INJECTED 발행,
  I1 짝 보존, 무주입 시 팬텀 없음. `.\test.ps1 ci` 전체 564 통과.

아래는 원래 설계 메모(보존).

---

> (원안) 상태: 🔲 미착수 · 우선순위 **상** · 메시지 큐 메커니즘을 **백로그 O와 공유**

## 문제·가치
1. **running vs waiting 구분이 모호** — 지금 돌고 있는지, 내 입력을 기다리는지 헷갈린다.
2. **작업 중 끼어들 수 없다** — 진행 중에는 입력창이 비활성(`chat.js setInputEnabled(false)`)이라
   긴급 수정·방향 전환을 하려면 중단(stop) 후 처음부터 다시 해야 한다.

## 접근

### 상태 명확화
- 기존 4상태(`chat.js STATE_META`: thinking/running/waiting/idle)를 **시각적으로 강하게 구분**:
  - running = 진행 애니메이션 + 현재 단계 표시
  - waiting = 사용자 액션 강조(색·아이콘·"**당신 차례**" 배지) → 놓치지 않게
- 상태바 + 우측 워크플로우 패널 상태 **동기화**.

### 작업 중 개입 (메시지 큐 주입)
- 작업 중에도 입력 허용(별도 **"끼어들기"** 버튼, stop과 구분).
- 입력 시 `_pending_messages[request_id]` 큐에 적재 → `generate()` 루프가 **단계 경계에서 드레인**해
  user 메시지로 주입. **I1(도구 짝 보존)** 지켜 도구 묶음 사이에서만 주입.
- **재사용**: `_stop_flags` 패턴, 루프 단계 경계, SSE `AGENT_STATE`. **백로그 O와 동일 큐**.

## 핵심 파일
- `agent/server.py`(generate 큐 드레인 + 신규 `POST /inject/{request_id}`),
  `electron/renderer/chat.js`(입력 활성·끼어들기 UI), `style.css`(상태 배지).

## 확인 필요
1. 주입 타이밍 — **즉시 vs 다음 단계 경계**(I1 보존상 다음 경계 권장).
2. 도구 실행 **도중** 도착한 메시지 처리(현 도구 완료 후 주입).
3. 긴급 수정 UX — 인라인 끼어들기 vs 모달.

## 규모
M~L. **O보다 먼저**(큐 메커니즘을 Q에서 확립 → O가 외부 입력으로 재사용).

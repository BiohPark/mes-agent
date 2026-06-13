---
name: loop-audit
description: agent/server.py의 generate() 루프를 감사·디버그한다. L1 계약 위반, 무한루프, 툴 짝 불일치를 찾는다.
metadata:
  type: debugging
---

## Generate() 루프 감사

### L1 루프 계약 핵심 (`docs/adr/0002-L1-loop-contract.md`)

| 불변식 | 내용 | 위반 증상 |
|--------|------|-----------|
| I1 | `tool_calls` 있는 assistant 메시지 뒤에 반드시 `tool` 결과 메시지 | API 400 / InvalidRequest |
| I3 | 루프 상한(`MAX_STEPS`·`MAX_NUDGES`·`MAX_COMPACT`) 준수 | 무한 루프, 비용 폭주 |
| I4 | 모든 경로(예외 포함)가 `DONE` 이벤트로 종료 | 클라이언트 SSE 연결 끊김 |

### 1단계: 증상 분류

- **API 400 / InvalidRequest** → I1 위반 의심 → 2단계로
- **루프가 끝나지 않음** → I3 상한 도달 여부 확인 → 3단계로
- **SSE가 갑자기 끊김** → I4 DONE 미발행 → 4단계로
- **컨텍스트 초과 오류** → overflow.py 5단 방어 미발동 → 5단계로

### 2단계: I1 짝 불일치 찾기

`server.py` 또는 로그에서 history 덤프 후:

```python
for i, msg in enumerate(history):
    if msg.get("role") == "assistant" and msg.get("tool_calls"):
        nxt = history[i+1] if i+1 < len(history) else None
        if not nxt or nxt.get("role") != "tool":
            print(f"짝 불일치: index {i}, tool_calls={[t['id'] for t in msg['tool_calls']]}")
```

**의심 위치**: `compaction.compact_history()`, safety gate CONFIRM 거부 처리, `capture_screen` 주입 로직.

### 3단계: 루프 상한 확인

`agent/server.py`에서 상수 확인:
- `_MAX_STEPS` (기본 40)
- `MAX_NUDGES` (기본 2)
- `MAX_COMPACT` (기본 3)

nudge 조건: `tool_rounds > 0` AND `finish_reason != "tool_calls"` AND 되묻기(`?` 미종결) AND 사용자 미중단.
nudge가 무한히 발생하면 위 조건 중 하나가 누락된 것.

### 4단계: DONE 미발행 경로 찾기

`generate()` 함수의 `try/except/finally` 블록에서 모든 `return` 또는 `break` 경로가 `yield` 또는 SSE로 `DONE`을 발행하는지 확인.
`agent/core/events.py`의 `DONE` 상수와 비교.

### 5단계: 컨텍스트 초과 (overflow.py 5단 방어)

`agent/core/overflow.py`의 5단계:
1. 이미지 prune (`prune_images`)
2. 이미지 다이어트 (`M1` 다운스케일)
3. 강제 compact
4. 재시도
5. 그래도 실패 → 구조화 오류로 DONE

미발동이면 `_estimate_tokens()` 반환값이 실제보다 낮을 가능성 → `agent/core/tokens.py` 점검.

### 유용한 디버그 커맨드

```python
# 현재 history 토큰 추정
from agent.core.tokens import estimate_tokens
from agent.server import _history  # 실행 중인 서버의 history
print(estimate_tokens(_history.get(request_id, [])))

# 툴 짝 검증
pairs = [(i, msg) for i, msg in enumerate(history) if msg.get("tool_calls")]
for i, msg in pairs:
    nxt = history[i+1] if i+1 < len(history) else "MISSING"
    print(i, "->", nxt.get("role") if isinstance(nxt, dict) else nxt)
```

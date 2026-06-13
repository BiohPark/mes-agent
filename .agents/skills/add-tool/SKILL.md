---
name: add-tool
description: mes-agent에 새 툴을 추가하는 표준 절차. MANIFEST 작성부터 문서 업데이트까지.
metadata:
  type: workflow
---

## 새 툴 추가 절차

### 1. EXPECTED_TOOL_COUNT 먼저 올리기 (TDD red)

`tests/smoke/test_tool_schemas.py`에서 `EXPECTED_TOOL_COUNT` 상수를 현재값 + 추가할 툴 수로 수정.
smoke test를 실행해 **실패를 확인**한 후 다음 단계.

### 2. MANIFEST 항목 작성

기존 모듈에 추가하거나 `agent/tools/<모듈>.py` 신규 생성.

```python
MANIFEST = [
    {
        "name": "tool_name",          # snake_case, 전체 고유
        "description": "한 문장 설명. LLM이 언제 이 툴을 쓸지 판단하는 유일한 근거.",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {
                    "type": "string",   # string|integer|boolean|array|object
                    "description": "파라미터 역할 설명"
                }
            },
            "required": ["param"]
        }
        # 위험한 작업이면 추가:
        # "_risk": "mutate"        # 쓰기/변경 → G3 CONFIRM 팝업
        # "_risk": "destructive"   # 삭제/파괴 → G3 CONFIRM 팝업
    }
]
```

### 3. 핸들러 함수 구현

함수명 = MANIFEST의 `name`.

```python
def tool_name(param: str) -> dict:
    # 성공
    return {"status": "ok", "result": ...}
    
    # 실패 — 예외 raise. server.py가 error 상태로 처리함.
    # raise ValueError("무엇이 왜 실패했는지 설명")
```

파일이 신규라면 `agent/tools/__init__.py`는 수정 불필요 (자동 디스커버리).

### 4. smoke test 통과 확인

```powershell
conda run -n mes-agent pytest tests/smoke/test_tool_schemas.py -v
```

### 5. 필수 문서 업데이트 체크리스트

- [ ] `AGENTS.md` — 현재 상태 표의 해당 모듈 툴 수 갱신, 총 툴 수(132→N) 갱신
- [ ] `README.md` — 기능 표에 해당하면 추가
- [ ] `CONTRIBUTING.md` — 툴 목록에 추가
- [ ] `tests/smoke/test_tool_schemas.py` — `EXPECTED_TOOL_COUNT` (이미 1단계에서 올렸을 것)

### 6. 전체 CI 통과

```powershell
.\test.ps1 ci
```

### 참고: 툴 수 한도

LLM API는 tools 배열을 **최대 128개**로 제한. 현재 총 132종이므로 `select_tools()`가 요청당 ≤128개를 자동 선별. 추가 시 우선순위(core 우선)와 키워드 관련도 로직을 `agent/tools/__init__.py`에서 확인.

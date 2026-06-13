---
name: tdd
description: mes-agent TDD 워크플로우. 새 기능·버그픽스를 테스트 우선으로 구현한다. pytest + conda 환경 기준.
metadata:
  type: workflow
---

## mes-agent TDD 워크플로우

### 테스트 계층

| 계층 | 경로 | 설명 | 실행 명령 |
|------|------|------|-----------|
| unit | `tests/unit/` | 순수 함수, mock 허용, 빠름 | `.\test.ps1 unit` |
| integration | `tests/integration/` | 서버/도구 연동, 실제 I/O | `.\test.ps1` |
| smoke | `tests/smoke/` | 툴 스키마 검증, 등록 수 | `.\test.ps1 smoke` |

CI 게이트: `.\test.ps1 ci` — LLM·디스플레이·Office 없이 실행 가능한 subset

### 단계

**1. 범위 파악**
구현할 기능의 경계를 명확히 한다.
- 어떤 입력 → 어떤 출력?
- 어떤 파일을 수정하게 되는가?
- 기존 테스트 중 영향 받는 것은?

**2. 실패 테스트 작성 (red)**
`tests/unit/` 또는 `tests/integration/`에 테스트를 먼저 작성한다.
```python
# 파일명: test_<모듈명>.py
# 함수명: test_<행위>_<조건>_<기대결과>

def test_ocr_extract_returns_text_when_screen_has_content():
    # Arrange
    ...
    # Act
    result = ocr_extract(...)
    # Assert
    assert result["status"] == "ok"
    assert "expected_text" in result["text"]
```
실행 → **실패를 확인**한 후 다음 단계로.

새 툴 추가라면 `tests/smoke/test_tool_schemas.py`의 `EXPECTED_TOOL_COUNT`를 먼저 N+1로 올려 smoke test를 실패시킨다.

**3. 최소 구현 (green)**
테스트를 통과시키는 가장 단순한 코드를 작성한다.
- 추상화 금지 (세 번 반복 전까지는 함수 추출 안 함)
- 에러 처리는 실제 발생하는 경우만
- 주석 없이 이름으로 의도를 전달

**4. 통과 확인**
```powershell
conda run -n mes-agent pytest tests/<파일> -v
```

**5. 리팩터 (refactor)**
동작을 유지하면서 코드를 정리한다. 이후 전체 suite 통과 확인:
```powershell
.\test.ps1 ci
```

**6. 문서 업데이트**
툴 추가·수정이면 AGENTS.md 자동 업데이트 규칙 체크리스트 확인 (AGENTS.md 상단 표 참조).

### 새 툴 TDD 순서 요약

```
EXPECTED_TOOL_COUNT += 추가수  →  smoke 실패 확인
→  MANIFEST 작성  →  핸들러 구현
→  smoke 통과 확인  →  unit 테스트 추가
→  AGENTS.md·README·CONTRIBUTING 업데이트
→  .\test.ps1 ci 통과
```

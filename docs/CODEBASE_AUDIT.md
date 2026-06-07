# Codebase Audit — MES Agent

> 작성일: 2026-06-07 | 기준 커밋: 4e07e3e | 브리프 §10 체크리스트 답변

---

## Q1. 워크플로우 모델

**파일:** `agent/workflow/model.py` (43 LOC)

```python
@dataclass
class WorkflowStep:
    id: str          # uuid4().hex[:8]
    title: str
    type: StepType   # "auto" | "semi_auto" | "manual"
    status: StepStatus  # "pending"|"running"|"waiting"|"done"|"error"|"skipped"
    notes: str = ""

@dataclass
class Workflow:
    thread_id: str
    task_type: str
    title: str
    steps: list      # list[WorkflowStep], 순서 = 실행 순서
```

**단계 간 관계:** list index 암묵적 순서뿐. 명시적 연결(edge)·조건(condition) 없음.

**실제 JSON 예시** (`agent/workflows/general/2026-0607-001.json`):
```json
{
  "thread_id": "2026-06-07-001",
  "task_type": "general",
  "title": "기본업무 워크플로우",
  "steps": [
    {"id": "a1b2c3d4", "title": "요청 분석", "type": "auto", "status": "done", "notes": ""},
    {"id": "e5f6a7b8", "title": "작업 실행", "type": "auto", "status": "running", "notes": ""}
  ]
}
```

**C1(노드/커넥션) 진화 시 깨지는 가정:**
- `reorder` 툴이 ordered_step_ids 리스트 순서를 실행 순서로 취급 (`storage.py:91`)
- `add_step`의 `after_step_id`가 list index 기반 삽입 (`workflow.py:51-54`)
- 기본 템플릿이 딕셔너리 순서를 실행 순서로 정의 (`storage.py:10-45`)
- 정의와 상태(status)가 같은 객체에 혼재 → C3 위반

---

## Q2. 워크플로우 편집 6종 툴

**파일:** `agent/tools/workflow.py` (286 LOC)

| 툴 | 동작 | 분기 그래프 전환 시 깨지는 지점 |
|----|------|-------------------------------|
| `workflow_init` | 전체 교체(save_workflow) | `steps` 배열만 받음, connections 개념 없음 |
| `workflow_set_step` | step_id로 status/notes 업데이트 | step_id만 있으면 동작 가능, 분기 구조엔 영향 없음 |
| `workflow_add_step` | after_step_id 뒤 list.insert | 선형 삽입 전제, 복수 출력 엣지 표현 불가 |
| `workflow_update_step` | title/type 변경 | 분기 안전, connections 미지원 |
| `workflow_remove_step` | step_id 필터링 | 해당 step을 가리키는 edge 고아 처리 없음 |
| `workflow_reorder` | ordered_ids → 새 list | 선형 전제, 그래프에선 무의미 |

**핵심:** `set_step`·`update_step`은 분기 전환 이후에도 인터페이스 변경 없이 재사용 가능. `init`·`add`·`remove`·`reorder`는 connections 지원 추가 필요.

---

## Q3. Obsidian 통신·동기화

**파일:** `agent/tools/obsidian_rag.py`, `agent/obsidian_session.py`

**통신 방식:** `urllib.request.urlopen(req, context=ssl_ctx, timeout=8)` — MCP 없음, 순수 HTTP REST.

**엔드포인트 패턴:**
```python
# obsidian_rag.py:43-63
req = urllib.request.Request(
    _api_base() + path,   # OBSIDIAN_HOST + /vault/path/to/note.md 등
    headers={"Authorization": OBSIDIAN_API_KEY},
    ...
)
```

**워크플로우 저장 경로:** `OBSIDIAN_VAULT_PATH/agent/workflows/{task_type}/{thread_id}.json`

**동기화 방향 분석 (P1-b):**
- 에이전트→파일: `save_workflow()` 호출 시 덮어씀 ✓
- 파일→에이전트: `load_workflow()`는 요청 시에만 파일을 읽음. **파일 변경 감시(inotify, polling) 없음.**
- 결론: **단방향 (에이전트 → Vault)**. 사람이 Obsidian에서 JSON을 수정해도 에이전트가 재로드하려면 해당 스레드로 새 메시지를 보내야 함(그때 `get_thread_messages` → `get_workflow`가 파일을 다시 읽음).
- P1-b 현재 상태: 씨앗(Vault 저장)은 있으나 양방향 동기화 없음.

---

## Q4. 에이전트 실행 루프

**파일:** `agent/server.py:99-286`

**루프 구조:**
```
generate() 진입
  ├─ thread_id 있으면 get_thread_messages() 로 이전 대화 복원
  └─ for _step in range(20):
       ├─ LLM 스트림 호출 (chat.completions.create stream=True)
       ├─ 텍스트 청크 → SSE TEXT
       ├─ tool_calls_raw 누적 (인덱스별 조각 조립)
       ├─ finish_reason == "stop" → idle 상태로 break
       └─ tool_calls_raw 있으면:
            for tc in tool_calls_raw:
              run_tool(name, args) → TOOL_START / TOOL_DONE SSE
              └─ workflow_* 툴이면 결과에서 workflow 추출 → WORKFLOW_UPDATE SSE
```

**단계 status 갱신:** LLM이 판단해서 `workflow_set_step` 툴을 직접 호출. 서버 코드는 툴 실행만 중계함. → **갱신이 LLM 재량에 맡겨짐.**

**정의/상태 분리(C3) 현재 상태:** WorkflowStep.status가 정의 파일에 포함됨. 한 파일에 정의(title, type)와 상태(status, notes)가 혼재. 분리되지 않음.

---

## Q5. 타겟팅/액션

**파일:** `agent/tools/desktop.py` (672 LOC)

**좌표 결정 방식:**
- **직접 좌표:** `mouse_click(x, y)` — LLM이 좌표를 직접 지정. 이미지·OCR로 찾은 좌표를 받아서 사용.
- **SendInput 경로:** UAC 앱용 — 절대 좌표를 65535 기준 정규화 후 `SendInput` API 호출 (`desktop.py:86-105`).
- **이미지 기반 타겟:** `find_image_on_screen` (screen.py) — OpenCV `matchTemplate`으로 위치 반환. 에이전트가 이 좌표로 `mouse_click` 호출.
- **텍스트 기반 타겟:** `find_text_location` (screen.py) — Tesseract OCR 결과에서 bbox 추출.

**접근성(a11y) API 기반 선택:** 없음 (`pywinauto`, `uiautomation` 등 미사용).

---

## Q6. 화면 인식

**파일:** `agent/tools/screen.py` (400 LOC), `agent/tools/ocr.py`

| 기법 | 구현 | 특징 |
|------|------|------|
| 전체 OCR | Tesseract pytesseract | kor+eng, 전체 화면 |
| 영역 OCR | mss 영역 캡처 + Tesseract | 영역 지정, 더 빠름 |
| 이미지 매칭 | OpenCV matchTemplate | 템플릿 이미지 파일 경로 필요 |
| 텍스트 위치 | Tesseract + bbox | 특정 문자열의 화면 좌표 반환 |
| 비교 | numpy array 차분 | compare_screenshots |
| 픽셀 색상 | mss + 인덱싱 | get_pixel_color(x, y) |

**LLM에 이미지 전달:** 없음. `멀티모달 LLM` 항목이 CLAUDE.md에 `🔲 개발 예정`으로 표기됨.

**변화 감지:** `compare_screenshots`는 있으나 능동 polling(스크린 watch loop) 없음. 호출 시점에만 비교.

**캐시:** 없음.

---

## Q7. 실패 처리

**파일:** `agent/server.py:217-219`

```python
try:
    result = await loop.run_in_executor(None, run_tool, tc["name"], tc["arguments"])
except Exception as e:
    result = f"툴 실행 오류: {e}"
```

**전파 경로:**
- 툴 실행 예외 → 문자열 `"툴 실행 오류: ..."` 로 변환 → `TOOL_DONE` SSE로 UI 전달 → LLM 컨텍스트에 tool 결과로 추가
- 워크플로우 단계 `error` 상태 자동 전환: **없음.** LLM이 error 메시지를 보고 스스로 `workflow_set_step(status="error")` 호출해야 함.
- 재시도 메커니즘: **없음.**
- 조용히 삼켜지지는 않으나, error 전환이 LLM 재량에 의존해 누락 가능.

---

## Q8. 테스트 현황

**현재 커밋(4e07e3e) 기준 구축 완료:**

| 계층 | 파일 수 | 테스트 수 | 내용 |
|------|---------|----------|------|
| unit | 3 | 34 | workflow model·storage·config |
| integration | 4 | 35 | FastAPI 엔드포인트, SSE 스트림 |
| smoke | 1 | 29 | 87개 툴 MANIFEST 유효성 |
| **합계** | **8** | **98** | **98/98 통과** |

**Mock 분리 현황:**
- LLM: `FakeLLMClient` (conftest) ✓
- Vault/파일: `tmp_path` monkeypatch ✓
- OS/GUI 호출: 단위·통합 테스트에서 직접 실행 안 함 ✓

**CI(GitHub Actions):** 없음.

**폰(Termux/Linux) 통과 가능성:**
- `unit` 테스트: `agent/tools/desktop.py` import 시 `pyautogui`·`pywin32` Windows 전용 → import 실패 가능성 있음. `conftest.py`에서 tools import를 간접적으로 유발하지 않는 한 unit 테스트는 통과할 것.
- `smoke` 테스트: `from agent.tools import _registry` → 모든 툴 모듈 import → Windows 전용 패키지 import 실패 가능성.
- **결론:** Linux 환경에서 smoke/integration은 의존성 문제로 실패 가능. unit은 대부분 통과.

---

## Q9. 관측 가능성

**SSE 이벤트 9종** (`agent/core/events.py`):

| 이벤트 | 정보 |
|--------|------|
| `request_id` | 에이전트 실행 ID (중단 키) |
| `context_usage` | tokens_used / tokens_total |
| `agent_state` | thinking / running / waiting / idle |
| `tool_start` | 툴 이름·레이블 |
| `tool_done` | 툴 이름·결과(1000자 truncate) |
| `workflow_update` | 갱신된 워크플로우 전체 |
| `confirm` | 사용자 확인 요청 |
| `text` | LLM 텍스트 청크 |
| `done` / `error` | 완료·오류 |

**실행 로그 탭 (`electron/renderer/workflow.js`):** 툴 실행 시간·결과 최대 50개 유지.

**노출되지 않는 것:**
- 툴 실패 횟수·재시도 기록
- 단계 error 원인 상세 (TOOL_DONE 결과에 포함되나 워크플로우 단계에 자동 링크 안 됨)
- 컨텍스트 토큰 추정이 4자=1토큰 근사값

---

## Q10. 의존성 표면

**폐쇄망 주의 패키지:**

| 패키지 | 위험도 | 오프라인 설치 방법 |
|--------|--------|-----------------|
| `playwright` | 높음 | 브라우저 바이너리 별도 이전 필요 |
| `pywin32` | 중간 | whl 파일 수동 이전 |
| `pytesseract` | 중간 | Tesseract 실행파일 별도 설치 |
| `opencv-python` | 낮음 | whl 이전 가능 |
| `httpx` (dev) | 낮음 | whl 이전 가능 |

**새 의존성 추가 시 충돌 위험:** Python 3.13 사용 중 — 일부 바이너리 패키지가 3.13 whl을 아직 미제공할 수 있음 (`maturin` 기반 패키지 주의).

---

## Q11. CLAUDE.md vs 실제 코드 괴리

| 항목 | 문서 | 실제 코드 | 괴리 |
|------|------|----------|------|
| 총 툴 수 87 | ✓ | 87 (smoke 테스트 확인) | 없음 |
| `tests/` 없음 | ×(과거) | 98개 테스트 구축됨 | 문서 이미 반영 |
| `obsidian_rag.py` 7종 | ✓ | 7종 | 없음 |
| `obsidian_session.py` 4종 툴 | ✓ | MANIFEST 있음 | 없음 |
| workflow 저장 경로 `agent/workflows/{type}/{id}.json` | ✓ | `storage.py:88-89` 일치 | 없음 |
| 워크플로우 편집 6종 툴 | ✓ | 6종 | 없음 |
| 멀티모달 비전 `🔲 개발 예정` | ✓ | 코드 없음 | 없음 |
| 일반 채팅 기억 `🔲 개발 예정` | ✓ | 코드 없음 | 없음 |

**사실상 괴리 없음.** 단, 브리프 §3 비목표에서 "Obsidian 통신 방식 교체 자체는 비목표"라고 명시한 것이 CLAUDE.md에는 반영되지 않음 — 향후 혼동 방지를 위해 추가 권장.

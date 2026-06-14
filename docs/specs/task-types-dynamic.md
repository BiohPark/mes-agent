# 스펙 — 동적 업무 타입 관리 (백로그 T)

> 상태: 구현 대상 · 수용 게이트 = `tests/unit/test_task_type_tools.py` + `tests/integration/test_task_config_api.py` + `.\test.ps1 ci`

## 해결하는 문제

새 업무(타입)를 추가·제거하려면 코드 2곳을 함께 수정해야 한다:
- `agent/obsidian_session.py` `TASK_CONFIGS` dict (Python)
- `electron/renderer/index.html` 하드코딩 `<div class="task-group">` 5개

"대화로 등록·삭제"가 불가하고 회사 PC(폐쇄망)에 개발 도구가 없어 코드 수정을 배포할 수 없다.

## 설계

### 1. `agent/obsidian_session.py` — TASK_CONFIGS 동적화

`TASK_CONFIGS` dict를 **내장 기본값 + Vault 오버레이** 방식으로 바꾼다.

```
_DEFAULT_TASK_CONFIGS = { ... }  # 기존 5타입 그대로 (삭제 불가 보호 대상)

def get_task_configs() -> dict:
    """내장 기본값 + Vault agent/task_types.json 머지. Vault 없으면 기본값만."""
```

- Vault 파일 경로: `agent/task_types.json` (없으면 자동 생성 X — 툴이 작성)
- 머지 규칙: `{**_DEFAULT_TASK_CONFIGS, **vault_custom}` — 사용자 타입이 기본 위로 올라와도 되고, 기본 타입 override도 허용
- **`TASK_CONFIGS` 이름 유지 금지** — 모든 호출부를 `get_task_configs()`로 교체(캐시 없음, 매 호출 Vault 재읽기 OK)
- Vault I/O: 기존 `self._read` / `self._write` 대신 `get_session_manager()._read/_write` 패턴 재사용. 단 `get_task_configs()`는 모듈 수준 함수라 `_sm()`= `get_session_manager()` 호출로 처리.

**교체 대상 (`TASK_CONFIGS` → `get_task_configs()`):**
| 파일 | 위치 |
|------|------|
| `agent/obsidian_session.py` | `setup_vault()` for loop, `create_thread()`, `load_thread_messages()`, `list_all_threads()`, `search_threads()` |
| `agent/server.py` | import 제거, `generate()` cfg 조회 (`line ~425`), `/task-config` 엔드포인트 |

### 2. 신규 툴 — `agent/tools/task_type.py`

**`task_type_create`**
```python
# parameters: name(str), label(str), icon(str), description(str), system_prompt(str)
# _risk = 'mutate'
# 동작: get_task_configs() 조회 → 이름 중복 확인 → vault task_types.json 읽기 → 추가 → 저장
# 반환: {"status": "ok", "name": name}
```

**`task_type_remove`**
```python
# parameters: name(str)
# _risk = 'mutate'
# 동작: _DEFAULT_TASK_CONFIGS에 있으면 거부("기본 업무 타입은 삭제할 수 없습니다")
#       없으면 vault task_types.json에서 해당 키 제거 → 저장
# 반환: {"status": "ok", "name": name} or {"status": "error", "reason": "..."}
```

Vault task_types.json 형식:
```json
{
  "my_custom": {
    "label": "내 업무",
    "icon": "🏭",
    "description": "설명",
    "system_prompt": "프롬프트"
  }
}
```

### 3. `agent/server.py` — `/task-config` 동적화

```python
@app.get("/task-config")
async def task_config():
    from agent.obsidian_session import get_task_configs
    return {
        k: {"label": v["label"], "icon": v["icon"], "description": v.get("description", "")}
        for k, v in get_task_configs().items()
    }
```

기존 `from agent.obsidian_session import get_session_manager, TASK_CONFIGS` import에서
`TASK_CONFIGS` 제거, `get_task_configs` 추가.

### 4. `electron/renderer/index.html` — 하드코딩 제거

`index.html`의 5개 `<div class="task-group" data-task="...">` 블록을 **모두 제거**하고,
빈 컨테이너 `<div id="task-groups-container"></div>`만 남긴다.

```html
<!-- 변경 전: 5개 하드코딩 div -->
<!-- 변경 후: -->
<div id="task-groups-container"></div>
```

### 5. `electron/renderer/chat.js` — 동적 렌더링

앱 시작 시 `/task-config` 응답으로 사이드바를 동적으로 생성한다.

```javascript
async function renderTaskGroups() {
    const configs = await fetch(`${serverBase}/task-config`).then(r => r.json());
    const container = document.getElementById('task-groups-container');
    container.innerHTML = '';
    for (const [taskType, cfg] of Object.entries(configs)) {
        container.insertAdjacentHTML('beforeend', `
          <div class="task-group" data-task="${taskType}">
            <div class="task-group-header">
              <span class="tg-arrow">▸</span>
              <span class="tg-icon">${cfg.icon}</span>
              <span class="tg-label">${cfg.label}</span>
            </div>
            <div class="task-group-body hidden"></div>
          </div>`);
    }
}
```

`renderTaskGroups()`는 **`initWhenReady()` 안에서** 기존 스레드 로드 전에 호출한다.
기존 코드에서 `data-task` 속성으로 `.task-group` 요소를 쿼리하는 모든 부분은 동적 생성 후에도 동작해야 한다 — `document.querySelector`, `document.querySelectorAll` 호출 시점이 `renderTaskGroups()` 완료 이후라면 OK.

---

## 범위

**IN**:
- `obsidian_session.py` `TASK_CONFIGS` → `get_task_configs()` 동적화 + Vault 머지
- 신규 `agent/tools/task_type.py` (task_type_create / task_type_remove 2종)
- `/task-config` 엔드포인트 동적화
- `index.html` 하드코딩 div 제거 → `task-groups-container`
- `chat.js` `renderTaskGroups()` + `initWhenReady()` 연동
- CLAUDE.md 현재 상태 표 T 완료 행 + 툴 수 +2
- `tests/smoke/test_tool_schemas.py` `EXPECTED_TOOL_COUNT` +2 (132 → 134)
- 테스트 2종 신규

**OUT** (후속):
- 시스템 프롬프트 인라인 편집 UI
- 업무 타입 순서 재정렬
- 사이드바 아이콘 커스텀 색상
- 업무 타입 별 전용 워크플로우 템플릿 자동 생성

---

## 수용 기준 (테스트로 검증)

### unit — `tests/unit/test_task_type_tools.py`
- [x] `task_type_create`: 중복 이름 거부 / 새 이름 Vault 저장
- [x] `task_type_remove`: 기본 5타입 삭제 거부 / 커스텀 타입 삭제 OK
- [x] `get_task_configs()`: Vault 없으면 기본 5타입만 / Vault 있으면 머지

### integration — `tests/integration/test_task_config_api.py`
- [x] `GET /task-config` — 기본 5타입 포함 응답
- [x] Vault에 커스텀 타입 추가 후 `GET /task-config` — 기본 + 커스텀 모두 반환
- [x] 기존 `test_server_health.py`의 `TestTaskConfig` 테스트 계속 통과

### smoke
- [x] `EXPECTED_TOOL_COUNT` = 134 (기존 132 + 2)

### CI 전체
- [ ] `.\test.ps1 ci` 전체 통과 (회귀 없음)

---

## 미결 사항 (루프 시작 전 확정)

| 항목 | 결정 |
|------|------|
| 시스템 프롬프트 편집? | No — 코드에 유지, 별도 백로그 |
| 기본 5타입 삭제 허용? | No — `task_type_remove`에서 차단 |
| P 의존성? | 없음 — P 완료 ✅ |

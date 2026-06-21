# 사용자 테스트 개선 구현 플랜 (AA-1~AA-7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2026-06-21 사용자 테스트(Z-goal-fitness-verification.md)에서 발견된 7개 이슈를 P0→P3 우선순위로 해결한다.

**Architecture:** P0 버그(Excel 저장 손상·PPT 의존성 오류)는 백엔드 Python 수정, P1·P2·P3는 SSE 피드백 개선 및 프론트엔드 UX 조정이다. 테스트는 기존 pytest 인프라(tests/unit/)와 scroll-utils.test.js를 활용한다.

**Tech Stack:** Python 3.11 + FastAPI, zipfile(stdlib), openpyxl, python-pptx, Vanilla JS (Electron Renderer)

---

## 배경 (Context)

2026-06-21 시나리오 기반 사용자 테스트(Z-goal-fitness-verification.md):
- **S1 실패(AA-1)**: Excel 셀 변경 논리는 정확했으나 저장된 .xlsx가 손상(EOCD 없음) — COM `wb.Save()` 성공 신호를 맹신하고 파일 무결성 미검증
- **S2 실패(AA-2)**: PPT `ppt_replace_text` 호출 시 `No module named pptx` — python-pptx 미설치임에도 에러 메시지에 설치 방법 없음
- **AA-3,AA-4**: PPT 편집 중 UI 피드백 없음, 의도 라벨 빈약
- **AA-5**: 자동스크롤이 사용자 스크롤 중에도 강제 이동하는 회귀 의심
- **AA-6**: 새 업무 시작 시 `+새 시작` 버튼 발견 어려움
- **AA-7**: G3 확인 팝업이 연속 스택될 때 시각적으로 동일해 혼동

---

## 파일 맵

| 파일 | 역할 | 담당 이슈 |
|------|------|-----------|
| `agent/tools/office_com.py` | Excel/PPT COM 편집 + 폴백 | AA-1, AA-2 |
| `agent/server.py` | `_intent_label` SSE 라벨 생성 | AA-3, AA-4 |
| `electron/renderer/chat.js` | SSE 처리, 스크롤, 확인 팝업 | AA-5, AA-7 |
| `electron/renderer/scroll-utils.js` | `isNearBottom()` 유틸 | AA-5 (읽기 전용) |
| `electron/renderer/style.css` | 사이드바 UX, 팝업 스타일 | AA-6, AA-7 |
| `tests/unit/test_excel_save_verification.py` | AA-1 단위 테스트 (신규) | AA-1 |
| `tests/unit/test_ppt_import_handling.py` | AA-2 단위 테스트 (신규) | AA-2 |

---

## Task 1: P0-AA-1 — Excel 저장 후 무결성 검증

**Files:**
- Modify: `agent/tools/office_com.py`
- Test: `tests/unit/test_excel_save_verification.py` (신규)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_excel_save_verification.py` 파일을 새로 생성:

```python
import zipfile
import pytest
import json
from pathlib import Path


# _verify_xlsx 함수를 직접 임포트 (아직 없으므로 테스트가 실패해야 함)
from agent.tools.office_com import _verify_xlsx


def test_verify_xlsx_raises_on_non_zip(tmp_path):
    bad = tmp_path / "corrupt.xlsx"
    bad.write_bytes(b"this is not a zip file at all")
    with pytest.raises(RuntimeError, match="손상"):
        _verify_xlsx(str(bad))


def test_verify_xlsx_raises_on_zip_missing_workbook(tmp_path):
    path = tmp_path / "empty.xlsx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("random.txt", "content")
    with pytest.raises(RuntimeError, match="workbook.xml"):
        _verify_xlsx(str(path))


def test_verify_xlsx_passes_for_valid_openpyxl_file(tmp_path):
    import openpyxl
    path = tmp_path / "valid.xlsx"
    wb = openpyxl.Workbook()
    wb.save(path)
    _verify_xlsx(str(path))  # 예외 없어야 함


def test_excel_set_cells_returns_error_on_corrupted_save(tmp_path, monkeypatch):
    """COM 저장 후 파일이 손상되면 error JSON 반환 (completed 아님)"""
    import openpyxl
    path = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "원본"
    wb.save(path)

    original_save = openpyxl.Workbook.save
    def broken_save(self, filename):
        original_save(self, filename)
        Path(filename).write_bytes(b"CORRUPTED")
    monkeypatch.setattr(openpyxl.Workbook, "save", broken_save)

    import agent.tools.office_com as mod
    monkeypatch.setattr(mod, "_HAS_PYWIN32", False)

    from agent.tools.office_com import excel_set_cells
    result = json.loads(excel_set_cells(str(path), {"A1": "변경값"}))
    assert "error" in result
    assert "손상" in result["error"] or "corrupt" in result["error"].lower()
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```
pytest tests/unit/test_excel_save_verification.py -v
```

예상: `ImportError: cannot import name '_verify_xlsx'`

- [ ] **Step 3: `_verify_xlsx` 함수 구현**

`agent/tools/office_com.py`에서 기존 헬퍼 함수들(`_abspath`, `_backup` 등) 근처에 추가:

```python
def _verify_xlsx(path: str) -> None:
    """저장된 XLSX가 유효한 ZIP임을 확인한다. 손상 시 RuntimeError."""
    import zipfile as _zf
    try:
        with _zf.ZipFile(path) as z:
            names = z.namelist()
    except _zf.BadZipFile as e:
        raise RuntimeError(
            f"저장된 파일이 손상된 ZIP입니다: {e}\n"
            f"경로: {path}\n"
            "백업 파일(.bak)에서 복구하거나 재저장을 시도하세요."
        )
    if "xl/workbook.xml" not in names:
        raise RuntimeError(
            f"저장된 파일 손상 의심 — xl/workbook.xml 누락: {path}\n"
            "백업 파일(.bak)에서 복구하거나 재저장을 시도하세요."
        )
```

- [ ] **Step 4: `excel_set_cells`의 두 저장 경로에 검증 호출 추가**

**COM 경로** (`wb.Save()` 호출 직후, `wb.Close()` → `return` 사이):
```python
            finally:
                wb.Close(SaveChanges=0)
            try:
                _verify_xlsx(path)
            except RuntimeError as ve:
                return json.dumps({"error": str(ve), "backup": backup}, ensure_ascii=False)
            return json.dumps({"path": path, "engine": "com", ...})
```

**openpyxl 폴백 경로** (`wb.save(path)` 직후):
```python
        wb.save(path)
        try:
            _verify_xlsx(path)
        except RuntimeError as ve:
            return json.dumps({"error": str(ve), "backup": backup}, ensure_ascii=False)
        return json.dumps({"path": path, "engine": "openpyxl", ...})
```

- [ ] **Step 5: 테스트 재실행 — PASS 확인**

```
pytest tests/unit/test_excel_save_verification.py -v
```

예상: 4개 테스트 모두 PASS

- [ ] **Step 6: 전체 유닛 테스트 회귀 확인**

```
pytest tests/unit/ -x -q
```

- [ ] **Step 7: 커밋**

```bash
git add agent/tools/office_com.py tests/unit/test_excel_save_verification.py
git commit -m "fix: add post-save XLSX integrity check in excel_set_cells (AA-1)"
```

---

## Task 2: P0-AA-2 — PPT 의존성 누락 시 친절한 오류 처리

`python-pptx`는 `requirements.txt`에 있으나 환경 미설치 시 bare `No module named pptx` 반환. 설치 안내를 포함한 메시지로 교체.

**Files:**
- Modify: `agent/tools/office_com.py` (`ppt_replace_text` 폴백 경로)
- Test: `tests/unit/test_ppt_import_handling.py` (신규)

- [ ] **Step 1: `ppt_replace_text` 함수 위치 확인**

```
grep -n "pptx\|ppt_replace" agent/tools/office_com.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/unit/test_ppt_import_handling.py`:

```python
import json
import sys
import pytest


def test_ppt_replace_returns_install_hint_when_pptx_missing(monkeypatch, tmp_path):
    """python-pptx 미설치 시 설치 방법을 포함한 error 반환"""
    monkeypatch.setitem(sys.modules, "pptx", None)
    monkeypatch.setitem(sys.modules, "pptx.util", None)

    import agent.tools.office_com as mod
    monkeypatch.setattr(mod, "_HAS_PYWIN32", False)

    pptx_path = tmp_path / "test.pptx"
    pptx_path.write_bytes(b"dummy")

    from agent.tools.office_com import ppt_replace_text
    result = json.loads(ppt_replace_text(str(pptx_path), "old", "new"))

    assert "error" in result
    error_msg = result["error"]
    assert "python-pptx" in error_msg, f"설치 패키지명 누락: {error_msg}"
    assert "pip install" in error_msg, f"설치 명령 누락: {error_msg}"
```

- [ ] **Step 3: 테스트 실행 — FAIL 확인**

```
pytest tests/unit/test_ppt_import_handling.py -v
```

- [ ] **Step 4: python-pptx 임포트를 친절한 오류로 교체**

`office_com.py`의 `ppt_replace_text` 함수에서 python-pptx 폴백 임포트 부분:

```python
    # COM 불가 시 python-pptx 폴백
    try:
        from pptx import Presentation
        from pptx.util import Pt
    except ImportError:
        return json.dumps({
            "error": (
                "python-pptx 미설치로 PPT 편집 불가.\n"
                "설치 방법: pip install \"python-pptx>=1.0.2\"\n"
                "(폐쇄망: USB로 .whl 반입 후 pip install --no-index --find-links=. python-pptx)"
            )
        }, ensure_ascii=False)
```

- [ ] **Step 5: 테스트 재실행 — PASS 확인**

```
pytest tests/unit/test_ppt_import_handling.py -v
```

- [ ] **Step 6: 커밋**

```bash
git add agent/tools/office_com.py tests/unit/test_ppt_import_handling.py
git commit -m "fix: return install instructions when python-pptx missing (AA-2)"
```

---

## Task 3: P1-AA-5 — 자동스크롤 회귀 감사 및 수정

**Files:**
- Modify: `electron/renderer/chat.js` (회귀 발견 시만)

- [ ] **Step 1: scrollToBottom 호출 전수 조회**

```
grep -n "scrollToBottom" electron/renderer/chat.js
```

올바른 패턴 (유지):
- `scrollToBottom(true)` — `appendUserMessage`, 끼어들기 에코에만
- `if (ScrollUtils.isNearBottom(chatMessages)) scrollToBottom()` — SSE 이벤트 핸들러

금지 패턴 (회귀):
- SSE `text`·`tool_start`·`tool_done` 이벤트 핸들러에서 게이트 없는 `scrollToBottom()` 호출

- [ ] **Step 2: 회귀 발견 시 — 게이트 추가**

```javascript
// 수정 전 (회귀)
scrollToBottom()

// 수정 후
if (ScrollUtils.isNearBottom(chatMessages)) {
  scrollToBottom()
}
```

- [ ] **Step 3: 기존 스크롤 테스트 확인**

```
pytest tests/unit/test_scroll_utils_js.py -v
```

- [ ] **Step 4: 커밋 또는 AA-5 닫기**

회귀 수정 시:
```bash
git add electron/renderer/chat.js
git commit -m "fix: restore isNearBottom gate for SSE auto-scroll (AA-5)"
```

회귀 없음 확인 시: `AA-agent-ux-gaps.md`의 AA-5 항목에 "✅ 회귀 없음 확인 (2026-06-22)" 메모 추가.

---

## Task 4: P1-AA-3, AA-4 — Office 작업 의도 라벨 개선

**Files:**
- Modify: `agent/server.py` (`_intent_label` 함수)

- [ ] **Step 1: `_intent_label` 현재 구현 확인**

```
grep -n "_intent_label\|intent_label" agent/server.py | head -30
```

- [ ] **Step 2: Office COM 도구별 라벨 케이스 추가**

기존 `_intent_label` 분기 패턴을 따라 Office 도구 케이스 추가:

```python
elif tool_name == "excel_set_cells":
    path = args.get("path", "")
    cells = args.get("cells", {})
    fname = Path(path).name if path else ""
    cell_list = ", ".join(list(cells.keys())[:3])
    suffix = f" 외 {len(cells)-3}개" if len(cells) > 3 else ""
    return f"Excel 셀 편집: {cell_list}{suffix} ← {fname}"

elif tool_name == "ppt_replace_text":
    path = args.get("path", "")
    old = str(args.get("old_text", args.get("old", "")))[:20]
    fname = Path(path).name if path else ""
    return f"PPT 텍스트 교체: '{old}…' ← {fname}"

elif tool_name in ("word_edit_text", "word_find_replace"):
    path = args.get("path", "")
    fname = Path(path).name if path else ""
    return f"Word 텍스트 편집 ← {fname}"

elif tool_name in ("word_export_pdf", "ppt_export_pdf"):
    path = args.get("path", "")
    fname = Path(path).name if path else ""
    return f"PDF 내보내기 ← {fname}"
```

- [ ] **Step 3: 수동 검증**

앱 실행 → Excel 셀 편집 요청 → 채팅창 툴 실행 라벨이 "Excel 셀 편집: B2, C3 ← 파일명.xlsx" 형태로 표시되는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add agent/server.py
git commit -m "feat: improve intent labels for Office COM tools (AA-3, AA-4)"
```

---

## Task 5: P2-AA-6 — 새 스레드 시작 버튼 UX 개선

**Files:**
- Modify: `electron/renderer/chat.js`
- Modify: `electron/renderer/style.css`

- [ ] **Step 1: 스레드 목록 렌더링 코드 확인**

```
grep -n "새 시작\|thread-new\|renderTask\|renderGroup" electron/renderer/chat.js | head -20
```

- [ ] **Step 2: 스레드가 있을 때 "+새 시작" 버튼 강조 클래스 추가**

`chat.js`에서 `+새 시작` 버튼 생성 위치를 찾아:

```javascript
const hasThreads = threads.length > 0
// 기존 버튼 클래스에 조건부 강조 추가
const newBtnClass = `thread-new-btn${hasThreads ? ' thread-new-btn--highlight' : ''}`
```

`style.css`에 추가:
```css
.thread-new-btn--highlight {
  border-color: var(--accent, #4a9eff);
  color: var(--accent, #4a9eff);
  font-weight: 600;
}
.thread-new-btn--highlight:hover {
  background: rgba(74, 158, 255, 0.12);
}
```

- [ ] **Step 3: 기존 스레드 선택 시 입력 플레이스홀더 힌트**

`chat.js`의 스레드 전환 함수에서:
```javascript
const hasMessages = (currentMessages || []).length > 0
chatInput.placeholder = hasMessages
  ? "이어서 입력… (새 업무는 ← + 새 시작)"
  : "무엇을 도와드릴까요?"
```

- [ ] **Step 4: 수동 검증**

앱 실행 → 스레드가 있는 업무 그룹에서 "+새 시작" 버튼이 강조 표시되고, 기존 스레드 선택 시 플레이스홀더 힌트 확인.

- [ ] **Step 5: 커밋**

```bash
git add electron/renderer/chat.js electron/renderer/style.css
git commit -m "feat: highlight new-thread button and add placeholder hint (AA-6)"
```

---

## Task 6: P3-AA-7 — 연속 확인 팝업 순번 배지

**Files:**
- Modify: `electron/renderer/chat.js` (`showConfirmDialog`)
- Modify: `electron/renderer/style.css`

- [ ] **Step 1: 카운터 상태 변수 추가**

`chat.js`에서 `showConfirmDialog` 함수 위에:
```javascript
let _confirmQueueCount = 0
```

- [ ] **Step 2: 팝업 헤더에 순번 배지 추가**

`showConfirmDialog` 함수 내:
```javascript
async function showConfirmDialog({ confirm_id, question, options, risk, command }) {
  _confirmQueueCount++
  const mySeq = _confirmQueueCount

  const seqBadge = _confirmQueueCount > 1
    ? `<span class="confirm-seq-badge">${mySeq}</span>`
    : ''

  const header = isDestructive ? '⛔ 위험 작업 확인' : '⚠ 에이전트 확인 요청'

  // overlay.innerHTML 의 confirm-header 라인:
  `<div class="confirm-header">${header}${seqBadge}</div>`

  // submit() 함수 안에:
  async function submit(choice, customText = '') {
    _confirmQueueCount = Math.max(0, _confirmQueueCount - 1)
    overlay.remove()
    // ... 기존 코드 유지 ...
  }
}
```

`style.css`에 추가:
```css
.confirm-seq-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--accent, #4a9eff);
  color: #fff;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  margin-left: 8px;
  vertical-align: middle;
}
```

- [ ] **Step 3: 수동 검증**

앱 실행 → G3 확인창 2개 연속 발생 시 두 번째 창 헤더에 `2` 배지 표시 확인.

- [ ] **Step 4: 커밋**

```bash
git add electron/renderer/chat.js electron/renderer/style.css
git commit -m "feat: add sequence badge to stacked confirm dialogs (AA-7)"
```

---

## 최종 검증

```
# Python 유닛 테스트 전체
pytest tests/unit/ -q

# 앱 기동 후 시나리오 재실행
.\start.ps1
```

| 시나리오 | 기대 결과 |
|---------|-----------|
| Excel 셀 수정 (xlsx 손상 시뮬레이션) | "손상" 포함 error 반환, completed 아님 |
| PPT 텍스트 교체 (python-pptx 미설치) | "pip install python-pptx" 안내 메시지 |
| 긴 응답 수신 중 스크롤 업 | 자동스크롤 정지, ↓ 버튼 표시 |
| Office 도구 실행 | 툴 라벨에 파일명·셀 주소 표시 |
| 스레드 있는 그룹 | "+새 시작" 파란 강조 표시 |
| G3 확인창 연속 2개 | 두 번째 창에 `2` 배지 |

---

## 백로그 완료 처리

모든 태스크 완료 후:
```bash
# AA-agent-ux-gaps.md 완료 처리 후 done 폴더로 이동
git mv docs/backlog/pending/AA-agent-ux-gaps.md docs/backlog/done/AA-agent-ux-gaps.md
git commit -m "docs: move AA backlog to done after user-test fix implementation"
```

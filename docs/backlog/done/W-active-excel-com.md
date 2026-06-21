# 실시간 활성 엑셀 연동 (Active COM)

> 작성: 2026-06-18
> 상태: ✅ 구현 완료
> 관련 파일: `agent/tools/office_com.py`, `agent/obsidian_session.py`, `tests/smoke/test_tool_schemas.py`, `CLAUDE.md`

## 1. 배경 및 목적
- **문제**: 기존 COM 연동 방식(`excel_set_cells`, `excel_get_range`)은 에이전트가 백그라운드에서 엑셀 워크북을 조용히 열고 편집한 뒤 바로 닫는 구조(`Visible = False`, `Close`)였습니다.
- **요구사항**: 사용자는 자신이 직접 엑셀을 화면에 띄워놓고("내가 엑셀 열어놓고도 같이 작업가능하나?"), 에이전트에게 "여기에 1+1 계산해봐"라고 지시하면 화면이 실시간으로 변하는 "호흡하는" 협업 방식을 원했습니다.
- **목표**: 사용자가 열어둔 활성 엑셀 창(Active Window)에 에이전트가 `win32com.client.GetActiveObject`를 통해 연결하여 셀 값을 직접 읽고 쓸 수 있는 전용 도구를 제공합니다.

## 2. 구현 내용

### 2.1 신규 도구 추가 (`office_com.py`)
1. **`excel_active_set_cells`**
   - **기능**: 현재 사용자가 띄워놓은 엑셀 창(ActiveWorkbook.ActiveSheet)의 특정 셀들에 값을 실시간으로 입력합니다.
   - **특징**: 파일 경로를 입력받지 않으며, 문서를 자동으로 저장하거나 닫지 않습니다. 오직 UI 상의 변경만 발생시켜 사용자가 눈으로 확인할 수 있게 합니다.
2. **`excel_active_get_range`**
   - **기능**: 활성 엑셀 창에서 지정된 범위의 값을 실시간으로 읽어옵니다.

### 2.2 시스템 프롬프트 업데이트 (`obsidian_session.py`)
- `_AUTO_EXEC` 지침에 다음 내용을 추가하여 에이전트가 상황에 맞게 도구를 선택하도록 유도했습니다.
  > "만약 사용자가 '열려있는 엑셀에 작업해줘' 또는 '실시간으로 호흡하자'라고 하면, 파일 경로 없이 바로 작동하는 excel_active_set_cells와 excel_active_get_range 툴을 사용하여 열려있는 창에 실시간으로 작업해라."

### 2.3 테스트 및 검증
- `test_tool_schemas.py`의 `EXPECTED_TOOL_COUNT`를 136종으로 업데이트하고 스모크 테스트 통과 확인.
- `test_excel_active.py` 스크립트를 작성해 실제로 파이썬이 활성화된 엑셀 창을 인식하고 값을 입력/수식 계산/결과 읽기를 완벽히 수행함을 검증했습니다.

## 3. 기대 효과
- **Shared-State Interaction**: 에이전트가 백그라운드 일꾼에 머물지 않고, 사용자와 동일한 화면(문서)을 보며 실시간으로 상호작용하는 진정한 의미의 **Pair-Programming/Co-pilot** 경험을 제공합니다.
- 복잡한 데이터가 담긴 엑셀 파일을 에이전트에게 열게 할 필요 없이, 사용자가 보고 있는 상태 그대로 특정 셀 조작만 위임할 수 있어 작업의 가시성과 안정성이 높아졌습니다.

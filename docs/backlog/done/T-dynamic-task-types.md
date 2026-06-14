# 백로그 T — 동적 업무 타입 관리(AI 대화로 추가/제거) 🧩

> 상태: ✅ 완료 · 기본 5타입 보호 + Vault 사용자 정의 타입 오버레이 + 동적 사이드바 렌더링

## 완료 내용

- `agent/obsidian_session.py`: 기본 업무 타입을 `_DEFAULT_TASK_CONFIGS`로 보존하고, Vault `agent/task_types.json` 사용자 정의 타입을 `get_task_configs()`에서 머지한다.
- `agent/tools/task_type.py`: `task_type_create`, `task_type_remove` 2종 도구를 추가했다. 두 도구는 `_risk="mutate"`로 중앙 안전 게이트를 타며, 기본 5타입 삭제는 거부한다.
- `agent/server.py`: `/task-config`와 `generate()`의 업무 타입 설정 조회가 동적 설정을 사용한다.
- `electron/renderer/index.html` + `chat.js`: 하드코딩된 5개 업무 그룹을 제거하고 `/task-config` 응답으로 사이드바 업무 그룹을 동적 렌더링한다.
- 문서/스모크: 총 툴 수 134종으로 갱신했고, 신규 backend unit/integration/smoke 테스트를 추가했다.

## 검증

- `cmd /c node --check electron\renderer\chat.js`
- `C:\Users\1600X\anaconda3\envs\mes-agent\python.exe -m pytest tests/unit/test_task_type_tools.py tests/integration/test_task_config_api.py tests/smoke/test_tool_schemas.py -q --tb=short -p no:cacheprovider`

## 후속 범위 밖

- 시스템 프롬프트 인라인 편집 UI
- 업무 타입 순서 재정렬
- 사이드바 아이콘 색상 커스터마이즈
- 업무 타입별 전용 워크플로우 템플릿 자동 생성

# 백로그 T — 동적 업무 타입 관리(AI 대화로 추가/제거) 🧩

> 상태: 🔲 미착수 · **사전확인 완료**: 스레드는 Obsidian Vault 전용 저장 · **백로그 P 이후** 권장

## 문제·가치

새 업무(타입)를 **코드 수정 없이 대화로 등록·삭제**하고 싶다. 현재 업무 타입(general/syncade/obsidian/
unscript/knox)은 **하드코딩**(`obsidian_session.py TASK_CONFIGS` + `index.html`의 그룹 div)이라 추가하려면
코드와 HTML을 함께 고쳐야 한다.

## 사전 확인 결과
- **스레드는 Obsidian Vault에만** 저장된다(`agent/threads/{task_type}/{id}.md`, REST 우선·파일 폴백). 로컬 DB 없음.
- 따라서 업무 타입 정의도 **같은 저장 계층(Vault)** 에 영속화하는 것이 일관적.

## 접근
- `TASK_CONFIGS`(하드코딩)를 **Vault 영속 설정**(`agent/task_types.md` 또는 json)으로 이전 + **내장 기본값 머지**
  (기본 5타입은 코드에, 사용자 추가분은 Vault에).
- 신규 도구 `task_type_create` / `task_type_remove`(+ `agent/tools/_safety.py` 확인 게이트 — mutate).
- `/task-config`가 **동적 소스** 반환, **사이드바를 동적 렌더링**(현 하드코딩 그룹 div 제거 → JS로 생성).
- **재사용**: Vault 저장(`obsidian_session._read/_write`), `/task-config` 엔드포인트, 메모리 관리 UI(`memory.js`) 패턴.

## 핵심 파일
- `agent/obsidian_session.py`(TASK_CONFIGS 동적화·로드/저장), `agent/tools/*`(신규 도구), `agent/server.py`,
  `electron/renderer/index.html` + `chat.js`(동적 사이드바 렌더).

## 확인 필요
1. **시스템 프롬프트도** 대화로 편집 가능하게 할지.
2. 기본 5타입 **삭제 허용** 여부(보호할지).
3. 백로그 **P(IA 개편)와 동시 진행** — 사이드바 동적 렌더링을 공유.

## 규모
M~L. **P 이후**(사이드바 동적화 공유).

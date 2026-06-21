# 백로그 N — 하네스(멀티에이전트 역할) 모드 🤖🤖

> 상태: PoC v1 + Phase 1~3(실측 계측·Reviewer 멀티모달·2번째 버티컬) 완료 ✅ · 잔여: Planner 역할 추가 여부 에픽 결정 · 참조: HarnessLab/claw-code-agent
> 거버넌스: 외부 하니스 패턴은 **클린룸**(유출 소스 금지) · 계약서(`docs/contracts/`) 먼저 → TDD (`docs/CLAW_PORT_PLAN.md`)

## 문제·가치

현재는 단일 `generate()` 루프(`agent/server.py`)가 계획·실행·검증을 혼자 수행한다. 복잡한 작업에서
역할을 분리(예: Planner / Executor / Reviewer)하면 **자기교정·품질·끈기**가 올라간다. 여러 에이전트를
생성해 각자 역할을 부여하는 "하네스" 패턴을 검증한다.

## 접근 (PoC 스파이크 우선)

- **오케스트레이터**가 역할별 서브-루프를 순차/병렬 호출. 각 역할 = 전용 system 프롬프트 +
  `select_tools` 도구 서브셋(`agent/tools/__init__.py`) + 공유 작업공간(스레드/워크플로우 RunState/Vault 메모).
- 기존 자산 재사용: `generate()` 루프 골격, `TASK_CONFIGS`(역할별 프롬프트 패턴), `select_tools`(역할별 도구 제한),
  워크플로우 `WorkflowRunState`(공유 진행 상태), 장기기억(`agent/memory.py`).
- **이벤트 스트림/상태머신은 백로그 L(OpenHands)과 통합 검토** — 중복 구현 회피.
- **PoC 범위**: 역할 2개(Executor + Reviewer)로 "실행→검증→수정" 루프의 가치만 먼저 측정. 가치 확인 시 확장.

## 거버넌스 (필수)

- claw-code-agent는 **라이선스·클린룸 적합성을 먼저 확인**한 뒤에만 패턴을 *참고*(코드 복붙 금지).
- L1 루프 강화와 동일하게 계약서(`docs/contracts/`) → TDD 순서. `docs/CLAW_PORT_PLAN.md` 거버넌스 준수.

## 핵심 파일 (예정)
- 신규: `agent/harness/*`(오케스트레이터·역할 정의), `docs/contracts/`(하네스 계약).
- 수정: `agent/server.py`(오케스트레이션 진입점), `agent/core/events.py`(역할별 이벤트).

## 확인 필요
1. claw-code-agent **라이선스·클린룸 적합성** (참고 가능 여부).
2. 역할 세트(2~4개?)와 책임 경계.
3. 병렬 vs 순차(비용·복잡도 트레이드오프).
4. 비용: 역할마다 LLM 호출 증가 → 토큰 예산(백로그 M 연계).
5. 백로그 L(OpenHands)과 **병합 범위**(이벤트 스트림/컨덴서 공유).

## 규모
XL(에픽). PoC 스파이크(Executor+Reviewer)는 가치 검증을 마쳤고 Phase 1~3까지 실 업무(syncade/unscript)에 배포됨.
정식 에픽화(Planner 역할 추가) 여부는 `docs/DEV_ROADMAP_2026-06.md` P1 #2에서 실측 데이터 확보 후 결정.

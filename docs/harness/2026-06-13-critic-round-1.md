# 2026-06-13 critic round 1

## 실행 결과

사용자가 repo 문서를 Codex CLI와 Claude Code 외부 모델에 보내는 것을 승인한 뒤 첫 critic 라운드를 수행했다.

산출물:

- Codex Implementation Critic: `C:\tmp\mes-agent-harness-reviews\20260613-231607-codex-implementation-critic.txt`
- Claude Risk/Test Critic: `C:\tmp\mes-agent-harness-reviews\20260613-233222-claude-risk-test-critic.txt`

주의:

- 최초 `run-plan-critics.ps1 -AllowExternalSend`는 Codex 결과를 생성한 뒤 Claude Read 호출에서 타임아웃됐다.
- Claude Code smoke와 짧은 critic 호출은 정상 통과했다.
- 반복 실행성을 위해 Claude critic은 파일 Read 도구 대신 승인된 repo 계약 요약을 짧은 프롬프트로 전달하는 방식으로 스크립트를 조정했다.
- 현재 기준으로 `-AllowExternalSend`는 deprecated이며 repo 파생 Claude prompt를 허용하지 않는다. 새 critic 라운드는 `-ClaudeMode None`, `-ClaudeMode Generic`, 또는 승인된 `-ClaudeMode Sanitized`로 실행한다.

## Codex Implementation Critic 요약

BLOCKER:

- 작업 카드에 `worktree`와 `branch`는 있지만 `git worktree add`, 스펙 동기화, base 확인, merge/commit 책임자가 없다.
- Codex CLI worker와 Claude worker를 동등한 agent로 병렬 운용할 때 파일 잠금, merge 순서, 충돌 처리 주체가 명시되지 않았다.

RISK:

- 외부 전송이 자주 막힐 수 있는데, 수동 critic fallback의 산출물 위치와 승인 기록 방식이 약하다.
- Codex CLI critic에 `--ignore-rules`를 쓰므로 prompt가 `AGENTS.md`, `CLAUDE.md`, L1 invariant 같은 핵심 제약을 직접 명시해야 한다.
- Task T 전체는 첫 성공 사이클로 크다. backend config, tool/API, frontend 반영으로 나누는 편이 낫다.
- Claude/Ralph/Codex CLI/PowerShell/auth/network 의존성 실패 시 계속 진행/중단 기준이 부족하다.

SUGGESTION:

- 작업 카드에 `owner.worktree_setup`, `owner.merge`, `base_branch`, `files.owned`, `files.readonly`, `spec_synced`, `conflict_policy`를 추가한다.
- 외부 전송 불가 모드를 공식 경로로 둔다.
- Codex CLI critic prompt에 `AGENTS.md` 준수, 파일 수정 금지, 근거 문서, 평가 범위를 명시한다.

## Claude Risk/Test Critic 요약

BLOCKER:

- 툴 추가/삭제 카드에서 `tests/smoke/test_tool_schemas.py::EXPECTED_TOOL_COUNT` 갱신이 DoD에 없으면 smoke/CI가 반복 실패한다.
- compaction, vision 주입, 끼어들기 등 히스토리 조작 카드에서 OpenAI tool-pair invariant가 깨지면 API 400으로 agent가 멈춘다. 착수 전 짝 보존 테스트가 필요하다.

RISK:

- `select_tools()`가 128개 제한을 맞추며 필수 도구를 무음 드롭할 수 있다. 필수 core tool 포함 검증이 필요하다.
- 폐쇄망/self-hosted runner에서는 `pip install`, `playwright install`, `npm install` 같은 런타임 다운로드가 실패한다. 워커 카드에 네트워크 호출 금지 조건이 필요하다.

SUGGESTION:

- 모든 작업 카드에 구조화된 `test_dod`를 추가한다.
- `_safety.py`의 `classify_risk`, plan mode, `auto_confirm="deny"`, `force=True` 경로를 파라미터화 테스트로 막는다.

## 통합 결정

다음 변경을 표준 계약으로 반영한다.

1. 작업 카드 템플릿에 ownership/conflict/test_dod 필드를 추가한다.
2. `run-plan-critics.ps1`의 Claude critic은 기본적으로 짧은 risk/test 계약 요약을 사용한다.
3. 외부 전송 불가 또는 Claude 타임아웃은 실패가 아니라 공식 fallback 경로로 기록한다.
4. Task T는 첫 성공 사이클에서 큰 카드 하나로 두지 않고 2~3개 카드로 쪼갠다.
5. product runtime을 건드리는 카드는 tool-pair invariant 테스트를 착수 게이트로 둔다.
6. 현재 repo 기본 브랜치는 `master`이므로 작업 카드의 `base_branch` 기본값도 `master`로 둔다.
7. 파일 소유권은 `files.owned`, `files.readonly`, `files.forbidden`을 중심으로 통일한다. `files.allowed`는 새 카드에서 쓰지 않는다.
8. Claude Code 토큰이 Codex보다 여유 있을 때는 Claude를 critic/worker 우선 실행 표면으로 쓰고, Codex CLI는 smoke 또는 보조 critic으로 제한한다.

## 후속 작업

- `docs/harness/task-card-template.md`에 필드 추가 완료
- `docs/ORCHESTRATION_GUIDE.md`에 worker 충돌 정책 추가 완료
- `docs/specs/development-harness.md`에 `test_dod`와 fallback 경로 추가 완료
- Task T 분할 카드 작성

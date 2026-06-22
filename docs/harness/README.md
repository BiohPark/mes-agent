# 개발 하네스 운영 인덱스

이 폴더는 Codex Desktop, Codex CLI, Claude Code, Ralph loop를 함께 써서 mes-agent 개발 계획의 품질을 높이는 운영 기록을 모은다.

## 현재 결론

- Codex CLI는 로컬에서 정상 실행된다.
- Windows에서는 `codex` 직접 호출보다 `cmd /c codex ...`가 안정적이다.
- Windows에서는 Claude Code도 smoke/critic 모두 `cmd /c claude.cmd ...`를 표준 호출형으로 쓴다. PowerShell-native 호출이 quoting 오류를 내면 Claude 문제가 아니라 호출 표면 문제로 분류한다.
- 이 PC에서는 PowerShell 실행 정책 때문에 `*.ps1` 직접 실행이 막힐 수 있으므로 `powershell -NoProfile -ExecutionPolicy Bypass -File ...`를 표준 실행형으로 쓴다.
- 계획 critic은 read-only로, 구현 worker는 별도 worktree에서 workspace-write로만 실행한다.
- Claude Code critic/worker는 외부 전송 등급을 나눈다. 기본 critic은 `-ClaudeMode None`이고, repo 정보 없는 일반 체크리스트만 `-ClaudeMode Generic`으로 보낸다.
- Claude Code CLI 인증은 정상이며, 이 Codex 관리 셸에서는 네트워크 제한 때문에 승인된 샌드박스 외부 실행으로 smoke/critic을 수행한다.
- Claude Code 2.1.168에서는 `--safe-mode`가 없으므로 `--permission-mode plan --tools "" --no-session-persistence` 조합을 smoke 기본형으로 쓴다.
- Claude Code 전역 설정에서 `ecc@ecc`와 `ralph-loop@claude-plugins-official`이 활성화되어 있다.
- ECC rules는 플러그인이 자동 배포하지 않으므로 이 repo의 `.claude/rules/ecc/{common,python,typescript,web}`를 project-local 표준으로 추적한다.
- ECC full/manual installer는 실행하지 않는다. plugin path에 full install을 겹치면 skills/hooks가 중복될 수 있다.
- Codex sandbox 안에서 Claude Code repo worker는 L3 repo context/code 전송으로 분류되어 자동 실행하지 않는다. Enterprise ZDR 또는 사내 승인 gateway가 없으면 우회 구현하지 않고 Claude Code 셋업/승인 경로 원인분석 작업으로 전환한다.
- Claude 긴 파일 Read critic은 타임아웃과 외부 전송 차단 위험이 있으므로 L0 smoke 또는 L1 generic critic까지만 기본 자동화한다.

Claude Code 실패 분류:

| 분류 | 대표 신호 | 다음 조치 |
|------|-----------|-----------|
| `quoting/powershell` | `terminator`, `ParserError` | `cmd /c claude ...` 표준 호출로 재실행 |
| `auth/session` | 로그인·OAuth·unauthorized | `cmd /c claude auth status --text`와 재로그인 확인 |
| `permission-mode/tools` | 옵션 오류, tools/permission 거부 | Claude Code 버전과 smoke 옵션 확인 |
| `hook/plugin` | `Hook cancelled`, plugin 경고 | 전역 plugin/hook 정리 카드로 분리 |
| `sandbox/file-permission` | `Access is denied`, EPERM, sandbox | 승인된 외부 실행 또는 권한 설정 확인 |
| `timeout/model-call` | stdout/stderr 없이 `claude -p`가 timeout | 네트워크/API/plugin 모델 호출 경로 진단 |

## 빠른 명령

Codex CLI 최소 실행 확인:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke
```

기본 critic 라운드:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1
```

Claude Code generic critic을 함께 실행:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -ClaudeMode Generic
```

Claude Code 단독 smoke 표준형:

```powershell
cmd /c claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence
```

## 문서 지도

| 문서 | 역할 |
|------|------|
| `docs/ORCHESTRATION_GUIDE.md` | 전체 운영법 |
| `docs/README.md` | 문서 구조 인덱스 |
| `docs/REFACTOR_BRIEF.md` | 아키텍처 원칙·차용 패턴·L1 불변식 |
| `docs/specs/development-harness.md` | 개발환경 하네스 스펙 |
| `docs/specs/product-agent-harness.md` | 제품 내부 런타임 하네스 스펙 |
| `docs/specs/supervisor-console.md` | 제품 내부 하네스 감독 UX |
| `docs/TRANSFORMATION_PLAN.md` | 트랙별 마스터 플랜 |
| `docs/harness/2026-06-13-plan-critic-readiness.md` | Codex CLI/Claude Code critic 준비 점검 |
| `docs/harness/2026-06-14-ecc-rules-readiness.md` | ECC plugin/rules 정합성 점검 |
| `docs/harness/2026-06-14-claude-code-smoke-diagnosis.md` | Claude Code `-p` smoke timeout 원인분석 |
| `docs/harness/2026-06-23-quality-eval-readiness.md` | GMP/SharePoint/Obsidian 품질평가 준비도 진단 |
| `docs/harness/cards/company-pc-b0-checklist.md` | 회사 PC 문서 백엔드·Office·Obsidian 실측 체크리스트 |
| `docs/harness/cards/gmp-validation-eval-procedure.md` | `gmp-validation` harness ON/OFF 반복 평가 절차 |
| `docs/harness/2026-06-13-existing-plan-review.md` | 기존 계획 수동 critic 리뷰 |
| `docs/harness/2026-06-13-critic-round-1.md` | 첫 외부 critic 라운드 통합 결과 |
| `docs/harness/phase-report.md` | 우선순위 기반 Phase 보고서 |
| `docs/harness/task-card-template.md` | worker에게 넘기기 전 작업 카드 템플릿 |
| `docs/contracts/product-harness-run-state.md` | 제품 하네스 `RunSnapshot` 초안 계약 |
| `docs/contracts/run-ledger.md` | 제품 하네스 `RunLedger` 초안 계약 |
| `docs/harness/cards/supervisor-phase1-reducer.md` | 첫 추천 작업 카드 |
| `docs/harness/cards/supervisor-hud-fit-to-view.md` | 감독 HUD/워크플로우 fit-to-view 후속 카드 |
| `docs/harness/cards/product-harness-contract-alignment.md` | 제품 하네스 계약 정렬 카드 |
| `docs/harness/cards/adaptive-timeout-v2-liveness-spike.md` | V-2 타임아웃 liveness spike 카드 |

## 다음 운영 순서

1. `-Smoke`로 Codex CLI와 Claude Code agent 경로를 확인한다.
2. `docs/harness/phase-report.md`에서 현재 Phase와 Next Actions를 확인한다.
3. 작업 카드 템플릿을 채운다.
4. `spec`이 대상 worktree에서 보이는지 확인한다.
5. Claude가 필요하면 `external_send` 등급을 확인하고 `-ClaudeMode Generic` 또는 승인된 sanitized prompt만 사용한다.
6. Claude repo 전송을 승인할 수 없으면 Codex Desktop 현재 세션에서 수동 critic을 수행하고 그 사실을 기록한다.
7. critic 결과를 통합해 worker 지시를 닫힌 형태로 만든다.
8. worker 완료 후 `code-reviewer` 또는 Codex 리뷰로 diff를 검토한다.

## GMP 품질평가 운영 순서

1. `docs/harness/cards/company-pc-b0-checklist.md`로 실제 문서 백엔드 경로를 먼저 확정한다.
2. `gmp-validation` 업무 스레드에서 같은 입력을 harness off 3회, harness on 3회 실행한다.
3. `docs/harness/cards/gmp-validation-eval-procedure.md`의 지표와 출력 위치에 맞춰 결과를 기록한다.
4. B-0 결과가 온프렘 SharePoint일 때만 후속으로 SharePoint REST roundtrip 구현을 계획한다.

# 개발 하네스 운영 인덱스

이 폴더는 Codex Desktop, Codex CLI, Claude Code, Ralph loop를 함께 써서 mes-agent 개발 계획의 품질을 높이는 운영 기록을 모은다.

## 현재 결론

- Codex CLI는 로컬에서 정상 실행된다.
- Windows에서는 `codex` 직접 호출보다 `cmd /c codex ...`가 안정적이다.
- 계획 critic은 read-only로, 구현 worker는 별도 worktree에서 workspace-write로만 실행한다.
- repo 문서 기반 critic 실행은 외부 모델 제공자에게 내용이 전송될 수 있으므로 `-AllowExternalSend` 승인 게이트를 둔다.
- Claude Code CLI 인증은 정상이며, 이 Codex 관리 셸에서는 네트워크 제한 때문에 승인된 샌드박스 외부 실행으로 smoke/critic을 수행한다.
- Codex 토큰이 낮고 Claude 토큰이 상대적으로 여유 있으면 Claude Code를 critic/worker 우선 표면으로 쓰고, Codex CLI는 smoke 또는 보조 critic으로 제한한다.
- Claude 긴 파일 Read critic은 타임아웃될 수 있으므로 짧은 Risk/Test Critic prompt 또는 worker 작업에 우선 사용한다.

## 빠른 명령

Codex CLI 최소 실행 확인:

```powershell
.\scripts\harness\run-plan-critics.ps1 -Smoke
```

외부 전송이 승인된 경우 실제 critic 라운드:

```powershell
.\scripts\harness\run-plan-critics.ps1 -AllowExternalSend
```

Claude Code 없이 Codex CLI critic만 먼저 실행:

```powershell
.\scripts\harness\run-plan-critics.ps1 -AllowExternalSend -SkipClaude
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
| `docs/harness/2026-06-13-existing-plan-review.md` | 기존 계획 수동 critic 리뷰 |
| `docs/harness/2026-06-13-critic-round-1.md` | 첫 외부 critic 라운드 통합 결과 |
| `docs/harness/phase-report.md` | 우선순위 기반 Phase 보고서 |
| `docs/harness/task-card-template.md` | worker에게 넘기기 전 작업 카드 템플릿 |
| `docs/harness/cards/supervisor-phase1-reducer.md` | 첫 추천 작업 카드 |

## 다음 운영 순서

1. `-Smoke`로 Codex CLI와 Claude Code agent 경로를 확인한다.
2. `docs/harness/phase-report.md`에서 현재 Phase와 Next Actions를 확인한다.
3. 작업 카드 템플릿을 채운다.
4. `spec`이 대상 worktree에서 보이는지 확인한다.
5. 외부 전송을 승인할 수 있으면 `-AllowExternalSend`로 critic을 돌린다.
6. 승인할 수 없으면 Codex Desktop 현재 세션에서 수동 critic을 수행하고 그 사실을 기록한다.
7. critic 결과를 통합해 worker 지시를 닫힌 형태로 만든다.
8. worker 완료 후 `code-reviewer` 또는 Codex 리뷰로 diff를 검토한다.

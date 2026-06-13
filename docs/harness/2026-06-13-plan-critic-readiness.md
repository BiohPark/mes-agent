# 2026-06-13 계획 critic 하네스 준비 점검

## 확인된 것

- Codex CLI는 로컬에서 정상 실행된다.
  - `cmd /c codex --version` → `codex-cli 0.139.0`
  - `cmd /c codex doctor` → 설치, 인증, 상태 DB, 네트워크, sandbox 진단은 실패 없음
  - read-only exec smoke:
    `cmd /c codex -a never exec -C D:\GithubRepositories\mes-agent -s read-only --ephemeral --ignore-user-config --ignore-rules "Do not edit files. Reply with exactly: CODEX_EXEC_OK"`
- PowerShell에서 `codex` 직접 호출은 `codex.ps1` 실행 정책이나 WindowsApps shim에 걸릴 수 있으므로 `cmd /c codex ...`를 표준형으로 쓴다.
- 기본 Codex config를 로드하면 플러그인, MCP, 훅 경고가 많다. critic 용도는 `--ignore-user-config --ignore-rules --ephemeral`이 더 적합하다.
- `scripts/harness/run-plan-critics.ps1`를 추가했다.
  - `-Help`는 안전하게 도움말만 출력한다.
  - `-Smoke`는 repo 파일을 읽지 않고 Codex CLI/Claude Code 최소 동작만 확인한다.
  - 승인된 샌드박스 외부 실행에서 `-Smoke` 검증 결과:
    - `[harness] Codex CLI smoke: CODEX_EXEC_OK`
    - `[harness] Claude Code smoke: CLAUDE_EXEC_OK`
  - `-AllowExternalSend`가 없으면 repo 문서 전송을 거부한다.
- Claude Code CLI 인증은 정상이다.
  - `cmd /c claude auth status --text` → Claude Pro 계정 로그인 확인
  - `--bare`는 OAuth/keychain을 읽지 않으므로 이 환경에서는 쓰지 않는다.
  - Claude Code 모델 호출은 현재 Codex 작업 셸의 네트워크 샌드박스 밖에서 실행해야 한다.

## 차단/주의

- 사용자가 repo 문서를 외부 모델 제공자에게 보내는 critic 라운드를 명시 승인했다.
- Codex CLI Implementation Critic 결과는 정상 생성됐다.
- Claude Code Risk/Test Critic은 긴 파일 Read 방식에서 타임아웃되어, 짧은 승인된 repo 계약 요약 프롬프트로 fallback 실행했다.
- `scripts/harness/run-plan-critics.ps1`는 Claude critic이 120초를 넘기면 timeout note를 결과 파일에 남기고 종료하도록 보호한다.

## 기존 계획 문서에 반영한 개선

- `docs/ORCHESTRATION_GUIDE.md`
  - 로컬 Codex CLI 엔진 섹션 추가
  - read-only critic과 workspace-write worker 실행형 분리
  - Implementation Critic / Risk-Test Critic 역할 추가
  - critic 단계를 표준 작업 흐름의 구현 전 단계로 추가
- `docs/specs/development-harness.md`
  - Codex CLI 역할 추가
  - 계획 품질 critic 단계 추가
  - Codex CLI worker는 별도 worktree에서만 `workspace-write` 사용하도록 명시
- `docs/TRANSFORMATION_PLAN.md`
  - 1.5단계로 Codex CLI critic 표면 정상화 결과 기록
  - Claude Code 실행 표면과 외부 전송 승인 게이트를 남김
- `docs/harness/2026-06-13-critic-round-1.md`
  - Codex/Claude critic 결과와 통합 결정을 기록
  - 작업 카드 ownership/conflict/test_dod 필드 추가 결정 기록

## 다음 실제 실행 절차

승인된 샌드박스 외부 실행으로 critic 라운드를 수행한다.

```powershell
.\scripts\harness\run-plan-critics.ps1 -AllowExternalSend
```

Claude Code 토큰이 더 여유 있을 때는 Claude를 우선 critic/worker로 쓰고, Codex CLI는 smoke 또는 Implementation Critic 보조로 제한한다.

Codex CLI 최소 동작만 확인하려면:

```powershell
.\scripts\harness\run-plan-critics.ps1 -Smoke
```

Claude Code 없이 먼저 Codex CLI만 검증하려면:

```powershell
.\scripts\harness\run-plan-critics.ps1 -AllowExternalSend -SkipClaude
```

결과는 `C:\tmp\mes-agent-harness-reviews`에 저장한다.

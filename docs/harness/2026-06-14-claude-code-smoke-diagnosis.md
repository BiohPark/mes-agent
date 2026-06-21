# Claude Code smoke 진단 — 2026-06-14

## 결론

Claude Code CLI 설치와 인증은 정상으로 보이나, `-p` 모델 호출 smoke가 stdout/stderr 없이 timeout된다. 따라서 현재 차단 원인은 `auth/session`이 아니라 `timeout/model-call`로 분류한다.

이 상태에서는 Claude Code가 맡기로 한 구현을 Codex가 우회 수행하지 않는다. 다음 작업은 Claude Code 실행 표면 정상화다.

## 재현 명령

정상 종료:

```powershell
cmd /c claude.cmd --version
cmd /c claude.cmd auth status --text
```

타임아웃:

```powershell
cmd /c claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence
```

## 관찰

- `claude.cmd --version` → `2.1.177 (Claude Code)` 정상 종료
- `claude.cmd auth status --text` → Claude Pro 로그인 정보 정상 출력
- `claude.cmd -p ...` → 150초 timeout, stdout/stderr 없음
- stdout/stderr 캡처 파일:
  - `.tmp/claude-smoke.out.txt` length 0
  - `.tmp/claude-smoke.err.txt` length 0
- `where claude` 결과:
  - `C:\nvm4w\nodejs\claude`
  - `C:\nvm4w\nodejs\claude.cmd`
  - `C:\Users\1600X\.local\bin\claude.exe`
- PATH 첫 항목에는 extension 없는 POSIX shim과 Windows `.cmd` shim이 함께 있으므로 Windows 표준 호출은 `claude.cmd`로 명시한다.
- 이전 smoke timeout 뒤 남은 CLI Claude 프로세스를 정리하자 `--version`은 정상 종료됐지만, `-p` timeout은 재현됐다.

## 실패 분류

| 항목 | 판정 |
|------|------|
| quoting/powershell | 최초 시도에서 발생했으나 `cmd /c claude.cmd`로 제거됨 |
| auth/session | 정상 |
| permission-mode/tools | 증거 없음 |
| hook/plugin | 가능성 있음. 전역 plugin이 많고 과거 `SessionEnd hook cancelled` 기록 있음 |
| sandbox/file-permission | 증거 없음 |
| timeout/model-call | 현재 1차 판정 |

## 다음 조치

1. Claude Code 전역 plugin을 최소 구성으로 줄인 별도 진단 세션을 만든다.
2. `vercel`, MCP/LSP 계열 plugin hook이 `-p` 종료를 막는지 순차 확인한다.
3. Claude Code daemon/session 상태를 정리한 뒤 `claude.cmd -p ...`를 재실행한다.
4. 여전히 timeout이면 네트워크/API 호출 경로를 진단한다.
5. smoke가 통과하기 전에는 Claude Code worker 대상 구현을 시작하지 않는다.

---

## 2026-06-17 후속 진단

| 실험 | 결과 |
|------|------|
| 1-A: `--ignore-user-config` | 플래그 미지원 (v2.1.178에 해당 옵션 없음) |
| 1-B: `--max-turns 1` | **정상** — `CLAUDE_EXEC_OK` 즉시 반환 |
| 1-C: Python SDK 직접 호출 | 미실행 (1-B에서 원인 특정됨) |
| 1-D: Stop hook 비활성화 후 원본 명령 | **정상** — `CLAUDE_EXEC_OK` 60초 내 반환 |

**원인 판정:** `.claude/settings.json`의 `Stop` hook이 `-p` 세션 종료 후 실행되면서 행(hang) 유발.  
구체적으로 `"git status --short 2>/dev/null | head -20 || true"` 명령이 포함된 Stop hook이  
비대화형(non-interactive) `-p` 실행에서 정상적으로 종료되지 않거나 행 상태에서 150초 timeout을 유발한 것으로 판단된다.  
전역 `settings.json` (~/.claude/settings.json)에는 Stop hook 없음 — 프로젝트 로컬 hook이 원인.

**해결 조치:** `.claude/settings.json`에서 `Stop` hook 블록을 제거 (PostToolUse는 유지).  
백업: `.claude/settings.json.bak_20260617` (git 미추적).

**최종 smoke 통과 명령:**
```powershell
& "C:\Users\qldh1\.local\bin\claude.exe" -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence
```
출력: `CLAUDE_EXEC_OK` (정상)

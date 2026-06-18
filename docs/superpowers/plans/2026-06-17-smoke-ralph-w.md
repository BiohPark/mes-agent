# Smoke 진단 + Ralph Loop 첫 실험 + W 완료 처리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code `-p` smoke timeout 원인을 고립화해 해결하고, ralph-loop 첫 실험으로 Track 1C Verifier 명시화를 자동 완성하며, W 백로그의 CLAUDE.md 상태를 갱신한다.

**Architecture:** 3개 독립 태스크를 순차 실행. Task 1(smoke 진단)이 Task 2(ralph-loop)의 전제이며, Task 3(W 상태 업데이트)은 완전 독립적이라 언제든 가능.

**Tech Stack:** PowerShell, Claude Code CLI (`claude.cmd`), Python pytest, JavaScript (supervisor-state.js), ralph-loop 플러그인

---

## 수정 파일 맵

| 파일 | Task | 변경 유형 |
|------|------|-----------|
| `~/.claude/settings.json` (전역) | 1 | 조건부 수정 — hook/plugin 고립화 후 |
| `docs/harness/2026-06-14-claude-code-smoke-diagnosis.md` | 1 | 진단 결과 추가 |
| `electron/renderer/supervisor-state.js` | 2 | verifier role 매핑 추가 |
| `tests/unit/test_supervisor_state_js.py` | 2 | contract 검증 테스트 |
| `tests/renderer/supervisor-state.test.js` | 2 | verifier role 단위 테스트 |
| `CLAUDE.md` | 3 | W 백로그 🔲→✅ 변경 |

---

## Task 1: Claude Code `-p` Smoke 진단 및 해결

**목표:** 150초 timeout을 단계별 고립화로 원인 특정 후 제거

**원칙:** 하나씩 변수를 제거해 고립화. 먼저 빠른 실험(전역 설정 제외)부터.

### 1-A: 전역 설정 제외 테스트

- [ ] **Step 1: `--ignore-user-config` 플래그로 전역 plugin/hook 우회 시도**

```powershell
# 전역 ~/.claude/settings.json 및 plugin hook을 완전히 제외
cmd /c claude.cmd --ignore-user-config -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence
```

기대: 정상 응답 → 전역 hook이 원인. 여전히 timeout → 다음 단계.

- [ ] **Step 2: 결과 파일로 저장 확인**

```powershell
# 출력을 파일에 저장하여 확인
New-Item -ItemType Directory -Force .tmp | Out-Null
cmd /c claude.cmd --ignore-user-config -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence > .tmp/smoke-1a.out.txt 2>.tmp/smoke-1a.err.txt
Get-Content .tmp/smoke-1a.out.txt
Get-Content .tmp/smoke-1a.err.txt
```

### 1-B: `--max-turns 1`로 응답 강제

- [ ] **Step 3: max-turns 1로 단일 응답 강제**

```powershell
cmd /c claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --max-turns 1 --output-format text > .tmp/smoke-1b.out.txt 2>.tmp/smoke-1b.err.txt
Get-Content .tmp/smoke-1b.out.txt
Get-Content .tmp/smoke-1b.err.txt
```

기대: 첫 응답 후 즉시 종료 → timeout 여부 확인.

### 1-C: Python SDK 직접 호출 (network/proxy 격리)

- [ ] **Step 4: Python으로 동일 엔드포인트 직접 호출 — Claude Code 레이어 우회**

```powershell
conda run -n mes-agent python -c "
import openai, os
client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY',''))
r = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[{'role':'user','content':'Reply exactly CLAUDE_EXEC_OK'}],
    max_tokens=20
)
print(r.choices[0].message.content)
"
```

기대: Python SDK 정상 → Claude Code 레이어 문제. timeout → 네트워크/프록시 문제.

### 1-D: 전역 Stop hook 임시 비활성화

- [ ] **Step 5: 전역 plugin hook 목록 확인**

```powershell
$globalSettings = "$env:USERPROFILE\.claude\settings.json"
if (Test-Path $globalSettings) {
  Get-Content $globalSettings | ConvertFrom-Json | Select-Object -ExpandProperty hooks
} else {
  Write-Host "전역 settings.json 없음"
}
```

- [ ] **Step 6: Stop hook이 있으면 임시 백업 후 비활성화**

```powershell
# 백업
Copy-Item "$env:USERPROFILE\.claude\settings.json" "$env:USERPROFILE\.claude\settings.json.bak"
# Stop hook 비활성화 후 smoke 재시도
```

```powershell
cmd /c claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence
```

```powershell
# 복원
Copy-Item "$env:USERPROFILE\.claude\settings.json.bak" "$env:USERPROFILE\.claude\settings.json"
```

### 1-E: 진단 결과 문서화 및 커밋

- [ ] **Step 7: `docs/harness/2026-06-14-claude-code-smoke-diagnosis.md` 하단에 결과 추가**

```markdown
## 2026-06-17 후속 진단

| 실험 | 명령 핵심 | 결과 |
|------|-----------|------|
| 1-A: --ignore-user-config | claude.cmd --ignore-user-config -p ... | (정상/timeout) |
| 1-B: --max-turns 1 | claude.cmd -p ... --max-turns 1 | (정상/timeout) |
| 1-C: Python SDK 직접 | openai.OpenAI().chat.completions.create | (정상/timeout) |
| 1-D: Stop hook 비활성화 | ~/.claude/settings.json Stop:[] | (정상/timeout) |

**원인 판정:** [고립화 결과 기록]
**해결 조치:** [설정 변경 내용]
**smoke 통과 명령:**
```powershell
cmd /c claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence
```
```

- [ ] **Step 8: smoke 최종 통과 확인**

```powershell
cmd /c claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence
# 기대 출력: CLAUDE_EXEC_OK 포함 짧은 응답
```

- [ ] **Step 9: 커밋**

```bash
git add docs/harness/2026-06-14-claude-code-smoke-diagnosis.md
git commit -m "docs(harness): Claude Code smoke 진단 후속 결과 기록 — 원인 [고립화 결과]"
```

---

## Task 2: Ralph Loop 첫 실험 — Track 1C Verifier 명시화

**배경:**
- `docs/contracts/product-harness-run-state.md` 계약서: `verifier` role + `verifying` phase 정의됨
- `electron/renderer/supervisor-state.js` reducer: 기존 SSE 이벤트 → phase/role 매핑 구현됨
- 목표: 계약서의 verifier 케이스가 reducer 코드 + 테스트로 완전히 커버되도록 ralph-loop 실험

**사전 확인: verifier 구현 현황 파악**

- [ ] **Step 1: verifier/verifying 키워드 현황 확인**

```powershell
Select-String -Pattern "verifier|verifying" "electron/renderer/supervisor-state.js"
Select-String -Pattern "verifier|verifying" "tests/renderer/supervisor-state.test.js"
Select-String -Pattern "verifier|verifying" "tests/unit/test_supervisor_state_js.py"
```

결과 해석:
- 없음 → ralph-loop 작업: "verifier role + verifying phase 구현 + 테스트"
- 있음 → ralph-loop 작업: "계약서 8개 phase 전이 전부 테스트로 커버"

### 2-A: ralph-loop 스킬 호출

- [ ] **Step 2: ralph-loop 스킬 실행**

`ralph-loop:ralph-loop` 스킬을 Skill 도구로 호출한다.

**verifier 미구현 경우 task 문자열:**
```
docs/contracts/product-harness-run-state.md 계약서의 verifier role과 verifying phase를
electron/renderer/supervisor-state.js 의 reduce() 함수에 추가하라.

구체적으로:
1. evidence 배열이 2개 이상이면서 tool_done 이벤트가 오면 phase=verifying, role=verifier 전이 추가
2. tests/renderer/supervisor-state.test.js 에 verifier role 전이 테스트 추가 (AAA 패턴)
3. tests/unit/test_supervisor_state_js.py 에 동일 케이스 Python fixture 테스트 추가

완료 조건: .\test.ps1 unit 이 모두 통과하고 verifier role 테스트가 포함됨.
완료 시 반드시 "DONE"을 출력하라.
```

**verifier 구현됨 경우 task 문자열:**
```
docs/contracts/product-harness-run-state.md 의 phase/role Enum 기준 표 8개 행이
tests/renderer/supervisor-state.test.js 와 tests/unit/test_supervisor_state_js.py 에서
각각 하나 이상의 테스트로 커버되는지 확인하고 누락된 케이스를 추가하라.

8개 phase: planning, executing, observing, verifying, waiting, reporting, done, error
각 phase에 대해 최소 1개 test case.

완료 조건: .\test.ps1 unit 이 모두 통과하고 8개 phase가 모두 테스트됨.
완료 시 반드시 "DONE"을 출력하라.
```

**ralph-loop 파라미터:** `--max-iterations 5 --completion-promise "DONE"`

### 2-B: 루프 진행 모니터링

- [ ] **Step 3: 반복마다 상태 확인**

```powershell
# ralph-loop 상태 파일 (반복 횟수, 완료 여부)
Get-Content .claude/ralph-loop.local.md | Select-Object -First 10
```

- [ ] **Step 4: 루프 종료 후 테스트 최종 확인**

```powershell
.\test.ps1 unit
```

기대: 전체 unit 테스트 통과 + verifier 케이스 포함.

- [ ] **Step 5: 커밋**

```bash
git add electron/renderer/supervisor-state.js \
        tests/renderer/supervisor-state.test.js \
        tests/unit/test_supervisor_state_js.py
git commit -m "feat(supervisor): Track 1C Verifier role + verifying phase 계약서 테스트 완성"
```

---

## Task 3: W 백로그 CLAUDE.md 상태 업데이트

**배경:** `.env` 그룹핑·모델 출처 표시는 `docs/TRANSFORMATION_PLAN.md` 트랙0 P3·P2부가·I1 항목이 2026-06-16 모두 ✅ 완료됨. CLAUDE.md 백로그 W 항목만 🔲 미갱신.

- [ ] **Step 1: CLAUDE.md W 항목 상태 갱신**

`CLAUDE.md`의 향후 개선 아이디어(Backlog) 섹션에서:

**변경 전 (찾을 문자열):**
```
### W. 설정 정리·모델 출처 표기 (트랙0 P3·I1) 🔲
```

**변경 후:**
```
### W. 설정 정리·모델 출처 표기 (트랙0 P3·I1) ✅
> **완료 (2026-06-16)**: `.env.example` LLM/Office/Vision 블록 분리, COMPACT_RATIO 0.7,
> 모델 드롭다운 `loadModels()`에 `source` title 표시 (`chat.js`).
> 상세: `docs/TRANSFORMATION_PLAN.md` 트랙0 P3·P2·I1 항목.
```

- [ ] **Step 2: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: W 백로그 완료 표시 — .env 그룹핑·모델 출처 표시 2026-06-16 완료"
```

---

## 검증 방법

```powershell
# Task 1: smoke 통과
cmd /c claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence

# Task 2: unit 테스트 전체
.\test.ps1 unit

# Task 3: CLAUDE.md W 상태 확인
Select-String -Pattern "### W\." CLAUDE.md
```

---

## 위험 요소

| 위험 | 가능성 | 완화 |
|------|--------|------|
| smoke가 전역 설정 외 원인 (네트워크/프록시) | 중 | Python SDK 직접 호출(1-C)로 Claude Code 레이어 고립화 |
| ralph-loop 5회 안에 DONE 못 도달 | 저 | --max-iterations 10으로 늘리거나 task 단순화 |
| verifier 추가가 기존 테스트 깨뜨림 | 저 | TDD — 테스트 먼저, 기존 suite 통과 후 커밋 |
| 전역 hook 비활성화 후 복원 잊음 | 저 | Step 6에서 비활성화·재활성화를 같은 블록에서 처리 |

# Multi-CLI 상호 위임 (A2A: codex ↔ claude ↔ agy)

이 프로젝트는 Codex CLI, Claude Code CLI, agy CLI(에이전틱 코딩 CLI) 셋을 함께 쓴다. 셋 모두
**비대화형(headless) 단발 실행 모드**를 지원하므로, 한 CLI가 다른 CLI를 서브프로세스로 호출해
작업을 위임(A2A)할 수 있다. 이 문서는 실측으로 확인한 명령/플래그만 기록한다(추측 금지).

## 검증 방법

모든 명령은 `<cli> --help` / `<cli> exec --help` 직접 실행으로 확인했다(버전 고정 아님 — CLI가
업데이트되면 재확인 필요). 검증일: 2026-06-22.

## 안전 원칙 (가드레일)

위임 호출은 **항상 최소권한 모드만 자동으로 사용**한다(`.claude/skills/delegate-cli/`,
`.codex/agents/delegate.toml` 모두 이 원칙으로 작성됨). `--dangerously-*` 류 완전우회 플래그는
**에이전트가 스스로 선택해 재시도하지 않는다** — 최소권한 모드가 승인 대기로 막히면 무엇이 막혔는지
사용자에게 보고하고, 완전우회를 이번 한 번만 써도 될지 명시적으로 물어본 뒤 승인받은 경우에만
그 작업 한정으로 사용한다. 파괴적 작업(파일 삭제, git push, 외부 API 변경 등)은 위임 체인을 통해
무인으로 실행하지 않는다 — 사람이 직접 승인한다.

### 데이터 기밀성 / 외부 전송 위험 (도구 권한 위험과 별개)

위 가드레일은 **도구 권한 위험**(위험한 플래그, 샌드박스, 승인 우회)을 다룬다. 이와 별개로
**데이터 기밀성/외부 전송 위험**이 있다 — 위임 호출에 쓰는 플래그가 전부 최소권한이어도,
**프롬프트 본문 자체**가 사외 벤더(Anthropic 등)의 호스팅 API로 네트워크를 떠난다는 사실은
바뀌지 않는다. 사내 폐쇄망 프로젝트(`CLAUDE.md` 참조)에서는 GMP/사내 워크플로우의 구체적인
내용(문서명, 시스템 명세, 회사 도메인 등)을 위임 프롬프트에 그대로 담아 보내면 이 위험이 발생한다.

**기록된 사례(2026-06-23, 미확정 정확한 메커니즘 — 아래 헤지 참고)**: 이전 Codex 세션에서
GMP 품질평가 readiness 설계 검토를 `claude --print --output-format json \
--permission-mode plan --max-budget-usd 1.0 "...GMP quality evaluation readiness..."`로 claude에 위임 시도했고,
Codex 자신이 "사내 폐쇄망/회사 워크플로우 세부사항을 Anthropic 외부 API로 전송할 위험이 있어
정책상 거부"라고 자체 보고하며 로컬 구현으로 대체했다는 보고가 있다. **이 보고는 호출 당사자(Codex)의
자체 진술이며, 본 문서 작성 시점에 이 거부가 claude CLI 자체의 구조적 차단(예: 특정 키워드 필터)인지,
Codex 쪽의 자율적 판단인지는 재현·확인되지 않았다** — 단정하지 않는다.

이 사례는 `2026-06-14-claude-code-smoke-diagnosis.md`가 다루는 **다른**, 이미 해결된 문제
(Stop hook으로 인한 `--print` 행 걸림, 2026-06-17 `.claude/settings.json`에서 Stop hook 제거로 해결)와는 무관하다.
이번 건은 행 걸림이 아니라 **내용 민감도에 대한 호출측의 자체 판단**으로 보인다.

추가로 확인한 사항: 이 저장소에는 Bedrock/Vertex 등 엔터프라이즈 라우팅 Claude Code 설정이
없다(`ANTHROPIC_BASE_URL` 등 미설정, grep 확인) — 즉 "내부적으로 승인된 별도 실행 경로"는 존재하지
않고, 위임에 쓰는 `claude` CLI는 이 세션이 쓰는 것과 동일한 퍼블릭 Anthropic API를 그대로 탄다.

**권장 실무**:
1. GMP/사내 구체 내용이 들어가는 검토 작업은, 가능하면 **이 인터랙티브 세션 안에서 직접** 수행한다
   (서브프로세스 위임으로 사내 구체 내용을 그대로 넘기지 않는다).
2. 정말 위임이 필요하면, 위임 프롬프트를 **일반화/스크러빙**해서 사내 고유 식별자(문서명, 시스템명,
   회사 도메인 등)를 제거한 뒤 보낸다.
3. 스크러빙이 어렵거나 위임의 가치가 명확하지 않으면, 위임을 강행하지 않고 **사용자에게 명시적으로
   승인을 구한다** — 이는 "막히면 사용자에게 묻는다"는 기존 도구-권한 원칙을 데이터 민감도 차단에도
   동일하게 확장한 것이다.

## ⚠️ 회귀 이력 — "고쳤는데 다시 하면 또 안 됨" (2026-06-24, 우선순위 상향)

사용자 보고(2026-06-24): claude/agy A2A 호출이 **여러 차례 고쳤음에도 다시 시도하면 또 실패**하는
패턴이 반복되고 있다 ("몇번을 개선했는데, 다시하면 또 안되고 그러네"). 이는 위 agy 섹션의
"업스트림 버그 1회 확인" 같은 **고정된 단일 원인 문제가 아니라, 환경 드리프트(CLI 자동 업데이트·
PATH 변경·세션별 인증 상태·OS 셸 차이)로 계속 재발하는 신뢰성 문제**로 취급해야 한다.

**이 문서 갱신만으로는 재발을 막지 못한다** — 매번 사람이 수동으로 재진단하는 대신, 다음을
`docs/DEV_ROADMAP_2026-06.md` P0/P1에 우선순위로 반영한다(상세는 로드맵 참조):

1. **자동 스모크 체크** — 이 저장소의 `tests/smoke/` 패턴을 따라, codex/claude/agy 각각에 대해
   "버전 확인 → 헤드리스 1줄 프롬프트 실행 → stdout 비어있지 않음 + exit 0" 를 검증하는 가벼운
   스모크 스크립트를 두고, 위임을 시도하기 **직전에** 그 CLI가 살아있는지 먼저 확인한다(매번 전체
   위임을 시도했다가 조용히 실패하는 대신, 실패를 빨리 드러내고 사람에게 보고).
   - 2026-06-25 반영: `scripts/harness/run-plan-critics.ps1 -Smoke`가 codex/claude/agy를 순서대로
     확인한다. 개별 확인은 `-SkipCodex`, `-SkipClaude`, `-SkipAgy`로 분리한다.
   - Claude는 `claude.cmd` 하드코딩을 제거하고 `Get-Command claude`로 실제 실행 파일을 찾는다.
     `cmd.exe` 문자열 호출 대신 실행 파일 + 인자 quote helper를 사용한다.
   - agy는 `--print-timeout 20s`를 쓰되, CLI 자체가 timeout을 지키지 않는 경우를 대비해 외부 30초
     hard timeout으로 `AGY_TIMEOUT`을 기록하고 프로세스를 종료한다.
2. **재발 시 진단 우선순위** — 막히면 먼저 ① `<cli> --version` 변경 여부(자동 업데이트로 플래그가
   바뀌었는지) ② PATH 상의 실제 실행 바이너리 경로 ③ 인증/세션 상태(만료) 순으로 확인하고, 이
   문서의 "최후수단" 플래그로 임의 재시도하지 않는다(가드레일 유지).
3. **agy는 여전히 비권장 유지** — 위 "업스트림 버그" 분석은 변경 없음. claude CLI 회귀는 agy와
   별개 현상이므로 혼동하지 않는다.

## codex

- 버전: 0.139.0, 위치: 현재 PC에서는 WindowsApps 패키지 경로
  (`C:\Program Files\WindowsApps\OpenAI.Codex_...\app\resources\codex.exe`)
- 비대화형 실행: `codex exec [PROMPT]` (별칭 `e`)
- 결과 캡처: `-o, --output-last-message <FILE>` (마지막 메시지만 파일로), `--json` (전체 이벤트 JSONL stdout)
- 구조화 출력: `--output-schema <FILE>` (JSON Schema로 응답 형식 강제)

### 권장(최소권한) 호출
```bash
codex exec --sandbox workspace-write --ask-for-approval never \
  -o result.txt "<위임할 작업 지시>"
```
- `-s/--sandbox {read-only|workspace-write|danger-full-access}` — 분석만 시키면 `read-only`
- `-a/--ask-for-approval {untrusted|on-request|never}` — 무인 실행이면 `never` 필수(대화형 승인 대기 시 행 걸림)

### 최후수단(완전우회)
```bash
codex exec --dangerously-bypass-approvals-and-sandbox "<작업 지시>"
```
승인·샌드박스를 전부 건너뛴다. "EXTREMELY DANGEROUS"라고 codex 자체가 경고함 — 외부에서 이미
샌드박싱된 환경에서만 사용.

### 기타
- `-C, --cd <DIR>` — 작업 루트 지정
- `--ephemeral` — 세션 파일 저장 안 함(위임용 일회성 호출에 적합)
- `--skip-git-repo-check` — git repo 밖에서도 실행 허용

## claude (Claude Code)

- 버전: 2.1.187, 위치: `C:\Users\qldh1\.local\bin\claude.exe`
- 비대화형 실행: `claude --print [options] "<prompt>"` (`-p`도 가능하나, `-p "<prompt>"` 형태가 아님)
- 출력 형식: `--output-format {text|json|stream-json}` — 위임 결과 파싱에는 `json` 권장
- 비용 상한: `--max-budget-usd <amount>` (print 모드 전용) — Claude Code의 기본 제한이 아니라
  호출자가 선택적으로 거는 1회 호출 상한이다.

### 권장(최소권한) 호출
```bash
claude --print --output-format json --permission-mode acceptEdits \
  --safe-mode --no-session-persistence \
  "<위임할 작업 지시>"
```
- Windows PowerShell에서 `--tools ""`는 variadic 옵션 파싱 때문에 뒤의 프롬프트까지 먹을 수 있으므로
  권장 예시에서 제외한다. 도구를 제한해야 하면 짧은 별도 실측 후 사용한다.
- `--max-budget-usd 0.2`나 `1.0`은 이 프로젝트 스크립트가 넘겼던 호출별 비용 상한일 뿐, Claude Code의
  일반 기본값이 아니다. 2026-06-25 기준 스모크/critic 스크립트에서는 이 제한을 제거했다. 특정 실험에서
  비용을 반드시 봉쇄해야 할 때만 명시적으로 추가한다.
- `--permission-mode {acceptEdits|auto|bypassPermissions|default|dontAsk|plan}`
  - `acceptEdits`: 파일 편집은 자동 승인, 그 외 위험 작업은 여전히 막힘(무인 실행엔 완전하지 않음)
  - `plan`: 실행 안 하고 계획만 — 위임받은 쪽이 "검토만" 해야 할 때 적합

### 최후수단(완전우회)
```bash
claude --print --dangerously-skip-permissions --max-budget-usd 1.0 "<작업 지시>"
```
모든 권한 검사를 우회한다. "Recommended only for sandboxes with no internet access"라고 명시됨.

### 기타
- `--add-dir <dir>` — 추가로 접근 허용할 디렉토리
- `--mcp-config <file>` / `--strict-mcp-config` — MCP 서버를 통한 연동(아래 "향후 보강" 참조)
- `--safe-mode` — 이 프로젝트의 모든 커스터마이징(CLAUDE.md/스킬/플러그인/훅 등)을 끄고 깨끗한 상태로 실행 — 위임받은 단발 작업이 불필요한 스킬 호출로 오염되지 않게 하려면 유용

## agy — ⚠️ 헤드리스 위임 현재 비권장 (업스트림 버그, 2026-06-22 확인)

- 버전: 1.0.10, 위치: `C:\Users\qldh1\AppData\Local\agy\bin\agy.exe`
- 비대화형 실행: `agy --print "<prompt>"` (`-p`, 별칭 `--prompt`)
- 타임아웃: `--print-timeout` (기본 5m) — 긴 위임 작업은 늘려야 함

### 정체 확인됨: Google Antigravity CLI(Gemini 3.1 Pro 백엔드)
`--log-file`로 강제 로그를 떠서 확인한 결과, `agy`는 실제로는 **Google Antigravity CLI**다
(내부 로그에 "Antigravity", "GeminiDir", `daily-cloudcode-pa.googleapis.com` 등 등장).
OAuth 인증은 정상 동작한다 — 키체인 경유로 `qldh1669@gmail.com` 계정으로 인증 성공하고
`loadCodeAssist`/`fetchAvailableModels`/`streamGenerateContent` 호출까지 실제로 일어난다.
즉 **권한/PATH/인증 문제가 아니다.**

### 실측한 두 가지 실패 모드(둘 다 `--print` 헤드리스 모드 자체의 버그로 판단)
1. **Git Bash에서 실행**: 실제 모델 응답 스트림(`streamGenerateContent`, 2회 확인)을 받고도,
   그 직후 transcript 로그를 `/Users/qldh1/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/transcript.jsonl`
   (드라이브 문자 없는 비정상 Unix식 경로)에 쓰려다 `The system cannot find the path specified`로
   반복 실패한다. 결과적으로 **stdout에 아무것도 출력하지 않고 조용히 종료**(exit 0).
2. **PowerShell에서 실행**: 같은 프롬프트가 `--print-timeout 20s`를 명시했음에도 응답 없이
   행이 걸렸다(CPU 사용량도 거의 0 — 진짜로 멈춤). 2026-06-25 스모크에서는 외부 30초 hard timeout으로
   `AGY_TIMEOUT`을 기록하고 강제 종료하도록 보강했다.
3. `agy models`도 동일하게 무출력·exit 0으로 끝남(인증/네트워크 문제가 아니라 출력 파이프라인 자체의
   문제로 보임).

### 결론 및 권고
- 코드/설정으로 우리 쪽에서 고칠 수 있는 문제가 아니다(agy 자체의 업스트림 버그로 판단).
- **헤드리스 `--print` 위임은 현재 신뢰할 수 없다** — 스모크는 실행하지만, `AGY_EXEC_OK`가 나오지
  않으면 자동 위임 대상으로 쓰지 않는다. `.claude/skills/delegate-cli/`, `.codex/agents/delegate.toml`에서
  agy는 재확인 전까지 비권장으로 취급한다.
- 사용자가 원하면 직접 `agy`를 인자 없이 대화형으로 한 번 실행해 같은 증상이 재현되는지, 또는 agy를
  업데이트(`agy update`)한 뒤 재현되는지 확인하는 게 다음 진단 단계.

### 미확인 사항 (남은 것)
- agy의 MCP 지원 여부 — `--help`에 MCP 관련 서브커맨드 없음 (plugin/plugins만 노출)
- agy가 프로젝트 지침 파일(`AGENTS.md` 등)을 읽는지 — 미확인. 읽는다면 이 문서 링크가 자동으로 agy에도 전달됨

## 결과 파싱 패턴

| CLI | 추천 캡처 방법 |
|-----|---------------|
| codex | `-o result.txt`로 마지막 메시지만 받거나 `--json`으로 전체 이벤트 스트림 파싱 |
| claude | `--output-format json` → stdout 전체가 단일 JSON, `result` 필드에 최종 텍스트 |
| agy | stdout 그대로 텍스트 — 구조화 출력 미확인, 필요하면 프롬프트에 "JSON으로만 답해" 명시 |

## 향후 보강 (이번 작업 범위 밖)

- **MCP 기반 연동**: codex는 `codex mcp-server`(자신을 stdio MCP 서버로 노출)와 `codex mcp add/list/remove`(외부 MCP 서버 등록)를 지원하고, claude도 `--mcp-config`/`claude mcp`로 MCP 서버를 붙일 수 있다. claude ↔ codex는 셸 호출 대신 MCP로 더 구조화된 연동이 가능 — agy는 MCP 미지원이라 통일성을 위해 이 문서는 셸 호출 방식을 기본으로 채택했다.
- agy의 config/확장 메커니즘이 추후 확인되면 이 문서와 `.codex/agents/delegate.toml`/`.claude/skills/delegate-cli/`를 보강한다.

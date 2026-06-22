---
name: delegate-cli
description: Claude Code가 codex 또는 agy CLI에 작업을 서브프로세스로 위임할 때 따르는 절차. 최소권한 모드만 사용, 막히면 사용자에게 묻는다.
metadata:
  type: workflow
---

## 언제 위임하는가

사용자가 명시적으로 "codex한테 시켜", "agy로 돌려봐" 같이 요청했을 때만 위임한다.
자발적으로 다른 CLI를 호출하지 않는다(이 프로젝트의 스킬/플러그인 사용 정책 — `CLAUDE.md` 참조).

## 절차

### 1. 최소권한 모드로만 시도

`docs/harness/a2a-cli-delegation.md`의 "권장(최소권한) 호출" 명령만 사용한다. 완전우회
(`--dangerously-*`) 플래그는 이 스킬이 자동으로 선택하지 않는다.

- codex: `codex exec --sandbox workspace-write --ask-for-approval never -o result.txt "<작업>"`
- agy: ⚠️ **현재 비권장** — `--print` 헤드리스 모드에 업스트림 버그 확인됨(2026-06-22, 응답을 받고도
  무출력 종료 또는 무한 행). 자세한 내용·재확인 방법은 `docs/harness/a2a-cli-delegation.md`의 agy
  섹션 참조. 사용자가 명시적으로 agy를 지정해도, 먼저 이 한계를 알리고 진행 여부를 물어본다.

### 2. 결과 캡처 및 파싱

- codex: `-o`로 지정한 파일을 읽는다(`Read` 도구). `--json`을 쓴 경우 JSONL을 한 줄씩 파싱.
- agy: stdout 텍스트를 그대로 사용. 구조화가 필요하면 프롬프트에 "JSON 한 줄로만 답하라"를 명시.

### 3. 막히면 멈추고 사용자에게 묻기 — 절대 스스로 우회하지 않음

최소권한 모드가 승인 대기로 멈추거나(타임아웃) 실패하면, **완전우회 플래그로 자동 재시도하지 않는다.**
대신 사용자에게 무엇이 막혔는지 보고하고, `--dangerously-bypass-approvals-and-sandbox`(codex)나
`--dangerously-skip-permissions`(agy)를 이번 한 번만 사용해도 될지 명시적으로 물어본다. 사용자가
승인한 경우에만 그 작업 한정으로 사용한다.

### 4. 결과 보고

위임받은 CLI의 출력을 그대로 붙여넣지 말고, 핵심 결과만 요약해서 사용자에게 보고한다. 어떤 CLI에
어떤 명령으로 위임했는지 명시한다.

## 참고

전체 플래그 레퍼런스와 검증된 사실: `docs/harness/a2a-cli-delegation.md`

# Cowork + Computer-Use 평가 세션 교훈 (다음 세션 빠른 진행용)

> 작성: 2026-06-25 Cowork(Computer Use) 세션. 목적: 이 세션에서 live synthetic GMP
> 평가가 ~20분 동안 "프롬프트 1개 전송"까지밖에 못 간 원인을 기록하고, 다음 Cowork 에이전트가
> 같은 함정에 빠지지 않도록 **사전 점검 체크리스트 + 검증된 우회법**을 남긴다.
> 평가 방법론 자체는 `harness-eval-methodology.md` / `gmp-validation-eval-procedure.md` 참조.

## TL;DR — 다음 세션은 이 순서로

1. **사용자에게 먼저 부탁**(에이전트가 못 하는 것): ① MES Agent를 사용자가 직접 실행하고
   창을 **전면(foreground)**에 둔다. ② 실행 전 **busy-mode를 OFF**로 바꾼다(헤더 토글). ③ 모델을
   빠른 것으로 바꾼다(아래 7번). ④ 필요 시 `HARNESS_ENABLED` 토글 후 **서버 재시작**(에이전트는
   터미널 입력 불가라 못 함). ⑤ (선택) 결과 파일을 읽으려면 vault 폴더 접근을 승인.
2. **권한을 한 번에 모두 요청**: `request_access`에 Electron(full) + `clipboardWrite` +
   `clipboardRead` + `systemKeyCombos`를 **한 콜에** 넣는다. 쪼개 요청하면 다이얼로그가 반복되고
   이름 불일치로 short-circuit 된다.
3. **프롬프트 입력은 클립보드로**: `write_clipboard` → 입력창 클릭 → `ctrl+a` → `ctrl+v`.
   `type` 툴을 긴 텍스트에 쓰지 말 것(아래 6번).
4. **결과 읽기**: busy-mode가 OFF면 채팅에서 바로 읽고, vault 접근이 승인됐으면 persisted
   transcript 파일을 읽는다(아래 8번).

## 이 세션에서 실제로 막힌 지점 (원인 → 우회)

1. **Bash 샌드박스가 repo에 닿지 못함.** `D:\GithubRepositories\mes-agent`는 Linux 샌드박스에
   마운트 안 됨 → `test.ps1`/`git`/서버 실행을 bash로 못 한다. 파일은 `Read/Write/Edit/Grep/Glob`로
   host 경로에서 직접 다룬다. 셸이 필요하면 **사용자가 실행**해야 한다.

2. **터미널은 tier "click" — 타이핑 금지.** PowerShell/Anaconda/터미널은 모두 "click" 등급으로
   grant된다(클릭·스크롤만, 키 입력·붙여넣기·우클릭 불가). 따라서 `start.ps1` 실행, `test.ps1`,
   서버 재시작, `.env`의 `HARNESS_ENABLED` 토글을 **Computer Use로 할 수 없다.** 전부 사용자 몫.

3. **`open_application "Electron"`은 실행 중인 창을 포커스하지 않고 새 빈 Electron 창을 띄운다.**
   grant가 `electron.exe` 바이너리(`...\node_modules\electron\dist\electron.exe`)로 잡히기 때문에,
   open 할 때마다 "To run a local app: electron.exe path-to-app"라는 **기본 환영 창**이 새로 뜬다
   (MES Agent 렌더러가 아님). 이 세션에서 환영 창을 2~3개 양산해 화면만 어지럽혔다.
   → MES Agent 창을 앞으로 가져오려면 **그 창의 보이는 타이틀바를 직접 클릭**하거나, 처음부터
   사용자가 전면에 둔 상태로 시작한다. `open_application`으로 포커스 시도 금지.

4. **작업표시줄은 Explorer 소유 → 클릭 불가.** 최소화된 MES Agent 창을 작업표시줄 버튼으로 복원하려
   해도 "Explorer is not in the allowed applications"로 막힌다. 필요하면 `파일 탐색기`를 grant 하거나
   `systemKeyCombos`를 받아 Alt+Tab. (이 세션에선 Alt+Tab도 잘 안 먹었다 — 신뢰도 낮음.)

5. **busy-mode가 실행 중 메인 창을 숨긴다(가장 큰 시간 손실).** 실행이 시작되면 메인 창이
   최소화/도킹되고 작은 "작업 감독" HUD만 남는다. 이 세션에서는 **긴 실행 동안 자동 복원이 안 됐고**
   HUD의 "자세히 보기"도 창을 되살리지 못했다. 그래서 진행 상황(과 step 6/7에서 멈춘 듯한 상태,
   혹시 사용자 질문 대기?)을 채팅에서 확인할 수 없었다. → **평가 전에 busy-mode를 OFF**로 두는 것이
   사실상 필수. (이건 제품 측 트러스트 이슈이기도 함 — 로드맵 P0 UX/감독 가시성과 연결.)

6. **`type` 툴은 긴 텍스트에서 클립보드 fast-path를 쓰는데, `clipboardWrite` 권한이 없으면
   '이전 클립보드 내용'을 붙여넣는다.** 이 세션에서 프롬프트 대신 옛 클립보드 문자열
   (`D:\GithubRepositories\mes-agent`)이 입력돼 한 번 헛돌았다. → `clipboardWrite`를 미리 grant 하고,
   확실하게 하려면 `write_clipboard` + `ctrl+v`를 직접 쓴다. 또한 채팅 입력창은 **Enter=전송**이라
   여러 줄을 `type`하면 중간에 전송될 수 있다 → 한 줄로(개행 제거) 보내거나 ⛶ 확대 에디터 사용.

7. **모델이 gpt-5.4-nano라 느림.** 7단계 워크플로우 한 번에 수 분. 창 문제와 겹쳐 처리량이 바닥.
   타임드 평가 전에 더 빠르고 충분한 모델로 바꾸고 사용자 확인.

8. **결과 파일(vault)이 connected folder 밖이라 못 읽음.** `OBSIDIAN_VAULT_PATH=D:/archive/obsidian/brain`
   는 마운트된 `mes-agent` 폴더 밖 → `Read/Glob` 불가("outside this session's connected folders").
   transcript 직독을 하려면 `request_cowork_directory`로 vault를 승인받아야 하는데, 개인 노트라
   침습적이다. **대안: busy-mode OFF로 두고 채팅 UI에서 결과를 읽는다.** 평가 시작 전에 어느 경로로
   결과를 읽을지 정해두기.

9. **host 경로 Glob 주의.** `Glob(pattern="docs/harness/**")`는 "No files found"가 난다.
   **`path` 인자 + 상대 재귀 패턴**으로 써야 함: `Glob(pattern="**/*", path="D:\\...\\폴더")`.
   (vault 마운트의 알려진 quirk와 동일 — 리터럴 다중 세그먼트 패턴은 신뢰 불가.)

## 에이전트가 못 하는 것 vs 할 수 있는 것 (역할 분담)

| 작업 | Computer Use 에이전트 | 사용자 |
|------|:--:|:--:|
| 앱/서버 기동(`start.ps1`), 서버 재시작 | ✗ (터미널 타이핑 금지) | ✓ |
| `test.ps1` smoke/ci 실행 | ✗ | ✓ |
| `.env` `HARNESS_ENABLED` 토글 | ✗ | ✓ |
| busy-mode OFF / 모델 변경(헤더 UI) | △ (창 보이면 가능) | ✓ (가장 확실) |
| 스레드 생성·프롬프트 입력·전송 | ✓ (창 전면 + 클립보드 권한 시) | ✓ |
| repo 파일 읽기/수정, 문서 기록 | ✓ (host 경로) | — |
| vault transcript 직독 | ✗ (폴더 미승인 시) | ✓ 승인 시 가능 |

## 다음 세션 사전 점검 체크리스트 (복붙용)

- [ ] 사용자가 MES Agent 실행 + 창 전면 확인
- [ ] busy-mode = OFF (실행 중 채팅 보이게)
- [ ] 모델 = 빠른/충분한 것으로 설정
- [ ] `HARNESS_ENABLED` 의도대로 설정 + 서버 재시작 완료 (baseline=off / harness=on)
- [ ] `request_access` 한 콜: Electron(full) + clipboardWrite + clipboardRead + systemKeyCombos
- [ ] 결과 읽기 경로 결정: (A) 채팅 UI(busy-off) 또는 (B) vault 폴더 승인 후 transcript 직독
- [ ] 프롬프트 입력: `write_clipboard` → 입력창 클릭 → `ctrl+a` → `ctrl+v` → 전송 버튼 클릭
- [ ] `open_application "Electron"` 금지(빈 창 양산). 포커스는 타이틀바 클릭으로.

## 이 세션 미완/정리 필요

- live 평가 미완: gmp-validation 스레드 **#006**에 프롬프트를 전송했고 HUD 기준 step 6/7까지 진행됐으나,
  창 복원 실패로 최종 보고/질문을 확인하지 못함. 다음 세션에서 #006 결과를 확인(또는 폐기)하고
  깨끗한 새 스레드로 재실행 권장.
- 실수로 만든 **빈 스레드 #005** 정리(삭제) 필요.
- `open_application`로 띄운 빈 Electron 환영 창이 남아있을 수 있음 — 닫기.
- 평가 결과(scorecard 채점·Results 행)는 위 두 harness 문서에 **다음 세션에서** 이어 기록.

## 안전 가드(변동 없음, 재확인)

- evaluator-only 파일 열람 금지: `scorecard.md`, `expected/findings_manifest.csv`,
  `tests/fixtures/gmp_validation/**/expected_findings.csv`.
- repo에 회사 GMP 원문 기록 금지. 외부 CLI에 repo/GMP 상세 전달 금지.
- 원본 문서 mutate/업로드/승인은 사용자 승인 전까지 금지. B-0 Path B 확인 전 SharePoint REST 금지.

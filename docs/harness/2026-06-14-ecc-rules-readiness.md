# 2026-06-14 ECC rules 정합성 점검

## 확인된 것

- 사용자 Claude Code 전역 설정(`C:\Users\1600X\.claude\settings.json`)에서 다음 플러그인이 활성화되어 있다.
  - `ecc@ecc`
  - `ralph-loop@claude-plugins-official`
- ECC 공식 문서 기준 Claude Code plugin은 `rules`를 자동 배포하지 않는다.
- mes-agent에는 project-local rules로 `.claude/rules/ecc/{common,python,typescript,web}`만 둔다.
- rules는 directory 단위로 유지한다. flatten하면 공통/언어별 동일 파일명이 충돌하고 `../common/*` 참조가 깨질 수 있다.

## 통합 결정

- ECC는 Claude Code 전역 plugin path를 유지한다.
- ECC full/manual installer는 실행하지 않는다. plugin path 위에 full installer를 겹치면 skills/hooks/runtime 동작이 중복될 수 있다.
- `.claude/rules/ecc`는 개인 PC 전용 설정이 아니라 repo 표준 개발 하네스 설정으로 추적한다.
- Codex CLI critic은 `--ignore-rules`를 쓰므로 ECC rules 자동 적용을 기대하지 않고, 필요한 제약은 critic prompt에 직접 명시한다.
- Ralph-loop은 P0 정리에는 쓰지 않고, Task T처럼 반복 테스트가 명확한 작업 카드부터 사용한다.

## 적용된 rule packs

- `common`
- `python`
- `typescript`
- `web`

## 검증 기준

- `git status --short --untracked-files=all`에서 `.claude/rules/ecc` 파일들이 추적 대상에 포함된다.
- `.claude/rules/ecc` 하위에는 위 4개 rule pack과 로컬 README만 둔다.
- `git diff --check`가 통과한다.
- 하네스 smoke는 승인된 샌드박스 외부 실행에서 통과해야 한다.

## 비차단 관찰

- 하네스 smoke는 `CODEX_EXEC_OK`와 `CLAUDE_EXEC_OK`까지 성공한다.
- Claude Code 종료 시 `vercel@claude-plugins-official`의 `session-end-cleanup.mjs` hook cancelled 경고가 출력될 수 있다. 확인 결과 ECC hook이 아니라 Vercel plugin의 임시파일 정리 hook이다.
- `cmd /c claude doctor`는 전역 플러그인 health check 과정에서 240초 안에 종료되지 않았다. P0 하네스 smoke의 차단 조건으로 보지 않고, 필요 시 전역 Claude plugin 정리 작업으로 분리한다.

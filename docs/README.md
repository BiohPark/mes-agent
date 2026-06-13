# MES Agent docs index

이 폴더는 제품 스펙, 운영 계획, ADR, 하네스 기록을 모은다.

## Root에 남기는 문서

다음 파일은 도구 자동 탐색 또는 빠른 온보딩 때문에 root에 남긴다.

| 문서 | 이유 |
|------|------|
| `README.md` | 사용자/개발자 첫 진입점 |
| `CLAUDE.md` | Claude Code가 자동으로 읽는 구현 상태 SSOT |
| `AGENTS.md` | 여러 AI coding assistant용 짧은 orientation |
| `CONTRIBUTING.md` | 기여와 툴 추가 절차 |
| `SETUP.md` / `USAGE.md` / `SECURITY.md` | 설치, 사용, 보안 안내 |
| `REFACTOR_BRIEF.md` | 이전 prompt 호환용 pointer. 본문은 `docs/REFACTOR_BRIEF.md` |

## 주요 문서

| 문서 | 역할 |
|------|------|
| `docs/TRANSFORMATION_PLAN.md` | 트랙별 마스터 플랜 |
| `docs/ORCHESTRATION_GUIDE.md` | Codex/Claude/Ralph 개발 오케스트레이션 |
| `docs/REFACTOR_BRIEF.md` | 아키텍처 원칙, 차용 패턴, L1 불변식 |
| `docs/specs/development-harness.md` | 개발환경 하네스 스펙 |
| `docs/specs/product-agent-harness.md` | 제품 내부 agent 하네스 스펙 |
| `docs/specs/supervisor-console.md` | 감독 콘솔 UX 스펙 |
| `docs/harness/README.md` | 하네스 운영 기록 인덱스 |
| `docs/adr/` | 아키텍처 결정 기록 |
| `docs/backlog/` | pending/done 작업 기록 |

## 현재 정리 결과

- `REFACTOR_BRIEF.md` 본문을 `docs/REFACTOR_BRIEF.md`로 이동했다.
- root의 `REFACTOR_BRIEF.md`는 호환용 pointer만 유지한다.
- 하네스 관련 기록과 작업 카드는 `docs/harness/` 아래로 모았다.
- 실행 스크립트는 코드성 자산이므로 `scripts/harness/`에 둔다.

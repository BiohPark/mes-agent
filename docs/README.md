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
| **`docs/DEV_ROADMAP_2026-06.md`** | **현재 개발 우선순위 P0~P3 — 단일 SSOT (여기부터 본다)** |
| `docs/TRANSFORMATION_PLAN.md` | 트랙별 마스터 플랜 (불변 제약·아키텍처 트랙). 우선순위는 DEV_ROADMAP 참조 |
| `docs/ORCHESTRATION_GUIDE.md` | Codex/Claude/Ralph 개발 오케스트레이션 |
| `docs/REFACTOR_BRIEF.md` | 아키텍처 원칙, 차용 패턴, L1 불변식 |
| `docs/specs/` | 제품/개발 스펙 (development-harness·product-agent-harness·supervisor-console·domain-harness-pack·task-types-dynamic·ocr-provider) |
| `docs/contracts/` | 루프·하네스·RunLedger 계약 (L2 메시지 불변식·harness-poc-v1·run-state·run-ledger) |
| `docs/adr/` | 아키텍처 결정 기록 (0001~0004) |
| `docs/harness/` | 하네스 운영 기록·작업 카드 (`README.md` 인덱스, `phase-report.md`=Phase 0~5 이력) |
| `docs/backlog/` | 미착수 사양(`pending/`) · 완료 배경 기록(`done/`) |

## 문서 위계 (중복 방지)

- **우선순위**: `DEV_ROADMAP_2026-06.md` (유일 SSOT). 다른 문서의 "다음 작업/우선순위"는 모두 여기를 가리킨다.
- **구현 상태**: 루트 `CLAUDE.md` 현재상태 표 (유일 SSOT).
- **마스터 플랜/제약**: `TRANSFORMATION_PLAN.md` (트랙·불변 제약). 우선순위는 비워 두고 DEV_ROADMAP 참조.
- **이력/감사**: `docs/harness/*.md`(날짜별 기록)·`docs/backlog/done/`·`docs/harness/cards/` 완료 카드는 역사 기록으로 보존.

## 정리 관례

- `REFACTOR_BRIEF.md` 본문은 `docs/REFACTOR_BRIEF.md`, root는 호환용 pointer.
- 하네스 기록·작업 카드는 `docs/harness/` 아래로 모은다. 실행 스크립트는 `scripts/harness/`.

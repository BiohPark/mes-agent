# MES Agent — 향후 개발 미션 우선순위 로드맵 (2026-06)

> 작성: 2026-06-19 · 기준 문서: `CLAUDE.md`(현재 상태 SSOT), `docs/TRANSFORMATION_PLAN.md`,
> `docs/backlog/`. 우선순위 기준: **업무 가치(MES 도메인) 우선**.

## 배경

지난 2주 개발은 **에이전트 하네스 인프라**(적응형 타임아웃 V2·감독 콘솔·RunLedger·
하네스 PoC·Verifier phase·동적 업무타입·Tesseract 제거·Active Excel COM)에 집중되어
거의 완성됐다. 그러나 이 인프라가 **실제 MES 업무 버티컬에 아직 연결되지 않았다** —
하네스 PoC는 기본 off, Verifier는 라벨만, 업무타입(syncade/unscript/knox)은 일반 프롬프트만
있고 검증·감사 루프를 쓰지 않는다. **인프라→업무가치 전환**이 가장 큰 미연결 지점이며,
회사 PC 검증·하드웨어 결정 같은 외부 차단요인이 없는 최상위 가치 미션이다.

> 완료 항목(Track 0 전체, T, O-A, V-1/V-2 대부분, Track 1 Stage 1/1.5, 감독 reducer·
> RunLedger·Verifier 라벨, 하네스 PoC v1, Tesseract 제거, Active Excel COM)은 미션에서 제외.

## P0 — 최우선 (업무가치 高 · 차단요인 無)

| # | 미션 | 근거 | 규모 | 상태 |
|---|------|------|------|------|
| 1 | **도메인 하네스 팩** — 업무타입별 옵트인 하네스/Verifier 연결 + 검증형 워크플로우 | 이미 만든 PoC·Verifier·RunLedger·워크플로우 템플릿을 실제 MES 버티컬에 연결. 자기검증으로 배포/검증 신뢰도↑(GxP 감사) | M | 🚧 v1 착수(syncade) |

**v1 진행(2026-06-19)**: 업무 설정에 `harness`/`verify_prompt` 추가, `_should_use_harness()`
업무타입 옵트인 라우팅, `syncade` 배포 버티컬 자기검증 활성. 후속: 추가 버티컬(MES 검증·
Office 작성)은 회사 도메인 정보 확보 후.

## P1 — 높음 (가치·견고성, 대부분 unblocked)

| # | 미션 | 근거 | 규모 |
|---|------|------|------|
| 2 | **하네스 N 에픽 결정** — PoC 가치 평가 → Planner 역할 추가 여부(계약서→TDD) | 복잡 작업 자기교정 품질. #1 실사용 데이터 확보 후 결정 | XL |
| 3 | **V-2 잔여** — baseline 적응학습(p50/p90), OS별 liveness 신뢰성 보강 | 무한 행·실패 MES 작업 감소(Windows 실검증 일부 필요) | L |
| 4 | **감독 도메인 버티컬 템플릿** — MES 검증/Office 작성/배포별 감독 콘솔 표현(#1 연계) | 감독 UX를 실제 업무에 특화 | M |

## P2 — 중간 (가치 보통 또는 보안 검토 필요)

| # | 미션 | 근거 | 규모 |
|---|------|------|------|
| 5 | **O-B LAN 바인딩 + 인증강화** — host=0.0.0.0 옵트인·Origin 허용목록·토큰 영속화 | O-A로 원격 이미 가능. 보안 민감 | M |
| 6 | **Track 2 스펙 역설계 1건** — context condenser 또는 external stop 선택 | 개발 하네스 가치 | M |
| 7 | **감독 HUD fit-to-view 마감**(진행중 카드) | 폴리시 | S |

## P3 — 차단/연기 (외부 결정 선행 필수)

| # | 미션 | 차단요인 |
|---|------|---------|
| 8 | Office 편집 백엔드(Path B/C/D) + Y Office365 로그인 | **회사 PC B-0 체크리스트 검증 선행** |
| 9 | F Electron 패키징 배포 | 현재 개발단계 — 명시적 연기 |
| 10 | K Office base64 멀티모달 | 사내 LLM 멀티모달 지원 확인 선행 |
| 11 | L OpenHands 패턴 이식 | 리서치·클린룸 거버넌스 |
| 12 | X 창 UX 고도화 / 입력 가로채기 | **보안 검토 선행** |
| 13 | Track 1 Stage 2 Ralph 루프 | **루프 호스트 하드웨어 결정 선행** |
| 14 | Track 3b Knox 챗봇 | Track 1/2 안정화 후 |

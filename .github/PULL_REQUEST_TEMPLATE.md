## 변경 요약

무엇을 바꿨나요? 왜 바꿨나요?

## 변경 유형

- [ ] 버그 수정 (기존 기능 정상화)
- [ ] 새 기능 (새 툴 추가 / 새 워크플로우 / 새 API)
- [ ] 리팩토링 (동작 변경 없음)
- [ ] 문서 업데이트
- [ ] 테스트 추가

## 새 툴 추가 체크리스트

새 `MANIFEST`가 있는 툴을 추가했다면:

- [ ] `agent/tools/<name>.py` — MANIFEST 정의 완료
- [ ] `CLAUDE.md` — 현재 상태 표 업데이트, 총 툴 수 업데이트
- [ ] `CONTRIBUTING.md` — 해당 섹션 툴 목록에 추가
- [ ] `README.md` — 기능 현황 표 업데이트
- [ ] `tests/smoke/test_tool_schemas.py` — `EXPECTED_TOOL_COUNT` 상수 업데이트

## 문서 업데이트 체크리스트

- [ ] `CLAUDE.md` 현재 상태 반영 완료
- [ ] 신규 백로그 항목이 있다면 `docs/backlog/pending/`에 추가
- [ ] 완료된 백로그 항목이 있다면 `docs/backlog/done/`으로 이동

## 테스트

- [ ] `.\test.ps1 ci` 통과 (로컬 확인)
- [ ] 새 기능에 대한 테스트 추가 (unit / integration / smoke)

## 스크린샷 / 데모 (UI 변경 시)

UI가 변경되었다면 전/후 스크린샷을 첨부해주세요.

# 백로그 U — 워크플로우 시각화 고도화 🗺️ (핵심·매우 중요)

> 상태: ✅ 완료 · 백로그 S(대화 가독성)의 **근본 해결책**

## 구현 결과 (결정사항)

- **팬/줌 라이브러리**: anvaka/panzoom 원본 UMD를 `electron/renderer/vendor/panzoom.min.js`로 벤더링(의존성 없음, 폐쇄망 USB 반입). `index.html`이 `vendor/panzoom.min.js`를 로드해 전역 `window.panzoom` 노출. 그래프 캔버스를 휠 줌·드래그 팬, ⊕⊖⊙ 줌 버튼, 재렌더 간 뷰 보존. anvaka에는 `setTransform`/`reset`이 없어 뷰 복원·리셋은 `zoomAbs(0,0,scale)`+`moveTo(x,y)` 조합으로 처리(`workflow.js`). **최초 렌더 시 `_fitToViewport`로 그래프 전체가 뷰포트에 들어오도록 축소·중앙정렬하고, ⊙ 버튼은 "전체 보기"로 동작** — 이 fit-to-view가 없으면 고정 높이(`min(70vh,640px)`) `overflow:hidden` 뷰포트에서 큰 그래프 하단이 잘리고 좁은 그래프는 좌측에 치우쳐 "구버전보다 못생겨" 보이던 회귀를 해결. _초기 구현은 자작 경량 `panzoom.js`였으나 원본 라이브러리로 교체._
- **동적 디테일(LoD)**: 줌 배율(<0.7 / 0.7–1.3 / >1.3)에 따라 `lod-low/mid/high` 클래스를 캔버스에 토글 → CSS가 노드 메타·인라인 로그·notes를 점진 노출.
- **노드 인라인 로그(S 해결)**: 프론트 전용. `chat.js`의 `tool_done`에서 `recordToolLog`가 현재 running 노드에 도구 결과 요약을 적재(노드당 최근 5개, ephemeral). 노드 카드·컴팩트 행·액션 패널에 표시.
- **미니맵**: 전체 그래프 점 오버뷰 + 현재 뷰포트 사각형, 클릭 시 이동(노드 6개 미만이면 숨김).
- **그룹/서브워크플로우**: **모델 레벨** — `WorkflowNode.group`(+ `WorkflowStep.group`) 필드 추가, 신규 `workflow_set_group` 툴. 그룹 박스(반투명) + 접기(단일 pill 치환, 경계 횡단 연결 재라우팅) + rank 내 레인 정렬. 하위 호환: `group` 키 없으면 빈 문자열.

이하는 착수 전 원본 사양이다.

---


## 문제·가치

대화창이 명령으로 길어지는 문제(백로그 S·사용자 6번)의 **근본 해결**은 우측 워크플로우 패널이다.
복잡한 워크플로우도 담고, 사용자가 **한눈에** 진행을 파악하게 만든다(사용자 7번 — "매우 중요").

## 현황 (이미 갖춘 것)
- 분기 그래프 모델: `model.py` `WorkflowConnection.from_output`(0=기본/1=true/2=false), `WorkflowRunState` 런타임 라우팅.
- `workflow.js`: BFS 2D 레이아웃(`_computeLayout`) + 컴팩트 카드 반응형 + SVG 분기 연결선(색상 구분).
- 편집 도구 8종(`tools/workflow.py`): init/add/update/remove/reorder/add·remove_connection.
- **한계**: ~20노드 이상 혼잡 · 서브워크플로우/그룹 없음 · 팬/줌 없음.

## 접근 (기존 위에 증축)
1. **팬/줌** — 노드 많아도 탐색 가능.
2. **그룹/서브워크플로우(접기)** — 큰 흐름을 묶어 접고 펼치기.
3. **상태·진행률 한눈 요약** — 상단 미니맵/진행 바(전체 N단계 중 M완료).
4. **노드 인라인 요약** — 도구·로그 요약을 노드에 표시(대화에서 옮겨온 정보의 그릇 = S 해결).
5. **큰 그래프 가독성** — 레인/정렬·간격 개선.

## 재사용
- `workflow.js`(`_computeLayout`·SVG·반응형), `model.py`(분기 모델·RunState), 편집 도구 8종.

## 핵심 파일
- `electron/renderer/workflow.js` + `style.css`, 필요 시 `agent/workflow/model.py`(그룹/서브 노드 타입).

## 확인 필요
1. **서브워크플로우를 모델에 추가** vs 시각적 그룹만(모델 불변 유지).
2. 경량 그래프 렌더 **라이브러리 도입 허용 여부**(폐쇄망 USB 번들 필요).
3. **노드 클릭 → 대화/로그 연결** 범위(S와의 연계 깊이).

## 규모
L. **S와 함께 사용자 6·7번을 근본 해결** — 우선순위 상.

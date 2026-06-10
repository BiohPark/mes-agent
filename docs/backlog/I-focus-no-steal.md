# 백로그 I — 협업 UX: 포커스 비탈취 🪟

> 상태: ✅ 구현 완료 (2026-06-10) · H(협업모드)의 선행조건
>
> **구현**: `agent/tools/browser.py`에 `_focus_steal_allowed`/`_capture_foreground`/`_restore_foreground`/
> `_preserve_focus` 추가. `browser_open`(+`bring_to_front` 파라미터)·`browser_navigate`가 작업 직전
> foreground 창을 기억했다가 작업 후 복원(win32 `AttachThreadInput`+`SetForegroundWindow`).
> `BROWSER_FOCUS_STEAL=false`(기본). 테스트 `tests/unit/test_browser_focus.py`(8). 실제 포커스 동작은 Windows 수동 검증.
>
> 아래는 원래 설계 메모(보존).

## 목표

에이전트가 브라우저/창을 조작할 때 사용자의 **현재 작업 포커스를 빼앗지 않는다**.
(메신저 상주 필요는 H의 플로팅 HUD가 해소하므로, 이 문서는 "브라우저 자동 전면화" 문제에 집중.)

## 문제

`agent/tools/browser.py _get_page()`가 `headless=False`로 새 페이지를 열면 Playwright/OS가
브라우저 창을 **자동 전면화** → 사용자가 다른 작업 중이면 포커스를 가로채 작업이 꼬인다.
명시적 `page.bring_to_front()` 호출도 동일.

## 접근

1. **`bring_to_front` 옵션**(기본 `False`): `browser.py`에서 명시적 전면화 호출을 제거/가드.
   협업모드(H)에선 강제 `False`.
2. **OS 포커스 복원**(핵심): 브라우저 launch/`goto` **직전** 현재 foreground 창 핸들을
   win32(`pywin32`, 이미 의존)로 기록(`win32gui.GetForegroundWindow`) → 작업 후 사용자 창으로
   복원(`win32gui.SetForegroundWindow`). browser.py 전용 단일 스레드 executor(`_on_pw_thread`) 안에서 수행.
   신규 헬퍼 `_restore_user_focus(prev_hwnd)`.
3. **`.env`**: `BROWSER_FOCUS_STEAL=false`(기본). `true`면 기존처럼 전면화 허용(디버깅 편의).

## 파일 · 재사용

- `agent/tools/browser.py`: `_get_page`/`browser_open`/`browser_navigate`에 포커스 기록·복원 래핑 +
  win32 헬퍼. 기존 `_on_pw_thread`(전용 스레드) 패턴 재사용.
- `.env.example`: `BROWSER_FOCUS_STEAL=false`.
- 백로그 C(`main.js` 창 최소화/반투명)와 결합 → "에이전트가 화면을 건드릴 때만 비키고, 평소엔 사용자 작업 우선".

## 테스트

포커스 동작은 CI(무디스플레이)에서 검증 불가. → 파라미터 전달·`_restore_user_focus` 호출 여부를
mock(win32 import 가드)으로 검증. 실제 회귀는 수동 실검증 의존.

## 열린 질문 · 리스크

- `SetForegroundWindow`는 Windows 제약: **전면 프로세스만** 다른 창을 전면화 가능 →
  `AttachThreadInput` 결합 또는 `ALT 키 합성` 트릭이 필요할 수 있음.
- `BROWSER_CHANNEL=msedge`는 별도 프로세스라 창 생성·복원 타이밍에 레이스 가능 → 복원 전 짧은 대기/재시도.
- 멀티모니터·가상 데스크톱 환경 동작 확인 필요.

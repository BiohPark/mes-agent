// Pure busy-mode → body-class mapping shared by the Electron renderer and Node tests.
// 실행 중 창 모드(개선 아이디어 C / 백로그 X)에서 사이드바·우측 패널 숨김을 결정한다.
//   dock-right → 'chat-only'      (사이드바 + 우측 패널 숨김, 대화창만)
//   dock-keep  → 'sidebar-hidden' (사이드바만 숨김, 우측 패널 유지)
//   그 외       → ''              (창 레이아웃 변경 없음)
(function (root, factory) {
  const api = factory()
  if (typeof module !== 'undefined' && module.exports) module.exports = api
  root.BusyMode = api
})(typeof globalThis !== 'undefined' ? globalThis : window, function () {
  // 적용 가능한 모든 body 클래스 (running이 아닐 때 전부 제거하는 데 사용)
  const ALL_BODY_CLASSES = ['chat-only', 'sidebar-hidden']

  function bodyClassForBusyMode(mode) {
    if (mode === 'dock-right') return 'chat-only'
    if (mode === 'dock-keep') return 'sidebar-hidden'
    return ''
  }

  // 메인 프로세스가 창을 우측 도킹해야 하는 모드인지
  function isDockMode(mode) {
    return mode === 'dock-right' || mode === 'dock-keep'
  }

  return { bodyClassForBusyMode, isDockMode, ALL_BODY_CLASSES }
})

const assert = require('assert')
const BusyMode = require('../../electron/renderer/busy-mode.js')

// dock-right → 사이드바 + 우측 패널 숨김 (대화창만)
assert.equal(BusyMode.bodyClassForBusyMode('dock-right'), 'chat-only')

// dock-keep → 사이드바만 숨김
assert.equal(BusyMode.bodyClassForBusyMode('dock-keep'), 'sidebar-hidden')

// 레이아웃을 바꾸지 않는 모드 → 빈 문자열
assert.equal(BusyMode.bodyClassForBusyMode('hud'), '')
assert.equal(BusyMode.bodyClassForBusyMode('minimize'), '')
assert.equal(BusyMode.bodyClassForBusyMode('translucent'), '')
assert.equal(BusyMode.bodyClassForBusyMode('off'), '')
assert.equal(BusyMode.bodyClassForBusyMode(undefined), '')

// isDockMode: 두 도킹 모드만 true
assert.equal(BusyMode.isDockMode('dock-right'), true)
assert.equal(BusyMode.isDockMode('dock-keep'), true)
assert.equal(BusyMode.isDockMode('hud'), false)
assert.equal(BusyMode.isDockMode('off'), false)
assert.equal(BusyMode.isDockMode(undefined), false)

// ALL_BODY_CLASSES: running이 아닐 때 전부 제거하는 데 사용하는 전체 목록
assert.deepEqual(BusyMode.ALL_BODY_CLASSES, ['chat-only', 'sidebar-hidden'])

// bodyClassForBusyMode가 반환하는 비어있지 않은 클래스는 모두 ALL_BODY_CLASSES에 포함돼야 함
for (const mode of ['dock-right', 'dock-keep']) {
  const cls = BusyMode.bodyClassForBusyMode(mode)
  assert.ok(BusyMode.ALL_BODY_CLASSES.includes(cls), `${cls} must be in ALL_BODY_CLASSES`)
}

console.log('busy-mode fixtures passed')

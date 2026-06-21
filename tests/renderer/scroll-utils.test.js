const assert = require('assert')
const ScrollUtils = require('../../electron/renderer/scroll-utils.js')

function makeEl({ scrollHeight, scrollTop, clientHeight }) {
  return { scrollHeight, scrollTop, clientHeight }
}

{
  // 정확히 threshold(기본 100)와 일치 → true (경계 포함)
  const el = makeEl({ scrollHeight: 1000, scrollTop: 700, clientHeight: 200 })
  // distance = 1000 - 700 - 200 = 100
  assert.equal(ScrollUtils.isNearBottom(el), true)
}

{
  // threshold + 1 → false (경계 초과)
  const el = makeEl({ scrollHeight: 1001, scrollTop: 700, clientHeight: 200 })
  // distance = 1001 - 700 - 200 = 101
  assert.equal(ScrollUtils.isNearBottom(el), false)
}

{
  // 완전히 바닥(distance = 0) → true
  const el = makeEl({ scrollHeight: 1000, scrollTop: 800, clientHeight: 200 })
  // distance = 1000 - 800 - 200 = 0
  assert.equal(ScrollUtils.isNearBottom(el), true)
}

{
  // 멀리 스크롤(distance가 threshold보다 훨씬 큼) → false
  const el = makeEl({ scrollHeight: 2000, scrollTop: 0, clientHeight: 200 })
  // distance = 2000 - 0 - 200 = 1800
  assert.equal(ScrollUtils.isNearBottom(el), false)
}

{
  // 커스텀 threshold: distance(50) <= threshold(50) → true
  const el = makeEl({ scrollHeight: 1000, scrollTop: 750, clientHeight: 200 })
  // distance = 1000 - 750 - 200 = 50
  assert.equal(ScrollUtils.isNearBottom(el, 50), true)
}

{
  // 커스텀 threshold: distance(51) > threshold(50) → false
  const el = makeEl({ scrollHeight: 1001, scrollTop: 750, clientHeight: 200 })
  // distance = 1001 - 750 - 200 = 51
  assert.equal(ScrollUtils.isNearBottom(el, 50), false)
}

{
  // el이 없으면(아직 마운트 전 등) 안전하게 true(강제 스크롤 허용)
  assert.equal(ScrollUtils.isNearBottom(null), true)
}

console.log('scroll-utils fixtures passed')

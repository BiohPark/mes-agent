/*!
 * panzoom.js — 경량 팬/줌 모듈 (의존성 없음, 벤더링)
 *
 * 워크플로우 그래프 캔버스(절대배치 div + SVG)를 휠 줌·드래그 팬한다.
 * API는 anvaka/panzoom(https://github.com/anvaka/panzoom)의 사용 부분집합과
 * 호환된다. 폐쇄망 배포 시 이 파일을 anvaka/panzoom의 dist UMD로 교체해도
 * workflow.js 변경 없이 동작한다.
 *
 * 노출 API (window.panzoom):
 *   const pz = panzoom(el, {
 *     minZoom, maxZoom, bounds,        // bounds=true면 과도한 팬 제한
 *     beforeMouseDown(e) -> bool,      // true면 해당 마우스다운은 팬 시작 안 함
 *   })
 *   pz.on('transform', (pz) => { ... })  // 변환 변경 시
 *   pz.getTransform() -> { x, y, scale }
 *   pz.smoothZoom(clientX, clientY, factor)
 *   pz.moveTo(x, y)
 *   pz.zoomAbs(clientX, clientY, scale)
 *   pz.dispose()
 */
(function (global) {
  'use strict'

  function panzoom(el, options) {
    options = options || {}
    var minZoom = options.minZoom || 0.25
    var maxZoom = options.maxZoom || 3
    var useBounds = options.bounds !== false
    var beforeMouseDown = options.beforeMouseDown || null
    var zoomSpeed = options.zoomSpeed || 0.065

    var transform = { x: 0, y: 0, scale: 1 }
    var listeners = { transform: [] }
    var parent = el.parentElement

    var dragging = false
    var lastX = 0
    var lastY = 0

    el.style.transformOrigin = '0 0'

    function clampScale(s) {
      return Math.max(minZoom, Math.min(maxZoom, s))
    }

    function applyBounds() {
      if (!useBounds || !parent) return
      var pw = parent.clientWidth
      var ph = parent.clientHeight
      var cw = el.offsetWidth * transform.scale
      var ch = el.offsetHeight * transform.scale
      // 콘텐츠가 뷰포트보다 크면 가장자리를 넘지 않게, 작으면 자유롭게(약간의 여백 허용)
      var marginX = pw * 0.5
      var marginY = ph * 0.5
      var minX = Math.min(0, pw - cw) - marginX
      var maxX = marginX
      var minY = Math.min(0, ph - ch) - marginY
      var maxY = marginY
      transform.x = Math.max(minX, Math.min(maxX, transform.x))
      transform.y = Math.max(minY, Math.min(maxY, transform.y))
    }

    function render() {
      applyBounds()
      el.style.transform =
        'translate(' + transform.x + 'px,' + transform.y + 'px) scale(' + transform.scale + ')'
      emit()
    }

    function emit() {
      listeners.transform.forEach(function (cb) {
        try { cb(api) } catch (e) { /* noop */ }
      })
    }

    // 화면 좌표(clientX/Y)를 중심으로 절대 스케일 적용
    function zoomAbs(clientX, clientY, newScale) {
      newScale = clampScale(newScale)
      var rect = parent ? parent.getBoundingClientRect() : el.getBoundingClientRect()
      var px = clientX - rect.left
      var py = clientY - rect.top
      // 줌 중심 고정: content point under cursor stays put
      var cx = (px - transform.x) / transform.scale
      var cy = (py - transform.y) / transform.scale
      transform.scale = newScale
      transform.x = px - cx * newScale
      transform.y = py - cy * newScale
      render()
    }

    function smoothZoom(clientX, clientY, factor) {
      zoomAbs(clientX, clientY, transform.scale * factor)
    }

    function onWheel(e) {
      e.preventDefault()
      var delta = e.deltaY < 0 ? 1 : -1
      var factor = 1 + delta * zoomSpeed * (e.deltaMode === 1 ? 3 : 1)
      smoothZoom(e.clientX, e.clientY, factor)
    }

    function onMouseDown(e) {
      if (e.button !== 0) return
      if (beforeMouseDown && beforeMouseDown(e)) return
      dragging = true
      lastX = e.clientX
      lastY = e.clientY
      el.classList.add('pz-grabbing')
      e.preventDefault()
    }

    function onMouseMove(e) {
      if (!dragging) return
      transform.x += e.clientX - lastX
      transform.y += e.clientY - lastY
      lastX = e.clientX
      lastY = e.clientY
      render()
    }

    function onMouseUp() {
      if (!dragging) return
      dragging = false
      el.classList.remove('pz-grabbing')
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)

    var api = {
      getTransform: function () { return { x: transform.x, y: transform.y, scale: transform.scale } },
      zoomAbs: zoomAbs,
      smoothZoom: smoothZoom,
      moveTo: function (x, y) { transform.x = x; transform.y = y; render() },
      setTransform: function (x, y, s) { transform.x = x; transform.y = y; transform.scale = clampScale(s); render() },
      reset: function () { transform.x = 0; transform.y = 0; transform.scale = 1; render() },
      on: function (name, cb) {
        if (listeners[name]) listeners[name].push(cb)
        return api
      },
      dispose: function () {
        el.removeEventListener('wheel', onWheel)
        el.removeEventListener('mousedown', onMouseDown)
        window.removeEventListener('mousemove', onMouseMove)
        window.removeEventListener('mouseup', onMouseUp)
        listeners.transform = []
      },
    }

    return api
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = panzoom
  } else {
    global.panzoom = panzoom
  }
})(typeof window !== 'undefined' ? window : this)

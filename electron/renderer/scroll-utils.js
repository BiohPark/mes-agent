// Pure scroll-position helper shared by the Electron renderer and Node tests.
(function (root, factory) {
  const api = factory()
  if (typeof module !== 'undefined' && module.exports) module.exports = api
  root.ScrollUtils = api
})(typeof globalThis !== 'undefined' ? globalThis : window, function () {
  function isNearBottom(el, threshold = 100) {
    if (!el) return true
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight
    return distance <= threshold
  }
  return { isNearBottom }
})

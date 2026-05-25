const toastContainer = document.getElementById('toast-container')
const TOAST_DURATION = 5000  // ms, OCR처럼 긴 결과는 더 오래

function showToast(tool, text, isError = false) {
  const duration = text.length > 200 ? 9000 : TOAST_DURATION

  const toast = document.createElement('div')
  toast.className = `toast${isError ? ' error' : ''}`
  toast.innerHTML = `
    <div class="toast-header">
      <span class="toast-tool">${tool}</span>
      <button class="toast-close">✕</button>
    </div>
    <pre class="toast-body">${escapeHtml(text)}</pre>
    <div class="toast-progress" style="animation-duration:${duration}ms"></div>
  `

  const close = () => {
    toast.classList.add('hiding')
    toast.addEventListener('animationend', () => toast.remove(), { once: true })
  }

  toast.querySelector('.toast-close').addEventListener('click', close)
  toastContainer.appendChild(toast)
  setTimeout(close, duration)
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

document.querySelectorAll('.tool-test-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const tool = btn.dataset.tool
    const args = JSON.parse(btn.dataset.args || '{}')
    const originalText = btn.textContent.trim()

    btn.disabled = true
    btn.textContent = '실행 중...'

    try {
      const res = await fetch(`${BASE_URL}/tool/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool, arguments: args })
      })
      const data = await res.json()
      showToast(tool, data.ok ? data.result : data.error, !data.ok)
    } catch (e) {
      showToast(tool, `연결 오류: ${e.message}`, true)
    } finally {
      btn.disabled = false
      btn.textContent = originalText
    }
  })
})

// 협업 HUD 로직 (백로그 H) — 메인 렌더러가 두뇌, HUD는 표시+사용자 동작 중계
const hintEl = document.getElementById('hud-hint')
const manualBtn = document.getElementById('hud-manual')
const closeBtn = document.getElementById('hud-close')

window.hudAPI.onUpdate(({ hint, state }) => {
  if (state === 'thinking') {
    hintEl.classList.add('idle')
    hintEl.textContent = '화면 확인 중…'
    return
  }
  if (hint) {
    hintEl.classList.remove('idle')
    hintEl.textContent = hint
  } else if (state === 'idle') {
    hintEl.classList.add('idle')
    hintEl.textContent = '관찰 중…'
  }
})

manualBtn.addEventListener('click', () => window.hudAPI.emit({ type: 'manual' }))
closeBtn.addEventListener('click', () => window.hudAPI.emit({ type: 'stop' }))

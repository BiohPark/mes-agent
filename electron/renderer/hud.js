// 협업 HUD 로직 (백로그 H) — 메인 렌더러가 두뇌, HUD는 표시+사용자 동작 중계
const hintEl = document.getElementById('hud-hint')
const titleEl = document.getElementById('hud-title')
const manualBtn = document.getElementById('hud-manual')
const closeBtn = document.getElementById('hud-close')
let hudMode = 'collab'

window.hudAPI.onUpdate(({ hint, state, mode, title, actionLabel }) => {
  if (mode) hudMode = mode
  if (title) titleEl.textContent = title
  manualBtn.textContent = actionLabel || (hudMode === 'agent' ? '자세히 보기' : '👁 지금 봐줘')
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

manualBtn.addEventListener('click', () => window.hudAPI.emit({ type: 'manual', mode: hudMode }))
closeBtn.addEventListener('click', () => window.hudAPI.emit({ type: 'stop', mode: hudMode }))

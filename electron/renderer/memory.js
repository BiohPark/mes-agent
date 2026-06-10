// 장기기억 관리 모달 — 무엇을 기억 중인지 보기/추가/삭제 (장기기억 후속)
// BASE_URL, escapeHtml 은 chat.js(먼저 로드)의 전역을 재사용한다.

(function () {
  const overlay = document.getElementById('memory-overlay')
  const openBtn = document.getElementById('memory-btn')
  const closeBtn = document.getElementById('memory-modal-close')
  const listEl = document.getElementById('memory-list')
  const addInput = document.getElementById('memory-add-input')
  const addCategory = document.getElementById('memory-add-category')
  const addBtn = document.getElementById('memory-add-btn')

  const CATEGORY_LABEL = { fact: '사실', preference: '선호', decision: '결정' }

  async function loadMemories() {
    listEl.innerHTML = '<div class="memory-empty">불러오는 중…</div>'
    try {
      const res = await fetch(`${BASE_URL}/memory`)
      const data = await res.json()
      renderList(data.memories || [])
    } catch (e) {
      listEl.innerHTML = `<div class="memory-empty">불러오기 실패: ${escapeHtml(String(e))}</div>`
    }
  }

  function renderList(memories) {
    if (!memories.length) {
      listEl.innerHTML = '<div class="memory-empty">아직 기억된 내용이 없습니다.</div>'
      return
    }
    listEl.innerHTML = memories.map(m => `
      <div class="memory-row" data-id="${escapeHtml(m.id)}">
        <span class="memory-cat memory-cat-${escapeHtml(m.category)}">${escapeHtml(CATEGORY_LABEL[m.category] || m.category)}</span>
        <span class="memory-text">${escapeHtml(m.text)}</span>
        <span class="memory-date">${escapeHtml(m.created || '')}</span>
        <button class="memory-del" title="삭제">✕</button>
      </div>
    `).join('')
    listEl.querySelectorAll('.memory-del').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.closest('.memory-row')?.dataset.id
        if (!id) return
        await fetch(`${BASE_URL}/memory/${encodeURIComponent(id)}`, { method: 'DELETE' })
        loadMemories()
      })
    })
  }

  async function addMemory() {
    const text = addInput.value.trim()
    if (!text) return
    await fetch(`${BASE_URL}/memory`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, category: addCategory.value }),
    })
    addInput.value = ''
    loadMemories()
  }

  function open() {
    overlay.classList.remove('hidden')
    loadMemories()
  }
  function close() {
    overlay.classList.add('hidden')
  }

  openBtn?.addEventListener('click', open)
  closeBtn?.addEventListener('click', close)
  overlay?.addEventListener('click', (e) => { if (e.target === overlay) close() })
  addBtn?.addEventListener('click', addMemory)
  addInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') addMemory() })
})()

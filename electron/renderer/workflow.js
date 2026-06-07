// ── 우측 워크플로우 패널 ──────────────────────────────────────

const rightPanel = document.getElementById('right-panel')
const rightResizeHandle = document.getElementById('right-resize-handle')
const rightPanelToggle = document.getElementById('right-panel-toggle')
const rpTabs = document.querySelectorAll('.rp-tab')
const workflowPanel = document.getElementById('workflow-panel')
const logPanel = document.getElementById('log-panel')
const workflowEmpty = document.getElementById('workflow-empty')
const workflowContent = document.getElementById('workflow-content')
const workflowTitleEl = document.getElementById('workflow-title')
const workflowStepsEl = document.getElementById('workflow-steps')
const workflowEditBtn = document.getElementById('workflow-edit-btn')
const workflowClearBtn = document.getElementById('workflow-clear-btn')
const workflowSaveBtn = document.getElementById('workflow-save-btn')
const workflowCancelBtn = document.getElementById('workflow-cancel-btn')
const logEntries = document.getElementById('log-entries')

let _currentWorkflow = null
let _panelCollapsed = false
let _panelWidth = 300
let _editMode = false
let _editDraft = null
let _dragIdx = null

// ── 탭 전환 ─────────────────────────────────────────────────

rpTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    if (tab.id === 'right-panel-toggle') return
    rpTabs.forEach(t => t.classList.remove('active'))
    tab.classList.add('active')
    const target = tab.dataset.tab
    workflowPanel.classList.toggle('active', target === 'workflow')
    logPanel.classList.toggle('active', target === 'log')
  })
})

// ── 패널 접기/펼치기 ─────────────────────────────────────────

rightPanelToggle.addEventListener('click', () => {
  _panelCollapsed = !_panelCollapsed
  if (_panelCollapsed) {
    rightPanel.style.width = '0'
    rightResizeHandle.style.display = 'none'
    rightPanelToggle.textContent = '‹'
    rightPanelToggle.title = '패널 열기'
  } else {
    rightPanel.style.width = _panelWidth + 'px'
    rightResizeHandle.style.display = ''
    rightPanelToggle.textContent = '›'
    rightPanelToggle.title = '패널 닫기'
  }
})

// ── 리사이즈 핸들 ────────────────────────────────────────────

let _resizing = false
let _resizeStartX = 0
let _resizeStartWidth = 0

rightResizeHandle.addEventListener('mousedown', (e) => {
  _resizing = true
  _resizeStartX = e.clientX
  _resizeStartWidth = rightPanel.offsetWidth
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
})

document.addEventListener('mousemove', (e) => {
  if (!_resizing) return
  const delta = _resizeStartX - e.clientX
  const newWidth = Math.max(200, Math.min(600, _resizeStartWidth + delta))
  rightPanel.style.width = newWidth + 'px'
  _panelWidth = newWidth
})

document.addEventListener('mouseup', () => {
  if (_resizing) {
    _resizing = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
})

// ── 워크플로우 렌더링 ────────────────────────────────────────

const STATUS_META = {
  pending:  { icon: '○', cls: 'pending',  label: '대기' },
  running:  { icon: '⏳', cls: 'running',  label: '실행 중' },
  waiting:  { icon: '⏸', cls: 'waiting',  label: '확인 대기' },
  done:     { icon: '✓', cls: 'done',     label: '완료' },
  error:    { icon: '✗', cls: 'error',    label: '오류' },
  skipped:  { icon: '–', cls: 'skipped',  label: '건너뜀' },
}

const TYPE_META = {
  auto:      { icon: '🤖', label: '자동' },
  semi_auto: { icon: '👁️', label: '반자동' },
  manual:    { icon: '✋', label: '수동' },
}

function renderWorkflow(wf) {
  _currentWorkflow = wf
  workflowEmpty.classList.add('hidden')
  workflowContent.classList.remove('hidden')

  workflowTitleEl.textContent = wf.title

  workflowStepsEl.innerHTML = ''
  wf.steps.forEach((step, idx) => {
    const sm = STATUS_META[step.status] || STATUS_META.pending
    const tm = TYPE_META[step.type] || TYPE_META.auto
    const card = document.createElement('div')
    card.className = `wf-step ${sm.cls}`
    card.dataset.stepId = step.id
    const retryBtn = step.status === 'error'
      ? `<button class="wf-retry-btn" title="이 단계부터 재시도">↺ 재시도</button>`
      : ''
    card.innerHTML = `
      <div class="wf-step-header">
        <span class="wf-step-num">${idx + 1}</span>
        <span class="wf-step-icon">${sm.icon}</span>
        <span class="wf-step-title">${escapeWf(step.title)}</span>
        <span class="wf-step-type" title="${tm.label}">${tm.icon}</span>
        <span class="wf-step-caret">▸</span>
      </div>
      <div class="wf-step-detail">
        <div class="wf-step-detail-row"><span class="wf-detail-key">상태</span><span class="wf-detail-val">${sm.icon} ${sm.label}</span></div>
        <div class="wf-step-detail-row"><span class="wf-detail-key">유형</span><span class="wf-detail-val">${tm.icon} ${tm.label}</span></div>
        <div class="wf-step-detail-row"><span class="wf-detail-key">메모</span><span class="wf-detail-val">${step.notes ? escapeWf(step.notes) : '—'}</span></div>
        ${retryBtn}
      </div>
    `
    card.querySelector('.wf-step-header').addEventListener('click', () => {
      card.classList.toggle('expanded')
    })
    if (step.status === 'error') {
      card.querySelector('.wf-retry-btn').addEventListener('click', e => {
        e.stopPropagation()
        document.dispatchEvent(new CustomEvent('wf:retry-step', {
          detail: { stepId: step.id, stepTitle: step.title },
        }))
      })
    }
    workflowStepsEl.appendChild(card)
  })
}

function clearWorkflow() {
  _currentWorkflow = null
  workflowContent.classList.add('hidden')
  workflowEmpty.classList.remove('hidden')
  workflowStepsEl.innerHTML = ''
}

function escapeWf(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function escapeAttr(str) {
  return escapeWf(str).replace(/"/g, '&quot;')
}

// ── 편집모드 ─────────────────────────────────────────────────

function renderEditMode() {
  workflowEmpty.classList.add('hidden')
  workflowContent.classList.remove('hidden')

  workflowTitleEl.innerHTML =
    `<input id="wf-title-input" class="wf-title-input" value="${escapeAttr(_editDraft.title)}" />`
  workflowTitleEl.querySelector('#wf-title-input')
    .addEventListener('input', e => { _editDraft.title = e.target.value })

  workflowStepsEl.innerHTML = ''
  _editDraft.steps.forEach((step, idx) => {
    const row = document.createElement('div')
    row.className = 'wf-step-edit'
    row.draggable = true
    row.dataset.idx = idx
    row.innerHTML = `
      <span class="wf-drag-handle" title="드래그하여 순서 변경">⠿</span>
      <span class="wf-step-num">${idx + 1}</span>
      <input class="wf-edit-title" value="${escapeAttr(step.title)}" placeholder="단계 설명" />
      <select class="wf-edit-type" title="단계 유형">
        <option value="auto" ${step.type === 'auto' ? 'selected' : ''}>🤖 자동</option>
        <option value="semi_auto" ${step.type === 'semi_auto' ? 'selected' : ''}>👁️ 반자동</option>
        <option value="manual" ${step.type === 'manual' ? 'selected' : ''}>✋ 수동</option>
      </select>
      <button class="wf-edit-del" title="단계 삭제">✕</button>
    `
    row.querySelector('.wf-edit-title')
      .addEventListener('input', e => { _editDraft.steps[idx].title = e.target.value })
    row.querySelector('.wf-edit-type')
      .addEventListener('change', e => { _editDraft.steps[idx].type = e.target.value })
    row.querySelector('.wf-edit-del')
      .addEventListener('click', () => { _editDraft.steps.splice(idx, 1); renderEditMode() })

    row.addEventListener('dragstart', () => { _dragIdx = idx; row.classList.add('dragging') })
    row.addEventListener('dragend', () => row.classList.remove('dragging'))
    row.addEventListener('dragover', e => e.preventDefault())
    row.addEventListener('drop', e => {
      e.preventDefault()
      if (_dragIdx === null || _dragIdx === idx) return
      const [moved] = _editDraft.steps.splice(_dragIdx, 1)
      _editDraft.steps.splice(idx, 0, moved)
      _dragIdx = null
      renderEditMode()
    })
    workflowStepsEl.appendChild(row)
  })

  const addBtn = document.createElement('button')
  addBtn.className = 'wf-add-step-btn'
  addBtn.textContent = '+ 단계 추가'
  addBtn.addEventListener('click', () => {
    _editDraft.steps.push({ id: '', title: '새 단계', type: 'auto', status: 'pending', notes: '' })
    renderEditMode()
  })
  workflowStepsEl.appendChild(addBtn)
}

function _enterEdit() {
  if (!_currentWorkflow) return
  _editMode = true
  _editDraft = JSON.parse(JSON.stringify(_currentWorkflow))
  workflowEditBtn.classList.add('hidden')
  workflowClearBtn.classList.add('hidden')
  workflowSaveBtn.classList.remove('hidden')
  workflowCancelBtn.classList.remove('hidden')
  renderEditMode()
}

function _leaveEdit() {
  _editMode = false
  _editDraft = null
  _dragIdx = null
  workflowSaveBtn.classList.add('hidden')
  workflowCancelBtn.classList.add('hidden')
  workflowEditBtn.classList.remove('hidden')
  workflowClearBtn.classList.remove('hidden')
}

async function _saveEdit() {
  if (!_editDraft || !_currentWorkflow) return
  const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
  const { task_type, thread_id } = _currentWorkflow
  try {
    const res = await fetch(`${base}/threads/${task_type}/${thread_id}/workflow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: _editDraft.title, steps: _editDraft.steps }),
    })
    const saved = await res.json()
    _leaveEdit()
    if (saved && saved.steps) renderWorkflow(saved)
  } catch (e) {
    console.error('워크플로우 저장 실패', e)
  }
}

function _cancelEdit() {
  const wf = _currentWorkflow
  _leaveEdit()
  if (wf) renderWorkflow(wf)
}

// ── 워크플로우 로드 (스레드 선택 시) ──────────────────────────

async function loadWorkflowForThread(taskType, threadId) {
  if (_editMode) _leaveEdit()
  if (!taskType || !threadId) { clearWorkflow(); return }
  try {
    const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
    const res = await fetch(`${base}/threads/${taskType}/${threadId}/workflow`)
    if (!res.ok) { clearWorkflow(); return }
    const wf = await res.json()
    if (wf && wf.steps) renderWorkflow(wf)
    else clearWorkflow()
  } catch {
    clearWorkflow()
  }
}

// SSE로부터 워크플로우 업데이트 수신 (chat.js에서 호출)
function handleWorkflowUpdate(wf) {
  if (_editMode) { _currentWorkflow = wf; return }  // 편집 중에는 화면 갱신 보류
  renderWorkflow(wf)
}

// ── 실행 로그 ────────────────────────────────────────────────

function appendLog(tool, result, durationMs) {
  const entry = document.createElement('div')
  entry.className = 'log-entry'
  const now = new Date()
  const time = now.toTimeString().slice(0, 8)
  const status = result.startsWith('툴 실행 오류') ? 'error' : 'ok'
  const dur = durationMs != null ? `${durationMs}ms` : ''
  entry.innerHTML = `
    <div class="log-entry-header">
      <span class="log-time">${time}</span>
      <span class="log-tool ${status}">${escapeWf(tool)}</span>
      <span class="log-dur">${dur}</span>
    </div>
    <div class="log-result">${escapeWf(result.slice(0, 300))}</div>
  `
  logEntries.prepend(entry)

  // 최대 50개 유지
  while (logEntries.children.length > 50) {
    logEntries.removeChild(logEntries.lastChild)
  }
}

function clearLog() {
  logEntries.innerHTML = ''
}

// ── 버튼 ─────────────────────────────────────────────────────

workflowEditBtn.addEventListener('click', _enterEdit)
workflowSaveBtn.addEventListener('click', _saveEdit)
workflowCancelBtn.addEventListener('click', _cancelEdit)

workflowClearBtn.addEventListener('click', async () => {
  if (!_currentWorkflow) return
  if (!confirm('이 스레드의 워크플로우를 삭제할까요?\n(다시 열면 기본 템플릿으로 초기화됩니다)')) return
  const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
  const { task_type, thread_id } = _currentWorkflow
  try {
    await fetch(`${base}/threads/${task_type}/${thread_id}/workflow`, { method: 'DELETE' })
    loadWorkflowForThread(task_type, thread_id)  // 서버가 기본 템플릿 재생성
  } catch (e) {
    console.error('워크플로우 삭제 실패', e)
  }
})

// 공개 API (chat.js에서 사용)
window.workflowPanel = {
  load: loadWorkflowForThread,
  handleUpdate: handleWorkflowUpdate,
  appendLog,
  clearLog,
}

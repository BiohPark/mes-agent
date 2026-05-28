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
const logEntries = document.getElementById('log-entries')

let _currentWorkflow = null
let _panelCollapsed = false
let _panelWidth = 300

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
    card.innerHTML = `
      <div class="wf-step-header">
        <span class="wf-step-num">${idx + 1}</span>
        <span class="wf-step-icon">${sm.icon}</span>
        <span class="wf-step-title">${escapeWf(step.title)}</span>
        <span class="wf-step-type" title="${tm.label}">${tm.icon}</span>
      </div>
      ${step.notes ? `<div class="wf-step-notes">${escapeWf(step.notes)}</div>` : ''}
    `
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

// ── 워크플로우 로드 (스레드 선택 시) ──────────────────────────

async function loadWorkflowForThread(taskType, threadId) {
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

workflowClearBtn.addEventListener('click', () => {
  if (_currentWorkflow && confirm('워크플로우를 삭제하겠습니까?')) {
    clearWorkflow()
  }
})

workflowEditBtn.addEventListener('click', () => {
  if (!_currentWorkflow) return
  const newTitle = prompt('워크플로우 제목 변경:', _currentWorkflow.title)
  if (newTitle && newTitle !== _currentWorkflow.title) {
    _currentWorkflow.title = newTitle
    renderWorkflow(_currentWorkflow)
    _saveWorkflow()
  }
})

async function _saveWorkflow() {
  if (!_currentWorkflow) return
  try {
    const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
    const { task_type, thread_id } = _currentWorkflow
    await fetch(`${base}/threads/${task_type}/${thread_id}/workflow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_currentWorkflow),
    })
  } catch (e) {
    console.error('워크플로우 저장 실패', e)
  }
}

// 공개 API (chat.js에서 사용)
window.workflowPanel = {
  load: loadWorkflowForThread,
  handleUpdate: handleWorkflowUpdate,
  appendLog,
  clearLog,
}

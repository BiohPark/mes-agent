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
let _watcherES = null   // 파일 변경 감지 EventSource

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

  // 연결선 SVG 렌더링 (단순 직렬이면 생략, 분기가 있을 때만 표시)
  _renderConnectionsSVG(wf)
}

// ── SVG 연결선 렌더링 ─────────────────────────────────────────

function _renderConnectionsSVG(wf) {
  // 기존 SVG 제거
  const old = workflowStepsEl.querySelector('.wf-connections-svg')
  if (old) old.remove()

  const conns = wf.connections || []
  const steps = wf.steps || []

  // 단순 직렬(1→2→3…)이면 SVG 생략 — 시각적으로 순서가 명확하므로
  const isLinear = _isLinearConnections(steps, conns)
  if (isLinear || conns.length === 0) return

  // 비동기적으로 DOM이 레이아웃된 뒤 좌표 계산
  requestAnimationFrame(() => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.classList.add('wf-connections-svg')
    // defs for arrowhead
    svg.innerHTML = `<defs>
      <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
        <polygon points="0 0, 8 3, 0 6" class="wf-conn-arrow"/>
      </marker>
      <marker id="arrowhead-true" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
        <polygon points="0 0, 8 3, 0 6" class="wf-conn-arrow branch-true"/>
      </marker>
      <marker id="arrowhead-false" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
        <polygon points="0 0, 8 3, 0 6" class="wf-conn-arrow branch-false"/>
      </marker>
    </defs>`

    const containerRect = workflowStepsEl.getBoundingClientRect()
    const cardMap = {}
    steps.forEach(s => {
      const el = workflowStepsEl.querySelector(`[data-step-id="${s.id}"]`)
      if (el) cardMap[s.id] = el.getBoundingClientRect()
    })

    conns.forEach(conn => {
      const fromRect = cardMap[conn.from_node]
      const toRect = cardMap[conn.to_node]
      if (!fromRect || !toRect) return

      const x1 = fromRect.left - containerRect.left + fromRect.width / 2
      const y1 = fromRect.bottom - containerRect.top
      const x2 = toRect.left - containerRect.left + toRect.width / 2
      const y2 = toRect.top - containerRect.top

      const isBranchTrue = conn.from_output === 1
      const isBranchFalse = conn.from_output === 2
      const cls = isBranchTrue ? 'wf-conn-line branch-true'
        : isBranchFalse ? 'wf-conn-line branch-false'
        : 'wf-conn-line'
      const markerId = isBranchTrue ? 'arrowhead-true'
        : isBranchFalse ? 'arrowhead-false'
        : 'arrowhead'

      // 베지에 곡선
      const cy = (y1 + y2) / 2
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
      path.setAttribute('d', `M${x1},${y1} C${x1},${cy} ${x2},${cy} ${x2},${y2}`)
      path.setAttribute('class', cls)
      path.setAttribute('marker-end', `url(#${markerId})`)
      svg.appendChild(path)
    })

    workflowStepsEl.appendChild(svg)
  })
}

function _isLinearConnections(steps, conns) {
  if (conns.length !== steps.length - 1) return false
  for (let i = 0; i < steps.length - 1; i++) {
    const c = conns[i]
    if (!c || c.from_node !== steps[i].id || c.to_node !== steps[i + 1].id) return false
  }
  return true
}

function clearWorkflow() {
  _stopFileWatcher()
  _currentWorkflow = null
  workflowContent.classList.add('hidden')
  workflowEmpty.classList.remove('hidden')
  workflowStepsEl.innerHTML = ''
}

// ── 파일 변경 감지 (SSE) ──────────────────────────────────────

function _startFileWatcher(taskType, threadId) {
  _stopFileWatcher()
  if (!taskType || !threadId) return
  const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
  _watcherES = new EventSource(`${base}/threads/${taskType}/${threadId}/workflow/events`)
  _watcherES.onmessage = e => {
    try {
      const evt = JSON.parse(e.data)
      if (evt.type === 'workflow_update' && evt.workflow) {
        if (_editMode) {
          _currentWorkflow = evt.workflow  // 편집 중에는 캐시만 갱신
        } else {
          renderWorkflow(evt.workflow)
        }
      }
    } catch {}
  }
  _watcherES.onerror = () => {
    if (_watcherES && _watcherES.readyState === EventSource.CLOSED) {
      _watcherES = null
    }
  }
}

function _stopFileWatcher() {
  if (_watcherES) {
    _watcherES.close()
    _watcherES = null
  }
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

  // ── 연결 편집 섹션 ─────────────────────────────────────────
  const connSection = document.createElement('div')
  connSection.className = 'wf-connections-section'
  connSection.innerHTML = `<div class="wf-connections-title">연결 (분기)</div>`

  const conns = _editDraft.connections || []
  const stepsById = Object.fromEntries(_editDraft.steps.filter(s => s.id).map(s => [s.id, s]))

  conns.forEach((conn, ci) => {
    const fromTitle = stepsById[conn.from_node]?.title || conn.from_node
    const toTitle = stepsById[conn.to_node]?.title || conn.to_node
    const label = conn.from_output === 1 ? ' ✔' : conn.from_output === 2 ? ' ✘' : ''
    const item = document.createElement('div')
    item.className = 'wf-conn-item'
    item.innerHTML = `
      <span class="wf-conn-item-label">${escapeWf(fromTitle)}${label} → ${escapeWf(toTitle)}</span>
      <button class="wf-conn-del-btn" title="연결 삭제">✕</button>
    `
    item.querySelector('.wf-conn-del-btn').addEventListener('click', () => {
      _editDraft.connections.splice(ci, 1)
      renderEditMode()
    })
    connSection.appendChild(item)
  })

  // 연결 추가 폼
  const validSteps = _editDraft.steps.filter(s => s.id || s.title)
  const stepOptions = validSteps.map((s, i) =>
    `<option value="${escapeAttr(s.id || '')}">${escapeWf(s.title || `단계 ${i + 1}`)}</option>`
  ).join('')

  const addConnForm = document.createElement('div')
  addConnForm.className = 'wf-add-conn-form'
  addConnForm.innerHTML = `
    <select class="wf-conn-select" id="wf-conn-from" title="출발 단계">${stepOptions}</select>
    <select class="wf-conn-select" id="wf-conn-output" title="출력 포트">
      <option value="0">→ 기본</option>
      <option value="1">✔ true</option>
      <option value="2">✘ false</option>
    </select>
    <select class="wf-conn-select" id="wf-conn-to" title="도착 단계">${stepOptions}</select>
    <button class="wf-add-conn-btn" id="wf-add-conn-btn">+ 연결</button>
  `
  connSection.appendChild(addConnForm)

  addConnForm.querySelector('#wf-add-conn-btn').addEventListener('click', () => {
    const fromNode = addConnForm.querySelector('#wf-conn-from').value
    const toNode = addConnForm.querySelector('#wf-conn-to').value
    const fromOutput = parseInt(addConnForm.querySelector('#wf-conn-output').value, 10)
    if (!fromNode || !toNode || fromNode === toNode) return
    const already = (_editDraft.connections || []).some(
      c => c.from_node === fromNode && c.to_node === toNode && c.from_output === fromOutput
    )
    if (already) return
    if (!_editDraft.connections) _editDraft.connections = []
    _editDraft.connections.push({ from_node: fromNode, to_node: toNode, from_output: fromOutput })
    renderEditMode()
  })

  workflowStepsEl.appendChild(connSection)
}

function _enterEdit() {
  if (!_currentWorkflow) return
  _editMode = true
  _editDraft = JSON.parse(JSON.stringify(_currentWorkflow))
  if (!_editDraft.connections) _editDraft.connections = []
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
      body: JSON.stringify({ title: _editDraft.title, steps: _editDraft.steps, connections: _editDraft.connections || [] }),
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
  _stopFileWatcher()
  if (!taskType || !threadId) { clearWorkflow(); return }
  try {
    const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
    const res = await fetch(`${base}/threads/${taskType}/${threadId}/workflow`)
    if (!res.ok) { clearWorkflow(); return }
    const wf = await res.json()
    if (wf && wf.steps) {
      renderWorkflow(wf)
      _startFileWatcher(taskType, threadId)
    } else {
      clearWorkflow()
    }
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

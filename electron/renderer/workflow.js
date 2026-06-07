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

// ── 그래프 레이아웃 상수 ────────────────────────────────────────
const GRAPH = { NODE_W: 200, NODE_H: 68, H_GAP: 36, V_GAP: 64, PAD: 16 }

function _computeLayout(steps, connections) {
  const { NODE_W, NODE_H, H_GAP, V_GAP, PAD } = GRAPH
  const out = {}, inc = {}
  for (const s of steps) { out[s.id] = []; inc[s.id] = [] }
  for (const c of connections) {
    if (out[c.from_node] !== undefined) out[c.from_node].push(c)
    if (inc[c.to_node]  !== undefined) inc[c.to_node].push(c.from_node)
  }
  // BFS rank
  const rank = {}
  const roots = steps.filter(s => !inc[s.id].length).map(s => s.id)
  const q = [...roots]; q.forEach(id => (rank[id] = 0))
  let qi = 0
  while (qi < q.length) {
    const curr = q[qi++]
    for (const conn of out[curr]) {
      const nr = (rank[curr] ?? 0) + 1
      if (rank[conn.to_node] === undefined || rank[conn.to_node] < nr) {
        rank[conn.to_node] = nr; q.push(conn.to_node)
      }
    }
  }
  for (const s of steps) if (rank[s.id] === undefined) rank[s.id] = 0

  const maxRank = Math.max(0, ...Object.values(rank))
  const byRank = {}
  for (let r = 0; r <= maxRank; r++) byRank[r] = []
  for (const s of steps) byRank[rank[s.id]].push(s.id)

  const maxRow = Math.max(1, ...Object.values(byRank).map(ids => ids.length))
  const canvasW = Math.max(NODE_W + PAD * 2, maxRow * NODE_W + (maxRow - 1) * H_GAP + PAD * 2)

  const positions = {}
  for (const [r, ids] of Object.entries(byRank)) {
    const totalW = ids.length * NODE_W + (ids.length - 1) * H_GAP
    const sx = (canvasW - totalW) / 2
    ids.forEach((id, i) => {
      positions[id] = { x: sx + i * (NODE_W + H_GAP), y: +r * (NODE_H + V_GAP) + PAD }
    })
  }
  const canvasH = (maxRank + 1) * (NODE_H + V_GAP) - V_GAP + PAD * 2
  return { positions, canvasW, canvasH }
}

function renderWorkflow(wf) {
  _currentWorkflow = wf
  workflowEmpty.classList.add('hidden')
  workflowContent.classList.remove('hidden')

  const steps = wf.steps || []
  const connections = wf.connections || []

  // 진행 배지
  const doneCount = steps.filter(s => s.status === 'done' || s.status === 'skipped').length
  const pct = steps.length ? Math.round(doneCount / steps.length * 100) : 0
  workflowTitleEl.innerHTML =
    `<span class="wf-title-text">${escapeWf(wf.title)}</span>` +
    `<span class="wf-progress-badge">${doneCount}/${steps.length}</span>`

  // 진행 바
  let progressWrap = workflowContent.querySelector('[data-wf-progress]')
  if (!progressWrap) {
    progressWrap = document.createElement('div')
    progressWrap.setAttribute('data-wf-progress', '1')
    progressWrap.className = 'wf-progress-wrap'
    progressWrap.innerHTML = `<div class="wf-progress-bar"><div class="wf-progress-fill"></div></div>`
    workflowStepsEl.parentNode.insertBefore(progressWrap, workflowStepsEl)
  }
  progressWrap.querySelector('.wf-progress-fill').style.width = pct + '%'

  workflowStepsEl.innerHTML = ''
  if (!steps.length) return

  const { positions, canvasW, canvasH } = _computeLayout(steps, connections)
  const { NODE_W, NODE_H } = GRAPH

  // 캔버스 컨테이너
  const canvas = document.createElement('div')
  canvas.className = 'wf-graph-canvas'
  canvas.style.cssText = `width:${canvasW}px;height:${canvasH}px;position:relative;`

  // ── SVG 연결선 ──────────────────────────────────────────────
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('width', canvasW); svg.setAttribute('height', canvasH)
  svg.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;overflow:visible;'

  const MK = (id, color, op = 1) =>
    `<marker id="${id}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">` +
    `<polygon points="0 0,8 3,0 6" fill="${color}" opacity="${op}"/></marker>`
  svg.innerHTML = `<defs>
    ${MK('mk-d',    '#6b7280', 0.5)}${MK('mk-da', '#3b82f6')}
    ${MK('mk-t',    '#22c55e', 0.4)}${MK('mk-ta', '#22c55e')}
    ${MK('mk-f',    '#ef4444', 0.4)}${MK('mk-fa', '#ef4444')}
  </defs>`

  const statusOf = id => (steps.find(s => s.id === id) || {}).status || 'pending'

  for (const conn of connections) {
    const fp = positions[conn.from_node], tp = positions[conn.to_node]
    if (!fp || !tp) continue
    const fromSt = statusOf(conn.from_node), toSt = statusOf(conn.to_node)
    const active = fromSt === 'done' && (toSt === 'running' || toSt === 'done' || toSt === 'skipped')
    const flowing = fromSt === 'done' && toSt === 'running'

    // 출발점: 분기면 좌/우 오프셋
    let x1 = fp.x + NODE_W / 2
    if (conn.from_output === 1) x1 = fp.x + NODE_W * 0.33
    if (conn.from_output === 2) x1 = fp.x + NODE_W * 0.67
    const y1 = fp.y + NODE_H
    const x2 = tp.x + NODE_W / 2, y2 = tp.y
    const mid = (y1 + y2) / 2

    let stroke, mId, strokeW = active ? 2.5 : 1.5, opacity = active ? 1 : 0.38
    if (conn.from_output === 1) { stroke = '#22c55e'; mId = active ? 'mk-ta' : 'mk-t' }
    else if (conn.from_output === 2) { stroke = '#ef4444'; mId = active ? 'mk-fa' : 'mk-f' }
    else { stroke = active ? '#3b82f6' : '#6b7280'; mId = active ? 'mk-da' : 'mk-d' }

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    path.setAttribute('d', `M${x1},${y1} C${x1},${mid} ${x2},${mid} ${x2},${y2}`)
    path.setAttribute('fill', 'none')
    path.setAttribute('stroke', stroke)
    path.setAttribute('stroke-width', strokeW)
    path.setAttribute('stroke-opacity', opacity)
    path.setAttribute('marker-end', `url(#${mId})`)
    if (flowing) { path.setAttribute('stroke-dasharray', '8 4'); path.classList.add('wf-conn-active') }
    svg.appendChild(path)

    // 분기 레이블
    if (conn.from_output === 1 || conn.from_output === 2) {
      const lbl = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      lbl.setAttribute('x', x1 + (conn.from_output === 1 ? -14 : 14))
      lbl.setAttribute('y', (y1 + y2) / 2 - 4)
      lbl.setAttribute('text-anchor', 'middle')
      lbl.setAttribute('font-size', '10'); lbl.setAttribute('font-weight', '700')
      lbl.setAttribute('fill', conn.from_output === 1 ? '#22c55e' : '#ef4444')
      lbl.setAttribute('opacity', active ? '1' : '0.5')
      lbl.textContent = conn.from_output === 1 ? 'true' : 'false'
      svg.appendChild(lbl)
    }
  }
  canvas.appendChild(svg)

  // ── 노드 카드 ────────────────────────────────────────────────
  for (const step of steps) {
    const pos = positions[step.id]; if (!pos) continue
    const sm = STATUS_META[step.status] || STATUS_META.pending
    const tm = TYPE_META[step.type] || TYPE_META.auto

    const node = document.createElement('div')
    node.className = `wf-graph-node ${sm.cls}`
    node.dataset.stepId = step.id
    node.style.cssText = `left:${pos.x}px;top:${pos.y}px;width:${NODE_W}px;height:${NODE_H}px;position:absolute;`

    node.innerHTML = `
      <div class="wf-node-inner">
        <div class="wf-node-status-icon">${sm.icon}</div>
        <div class="wf-node-body">
          <div class="wf-node-title">${escapeWf(step.title)}</div>
          <div class="wf-node-meta">
            <span>${tm.icon}</span>
            <span class="wf-node-status-label">${sm.label}</span>
            ${step.notes ? `<span class="wf-node-notes-dot" title="${escapeAttr(step.notes)}">📝</span>` : ''}
          </div>
        </div>
        <button class="wf-node-menu-btn" title="작업">⋮</button>
      </div>
    `
    node.querySelector('.wf-node-menu-btn').addEventListener('click', e => {
      e.stopPropagation()
      _showNodeActions(node, step, wf)
    })
    canvas.appendChild(node)
  }

  workflowStepsEl.appendChild(canvas)
}

// ── 노드 인터랙션 패널 (Phase 6C) ─────────────────────────────

function _showNodeActions(nodeEl, step, wf) {
  document.querySelectorAll('.wf-action-panel').forEach(p => p.remove())
  const conns = (wf.connections || []).filter(c => c.from_node === step.id)
  const hasBranch = conns.some(c => c.from_output === 1 || c.from_output === 2)
  const stepsById = Object.fromEntries((wf.steps || []).map(s => [s.id, s]))

  const trueConn  = conns.find(c => c.from_output === 1)
  const falseConn = conns.find(c => c.from_output === 2)

  const sm = STATUS_META[step.status] || STATUS_META.pending
  const canDone    = step.status !== 'done'
  const canSkip    = step.status !== 'done' && step.status !== 'skipped'
  const canRun     = step.status !== 'running' && step.status !== 'done'
  const canRetry   = step.status === 'error'

  const branchHTML = (hasBranch && canDone) ? `
    <div class="wf-action-branch">
      <div class="wf-action-branch-label">완료 후 경로 선택</div>
      <div class="wf-action-branch-btns">
        ${trueConn  ? `<button class="wf-branch-btn branch-true"  data-output="1">✔ true → ${escapeWf(stepsById[trueConn.to_node]?.title  || '')}</button>` : ''}
        ${falseConn ? `<button class="wf-branch-btn branch-false" data-output="2">✘ false → ${escapeWf(stepsById[falseConn.to_node]?.title || '')}</button>` : ''}
      </div>
    </div>` : ''

  const panel = document.createElement('div')
  panel.className = 'wf-action-panel'
  panel.innerHTML = `
    <div class="wf-action-header">
      <span class="wf-action-step-name">${sm.icon} ${escapeWf(step.title)}</span>
      <button class="wf-action-close">✕</button>
    </div>
    ${step.notes ? `<div class="wf-action-current-notes">${escapeWf(step.notes)}</div>` : ''}
    <div class="wf-action-notes-wrap">
      <textarea class="wf-action-notes-input" placeholder="메모 추가...">${escapeWf(step.notes || '')}</textarea>
    </div>
    ${branchHTML}
    <div class="wf-action-btns">
      ${canDone  && !hasBranch ? `<button class="wf-action-btn wf-btn-done">✓ 완료</button>` : ''}
      ${canSkip  ? `<button class="wf-action-btn wf-btn-skip">⏭ 건너뛰기</button>` : ''}
      ${canRun   ? `<button class="wf-action-btn wf-btn-run">▶ 실행 중</button>` : ''}
      ${canRetry ? `<button class="wf-action-btn wf-btn-retry">↺ 재시도</button>` : ''}
    </div>
  `

  // 위치 계산: 노드 아래, 화면 벗어나지 않게
  const rect = nodeEl.getBoundingClientRect()
  panel.style.cssText = `position:fixed;z-index:1000;left:${Math.min(rect.left, window.innerWidth - 270)}px;top:${rect.bottom + 6}px;`
  document.body.appendChild(panel)

  const notesInput = panel.querySelector('.wf-action-notes-input')
  const close = () => panel.remove()

  panel.querySelector('.wf-action-close').addEventListener('click', close)
  document.addEventListener('click', function oc(e) {
    if (!panel.contains(e.target) && e.target !== nodeEl) { close(); document.removeEventListener('click', oc) }
  })

  const doAction = async (status, branchOutput = null) => {
    const notes = notesInput.value.trim()
    close()
    await _patchNode(wf, step.id, status, notes, branchOutput)
  }

  if (panel.querySelector('.wf-btn-done'))
    panel.querySelector('.wf-btn-done').addEventListener('click', () => doAction('done'))

  panel.querySelectorAll('.wf-branch-btn').forEach(btn =>
    btn.addEventListener('click', () => doAction('done', parseInt(btn.dataset.output))))

  if (panel.querySelector('.wf-btn-skip'))
    panel.querySelector('.wf-btn-skip').addEventListener('click', () => doAction('skipped'))
  if (panel.querySelector('.wf-btn-run'))
    panel.querySelector('.wf-btn-run').addEventListener('click', () => doAction('running'))
  if (panel.querySelector('.wf-btn-retry'))
    panel.querySelector('.wf-btn-retry').addEventListener('click', () => {
      close()
      document.dispatchEvent(new CustomEvent('wf:retry-step', { detail: { stepId: step.id, stepTitle: step.title } }))
    })
}

async function _patchNode(wf, nodeId, status, notes = '', branchOutput = null) {
  const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
  const body = { status, notes }
  if (branchOutput !== null) body.branch_output = branchOutput
  try {
    const res = await fetch(`${base}/threads/${wf.task_type}/${wf.thread_id}/workflow/nodes/${nodeId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const result = await res.json()
    if (result.workflow) renderWorkflow(result.workflow)
  } catch (e) { console.error('노드 상태 업데이트 실패', e) }
}

function clearWorkflow() {
  _stopFileWatcher()
  _currentWorkflow = null
  workflowContent.classList.add('hidden')
  workflowEmpty.classList.remove('hidden')
  workflowStepsEl.innerHTML = ''
  // 진행 바 제거 (다음 스레드 로드 시 새로 생성)
  const pw = workflowContent.querySelector('[data-wf-progress]')
  if (pw) pw.remove()
  document.querySelectorAll('.wf-action-panel').forEach(p => p.remove())
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

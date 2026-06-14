// ── 우측 워크플로우 패널 ──────────────────────────────────────

const rightPanel = document.getElementById('right-panel')
const rightResizeHandle = document.getElementById('right-resize-handle')
const rightPanelToggle = document.getElementById('right-panel-toggle')
const rpTabs = document.querySelectorAll('.rp-tab')
const supervisorPanel = document.getElementById('supervisor-panel')
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
const workflowTemplateBtn = document.getElementById('workflow-template-btn')
const logEntries = document.getElementById('log-entries')
const svGoal = document.getElementById('sv-goal')
const svState = document.getElementById('sv-state')
const svStep = document.getElementById('sv-step')
const svTool = document.getElementById('sv-tool')
const svElapsed = document.getElementById('sv-elapsed')
const svApproval = document.getElementById('sv-approval')
const svRisk = document.getElementById('sv-risk')
const svContext = document.getElementById('sv-context')
const svEvidence = document.getElementById('sv-evidence')
const svError = document.getElementById('sv-error')

let _currentWorkflow = null
let _panelCollapsed = false
let _panelWidth = 300
let _editMode = false
let _templateMode = false   // true일 때 저장은 템플릿 endpoint로
let _editDraft = null
let _dragIdx = null
let _watcherES = null   // 파일 변경 감지 EventSource
let _currentTaskType = null  // 현재 선택된 업무 유형

// ── U: 시각화 고도화 상태 ─────────────────────────────────────
let _panzoom = null                  // 현재 그래프의 팬/줌 인스턴스
let _nodeLogs = {}                   // { [nodeId]: [{tool, summary, ok}] } — 노드별 최근 도구 로그 (ephemeral)
let _collapsedGroups = new Set()     // 접힌 그룹 라벨 (스레드 단위 유지)
let _lodRafPending = false
let _savedView = null                // 재렌더 간 팬/줌 위치 보존 (스레드 전환 시 초기화)

const wfZoomControls = document.getElementById('wf-zoom-controls')

function _disposePanzoom() {
  if (_panzoom) { _savedView = _panzoom.getTransform(); _panzoom.dispose(); _panzoom = null }
}

// 그래프 캔버스를 뷰포트 크기에 맞춰 축소(최대 1배)하고 중앙 정렬 → 전체가 한눈에 보이게
function _fitToViewport(pz, viewport, canvasW, canvasH) {
  const vw = viewport.clientWidth, vh = viewport.clientHeight
  if (!vw || !vh || !canvasW || !canvasH) return
  const scale = Math.min(vw / canvasW, vh / canvasH, 1) * 0.94  // 가장자리 여백
  const x = (vw - canvasW * scale) / 2
  const y = Math.max(8, (vh - canvasH * scale) / 2)
  pz.zoomAbs(0, 0, scale)
  pz.moveTo(x, y)
}

// ── 탭 전환 ─────────────────────────────────────────────────

rpTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    if (tab.id === 'right-panel-toggle') return
    rpTabs.forEach(t => t.classList.remove('active'))
    tab.classList.add('active')
    const target = tab.dataset.tab
    supervisorPanel.classList.toggle('active', target === 'supervisor')
    workflowPanel.classList.toggle('active', target === 'workflow')
    logPanel.classList.toggle('active', target === 'log')
  })
})

// ── 감독 패널 reducer ────────────────────────────────────────

const SUPERVISOR_INITIAL = {
  requestId: '',
  goal: '대기 중',
  step: '-',
  agentState: 'idle',
  currentTool: '',
  currentToolLabel: '',
  toolStartedAt: 0,
  elapsedMs: 0,
  waitingApproval: false,
  approvalText: '대기 없음',
  risk: 'none',
  contextText: '-',
  evidence: [],
  lastError: '',
}

let _supervisorState = { ...SUPERVISOR_INITIAL }
let _supervisorTimer = null

function _resetSupervisorState(requestId = '') {
  _stopSupervisorTimer()
  _supervisorState = { ...SUPERVISOR_INITIAL, requestId }
}

function _summarizeWorkflow(wf) {
  const steps = wf?.steps || []
  const current = steps.find(s => ['running', 'waiting', 'error'].includes(s.status)) ||
    steps.find(s => s.status === 'pending') ||
    steps[steps.length - 1]
  const doneCount = steps.filter(s => s.status === 'done' || s.status === 'skipped').length
  const total = steps.length
  return {
    goal: wf?.title || '실행 중',
    step: current
      ? `${doneCount}/${total || 1} · ${current.title || current.id || '현재 단계'}`
      : '-',
  }
}

function _appendEvidence(label, detail = '') {
  const text = detail ? `${label}: ${detail}` : label
  _supervisorState.evidence = [
    { text, at: new Date().toTimeString().slice(0, 8) },
    ..._supervisorState.evidence,
  ].slice(0, 5)
}

function _startSupervisorTimer() {
  if (_supervisorTimer) return
  _supervisorTimer = setInterval(() => {
    if (!_supervisorState.toolStartedAt) return
    _supervisorState.elapsedMs = Date.now() - _supervisorState.toolStartedAt
    renderSupervisor()
  }, 500)
}

function _stopSupervisorTimer() {
  if (_supervisorTimer) clearInterval(_supervisorTimer)
  _supervisorTimer = null
}

function _reduceSupervisor(event) {
  if (!event) return
  if (event.request_id && !event.type) {
    _resetSupervisorState(event.request_id)
    renderSupervisor()
    return
  }

  switch (event.type) {
    case 'agent_state':
      _supervisorState.agentState = event.state || 'unknown'
      if (event.state === 'idle') {
        _supervisorState.currentTool = ''
        _supervisorState.currentToolLabel = ''
        _supervisorState.toolStartedAt = 0
        _supervisorState.elapsedMs = 0
        _supervisorState.waitingApproval = false
        _supervisorState.approvalText = '대기 없음'
        _supervisorState.risk = 'none'
        _stopSupervisorTimer()
      }
      break

    case 'tool_start':
      _supervisorState.agentState = 'working'
      _supervisorState.currentTool = event.tool || ''
      _supervisorState.currentToolLabel = event.label || event.tool || '도구 실행 중'
      _supervisorState.toolStartedAt = Date.now()
      _supervisorState.elapsedMs = 0
      _supervisorState.waitingApproval = false
      _supervisorState.approvalText = '대기 없음'
      _supervisorState.risk = 'none'
      _supervisorState.lastError = ''
      _startSupervisorTimer()
      break

    case 'tool_wait':
      _supervisorState.agentState = 'waiting'
      _supervisorState.approvalText = `도구 지연: ${event.next || '?'}s까지 대기`
      break

    case 'tool_done':
      if (_supervisorState.currentTool === event.tool) {
        _supervisorState.currentTool = ''
        _supervisorState.currentToolLabel = ''
        _supervisorState.toolStartedAt = 0
        _supervisorState.elapsedMs = 0
        _stopSupervisorTimer()
      }
      if (!_supervisorState.waitingApproval) {
        _supervisorState.agentState = 'running'
        _supervisorState.approvalText = '대기 없음'
        _supervisorState.risk = 'none'
      }
      _appendEvidence(event.tool || 'tool', String(event.result || '').slice(0, 80))
      break

    case 'confirm':
      _supervisorState.agentState = 'waiting'
      _supervisorState.waitingApproval = true
      _supervisorState.approvalText = event.question || '사용자 승인 대기'
      _supervisorState.risk = event.risk || 'confirm'
      if (event.command) _appendEvidence('승인 대상 명령', event.command.slice(0, 80))
      break

    case 'workflow_update': {
      const summary = _summarizeWorkflow(event.workflow)
      _supervisorState.goal = summary.goal
      _supervisorState.step = summary.step
      break
    }

    case 'context_usage':
      _supervisorState.contextText = `${event.tokens_used || 0}/${event.tokens_total || 0}`
      break

    case 'vision_capture':
      _appendEvidence('화면 캡처', event.image_b64 ? '이미지 수집됨' : '캡처 이벤트')
      break

    case 'done':
      _supervisorState.agentState = 'idle'
      _supervisorState.currentTool = ''
      _supervisorState.currentToolLabel = ''
      _supervisorState.toolStartedAt = 0
      _supervisorState.elapsedMs = 0
      _supervisorState.waitingApproval = false
      _supervisorState.approvalText = '대기 없음'
      _supervisorState.risk = 'none'
      _supervisorState.lastError = ''
      _stopSupervisorTimer()
      break

    case 'error':
      _supervisorState.agentState = 'error'
      _supervisorState.currentTool = ''
      _supervisorState.currentToolLabel = ''
      _supervisorState.toolStartedAt = 0
      _supervisorState.elapsedMs = 0
      _supervisorState.waitingApproval = false
      _supervisorState.lastError = event.message || '알 수 없는 오류'
      _stopSupervisorTimer()
      break
  }
  renderSupervisor()
}

function renderSupervisor() {
  if (!supervisorPanel) return
  svGoal.textContent = _supervisorState.goal
  svState.textContent = _supervisorState.agentState
  svState.className = `sv-state ${_supervisorState.agentState || 'idle'}`
  svStep.textContent = _supervisorState.step
  svTool.textContent = _supervisorState.currentToolLabel || '-'
  svElapsed.textContent = `${(_supervisorState.elapsedMs / 1000).toFixed(1)}s`
  svApproval.textContent = _supervisorState.approvalText
  svRisk.textContent = `risk: ${_supervisorState.risk}`
  svContext.textContent = _supervisorState.contextText
  svError.textContent = _supervisorState.lastError
  svError.classList.toggle('hidden', !_supervisorState.lastError)

  if (_supervisorState.evidence.length) {
    svEvidence.className = 'sv-evidence-list'
    svEvidence.innerHTML = _supervisorState.evidence
      .map(item => `<div class="sv-evidence-item"><span>${escapeWf(item.at)}</span>${escapeWf(item.text)}</div>`)
      .join('')
  } else {
    svEvidence.className = 'sv-evidence-empty'
    svEvidence.textContent = '아직 수집된 근거가 없습니다.'
  }
}

// ── 패널 접기/펼치기 ─────────────────────────────────────────

rightPanelToggle.addEventListener('click', () => {
  _panelCollapsed = !_panelCollapsed
  if (_panelCollapsed) {
    rightPanel.classList.add('collapsed')
    rightResizeHandle.style.display = 'none'
    rightPanelToggle.textContent = '‹'
    rightPanelToggle.title = '패널 열기'
  } else {
    rightPanel.classList.remove('collapsed')
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

// 패널 너비가 컴팩트 임계값을 넘나들면 그래프 ↔ 컴팩트 카드 전환 (개선 아이디어 B)
let _lastCompact = null
const _panelResizeObserver = new ResizeObserver(() => {
  const c = _isCompact()
  if (c !== _lastCompact) {
    _lastCompact = c
    if (_currentWorkflow && !_editMode && !_templateMode) renderWorkflow(_currentWorkflow)
  }
})
_panelResizeObserver.observe(rightPanel)

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

function _computeLayout(steps, connections, groupOf = {}) {
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
  // 같은 그룹 노드를 rank 내에서 인접 배치 (레인 정렬, 안정 정렬)
  for (const r of Object.keys(byRank)) {
    byRank[r] = byRank[r]
      .map((id, i) => [id, i])
      .sort((a, b) => (groupOf[a[0]] || '￿').localeCompare(groupOf[b[0]] || '￿') || a[1] - b[1])
      .map(p => p[0])
  }

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
  const supervisorSummary = _summarizeWorkflow(wf)
  _supervisorState.goal = supervisorSummary.goal
  _supervisorState.step = supervisorSummary.step
  renderSupervisor()

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

  _disposePanzoom()
  workflowStepsEl.innerHTML = ''
  if (!steps.length) { if (wfZoomControls) wfZoomControls.classList.add('hidden'); return }

  // 반응형: 좁은 패널은 세로 컴팩트 카드, 넓으면 2D 그래프 (개선 아이디어 B)
  if (_isCompact()) {
    if (wfZoomControls) wfZoomControls.classList.add('hidden')
    _renderCompactList(wf, steps)
    return
  }
  if (wfZoomControls) wfZoomControls.classList.remove('hidden')
  _renderGraph(wf, steps, connections)
}

// ── U: 그룹 접기 변환 ─────────────────────────────────────────
// 접힌 그룹의 멤버 노드를 단일 pill 노드로 치환하고 연결을 재라우팅한다.
function _applyGroupCollapse(steps, connections) {
  const groupOf = {}
  for (const s of steps) groupOf[s.id] = s.group || ''
  const collapsed = [...steps.some(s => s.group) ? _collapsedGroups : []]
    .filter(g => steps.some(s => s.group === g))
  if (!collapsed.length) return { displaySteps: steps, displayConns: connections, pills: {}, groupOf }

  const memberToPill = {}   // memberId -> pillId
  const pills = {}          // pillId -> { id, group, members, doneCount, status }
  for (const g of collapsed) {
    const members = steps.filter(s => s.group === g)
    const pillId = `__grp__${g}`
    const doneCount = members.filter(m => m.status === 'done' || m.status === 'skipped').length
    const anyRunning = members.some(m => m.status === 'running')
    const anyError = members.some(m => m.status === 'error')
    pills[pillId] = {
      id: pillId, group: g, members,
      doneCount, total: members.length,
      status: anyError ? 'error' : anyRunning ? 'running' : doneCount === members.length ? 'done' : 'pending',
    }
    members.forEach(m => { memberToPill[m.id] = pillId })
  }

  const displaySteps = steps.filter(s => !memberToPill[s.id])
  for (const pillId of Object.keys(pills)) {
    const p = pills[pillId]
    displaySteps.push({
      id: pillId, title: p.group, type: 'auto', status: p.status,
      notes: '', group: '', __pill: p,
    })
  }

  const seen = new Set()
  const displayConns = []
  for (const c of connections) {
    const from = memberToPill[c.from_node] || c.from_node
    const to = memberToPill[c.to_node] || c.to_node
    if (from === to) continue  // 그룹 내부 연결은 숨김
    const key = `${from}|${to}|${c.from_output}`
    if (seen.has(key)) continue
    seen.add(key)
    displayConns.push({ from_node: from, to_node: to, from_output: c.from_output })
  }
  return { displaySteps, displayConns, pills, groupOf }
}

// ── 좁은 패널: 세로 컴팩트 카드 목록 (개선 아이디어 B) ──────────
// 이 폭 미만이면 세로 컴팩트 목록, 이상이면 2D 그래프.
// fit-to-view가 그래프를 어떤 폭에도 맞춰 축소하므로 기본 패널폭(300px)에서도 그래프가 보이도록 250으로 낮춤.
// (이전 360은 기본 패널폭 300보다 커서 항상 컴팩트 목록만 나오던 버그)
const COMPACT_THRESHOLD = 250

function _isCompact() {
  return (rightPanel.offsetWidth || _panelWidth) < COMPACT_THRESHOLD
}

function _renderCompactList(wf, steps) {
  const list = document.createElement('div')
  list.className = 'wf-compact-list'

  steps.forEach((step, idx) => {
    const sm = STATUS_META[step.status] || STATUS_META.pending
    const tm = TYPE_META[step.type] || TYPE_META.auto
    // 완료/건너뜀 단계는 접어서 한 줄로만 표시
    const collapsed = step.status === 'done' || step.status === 'skipped'

    const row = document.createElement('div')
    row.className = `wf-compact-row ${sm.cls}${collapsed ? ' collapsed' : ''}`
    row.dataset.stepId = step.id
    row.innerHTML = `
      <span class="wf-c-num">${idx + 1}</span>
      <span class="wf-c-icon">${sm.icon}</span>
      <div class="wf-c-body">
        <div class="wf-c-title">${escapeWf(step.title)}</div>
        ${collapsed ? '' : `<div class="wf-c-meta">
          <span>${tm.icon} ${tm.label}</span>
          <span class="wf-c-status">${sm.label}</span>
          ${step.notes ? `<span class="wf-node-notes-dot" title="${escapeAttr(step.notes)}">📝</span>` : ''}
        </div>`}
        ${collapsed ? '' : _nodeLogHtml(step.id)}
      </div>
      <button class="wf-node-menu-btn" title="작업">⋮</button>
    `
    row.querySelector('.wf-node-menu-btn').addEventListener('click', e => {
      e.stopPropagation()
      _showNodeActions(row, step, wf)
    })
    list.appendChild(row)
  })

  workflowStepsEl.appendChild(list)
}

function _nodeLogHtml(stepId) {
  const logs = _nodeLogs[stepId]
  if (!logs || !logs.length) return ''
  const recent = logs.slice(-2)
  return `<div class="wf-node-log">` + recent.map(l =>
    `<div class="wf-node-log-line${l.ok ? '' : ' err'}" title="${escapeAttr(l.tool + ': ' + l.summary)}">` +
    `${l.ok ? '✓' : '✗'} ${escapeWf(l.tool)}: ${escapeWf(l.summary)}</div>`
  ).join('') + `</div>`
}

function _actionLogHtml(stepId) {
  const logs = _nodeLogs[stepId]
  if (!logs || !logs.length) return ''
  return `<div class="wf-action-log"><div class="wf-action-log-title">실행 로그</div>` +
    logs.map(l =>
      `<div class="wf-action-log-line${l.ok ? '' : ' err'}">${l.ok ? '✓' : '✗'} ` +
      `<b>${escapeWf(l.tool)}</b> ${escapeWf(l.summary)}</div>`
    ).join('') + `</div>`
}

// chat.js의 tool_done에서 호출 — 현재 running 노드에 도구 로그 요약을 적재한다.
function recordToolLog(tool, result) {
  if (!_currentWorkflow || !tool || tool.startsWith('workflow_')) return
  const running = (_currentWorkflow.steps || []).find(s => s.status === 'running')
  if (!running) return
  const text = String(result || '')
  const ok = !text.startsWith('툴 실행 오류')
  const firstLine = (text.split('\n').find(l => l.trim()) || text).trim()
  const summary = firstLine.length > 80 ? firstLine.slice(0, 79) + '…' : firstLine
  const arr = _nodeLogs[running.id] || (_nodeLogs[running.id] = [])
  arr.push({ tool, summary, ok })
  if (arr.length > 5) arr.shift()
  if (!_editMode) renderWorkflow(_currentWorkflow)
}

function _renderGraph(wf, steps, connectionsRaw) {
  const { NODE_W, NODE_H, PAD } = GRAPH

  // 그룹 접기 변환 → 표시용 노드/연결
  const { displaySteps, displayConns, pills, groupOf } = _applyGroupCollapse(steps, connectionsRaw)
  const steps0 = displaySteps
  const connections = displayConns
  const { positions, canvasW, canvasH } = _computeLayout(steps0, connections, groupOf)

  // 팬/줌 뷰포트(고정 크기, overflow 숨김) + 캔버스(변환 대상)
  const viewport = document.createElement('div')
  viewport.className = 'wf-graph-viewport'

  // 캔버스 컨테이너
  const canvas = document.createElement('div')
  canvas.className = 'wf-graph-canvas ' + _lodClassFor(1)
  canvas.style.cssText = `width:${canvasW}px;height:${canvasH}px;position:relative;`

  // ── 그룹 박스 (펼쳐진 그룹의 멤버 bounding box) ───────────────
  _renderGroupBoxes(canvas, steps0, positions)

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

  const statusOf = id => (steps0.find(s => s.id === id) || {}).status || 'pending'

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

  // ── 노드 카드 (그룹 pill 포함) ───────────────────────────────
  for (const step of steps0) {
    const pos = positions[step.id]; if (!pos) continue
    const sm = STATUS_META[step.status] || STATUS_META.pending

    // 접힌 그룹 pill
    if (step.__pill) {
      const p = step.__pill
      const pill = document.createElement('div')
      pill.className = `wf-graph-node wf-group-pill ${sm.cls}`
      pill.style.cssText = `left:${pos.x}px;top:${pos.y}px;width:${NODE_W}px;height:${NODE_H}px;position:absolute;`
      pill.innerHTML = `
        <div class="wf-node-inner">
          <div class="wf-node-status-icon">📦</div>
          <div class="wf-node-body">
            <div class="wf-node-title">${escapeWf(p.group)}</div>
            <div class="wf-node-meta"><span class="wf-node-status-label">그룹 ${p.doneCount}/${p.total}</span></div>
          </div>
          <button class="wf-group-expand" title="펼치기">▸</button>
        </div>`
      pill.querySelector('.wf-group-expand').addEventListener('click', e => {
        e.stopPropagation()
        _collapsedGroups.delete(p.group)
        renderWorkflow(_currentWorkflow)
      })
      canvas.appendChild(pill)
      continue
    }

    const tm = TYPE_META[step.type] || TYPE_META.auto
    const node = document.createElement('div')
    node.className = `wf-graph-node ${sm.cls}`
    node.dataset.stepId = step.id
    node.style.cssText = `left:${pos.x}px;top:${pos.y}px;width:${NODE_W}px;min-height:${NODE_H}px;position:absolute;`

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
          ${_nodeLogHtml(step.id)}
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

  viewport.appendChild(canvas)
  workflowStepsEl.appendChild(viewport)

  // ── 미니맵 ────────────────────────────────────────────────────
  const minimap = _buildMinimap(steps0, positions, canvasW, canvasH)
  if (minimap) viewport.appendChild(minimap)

  // ── 팬/줌 초기화 ──────────────────────────────────────────────
  _disposePanzoom()
  if (typeof panzoom === 'function') {
    _panzoom = panzoom(canvas, {
      minZoom: 0.3, maxZoom: 2.5, bounds: true,
      beforeMouseDown: e => !!e.target.closest('.wf-node-menu-btn, .wf-group-expand, .wf-action-panel, .wf-minimap'),
    })
    _panzoom.on('transform', _onPanzoomTransform)
    if (_savedView) {
      // 재렌더: 사용자가 보던 위치 복원 (anvaka엔 setTransform이 없어 zoomAbs+moveTo)
      _panzoom.zoomAbs(0, 0, _savedView.scale)
      _panzoom.moveTo(_savedView.x, _savedView.y)
    } else {
      // 최초 렌더: 그래프 전체가 보이도록 뷰포트에 맞춰 축소·중앙정렬
      _fitToViewport(_panzoom, viewport, canvasW, canvasH)
    }
    _onPanzoomTransform(_panzoom)
  }
}

// ── U: 그룹 박스 (펼쳐진 그룹 멤버를 감싸는 반투명 사각형) ────────
function _renderGroupBoxes(canvas, steps, positions) {
  const { NODE_W, NODE_H } = GRAPH
  const groups = {}
  for (const s of steps) {
    if (!s.group || s.__pill) continue
    const pos = positions[s.id]; if (!pos) continue
    ;(groups[s.group] = groups[s.group] || []).push(pos)
  }
  for (const [label, ps] of Object.entries(groups)) {
    const minX = Math.min(...ps.map(p => p.x)) - 8
    const minY = Math.min(...ps.map(p => p.y)) - 22
    const maxX = Math.max(...ps.map(p => p.x + NODE_W)) + 8
    const maxY = Math.max(...ps.map(p => p.y + NODE_H)) + 8
    const box = document.createElement('div')
    box.className = 'wf-group-box'
    box.style.cssText = `left:${minX}px;top:${minY}px;width:${maxX - minX}px;height:${maxY - minY}px;position:absolute;`
    box.innerHTML = `<span class="wf-group-label">📦 ${escapeWf(label)}</span>` +
      `<button class="wf-group-collapse" title="그룹 접기">▾</button>`
    box.querySelector('.wf-group-collapse').addEventListener('click', e => {
      e.stopPropagation()
      _collapsedGroups.add(label)
      renderWorkflow(_currentWorkflow)
    })
    canvas.appendChild(box)
  }
}

// ── U: 동적 디테일(LoD) ───────────────────────────────────────
function _lodClassFor(scale) {
  if (scale < 0.7) return 'lod-low'
  if (scale > 1.3) return 'lod-high'
  return 'lod-mid'
}
let _lodClass = 'lod-mid'

function _onPanzoomTransform(pz) {
  if (_lodRafPending) return
  _lodRafPending = true
  requestAnimationFrame(() => {
    _lodRafPending = false
    const t = pz.getTransform()
    const canvas = workflowStepsEl.querySelector('.wf-graph-canvas')
    if (canvas) {
      const cls = _lodClassFor(t.scale)
      if (cls !== _lodClass) {
        canvas.classList.remove('lod-low', 'lod-mid', 'lod-high')
        canvas.classList.add(cls)
        _lodClass = cls
      }
    }
    _updateMinimapViewport(t)
  })
}

// ── U: 미니맵 ─────────────────────────────────────────────────
const MINIMAP = { W: 132, H: 96 }

function _buildMinimap(steps, positions, canvasW, canvasH) {
  if (steps.length < 6) return null
  const mm = document.createElement('div')
  mm.className = 'wf-minimap'
  mm.style.cssText = `width:${MINIMAP.W}px;height:${MINIMAP.H}px;`
  const scale = Math.min(MINIMAP.W / canvasW, MINIMAP.H / canvasH)
  mm.dataset.scale = scale
  mm.dataset.canvasW = canvasW
  mm.dataset.canvasH = canvasH
  const { NODE_W, NODE_H } = GRAPH
  for (const s of steps) {
    const pos = positions[s.id]; if (!pos) continue
    const dot = document.createElement('div')
    const sm = STATUS_META[s.status] || STATUS_META.pending
    dot.className = `wf-minimap-dot ${sm.cls}`
    dot.style.cssText =
      `left:${pos.x * scale}px;top:${pos.y * scale}px;` +
      `width:${Math.max(2, NODE_W * scale)}px;height:${Math.max(2, NODE_H * scale)}px;position:absolute;`
    mm.appendChild(dot)
  }
  const vp = document.createElement('div')
  vp.className = 'wf-minimap-viewport'
  mm.appendChild(vp)
  // 미니맵 클릭 → 해당 지점을 뷰포트 중심으로 이동
  mm.addEventListener('mousedown', e => {
    if (!_panzoom) return
    const rect = mm.getBoundingClientRect()
    const cx = (e.clientX - rect.left) / scale
    const cy = (e.clientY - rect.top) / scale
    const vw = workflowStepsEl.querySelector('.wf-graph-viewport')
    const t = _panzoom.getTransform()
    _panzoom.moveTo(vw.clientWidth / 2 - cx * t.scale, vw.clientHeight / 2 - cy * t.scale)
    e.stopPropagation()
  })
  return mm
}

function _updateMinimapViewport(t) {
  const mm = workflowStepsEl.querySelector('.wf-minimap')
  if (!mm) return
  const vp = mm.querySelector('.wf-minimap-viewport')
  const viewport = workflowStepsEl.querySelector('.wf-graph-viewport')
  if (!vp || !viewport) return
  const scale = parseFloat(mm.dataset.scale)
  // 뷰포트가 보는 콘텐츠 영역 (콘텐츠 좌표) → 미니맵 좌표
  const vx = -t.x / t.scale
  const vy = -t.y / t.scale
  const vw = viewport.clientWidth / t.scale
  const vh = viewport.clientHeight / t.scale
  vp.style.cssText =
    `left:${vx * scale}px;top:${vy * scale}px;width:${vw * scale}px;height:${vh * scale}px;`
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
    ${_actionLogHtml(step.id)}
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
  _disposePanzoom()
  _savedView = null
  _nodeLogs = {}
  _collapsedGroups = new Set()
  _currentWorkflow = null
  if (wfZoomControls) wfZoomControls.classList.add('hidden')
  workflowContent.classList.add('hidden')
  workflowEmpty.classList.remove('hidden')
  workflowStepsEl.innerHTML = ''
  // 진행 바 제거 (다음 스레드 로드 시 새로 생성)
  const pw = workflowContent.querySelector('[data-wf-progress]')
  if (pw) pw.remove()
  document.querySelectorAll('.wf-action-panel').forEach(p => p.remove())
  _supervisorState.goal = '대기 중'
  _supervisorState.step = '-'
  renderSupervisor()
}

// ── 파일 변경 감지 (SSE) ──────────────────────────────────────

function _startFileWatcher(taskType, threadId) {
  _stopFileWatcher()
  if (!taskType || !threadId) return
  const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
  // EventSource는 커스텀 헤더를 못 붙이므로 토큰을 쿼리로 전달 (S1)
  const tokenQ = (window.authTokenQuery || (() => ''))('?')
  _watcherES = new EventSource(`${base}/threads/${taskType}/${threadId}/workflow/events${tokenQ}`)
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
      <input class="wf-edit-group" value="${escapeAttr(step.group || '')}" placeholder="그룹" title="시각적 그룹 라벨 (선택)" />
      <button class="wf-edit-del" title="단계 삭제">✕</button>
    `
    row.querySelector('.wf-edit-title')
      .addEventListener('input', e => { _editDraft.steps[idx].title = e.target.value })
    row.querySelector('.wf-edit-type')
      .addEventListener('change', e => { _editDraft.steps[idx].type = e.target.value })
    row.querySelector('.wf-edit-group')
      .addEventListener('input', e => { _editDraft.steps[idx].group = e.target.value })
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
    _editDraft.steps.push({ id: '', title: '새 단계', type: 'auto', status: 'pending', notes: '', group: '' })
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
  _templateMode = false
  _editDraft = JSON.parse(JSON.stringify(_currentWorkflow))
  if (!_editDraft.connections) _editDraft.connections = []
  workflowEditBtn.classList.add('hidden')
  workflowClearBtn.classList.add('hidden')
  workflowTemplateBtn.classList.add('hidden')
  workflowSaveBtn.textContent = '💾 저장'
  workflowSaveBtn.classList.remove('hidden')
  workflowCancelBtn.classList.remove('hidden')
  renderEditMode()
}

function _leaveEdit() {
  _editMode = false
  _templateMode = false
  _editDraft = null
  _dragIdx = null
  workflowSaveBtn.classList.add('hidden')
  workflowSaveBtn.textContent = '💾 저장'
  workflowCancelBtn.classList.add('hidden')
  workflowEditBtn.classList.remove('hidden')
  workflowClearBtn.classList.remove('hidden')
  workflowTemplateBtn.classList.remove('hidden')
}

async function _enterTemplateEdit() {
  const taskType = _currentTaskType
  if (!taskType) return
  const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`
  try {
    const res = await fetch(`${base}/workflow/templates/${taskType}`)
    const tmpl = await res.json()
    _editMode = true
    _templateMode = true
    _editDraft = {
      title: tmpl.title || '워크플로우',
      steps: (tmpl.steps || []).map(s => ({
        id: '',
        title: s.title || s,
        type: s.type || 'auto',
        status: 'pending',
        notes: '',
      })),
      connections: [],
    }
    workflowEditBtn.classList.add('hidden')
    workflowClearBtn.classList.add('hidden')
    workflowTemplateBtn.classList.add('hidden')
    workflowSaveBtn.textContent = '💾 템플릿 저장'
    workflowSaveBtn.classList.remove('hidden')
    workflowCancelBtn.classList.remove('hidden')
    workflowEmpty.classList.add('hidden')
    workflowContent.classList.remove('hidden')
    renderEditMode()
  } catch (e) {
    console.error('템플릿 로드 실패', e)
  }
}

async function _saveEdit() {
  if (!_editDraft) return
  const base = `http://localhost:${window.electronAPI?.serverPort ?? 8000}`

  if (_templateMode) {
    try {
      await fetch(`${base}/workflow/templates/${_currentTaskType}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: _editDraft.title,
          steps: _editDraft.steps.map(s => ({ title: s.title, type: s.type || 'auto' })),
        }),
      })
      _leaveEdit()
      if (_currentWorkflow) renderWorkflow(_currentWorkflow)
      else { workflowContent.classList.add('hidden'); workflowEmpty.classList.remove('hidden') }
      if (typeof showToast === 'function') showToast('기본 템플릿이 저장됐습니다. 새 스레드부터 적용됩니다.')
    } catch (e) {
      console.error('템플릿 저장 실패', e)
    }
    return
  }

  if (!_currentWorkflow) return
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
  const wasTemplate = _templateMode
  _leaveEdit()
  if (wf) renderWorkflow(wf)
  else if (wasTemplate) { workflowContent.classList.add('hidden'); workflowEmpty.classList.remove('hidden') }
}

// ── 워크플로우 로드 (스레드 선택 시) ──────────────────────────

async function loadWorkflowForThread(taskType, threadId) {
  if (_editMode) _leaveEdit()
  _stopFileWatcher()
  _currentTaskType = taskType || null
  _nodeLogs = {}
  _collapsedGroups = new Set()
  _savedView = null
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
workflowTemplateBtn.addEventListener('click', _enterTemplateEdit)

// ── 줌 컨트롤 (U) ─────────────────────────────────────────────
function _zoomFromButton(factor) {
  if (!_panzoom) return
  const vp = workflowStepsEl.querySelector('.wf-graph-viewport')
  if (!vp) return
  const r = vp.getBoundingClientRect()
  _panzoom.smoothZoom(r.left + r.width / 2, r.top + r.height / 2, factor)
}
document.getElementById('wf-zoom-in')?.addEventListener('click', () => _zoomFromButton(1.25))
document.getElementById('wf-zoom-out')?.addEventListener('click', () => _zoomFromButton(0.8))
document.getElementById('wf-zoom-reset')?.addEventListener('click', () => {
  // 전체 보기: 그래프 전체가 보이도록 뷰포트에 맞춰 재정렬 (anvaka엔 reset()이 없음)
  if (!_panzoom) return
  const vp = workflowStepsEl.querySelector('.wf-graph-viewport')
  const canvas = vp && vp.querySelector('.wf-graph-canvas')
  if (vp && canvas) _fitToViewport(_panzoom, vp, canvas.offsetWidth, canvas.offsetHeight)
})

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
  handleEvent: _reduceSupervisor,
  getSupervisorState: () => ({ ..._supervisorState, evidence: [..._supervisorState.evidence] }),
  appendLog,
  recordToolLog,
  clearLog,
}

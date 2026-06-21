const PORT = window.electronAPI?.serverPort ?? 8000
const BASE_URL = `http://localhost:${PORT}`

// ── 서버 인증 토큰 주입 (S1) ──────────────────────────────────
// 모든 localhost API 요청에 X-Auth-Token 헤더를 자동 첨부한다.
// EventSource는 헤더를 못 붙이므로 workflow.js에서 ?token= 쿼리로 처리.
const AUTH_TOKEN = window.electronAPI?.authToken || ''
if (AUTH_TOKEN) {
  const _origFetch = window.fetch.bind(window)
  window.fetch = (url, opts = {}) => {
    const u = typeof url === 'string' ? url : (url && url.url) || ''
    if (u.includes('localhost') || u.includes('127.0.0.1')) {
      opts = { ...opts, headers: { ...(opts.headers || {}), 'X-Auth-Token': AUTH_TOKEN } }
    }
    return _origFetch(url, opts)
  }
}
// EventSource URL에 토큰 쿼리를 덧붙이는 헬퍼 (workflow.js에서 사용)
window.authTokenQuery = AUTH_TOKEN ? (sep => `${sep}token=${encodeURIComponent(AUTH_TOKEN)}`) : (() => '')

const messagesEl = document.getElementById('messages')
const inputEl = document.getElementById('input')
const sendBtn = document.getElementById('send-btn')
const inputExpandBtn = document.getElementById('input-expand-btn')
const statusEl = document.getElementById('status')
const profileSwitcher = document.getElementById('profile-switcher')
const profileBtn = document.getElementById('profile-btn')
const profileMenu = document.getElementById('profile-menu')
const currentThreadBar = document.getElementById('current-thread-bar')
const currentThreadInfo = document.getElementById('current-thread-info')
const threadCloseCurrentBtn = document.getElementById('thread-close-current-btn')
const openDeleteManagerBtn = document.getElementById('open-delete-manager-btn')
const deleteManagerOverlay = document.getElementById('delete-manager-overlay')
const deleteManagerBody = document.getElementById('delete-manager-body')
const deleteManagerClose = document.getElementById('delete-manager-close')
const agentStateBar = document.getElementById('agent-state-bar')
const agentStateIcon = document.getElementById('agent-state-icon')
const agentStateText = document.getElementById('agent-state-text')
const stopBtn = document.getElementById('stop-btn')
const interjectBtn = document.getElementById('interject-btn')
const contextBar = document.getElementById('context-bar')
const contextFill = document.getElementById('context-fill')
const contextLabel = document.getElementById('context-label')

// ── 스레드 상태 ──────────────────────────────────────────────
let currentTaskType = ''
let currentThreadId = ''
let taskConfigs = {}
let currentRequestId = ''
const showingArchiveGroups = new Set()
const expandedGroups = new Set()

// ── IDE식 열린 스레드 탭 (개선 아이디어 A) ────────────────────
// openTabs: { key, taskType, threadId, status, archived } 의 배열. X=닫기(탭에서만 제거).
const threadTabsEl = document.getElementById('thread-tabs')
let openTabs = []
const tabKey = (taskType, threadId) => `${taskType}::${threadId}`

function openOrFocusTab(taskType, threadId, status, archived = false) {
  const key = tabKey(taskType, threadId)
  let tab = openTabs.find(t => t.key === key)
  if (tab) {
    tab.status = status
    tab.archived = archived
  } else {
    tab = { key, taskType, threadId, status, archived }
    openTabs.push(tab)
  }
  renderTabs()
}

function closeTab(key) {
  const idx = openTabs.findIndex(t => t.key === key)
  if (idx === -1) return
  const wasActive = openTabs[idx].key === tabKey(currentTaskType, currentThreadId)
  openTabs.splice(idx, 1)

  if (wasActive) {
    const next = openTabs[idx] || openTabs[idx - 1]
    if (next) {
      if (next.archived) selectArchivedThread(next.taskType, next.threadId)
      else selectThread(next.taskType, next.threadId, next.status)
    } else {
      // 남은 탭 없음 — 메시지 영역 비우고 안내
      currentThreadId = ''
      messagesEl.innerHTML = ''
      updateCurrentThreadBar('', '', '')
      inputEl.placeholder = '스레드를 선택하거나 새로 시작하세요'
      setInputEnabled(false)
      if (window.workflowPanel) window.workflowPanel.load(null, null)
      renderTabs()
    }
  } else {
    renderTabs()
  }
}

function dropTab(taskType, threadId) {
  // 탭만 제거 (삭제/보관 등 상위 로직이 선택 전환을 직접 처리하는 경우 사용)
  const key = tabKey(taskType, threadId)
  const before = openTabs.length
  openTabs = openTabs.filter(t => t.key !== key)
  if (openTabs.length !== before) renderTabs()
}

function renderTabs() {
  if (!threadTabsEl) return
  if (openTabs.length === 0) {
    threadTabsEl.classList.add('hidden')
    threadTabsEl.innerHTML = ''
    return
  }
  threadTabsEl.classList.remove('hidden')
  threadTabsEl.innerHTML = ''
  const activeKey = tabKey(currentTaskType, currentThreadId)
  openTabs.forEach(tab => {
    const cfg = taskConfigs[tab.taskType] || {}
    const el = document.createElement('div')
    el.className = 'thread-tab' + (tab.key === activeKey ? ' active' : '') + (tab.archived ? ' archived' : '')
    el.title = `${cfg.label || tab.taskType} · ${formatThreadLabel(tab.threadId)}`
    const icon = tab.archived ? '🗑' : tab.status === 'completed' ? '✓' : (cfg.icon || '💬')
    el.innerHTML =
      `<span class="tt-icon">${icon}</span>` +
      `<span class="tt-label">${escapeHtml(cfg.label || tab.taskType)} ${escapeHtml(formatThreadLabel(tab.threadId))}</span>` +
      `<span class="tt-close" title="탭 닫기">×</span>`
    el.addEventListener('click', (e) => {
      if (e.target.classList.contains('tt-close')) {
        e.stopPropagation()
        closeTab(tab.key)
        return
      }
      if (tab.key === activeKey) return
      if (tab.archived) selectArchivedThread(tab.taskType, tab.threadId)
      else selectThread(tab.taskType, tab.threadId, tab.status)
    })
    threadTabsEl.appendChild(el)
  })
}

// ── 에이전트 상태 바 ─────────────────────────────────────────

const STATE_META = {
  thinking: { icon: '🧠', text: '생각 중...' },
  running:  { icon: '⚙️', text: '도구 실행 중...' },
  waiting:  { icon: '⏳', text: '당신 차례 — 입력해 주세요' },
  idle:     { icon: '✓',  text: '완료' },
}

function setAgentState(state) {
  const meta = STATE_META[state] || STATE_META.thinking
  agentStateIcon.textContent = meta.icon
  agentStateText.textContent = meta.text
  // 상태별 클래스 → CSS에서 waiting(당신 차례)/running 시각 강조 (백로그 Q)
  agentStateBar.dataset.state = state
  // 끼어들기 버튼: 실행 중(thinking/running/waiting)만 노출, idle엔 숨김
  if (interjectBtn) interjectBtn.classList.toggle('hidden', state === 'idle')
  if (state === 'idle') {
    setTimeout(() => agentStateBar.classList.add('hidden'), 800)
    // 실행 종료 → 창 원복 (개선 아이디어 C)
    window.electronAPI?.agentIdle?.()
  } else {
    agentStateBar.classList.remove('hidden')
    // 화면 제어가 시작되는 running 상태에서만 창을 비킨다
    if (state === 'running') {
      window.electronAPI?.agentBusy?.(busyMode)
      updateAgentHud()
    } else if (state === 'waiting') {
      // 사용자 확인 팝업이 보이도록 창을 원복 (응답 후 다시 running 되면 재최소화)
      window.electronAPI?.agentIdle?.()
    }
    // thinking 상태는 running 사이의 짧은 단계 — 창을 건드리지 않아 깜빡임 방지
  }
}

// ── 실행 중 창 모드 (개선 아이디어 C) ─────────────────────────
let busyMode = localStorage.getItem('busyMode') || 'hud'
if (busyMode === 'minimize' && !localStorage.getItem('busyMode')) busyMode = 'hud'
const BUSYMODE_LABELS = { hud: '📌 작게 보기', minimize: '🪟 최소화', translucent: '👻 반투명', off: '🚫 끄기' }
const busymodeBtn = document.getElementById('busymode-btn')
const busymodeMenu = document.getElementById('busymode-menu')

function renderBusyMode() {
  if (busymodeBtn) busymodeBtn.textContent = BUSYMODE_LABELS[busyMode] || BUSYMODE_LABELS.hud
  busymodeMenu?.querySelectorAll('.hdr-menu-item').forEach(it =>
    it.classList.toggle('active', it.dataset.mode === busyMode))
}
busymodeBtn?.addEventListener('click', (e) => {
  e.stopPropagation()
  busymodeMenu.classList.toggle('hidden')
})
busymodeMenu?.querySelectorAll('.hdr-menu-item').forEach(item => {
  item.addEventListener('click', () => {
    busyMode = item.dataset.mode
    localStorage.setItem('busyMode', busyMode)
    busymodeMenu.classList.add('hidden')
    renderBusyMode()
  })
})
document.addEventListener('click', () => busymodeMenu?.classList.add('hidden'))
renderBusyMode()

function updateAgentHud(extra = {}) {
  if (busyMode !== 'hud') return
  const state = window.workflowPanel?.getSupervisorState?.()
  const goal = state?.goal && state.goal !== '대기 중' ? state.goal : '작업 실행 중'
  const step = state?.step && state.step !== '-' ? state.step : '단계 확인 중'
  const tool = _currentTool?.label || state?.currentToolLabel || '도구 준비 중'
  const elapsed = state?.elapsedMs ? ` · ${(state.elapsedMs / 1000).toFixed(0)}초` : ''
  const risk = state?.waitingApproval ? ` · 승인 필요(${state.risk || 'confirm'})` : ''
  const phase = state?.phase && state?.role ? ` · ${state.phase}/${state.role}` : ''
  window.electronAPI?.collabUpdateHud?.({
    mode: 'agent',
    title: '📌 작업 감독',
    hint: `${goal}\n${step}${phase}\n${tool}${elapsed}${risk}`,
    actionLabel: '자세히 보기',
    ...extra,
  })
}

// ── 실행 모드 토글 (G4): 자동 ↔ 계획 후 승인 ──────────────────
let currentAgentMode = localStorage.getItem('agentMode') || 'auto'
const planmodeBtn = document.getElementById('planmode-btn')
function renderPlanMode() {
  if (!planmodeBtn) return
  planmodeBtn.textContent = currentAgentMode === 'plan' ? '📋 계획 모드' : '⚡ 자동'
  planmodeBtn.classList.toggle('active', currentAgentMode === 'plan')
}
planmodeBtn?.addEventListener('click', () => {
  currentAgentMode = currentAgentMode === 'plan' ? 'auto' : 'plan'
  localStorage.setItem('agentMode', currentAgentMode)
  renderPlanMode()
})
renderPlanMode()

function setContextUsage(tokensUsed, tokensTotal) {
  const pct = Math.min(100, Math.round((tokensUsed / tokensTotal) * 100))
  contextFill.style.width = pct + '%'
  contextFill.className = 'context-fill' + (pct > 80 ? ' warn' : pct > 95 ? ' crit' : '')
  contextLabel.textContent = `${(tokensUsed / 1000).toFixed(1)}k / ${(tokensTotal / 1000).toFixed(0)}k`
  contextBar.classList.remove('hidden')
}

stopBtn.addEventListener('click', async () => {
  if (!currentRequestId) return
  try {
    await fetch(`${BASE_URL}/stop/${currentRequestId}`, { method: 'POST' })
  } catch {}
})

// 백로그 Q: 끼어들기 버튼 — 입력칸 내용을 작업을 멈추지 않고 주입한다.
interjectBtn?.addEventListener('click', () => {
  const text = inputEl.value.trim()
  if (!text || !currentRequestId) return
  inputEl.value = ''
  autoGrowInput()
  injectMessage(text)
})

const PROFILE_LABELS = {
  openai: 'OpenAI',
  internal: '사내 LLM'
}

// 프로파일 UI
async function loadProfile() {
  try {
    const res = await fetch(`${BASE_URL}/profile`)
    const { active, profiles } = await res.json()
    renderProfileBtn(active)
    renderProfileMenu(active, profiles)
    profileSwitcher.classList.remove('hidden')
  } catch {}
}

function renderProfileBtn(active) {
  profileBtn.textContent = PROFILE_LABELS[active] ?? active
  profileBtn.className = `profile-btn ${active}`
}

function renderProfileMenu(active, profiles) {
  profileMenu.innerHTML = profiles.map(p => `
    <div class="profile-menu-item ${p === active ? 'active' : ''}" data-profile="${p}">
      ${p === active ? '✓ ' : ''}${PROFILE_LABELS[p] ?? p}
    </div>
  `).join('')

  profileMenu.querySelectorAll('.profile-menu-item').forEach(item => {
    item.addEventListener('click', async () => {
      const name = item.dataset.profile
      profileMenu.classList.add('hidden')
      try {
        await fetch(`${BASE_URL}/profile/${name}`, { method: 'POST' })
        await loadProfile()
        await loadModels()  // 프로파일 전환 시 모델 목록도 갱신
      } catch (e) {
        statusEl.textContent = `● 전환 실패: ${e.message}`
      }
    })
  })
}

profileBtn.addEventListener('click', (e) => {
  e.stopPropagation()
  profileMenu.classList.toggle('hidden')
})
document.addEventListener('click', () => profileMenu.classList.add('hidden'))

// ── 모델 선택 (개선 아이디어 D) ───────────────────────────────
const modelSwitcher = document.getElementById('model-switcher')
const modelBtn = document.getElementById('model-btn')
const modelMenu = document.getElementById('model-menu')

function shortModelName(name) {
  return name.length > 22 ? '…' + name.slice(-21) : name
}

async function loadModels() {
  try {
    const res = await fetch(`${BASE_URL}/models`)
    const { current, default: dflt, models, source } = await res.json()
    modelBtn.textContent = '🤖 ' + shortModelName(current)
    modelBtn.title = `현재 모델: ${current}\n목록 출처: ${source === 'dynamic' ? '서버 동적 조회' : '.env 프리셋'}`

    const srcLabel = source === 'dynamic' ? '서버 모델' : '프리셋 (.env)'
    let html = `<div class="hdr-menu-group-label">${srcLabel}</div>`
    html += models.map(m => `
      <div class="hdr-menu-item ${m === current ? 'active' : ''}" data-model="${escapeHtml(m)}">
        ${m === current ? '✓ ' : ''}${escapeHtml(m)}
      </div>`).join('')
    html += `<div class="hdr-menu-group-label">기타</div>`
    html += `<div class="hdr-menu-item" data-model="__default__">↺ 기본값 (${escapeHtml(shortModelName(dflt))})</div>`
    modelMenu.innerHTML = html

    modelMenu.querySelectorAll('.hdr-menu-item').forEach(item => {
      item.addEventListener('click', async () => {
        modelMenu.classList.add('hidden')
        try {
          await fetch(`${BASE_URL}/models/${encodeURIComponent(item.dataset.model)}`, { method: 'POST' })
          await loadModels()
        } catch (e) { console.error('모델 전환 실패', e) }
      })
    })
    modelSwitcher.classList.remove('hidden')
  } catch { modelSwitcher.classList.add('hidden') }
}

modelBtn?.addEventListener('click', (e) => {
  e.stopPropagation()
  modelMenu.classList.toggle('hidden')
})
document.addEventListener('click', () => modelMenu.classList.add('hidden'))

// 서버가 뜰 때까지 직접 폴링 (IPC 타이밍 문제 회피)
async function initWhenReady() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`${BASE_URL}/health`)
      if (res.ok) {
        statusEl.textContent = '● 준비됨'
        statusEl.className = 'status ready'
        setInputEnabled(true)
        await Promise.all([loadProfile(), loadModels(), loadTaskConfig()])
        await openTask('general')
        return
      }
    } catch {}
    await new Promise(r => setTimeout(r, 500))
  }
  statusEl.textContent = '● 서버 연결 실패'
  statusEl.className = 'status error'
}

initWhenReady()

function setInputEnabled(enabled) {
  // 백로그 Q: 실행 중에도 입력칸·확대 에디터는 열어 둬 끼어들기를 칠 수 있게 한다.
  // 새 메시지 전송(전송 버튼)만 비활성 — 실행 중엔 끼어들기 버튼/Enter로 주입한다.
  inputEl.disabled = false
  sendBtn.disabled = !enabled
  if (inputExpandBtn) inputExpandBtn.disabled = false
}

// ── 입력칸 자동 높이 확장 (백로그 R) ──────────────────────────
// 내용에 따라 textarea 높이를 늘리고, 최대치(뷰포트 40%)서 스크롤로 전환.
function autoGrowInput() {
  inputEl.style.height = 'auto'
  const max = Math.round(window.innerHeight * 0.4)
  const next = Math.min(inputEl.scrollHeight, max)
  inputEl.style.height = next + 'px'
  inputEl.style.overflowY = inputEl.scrollHeight > max ? 'auto' : 'hidden'
}

// 메시지 전송
async function sendMessage(text) {
  if (!text.trim()) return
  setInputEnabled(false)

  // 환영 메시지가 있으면 제거 (첫 메시지 전송 시)
  const welcome = messagesEl.querySelector('.thread-welcome')
  if (welcome) welcome.remove()

  appendUserMessage(text)
  const agentEl = appendAgentMessage()

  try {
    const response = await fetch(`${BASE_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        thread_id: currentThreadId,
        task_type: currentTaskType,
        agent_mode: currentAgentMode
      })
    })

    if (!response.ok) throw new Error(`서버 오류 ${response.status}`)

    await readStream(response, agentEl)
  } catch (e) {
    agentEl.querySelector('.msg-bubble').textContent = `오류: ${e.message}`
  } finally {
    setInputEnabled(true)
    inputEl.focus()
    refreshActiveRuns()
  }
}

// SSE 스트림 파싱
async function readStream(response, agentEl) {
  const bubble = agentEl.querySelector('.msg-bubble')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop()

    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data: ')) continue
      try {
        const event = JSON.parse(line.slice(6))
        handleEvent(event, agentEl, bubble)
      } catch {}
    }
  }
}

// tool_start별 시작 시각 (로그 duration 계산용)
const _toolStartTimes = {}

// 실행 중 도구의 경과시간 타이머 + 현재 도구(상태바 표시용) — 가시성(A3)
const _toolTimers = {}
let _currentTool = null

function _updateRunningStatebar(secs) {
  if (!agentStateText || !_currentTool) return
  const lbl = _currentTool.label || '도구 실행'
  agentStateText.textContent = secs >= 1 ? `${lbl} — ${secs}초` : `${lbl}…`
  updateAgentHud()
}

function _startToolTimer(tool) {
  _stopToolTimer(tool)
  _toolTimers[tool] = setInterval(() => {
    const start = _toolStartTimes[tool]
    if (!start) return
    const secs = Math.floor((Date.now() - start) / 1000)
    const step = agentEl && agentEl.querySelector(`.tool-step[data-tool="${tool}"]`)
    if (step) {
      const el = step.querySelector('.tool-elapsed')
      if (el) el.textContent = secs >= 1 ? ` · ${secs}초` : ''
    }
    if (_currentTool && _currentTool.tool === tool) _updateRunningStatebar(secs)
  }, 1000)
}

function _stopToolTimer(tool) {
  if (_toolTimers[tool]) { clearInterval(_toolTimers[tool]); delete _toolTimers[tool] }
}

function _stopAllToolTimers() {
  Object.keys(_toolTimers).forEach(_stopToolTimer)
  _currentTool = null
  stopBtn && stopBtn.classList.remove('pulse')
}

// ── S: 명령 로그 접힘 ─────────────────────────────────────────
// 스크립트/명령 도구나 긴 출력은 기본 접힘(요약+토글), 에러는 펼침.
const _SCRIPT_TOOLS = new Set([
  'run_command', 'run_powershell', 'start_process',
])
const _LONG_RESULT_CHARS = 200

function buildToolResult(tool, text, isError) {
  const isScript = _SCRIPT_TOOLS.has(tool)
  const isLong = text.length > _LONG_RESULT_CHARS
  // 짧은 비스크립트 결과 + 비에러 → 기존처럼 평문 노출
  if (!isError && !isScript && !isLong) {
    const el = document.createElement('div')
    el.className = 'tool-result'
    el.textContent = text
    return el
  }
  // 그 외 → 접이식 (에러는 기본 펼침)
  const wrap = document.createElement('div')
  wrap.className = 'tool-result collapsible' +
    (isError ? ' error' : ' collapsed') + (isScript ? ' script' : '')
  const firstLine = (text.split('\n').find(l => l.trim()) || text).trim()
  const summary = firstLine.length > 80 ? firstLine.slice(0, 79) + '…' : firstLine
  const lineCount = text.split('\n').length

  const toggle = document.createElement('div')
  toggle.className = 'tr-toggle'
  toggle.innerHTML =
    `<span class="tr-chevron">${isError ? '▾' : '▸'}</span>` +
    `<span class="tr-summary">${escapeHtml(summary)}</span>` +
    (lineCount > 1 ? `<span class="tr-meta">${lineCount}줄</span>` : '')
  const body = document.createElement('div')
  body.className = 'tr-body'
  body.textContent = text

  toggle.addEventListener('click', () => {
    const collapsed = wrap.classList.toggle('collapsed')
    wrap.querySelector('.tr-chevron').textContent = collapsed ? '▸' : '▾'
  })
  wrap.appendChild(toggle)
  wrap.appendChild(body)
  return wrap
}

function handleEvent(event, agentEl, bubble) {
  if (window.workflowPanel?.handleEvent) window.workflowPanel.handleEvent(event)

  // type 없이 request_id만 있는 경우 (최초 SSE)
  if (event.request_id && !event.type) {
    currentRequestId = event.request_id
    return
  }

  switch (event.type) {
    case 'text':
      if (!bubble.dataset.rawText) bubble.dataset.rawText = '';
      bubble.dataset.rawText += event.content;
      bubble.innerHTML = renderMarkdown(bubble.dataset.rawText);
      if (agentStateText) agentStateText.textContent = '✍️ 답변 작성 중...'
      scrollToBottom()
      break

    case 'tool_start': {
      _toolStartTimes[event.tool] = Date.now()
      const step = document.createElement('div')
      step.className = 'tool-step running'
      step.dataset.tool = event.tool
      step.innerHTML = `<span class="icon">⏳</span> <span class="tool-label">${event.label}</span><span class="tool-elapsed"></span>`
      agentEl.querySelector('.msg-bubble').before(step)
      // 경과 타이머 시작 + 상태바에 현재 도구 표시 (가시성 A3)
      _currentTool = { tool: event.tool, label: event.label }
      _updateRunningStatebar(0)
      _startToolTimer(event.tool)
      updateAgentHud()
      scrollToBottom()
      break
    }

    case 'tool_wait': {
      // 도구가 예상보다 오래 걸려 타임아웃을 연장하는 중 — 의도 내레이션 + 중단 강조
      const step = agentEl && agentEl.querySelector(`.tool-step[data-tool="${event.tool}"]`)
      if (step) {
        step.classList.add('slow')
        let hint = step.querySelector('.tool-wait-hint')
        if (!hint) {
          hint = document.createElement('span')
          hint.className = 'tool-wait-hint'
          step.appendChild(hint)
        }
        hint.textContent = ` ⏳ 예상보다 길어 더 기다리는 중… (~${event.next}s, 필요하면 중단)`
      }
      if (stopBtn) stopBtn.classList.add('pulse')
      if (agentStateText) agentStateText.textContent = '⏳ 도구 대기 중 (시간 연장)...'
      updateAgentHud()
      scrollToBottom()
      break
    }

    case 'tool_done': {
      const duration = _toolStartTimes[event.tool]
        ? Date.now() - _toolStartTimes[event.tool]
        : null
      delete _toolStartTimes[event.tool]

      const isError = event.result && event.result.startsWith('툴 실행 오류')
      _stopToolTimer(event.tool)
      if (_currentTool && _currentTool.tool === event.tool) _currentTool = null
      if (stopBtn) stopBtn.classList.remove('pulse')
      const step = agentEl.querySelector(`.tool-step[data-tool="${event.tool}"]`)
      if (step) {
        step.className = isError ? 'tool-step error' : 'tool-step done'
        step.querySelector('.icon').textContent = isError ? '✗' : '✓'
      }
      if (event.result) {
        const result = buildToolResult(event.tool, event.result, isError)
        agentEl.querySelector('.msg-bubble').before(result)
      }
      scrollToBottom()

      // 실행 로그에 추가 + 현재 진행 노드에 인라인 로그 적재 (백로그 U/S)
      if (window.workflowPanel) {
        window.workflowPanel.appendLog(event.tool, event.result || '', duration)
        window.workflowPanel.recordToolLog(event.tool, event.result || '')
      }
      updateAgentHud()
      break
    }

    case 'confirm':
      updateAgentHud()
      showConfirmDialog(event).catch(console.error)
      break

    case 'agent_state':
      if (event.state === 'idle') _stopAllToolTimers()
      setAgentState(event.state)
      break

    case 'context_usage':
      setContextUsage(event.tokens_used, event.tokens_total)
      break

    case 'workflow_update':
      if (window.workflowPanel) window.workflowPanel.handleUpdate(event.workflow)
      updateAgentHud()
      break

    case 'context_trim': {
      // M4: 컨텍스트 초과 복구로 payload를 줄였음을 사용자에게 투명하게 고지
      const note = document.createElement('div')
      note.className = 'context-trim-note'
      note.textContent = `🧹 ${event.action || '컨텍스트를 정리해 재시도했습니다.'}`
      agentEl.querySelector('.msg-bubble').before(note)
      if (agentStateText) agentStateText.textContent = '🧹 컨텍스트 정리하여 재시도 중...'
      scrollToBottom()
      break
    }

    case 'injected': {
      // 백로그 Q: 끼어든 메시지가 다음 단계에서 반영됐음을 투명 고지
      const note = document.createElement('div')
      note.className = 'context-trim-note'
      note.textContent = '↩ 끼어든 메시지를 반영합니다.'
      agentEl.querySelector('.msg-bubble').before(note)
      if (agentStateText) agentStateText.textContent = '↩ 피드백 반영 중...'
      scrollToBottom()
      break
    }

    case 'harness_round': {
      // 백로그 N PoC: Executor→Reviewer 하네스 라운드 전환 고지
      const badge = document.createElement('div')
      badge.className = 'context-trim-note'
      if (event.phase === 'reviewing') {
        badge.textContent = `🔍 검증 중 (라운드 ${event.round})…`
        if (agentStateText) agentStateText.textContent = `🔍 결과 검증 중 (라운드 ${event.round})`
      } else if (event.phase === 'retrying') {
        badge.textContent = `↺ 재시도 중 (라운드 ${event.round + 1}): ${event.feedback || ''}`
        if (agentStateText) agentStateText.textContent = `↺ 검증 실패하여 재시도 중 (라운드 ${event.round + 1})`
      }
      agentEl.querySelector('.msg-bubble').before(badge)
      scrollToBottom()
      break
    }

    case 'vision_capture': {
      // 에이전트가 직접 본 화면을 채팅에 썸네일로 표시
      if (event.image_b64) {
        const img = document.createElement('img')
        img.className = 'chat-screenshot'
        img.src = `data:image/png;base64,${event.image_b64}`
        img.alt = '캡처한 화면'
        agentEl.querySelector('.msg-bubble').before(img)
        scrollToBottom()
      }
      break
    }

    case 'done':
      currentRequestId = ''
      if (!bubble.textContent) bubble.textContent = '완료되었습니다.'
      break

    case 'error':
      bubble.textContent = `오류: ${event.message}`
      break
  }
}

// ── 사용자 확인 팝업 ─────────────────────────────────────────

function getOptionIcon(label) {
  if (label.includes('예') || label.includes('계속') || label.includes('진행')) return '✅'
  if (label.includes('항상')) return '🔓'
  if (label.includes('아니오') || label.includes('중단') || label.includes('취소')) return '❌'
  if (label.includes('방법') || label.includes('제안') || label.includes('변경')) return '💡'
  if (label.includes('의견') || label.includes('입력') || label.includes('전달')) return '✏️'
  return '•'
}

// 텍스트 입력이 필요한 옵션인지 판단
const TEXT_INPUT_KEYWORDS = ['방법 변경', '제안', '의견', '입력', '전달', '기타']
function needsTextInput(label) {
  return TEXT_INPUT_KEYWORDS.some(k => label.includes(k))
}

let _confirmQueueCount = 0

async function showConfirmDialog({ confirm_id, question, options, risk, command }) {
  _confirmQueueCount++
  const mySeq = _confirmQueueCount

  return new Promise((resolve) => {
    const overlay = document.createElement('div')
    overlay.className = 'confirm-overlay'

    const optBtns = options.map((opt, i) => `
      <button class="confirm-opt-btn" data-index="${i}" data-label="${escapeHtml(opt)}">
        <span class="confirm-opt-icon">${getOptionIcon(opt)}</span>
        <span>${escapeHtml(opt)}</span>
      </button>
    `).join('')

    const isDestructive = risk === 'destructive'
    const header = isDestructive ? '⛔ 위험 작업 확인' : '⚠ 에이전트 확인 요청'
    const cmdBlock = command
      ? `<div class="confirm-command">${escapeHtml(command)}</div>`
      : ''

    const seqBadge = mySeq > 1
      ? `<span class="confirm-seq-badge">${mySeq}</span>`
      : ''

    overlay.innerHTML = `
      <div class="confirm-dialog${isDestructive ? ' confirm-destructive' : ''}">
        <div class="confirm-header">${header}${seqBadge}</div>
        <div class="confirm-question">${escapeHtml(question)}</div>
        ${cmdBlock}
        <div class="confirm-options">${optBtns}</div>
        <div class="confirm-textarea-wrap hidden">
          <textarea class="confirm-textarea" placeholder="내용을 입력하세요..."></textarea>
          <div class="confirm-actions">
            <button class="confirm-cancel-text-btn">취소</button>
            <button class="confirm-send-btn">전송</button>
          </div>
        </div>
      </div>
    `
    document.body.appendChild(overlay)

    const textWrap = overlay.querySelector('.confirm-textarea-wrap')
    const textarea  = overlay.querySelector('.confirm-textarea')
    let selectedLabel = null

    async function submit(choice, customText = '') {
      _confirmQueueCount = Math.max(0, _confirmQueueCount - 1)
      overlay.remove()
      try {
        await fetch(`${BASE_URL}/confirm/${confirm_id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ choice, custom_text: customText }),
        })
      } catch (e) { console.error('confirm submit error', e) }
      resolve()
    }

    overlay.querySelectorAll('.confirm-opt-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const label = btn.dataset.label
        if (needsTextInput(label)) {
          overlay.querySelectorAll('.confirm-opt-btn').forEach(b => b.classList.remove('selected'))
          btn.classList.add('selected')
          selectedLabel = label
          textWrap.classList.remove('hidden')
          textarea.focus()
        } else {
          submit(label)
        }
      })
    })

    overlay.querySelector('.confirm-send-btn').addEventListener('click', () => {
      submit(selectedLabel || options[0], textarea.value.trim())
    })

    overlay.querySelector('.confirm-cancel-text-btn').addEventListener('click', () => {
      textWrap.classList.add('hidden')
      overlay.querySelectorAll('.confirm-opt-btn').forEach(b => b.classList.remove('selected'))
      selectedLabel = null
    })

    // Esc로 닫기 (중단으로 처리)
    const onKey = (e) => {
      if (e.key === 'Escape') {
        document.removeEventListener('keydown', onKey)
        submit('중단')
      }
    }
    document.addEventListener('keydown', onKey)
  })
}

function appendUserMessage(text) {
  const el = document.createElement('div')
  el.className = 'message user'
  el.innerHTML = `<div class="msg-role">나</div><div class="msg-bubble">${renderMarkdown(text)}</div>`
  messagesEl.appendChild(el)
  scrollToBottom(true)
}

function appendAgentMessage() {
  const el = document.createElement('div')
  el.className = 'message agent'
  el.innerHTML = `<div class="msg-role">Agent</div><div class="msg-bubble"></div>`
  messagesEl.appendChild(el)
  scrollToBottom()
  return el
}

const scrollJumpBtn = document.getElementById('scroll-jump-btn')

function scrollToBottom(force = false) {
  if (force || window.ScrollUtils.isNearBottom(messagesEl)) {
    messagesEl.scrollTop = messagesEl.scrollHeight
    if (scrollJumpBtn) scrollJumpBtn.classList.add('hidden')
  } else {
    if (scrollJumpBtn) scrollJumpBtn.classList.remove('hidden')
  }
}

scrollJumpBtn?.addEventListener('click', () => scrollToBottom(true))

messagesEl.addEventListener('scroll', () => {
  if (window.ScrollUtils.isNearBottom(messagesEl) && scrollJumpBtn) {
    scrollJumpBtn.classList.add('hidden')
  }
})

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // 1. 코드 블록 치환 (```lang\ncode```)
  const codeBlocks = [];
  const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  html = html.replace(codeBlockRegex, (match, lang, code) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push({ lang, code });
    return placeholder;
  });

  // 2. 인라인 코드: `code`
  html = html.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');

  // 3. 굵게: **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // 4. 기울임: *text*
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // 5. 링크: [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="markdown-link">$1</a>');

  // 6. 목록 처리 (- item 또는 * item)
  const lines = html.split('\n');
  let inList = false;
  const processedLines = lines.map(line => {
    const match = line.match(/^\s*[-*]\s+(.*)$/);
    if (match) {
      const content = match[1];
      if (!inList) {
        inList = true;
        return '<ul><li>' + content + '</li>';
      }
      return '<li>' + content + '</li>';
    } else {
      if (inList) {
        inList = false;
        return '</ul>' + line;
      }
      return line;
    }
  });
  if (inList) {
    processedLines.push('</ul>');
  }
  html = processedLines.join('\n');

  // 7. 일반 개행 -> <br>
  html = html.replace(/\n/g, '<br>');

  // 8. 코드 블록 복원 (Copy 버튼 포함)
  codeBlocks.forEach((block, idx) => {
    const placeholder = `__CODE_BLOCK_${idx}__`;
    const cleanCode = block.code.trim();
    const codeBlockHtml = `
<div class="code-block-wrapper" data-code="${encodeURIComponent(cleanCode)}">
  <div class="code-block-header">
    <span class="code-block-lang">${block.lang || 'code'}</span>
    <button class="code-block-copy-btn" onclick="copyCodeBlock(this)">Copy</button>
  </div>
  <pre><code class="language-${block.lang}">${cleanCode}</code></pre>
</div>`.trim();
    html = html.replace(placeholder, codeBlockHtml);
  });

  return html;
}

window.copyCodeBlock = function(btn) {
  const wrapper = btn.closest('.code-block-wrapper');
  if (!wrapper) return;
  const code = decodeURIComponent(wrapper.dataset.code);
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  }).catch(() => {
    const textarea = document.createElement('textarea');
    textarea.value = code;
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = 'Copy';
        btn.classList.remove('copied');
      }, 2000);
    } catch (e) {}
    document.body.removeChild(textarea);
  });
}

function showWelcome(taskType) {
  const cfg = taskConfigs[taskType] || {}
  const el = document.createElement('div')
  el.className = 'thread-welcome'
  const escapedDesc = escapeHtml(cfg.description || '').replace(/\n/g, '<br>')
  el.innerHTML =
    `<div class="welcome-icon">${cfg.icon || '💬'}</div>` +
    `<div class="welcome-title">${escapeHtml(cfg.label || taskType)}</div>` +
    `<div class="welcome-desc">${escapedDesc}</div>` +
    `<div class="welcome-hint">메시지를 입력하거나 여기를 클릭해서 시작하세요</div>`
  el.addEventListener('click', () => inputEl.focus())
  messagesEl.appendChild(el)
}

// ── 스레드 관리 ──────────────────────────────────────────────

function formatThreadLabel(threadId) {
  const m = threadId.match(/^(\d{4})-(\d{2})-(\d{2})-(\d{3})$/)
  if (!m) return '#' + threadId.slice(-3)
  const [, year, month, day, num] = m
  const now = new Date()
  const isToday = now.getFullYear() === +year &&
                  now.getMonth() + 1 === +month &&
                  now.getDate() === +day
  return isToday ? `#${num}` : `${month}/${day} #${num}`
}

async function loadTaskConfig() {
  try {
    const res = await fetch(`${BASE_URL}/task-config`)
    taskConfigs = await res.json()
    renderTaskGroups()
  } catch {}
}

// ── 사이드바 그룹 관리 ────────────────────────────────────────

function renderTaskGroups() {
  const container = document.getElementById('task-groups-container')
  if (!container) return
  container.innerHTML = ''
  Object.entries(taskConfigs).forEach(([taskType, cfg]) => {
    const group = document.createElement('div')
    group.className = 'task-group'
    group.dataset.task = taskType
    group.innerHTML = `
      <div class="task-group-header">
        <span class="tg-arrow">▸</span>
        <span class="tg-name">${escapeHtml(cfg.icon || '')} ${escapeHtml(cfg.label || taskType)}</span>
        <span class="tg-badge hidden"></span>
        <button class="tg-new-btn" title="새 스레드">＋</button>
      </div>
      <div class="task-group-body hidden"></div>
    `
    bindTaskGroup(group)
    container.appendChild(group)
  })
}

function bindTaskGroup(group) {
  const header = group.querySelector('.task-group-header')
  const newBtn = group.querySelector('.tg-new-btn')
  header?.addEventListener('click', (e) => {
    if (e.target.closest('.tg-new-btn')) return
    const taskType = group.dataset.task
    if (!expandedGroups.has(taskType) || currentTaskType !== taskType) {
      openTask(taskType)
    } else {
      collapseGroup(taskType)
    }
  })
  newBtn?.addEventListener('click', (e) => {
    e.stopPropagation()
    createNewThread(group.dataset.task)
  })
}

function getGroupEl(taskType) {
  return document.querySelector(`.task-group[data-task="${taskType}"]`)
}
function getGroupBody(taskType) {
  return document.querySelector(`.task-group[data-task="${taskType}"] .task-group-body`)
}

function expandGroup(taskType) {
  const group = getGroupEl(taskType)
  if (!group) return
  expandedGroups.add(taskType)
  getGroupBody(taskType).classList.remove('hidden')
  group.querySelector('.tg-arrow').textContent = '▾'
  group.classList.add('expanded')
}

function collapseGroup(taskType) {
  const group = getGroupEl(taskType)
  if (!group) return
  expandedGroups.delete(taskType)
  getGroupBody(taskType).classList.add('hidden')
  group.querySelector('.tg-arrow').textContent = '▸'
  group.classList.remove('expanded')
}

function updateGroupBadge(taskType, activeCount) {
  const badge = document.querySelector(`.task-group[data-task="${taskType}"] .tg-badge`)
  if (!badge) return
  if (activeCount > 0) {
    badge.textContent = activeCount
    badge.classList.remove('hidden')
  } else {
    badge.classList.add('hidden')
  }
}

function updateCurrentThreadBar(taskType, threadId, status) {
  if (!threadId) {
    currentThreadBar.classList.add('hidden')
    return
  }
  const cfg = taskConfigs[taskType] || {}
  currentThreadInfo.textContent = `${cfg.icon || ''} ${cfg.label || taskType}  ·  ${formatThreadLabel(threadId)}`
  currentThreadBar.classList.remove('hidden')
  threadCloseCurrentBtn.classList.toggle('hidden', status !== 'in_progress')
}

function _addAction(container, text, title, handler, variant = '') {
  const btn = document.createElement('span')
  btn.className = `ti-act${variant ? ' ti-act-' + variant : ''}`
  btn.textContent = text
  btn.title = title
  btn.addEventListener('click', (e) => { e.stopPropagation(); handler() })
  container.appendChild(btn)
}

function renderThreadItem(container, taskType, t, isArchived) {
  const item = document.createElement('div')
  const isActive = t.thread_id === currentThreadId && currentTaskType === taskType
  const statusIcon = isArchived ? '🗑' : t.status === 'completed' ? '✓' : '●'
  const cls = isArchived ? 'archived' : t.status === 'completed' ? 'completed' : 'in-progress'
  item.className = `thread-item ${cls}${isActive ? ' selected' : ''}`
  item.dataset.threadId = t.thread_id

  const label = formatThreadLabel(t.thread_id)
  const title = t.title && t.title !== t.thread_id ? t.title : ''
  const msgBadge = t.message_count > 0 ? `<span class="ti-count">${t.message_count}</span>` : ''

  item.innerHTML = `
    <span class="ti-status">${statusIcon}</span>
    <div class="ti-text">
      <span class="ti-label">${escapeHtml(label)}</span>
      ${title ? `<span class="ti-title">${escapeHtml(title)}</span>` : ''}
    </div>
    ${msgBadge}
    <div class="ti-actions"></div>
  `

  const actions = item.querySelector('.ti-actions')

  if (isArchived) {
    _addAction(actions, '↑', '보관 전으로 복원', () => restoreArchivedThread(taskType, t.thread_id))
    _addAction(actions, '×', '영구 삭제', () => deleteThreadFromSidebar(taskType, t.thread_id, true), 'delete')
    item.addEventListener('click', () => selectArchivedThread(taskType, t.thread_id))
  } else {
    if (t.status === 'in_progress') {
      _addAction(actions, '✓', '완료하기', async () => {
        currentThreadId = t.thread_id
        currentTaskType = taskType
        await closeCurrentThread()
      })
    } else if (t.status === 'completed') {
      _addAction(actions, '↺', '진행 중으로 재개', () => restoreThread(taskType, t.thread_id))
    }
    _addAction(actions, '↓', '보관함으로 이동', () => archiveThread(taskType, t.thread_id))
    _addAction(actions, '×', '영구 삭제', () => deleteThreadFromSidebar(taskType, t.thread_id, false), 'delete')
    item.addEventListener('click', () => selectThread(taskType, t.thread_id, t.status))
  }

  container.appendChild(item)
}

async function renderSidebarThreads(taskType) {
  let threads = []
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}`)
    threads = await res.json()
  } catch {}

  const activeCount = threads.filter(t => t.status === 'in_progress').length
  updateGroupBadge(taskType, activeCount)
  refreshActiveRuns()

  // 스레드가 1개 이상이면 "+ 새 시작" 버튼 강조
  const newBtn = document.querySelector(`.task-group[data-task="${taskType}"] .tg-new-btn`)
  if (newBtn) {
    newBtn.classList.toggle('tg-new-btn--highlight', threads.length > 0)
  }

  const body = getGroupBody(taskType)
  if (!body || !expandedGroups.has(taskType)) return threads

  body.innerHTML = ''

  if (threads.length === 0) {
    const empty = document.createElement('div')
    empty.className = 'tg-empty'
    empty.textContent = '스레드 없음'
    body.appendChild(empty)
  } else {
    threads.forEach(t => renderThreadItem(body, taskType, t, false))
  }

  // 보관 섹션
  const isArchiveOpen = showingArchiveGroups.has(taskType)
  const archiveHeader = document.createElement('div')
  archiveHeader.className = 'tg-archive-toggle'
  const archiveBody = document.createElement('div')
  archiveBody.className = 'tg-archive-body'

  let archivedThreads = []
  if (isArchiveOpen) {
    try {
      const res = await fetch(`${BASE_URL}/threads/${taskType}?archived=true`)
      archivedThreads = await res.json()
    } catch {}
    if (archivedThreads.length > 0) {
      archivedThreads.forEach(t => renderThreadItem(archiveBody, taskType, t, true))
    } else {
      const empty = document.createElement('div')
      empty.className = 'tg-empty'
      empty.textContent = '보관된 스레드 없음'
      archiveBody.appendChild(empty)
    }
  } else {
    archiveBody.classList.add('hidden')
  }

  const archivedLabel = archivedThreads.length > 0 ? ` ${archivedThreads.length}개` : ''
  archiveHeader.innerHTML = `<span class="tg-archive-arrow">${isArchiveOpen ? '▾' : '▸'}</span><span>보관${archivedLabel}</span>`
  archiveHeader.addEventListener('click', async () => {
    if (showingArchiveGroups.has(taskType)) showingArchiveGroups.delete(taskType)
    else showingArchiveGroups.add(taskType)
    await renderSidebarThreads(taskType)
  })

  body.appendChild(archiveHeader)
  body.appendChild(archiveBody)

  return threads
}

async function openTask(taskType) {
  currentTaskType = taskType
  messagesEl.innerHTML = ''
  inputEl.disabled = true
  sendBtn.disabled = true

  expandGroup(taskType)
  const threads = await renderSidebarThreads(taskType)

  const best = threads.find(t => t.message_count > 0 && t.status === 'in_progress')
    || threads.find(t => t.status === 'in_progress')
    || threads[0]

  if (best) {
    await selectThread(taskType, best.thread_id, best.status)
  } else {
    await createNewThread(taskType)
  }
}

async function archiveThread(taskType, threadId) {
  const wasActive = currentThreadId === threadId && currentTaskType === taskType
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}`, { method: 'DELETE' })
    dropTab(taskType, threadId)
    const threads = await renderSidebarThreads(taskType)
    if (wasActive) {
      currentThreadId = ''
      messagesEl.innerHTML = ''
      updateCurrentThreadBar(taskType, '', '')
      const next = threads.find(t => t.status === 'in_progress')
      if (next) {
        await selectThread(taskType, next.thread_id, next.status)
      } else {
        const cfg = taskConfigs[taskType] || {}
        inputEl.placeholder = `${cfg.label} — 스레드를 선택하거나 새로 시작하세요`
        inputEl.disabled = true
        sendBtn.disabled = true
      }
    }
  } catch (e) { console.error('스레드 보관 실패', e) }
}

async function selectArchivedThread(taskType, threadId) {
  currentThreadId = threadId
  currentTaskType = taskType
  document.querySelectorAll('.thread-item').forEach(item => {
    item.classList.toggle('selected', item.dataset.threadId === threadId && item.classList.contains('archived'))
  })
  updateCurrentThreadBar(taskType, threadId, 'archived')
  openOrFocusTab(taskType, threadId, 'archived', true)
  messagesEl.innerHTML = ''
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/messages?archived=true`)
    const msgs = await res.json()
    msgs.forEach(m => {
      if (m.role === 'user') appendUserMessage(m.content)
      else if (m.role === 'assistant') {
        const el = appendAgentMessage()
        const bubble = el.querySelector('.msg-bubble')
        bubble.dataset.rawText = m.content
        bubble.innerHTML = renderMarkdown(m.content)
      }
    })
  } catch {}
  inputEl.placeholder = '(보관된 스레드 — 읽기 전용)'
  inputEl.disabled = true
  sendBtn.disabled = true
}

async function restoreThread(taskType, threadId) {
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/restore`, { method: 'POST' })
    const threads = await renderSidebarThreads(taskType)
    const t = threads.find(t => t.thread_id === threadId)
    await selectThread(taskType, threadId, t ? t.status : 'in_progress')
  } catch (e) { console.error('스레드 복원 실패', e) }
}

async function restoreArchivedThread(taskType, threadId) {
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/unarchive`, { method: 'POST' })
    showingArchiveGroups.delete(taskType)
    const threads = await renderSidebarThreads(taskType)
    const t = threads.find(t => t.thread_id === threadId)
    if (t) await selectThread(taskType, threadId, t.status)
  } catch (e) { console.error('보관 스레드 복원 실패', e) }
}

async function deleteThreadFromSidebar(taskType, threadId, isArchived) {
  const wasActive = currentThreadId === threadId && currentTaskType === taskType
  const qs = isArchived ? '?archived=true' : ''
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/permanent${qs}`, { method: 'DELETE' })
    dropTab(taskType, threadId)
    const threads = await renderSidebarThreads(taskType)
    if (wasActive) {
      currentThreadId = ''
      messagesEl.innerHTML = ''
      updateCurrentThreadBar(taskType, '', '')
      const next = threads.find(t => t.status === 'in_progress')
      if (next) {
        await selectThread(taskType, next.thread_id, next.status)
      } else {
        const cfg = taskConfigs[taskType] || {}
        inputEl.placeholder = `${cfg.label} — 스레드를 선택하거나 새로 시작하세요`
        inputEl.disabled = true
        sendBtn.disabled = true
      }
    }
  } catch (e) { console.error('영구 삭제 실패', e) }
}

// ── 스레드 전체 관리 모달 ─────────────────────────────────────

async function openDeleteManager() {
  deleteManagerOverlay.classList.remove('hidden')
  deleteManagerBody.innerHTML = '<div class="dm-loading">로딩 중...</div>'
  try {
    const res = await fetch(`${BASE_URL}/threads`)
    const allThreads = await res.json()
    renderDeleteManager(allThreads)
  } catch (e) {
    deleteManagerBody.innerHTML = `<div class="dm-empty">로딩 실패: ${e.message}</div>`
  }
}

function renderDeleteManager(allThreads) {
  deleteManagerBody.innerHTML = ''
  const taskTypes = Object.keys(allThreads)
  if (taskTypes.length === 0) {
    deleteManagerBody.innerHTML = '<div class="dm-empty">스레드 없음</div>'
    return
  }
  taskTypes.forEach(taskType => {
    const cfg = taskConfigs[taskType] || { label: taskType, icon: '' }
    const threads = allThreads[taskType]
    const section = document.createElement('div')
    section.className = 'dm-section'
    const heading = document.createElement('div')
    heading.className = 'dm-heading'
    heading.textContent = `${cfg.icon} ${cfg.label}`
    section.appendChild(heading)
    threads.forEach(t => {
      const row = document.createElement('div')
      row.className = 'dm-row'
      const info = document.createElement('div')
      info.className = 'dm-info'
      const label = formatThreadLabel(t.thread_id)
      const statusMap = { in_progress: '진행 중', completed: '완료', archived: '보관됨' }
      const statusCls  = { in_progress: 'dm-status-active', completed: 'dm-status-done', archived: 'dm-status-archived' }
      const statusText = statusMap[t.status] || t.status
      const statusClass = statusCls[t.status] || ''
      const msgCount = t.message_count > 0 ? `${t.message_count}개` : ''
      info.innerHTML =
        `<span class="dm-label">${label}</span>` +
        `<span class="dm-title">${escapeHtml(t.title)}</span>` +
        `<span class="dm-count">${msgCount}</span>` +
        `<span class="dm-status ${statusClass}">${statusText}</span>`
      const delBtn = document.createElement('button')
      delBtn.className = 'dm-delete-btn'
      delBtn.textContent = '삭제'
      delBtn.addEventListener('click', () => permanentDeleteThread(taskType, t.thread_id, t.is_archived))
      row.appendChild(info)
      row.appendChild(delBtn)
      section.appendChild(row)
    })
    deleteManagerBody.appendChild(section)
  })
}

async function permanentDeleteThread(taskType, threadId, isArchived) {
  const qs = isArchived ? '?archived=true' : ''
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/permanent${qs}`, { method: 'DELETE' })
    dropTab(taskType, threadId)
    if (currentThreadId === threadId && currentTaskType === taskType) {
      currentThreadId = ''
      messagesEl.innerHTML = ''
      updateCurrentThreadBar(taskType, '', '')
      const cfg = taskConfigs[taskType] || {}
      inputEl.placeholder = `${cfg.label} — 스레드를 선택하거나 새로 시작하세요`
      inputEl.disabled = true
      sendBtn.disabled = true
    }
    await openDeleteManager()
    if (currentTaskType === taskType) await renderSidebarThreads(taskType)
  } catch (e) { console.error('영구 삭제 실패', e) }
}

async function createNewThread(taskType) {
  expandGroup(taskType)
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '' })
    })
    const { thread_id } = await res.json()
    await renderSidebarThreads(taskType)
    await selectThread(taskType, thread_id, 'in_progress')
  } catch (e) { console.error('스레드 생성 실패', e) }
}

async function selectThread(taskType, threadId, status) {
  currentThreadId = threadId
  currentTaskType = taskType

  document.querySelectorAll('.thread-item').forEach(item => {
    item.classList.toggle('selected', item.dataset.threadId === threadId && !item.classList.contains('archived'))
  })

  updateCurrentThreadBar(taskType, threadId, status)
  openOrFocusTab(taskType, threadId, status, false)

  messagesEl.innerHTML = ''
  let loadedMsgCount = 0
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/messages`)
    const msgs = await res.json()
    loadedMsgCount = msgs.length
    if (msgs.length === 0) {
      showWelcome(taskType)
    } else {
      msgs.forEach(m => {
        if (m.role === 'user') appendUserMessage(m.content)
        else if (m.role === 'assistant') {
          const el = appendAgentMessage()
          const bubble = el.querySelector('.msg-bubble')
          bubble.dataset.rawText = m.content
          bubble.innerHTML = renderMarkdown(m.content)
        }
      })
    }
  } catch {}

  const cfg = taskConfigs[taskType] || {}
  inputEl.placeholder = status === 'completed'
    ? '(완료된 스레드입니다)'
    : loadedMsgCount > 0
      ? `이어서 입력… (새 업무는 ＋ 새 시작)`
      : `${cfg.label || taskType} 스레드에 메시지를 입력하세요...`
  inputEl.disabled = status === 'completed'
  sendBtn.disabled = status === 'completed'

  if (window.workflowPanel) {
    window.workflowPanel.load(taskType, threadId)
    window.workflowPanel.clearLog()
  }
}

async function closeCurrentThread() {
  if (!currentTaskType || !currentThreadId) return
  const closingId = currentThreadId
  try {
    await fetch(`${BASE_URL}/threads/${currentTaskType}/${closingId}/close`, { method: 'POST' })
    const threads = await renderSidebarThreads(currentTaskType)
    const t = threads.find(t => t.thread_id === closingId)
    await selectThread(currentTaskType, closingId, t ? t.status : 'completed')
  } catch (e) { console.error('스레드 완료 처리 실패', e) }
}

// ── 이벤트 바인딩 ──────────────────────────────────────────

// 백로그 Q: 실행 중이면 끼어들기(/inject), 아니면 새 메시지(/chat)로 라우팅.
function submitInput(text) {
  if (!text.trim()) return
  if (currentRequestId) injectMessage(text)
  else sendMessage(text)
}

async function injectMessage(text) {
  if (!text.trim() || !currentRequestId) return
  const rid = currentRequestId
  try {
    const r = await fetch(`${BASE_URL}/inject/${rid}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    })
    const body = await r.json().catch(() => ({}))
    if (body.ok) {
      appendUserMessage(`↩ ${text}`)  // 끼어든 메시지 로컬 에코
      scrollToBottom(true)
    }
  } catch (e) { console.error('끼어들기 주입 실패', e) }
}

function submitFromInput() {
  const text = inputEl.value.trim()
  inputEl.value = ''
  autoGrowInput()
  submitInput(text)
}

// 커서 위치에 줄바꿈 삽입 (Ctrl+Enter / Ctrl+J 용)
function insertNewlineAtCursor() {
  const s = inputEl.selectionStart, e = inputEl.selectionEnd
  inputEl.value = inputEl.value.slice(0, s) + '\n' + inputEl.value.slice(e)
  inputEl.selectionStart = inputEl.selectionEnd = s + 1
  autoGrowInput()
}

sendBtn.addEventListener('click', submitFromInput)

inputEl.addEventListener('input', autoGrowInput)
inputEl.addEventListener('keydown', (e) => {
  // Ctrl+Enter / Ctrl+J → 줄바꿈 (Shift+Enter는 브라우저 기본 동작 유지)
  if ((e.ctrlKey || e.metaKey) && (e.key === 'Enter' || e.key === 'j')) {
    e.preventDefault()
    insertNewlineAtCursor()
    return
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
    e.preventDefault()
    submitFromInput()
  }
})

// ── 확대 에디터 모달 (백로그 R) ───────────────────────────────
const inputEditorOverlay = document.getElementById('input-editor-overlay')
const inputEditorTextarea = document.getElementById('input-editor-textarea')
const inputEditorClose = document.getElementById('input-editor-close')
const inputEditorCancel = document.getElementById('input-editor-cancel')
const inputEditorSend = document.getElementById('input-editor-send')

function openInputEditor() {
  if (inputEl.disabled) return
  inputEditorTextarea.value = inputEl.value
  inputEditorOverlay.classList.remove('hidden')
  inputEditorTextarea.focus()
  inputEditorTextarea.setSelectionRange(inputEditorTextarea.value.length, inputEditorTextarea.value.length)
}
function closeInputEditor(syncBack = true) {
  if (syncBack) {
    inputEl.value = inputEditorTextarea.value
    autoGrowInput()
  }
  inputEditorOverlay.classList.add('hidden')
  if (syncBack) inputEl.focus()
}
inputExpandBtn?.addEventListener('click', openInputEditor)
inputEditorClose?.addEventListener('click', () => closeInputEditor(true))
inputEditorCancel?.addEventListener('click', () => closeInputEditor(false))
inputEditorSend?.addEventListener('click', () => {
  const text = inputEditorTextarea.value.trim()
  inputEditorOverlay.classList.add('hidden')
  inputEl.value = ''
  autoGrowInput()
  if (text) submitInput(text)
})
inputEditorTextarea?.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); inputEditorSend.click() }
  else if (e.key === 'Escape') { e.preventDefault(); closeInputEditor(true) }
})
inputEditorOverlay?.addEventListener('click', (e) => {
  if (e.target === inputEditorOverlay) closeInputEditor(true)
})

document.querySelectorAll('.quick-action-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (inputEl.disabled) return
    const prompt = btn.dataset.prompt || ''
    if (btn.dataset.autosend === 'true') {
      inputEl.value = ''
      sendMessage(prompt)
    } else {
      inputEl.value = prompt
      autoGrowInput()
      inputEl.focus()
      inputEl.setSelectionRange(prompt.length, prompt.length)
    }
  })
})

threadCloseCurrentBtn.addEventListener('click', closeCurrentThread)

messagesEl.addEventListener('click', () => {
  const isArchived = document.querySelector('.thread-item.selected.archived')
  if (currentTaskType && currentThreadId && !isArchived) {
    if (!window.getSelection().toString()) {
      inputEl.focus()
    }
  }
})

openDeleteManagerBtn.addEventListener('click', openDeleteManager)
deleteManagerClose.addEventListener('click', () => deleteManagerOverlay.classList.add('hidden'))
deleteManagerOverlay.addEventListener('click', (e) => {
  if (e.target === deleteManagerOverlay) deleteManagerOverlay.classList.add('hidden')
})

document.addEventListener('wf:retry-step', ({ detail: { stepTitle } }) => {
  if (!currentTaskType || !currentThreadId || inputEl.disabled) return
  sendMessage(`"${stepTitle}" 단계에서 오류가 발생했습니다. 이 단계를 다시 시도해주세요.`)
})

// ── 전역 검색 + 진행 중 작업 (백로그 P) ──────────────────────────
const sidebarSearchInput = document.getElementById('sidebar-search-input')
const sidebarSearchResults = document.getElementById('sidebar-search-results')
const activeRunsEl = document.getElementById('active-runs')
const activeRunsList = document.getElementById('active-runs-list')
let _searchTimer = null

function hideSearchResults() {
  sidebarSearchResults?.classList.add('hidden')
}

async function runSearch(q) {
  if (!q.trim()) { hideSearchResults(); return }
  try {
    const res = await fetch(`${BASE_URL}/search?q=${encodeURIComponent(q)}`)
    const hits = await res.json()
    renderSearchResults(hits)
  } catch { hideSearchResults() }
}

function renderSearchResults(hits) {
  if (!sidebarSearchResults) return
  sidebarSearchResults.innerHTML = ''
  sidebarSearchResults.classList.remove('hidden')
  if (!hits || hits.length === 0) {
    sidebarSearchResults.innerHTML = '<div class="search-empty">검색 결과 없음</div>'
    return
  }
  hits.forEach(h => {
    const cfg = taskConfigs[h.task_type] || {}
    const el = document.createElement('div')
    el.className = 'search-hit'
    const titleText = h.title && h.title !== h.thread_id ? h.title : formatThreadLabel(h.thread_id)
    el.innerHTML =
      `<div class="search-hit-top">` +
        `<span>${h.archived ? '🗑' : (cfg.icon || '💬')}</span>` +
        `<span class="search-hit-title">${escapeHtml(titleText)}</span>` +
        `<span class="search-hit-task">${escapeHtml(cfg.label || h.task_type)}</span>` +
      `</div>` +
      (h.snippet ? `<div class="search-hit-snippet">${escapeHtml(h.snippet)}</div>` : '')
    el.addEventListener('click', async () => {
      hideSearchResults()
      sidebarSearchInput.value = ''
      if (h.archived) await selectArchivedThread(h.task_type, h.thread_id)
      else {
        expandGroup(h.task_type)
        await renderSidebarThreads(h.task_type)
        await selectThread(h.task_type, h.thread_id, h.status)
      }
    })
    sidebarSearchResults.appendChild(el)
  })
}

sidebarSearchInput?.addEventListener('input', () => {
  const q = sidebarSearchInput.value
  if (_searchTimer) clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => runSearch(q), 250)
})
sidebarSearchInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { sidebarSearchInput.value = ''; hideSearchResults() }
})
document.addEventListener('click', (e) => {
  if (!e.target.closest('#sidebar-search')) hideSearchResults()
})

async function refreshActiveRuns() {
  if (!activeRunsEl) return
  let all = {}
  try {
    const res = await fetch(`${BASE_URL}/threads`)
    all = await res.json()
  } catch { return }
  const runs = []
  for (const [taskType, threads] of Object.entries(all)) {
    threads.forEach(t => {
      if (t.status === 'in_progress' && t.message_count > 0) {
        runs.push({ taskType, ...t })
      }
    })
  }
  activeRunsList.innerHTML = ''
  if (runs.length === 0) { activeRunsEl.classList.add('hidden'); return }
  activeRunsEl.classList.remove('hidden')
  runs.slice(0, 8).forEach(r => {
    const cfg = taskConfigs[r.taskType] || {}
    const el = document.createElement('div')
    el.className = 'active-run-item'
    const label = r.title && r.title !== r.thread_id ? r.title : formatThreadLabel(r.thread_id)
    el.innerHTML =
      `<span class="ar-pulse"></span>` +
      `<span class="ar-label">${escapeHtml(cfg.icon || '💬')} ${escapeHtml(label)}</span>`
    el.title = `${cfg.label || r.taskType} · ${formatThreadLabel(r.thread_id)}`
    el.addEventListener('click', async () => {
      expandGroup(r.taskType)
      await renderSidebarThreads(r.taskType)
      await selectThread(r.taskType, r.thread_id, r.status)
    })
    activeRunsList.appendChild(el)
  })
}

// ── 협업모드(코치 모드) 컨트롤러 (백로그 H) ───────────────────────
// 메인 렌더러가 두뇌: 목표 설정 → 주기 틱(/collaborate/tick) → 힌트를 HUD로 중계.
// 화면을 직접 보는 건 서버이고, 여기선 폴링·표시만 한다(포커스 비탈취 = HUD가 focusable:false).
const COLLAB_TID = '__collab__'        // 스레드 전환과 무관한 고정 세션 키
const COLLAB_TICK_MS = 30000           // 클라이언트 폴링 주기(서버 .env COLLAB_CHANGE_THRESHOLD로 변화 게이트)
const collabBtn = document.getElementById('collab-btn')
const collabBar = document.getElementById('collab-bar')
const collabGoalInput = document.getElementById('collab-goal-input')
const collabStartBtn = document.getElementById('collab-start-btn')
const collabCancelBtn = document.getElementById('collab-cancel-btn')
let collabActive = false
let collabTimer = null

function collabUpdateHud(payload) {
  window.electronAPI?.collabUpdateHud?.(payload)
}

async function collabTick(force = false) {
  if (!collabActive) return
  if (force) collabUpdateHud({ state: 'thinking' })
  try {
    const res = await fetch(`${BASE_URL}/collaborate/tick`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: COLLAB_TID, force }),
    })
    const data = await res.json()
    if (data.hint) collabUpdateHud({ hint: data.hint })
    else collabUpdateHud({ state: 'idle' })
  } catch (e) {
    collabUpdateHud({ state: 'idle' })
  }
}

async function collabStart() {
  const goal = collabGoalInput.value.trim()
  try {
    await fetch(`${BASE_URL}/collaborate/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: COLLAB_TID, goal }),
    })
  } catch (e) { /* 서버 미연결이어도 UI는 토글 */ }
  collabActive = true
  collabBar.classList.add('hidden')
  collabBtn.classList.add('active')
  window.electronAPI?.collabShowHud?.()
  collabUpdateHud({ state: 'idle' })
  if (collabTimer) clearInterval(collabTimer)
  collabTimer = setInterval(() => collabTick(false), COLLAB_TICK_MS)
  collabTick(true)  // 시작 즉시 한 번
}

async function collabStop() {
  collabActive = false
  collabBar.classList.add('hidden')
  collabBtn.classList.remove('active')
  if (collabTimer) { clearInterval(collabTimer); collabTimer = null }
  window.electronAPI?.collabHideHud?.()
  try {
    await fetch(`${BASE_URL}/collaborate/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: COLLAB_TID }),
    })
  } catch (e) { /* noop */ }
}

collabBtn?.addEventListener('click', () => {
  if (collabActive) { collabStop(); return }
  // 목표 입력 바 토글
  const showing = !collabBar.classList.contains('hidden')
  collabBar.classList.toggle('hidden', showing)
  if (!showing) collabGoalInput.focus()
})
collabStartBtn?.addEventListener('click', collabStart)
collabGoalInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') collabStart() })
collabCancelBtn?.addEventListener('click', () => {
  if (collabActive) collabStop()
  else collabBar.classList.add('hidden')
})

// HUD에서 올라온 사용자 동작 처리
window.electronAPI?.onCollabCommand?.(({ type, mode }) => {
  if (mode === 'agent') {
    if (type === 'manual') window.electronAPI?.agentIdle?.()
    else if (type === 'stop') stopBtn?.click()
    return
  }
  if (type === 'manual') collabTick(true)
  else if (type === 'stop') collabStop()
})

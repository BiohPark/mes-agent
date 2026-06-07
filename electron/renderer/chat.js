const PORT = window.electronAPI?.serverPort ?? 8000
const BASE_URL = `http://localhost:${PORT}`

const messagesEl = document.getElementById('messages')
const inputEl = document.getElementById('input')
const sendBtn = document.getElementById('send-btn')
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
  waiting:  { icon: '⏸️', text: '사용자 입력 대기' },
  idle:     { icon: '✓',  text: '완료' },
}

function setAgentState(state) {
  const meta = STATE_META[state] || STATE_META.thinking
  agentStateIcon.textContent = meta.icon
  agentStateText.textContent = meta.text
  if (state === 'idle') {
    setTimeout(() => agentStateBar.classList.add('hidden'), 800)
    // 실행 종료 → 창 원복 (개선 아이디어 C)
    window.electronAPI?.agentIdle?.()
  } else {
    agentStateBar.classList.remove('hidden')
    // 화면 제어가 시작되는 running 상태에서만 창을 비킨다
    if (state === 'running') {
      window.electronAPI?.agentBusy?.(busyMode)
    } else if (state === 'waiting') {
      // 사용자 확인 팝업이 보이도록 창을 원복 (응답 후 다시 running 되면 재최소화)
      window.electronAPI?.agentIdle?.()
    }
    // thinking 상태는 running 사이의 짧은 단계 — 창을 건드리지 않아 깜빡임 방지
  }
}

// ── 실행 중 창 모드 (개선 아이디어 C) ─────────────────────────
let busyMode = localStorage.getItem('busyMode') || 'minimize'
const BUSYMODE_LABELS = { minimize: '🪟 최소화', translucent: '👻 반투명', off: '🚫 끄기' }
const busymodeBtn = document.getElementById('busymode-btn')
const busymodeMenu = document.getElementById('busymode-menu')

function renderBusyMode() {
  if (busymodeBtn) busymodeBtn.textContent = BUSYMODE_LABELS[busyMode] || '🪟 최소화'
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
  inputEl.disabled = !enabled
  sendBtn.disabled = !enabled
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
        task_type: currentTaskType
      })
    })

    if (!response.ok) throw new Error(`서버 오류 ${response.status}`)

    await readStream(response, agentEl)
  } catch (e) {
    agentEl.querySelector('.msg-bubble').textContent = `오류: ${e.message}`
  } finally {
    setInputEnabled(true)
    inputEl.focus()
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

function handleEvent(event, agentEl, bubble) {
  // type 없이 request_id만 있는 경우 (최초 SSE)
  if (event.request_id && !event.type) {
    currentRequestId = event.request_id
    return
  }

  switch (event.type) {
    case 'text':
      bubble.textContent += event.content
      scrollToBottom()
      break

    case 'tool_start': {
      _toolStartTimes[event.tool] = Date.now()
      const step = document.createElement('div')
      step.className = 'tool-step running'
      step.dataset.tool = event.tool
      step.innerHTML = `<span class="icon">⏳</span> ${event.label}`
      agentEl.querySelector('.msg-bubble').before(step)
      scrollToBottom()
      break
    }

    case 'tool_done': {
      const duration = _toolStartTimes[event.tool]
        ? Date.now() - _toolStartTimes[event.tool]
        : null
      delete _toolStartTimes[event.tool]

      const isError = event.result && event.result.startsWith('툴 실행 오류')
      const step = agentEl.querySelector(`.tool-step[data-tool="${event.tool}"]`)
      if (step) {
        step.className = isError ? 'tool-step error' : 'tool-step done'
        step.querySelector('.icon').textContent = isError ? '✗' : '✓'
      }
      if (event.result) {
        const result = document.createElement('div')
        result.className = 'tool-result' + (isError ? ' error' : '')
        result.textContent = event.result
        agentEl.querySelector('.msg-bubble').before(result)
      }
      scrollToBottom()

      // 실행 로그에 추가
      if (window.workflowPanel) {
        window.workflowPanel.appendLog(event.tool, event.result || '', duration)
      }
      break
    }

    case 'confirm':
      showConfirmDialog(event).catch(console.error)
      break

    case 'agent_state':
      setAgentState(event.state)
      break

    case 'context_usage':
      setContextUsage(event.tokens_used, event.tokens_total)
      break

    case 'workflow_update':
      if (window.workflowPanel) window.workflowPanel.handleUpdate(event.workflow)
      break

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
  if (label.includes('계속') || label.includes('진행')) return '✅'
  if (label.includes('중단') || label.includes('취소')) return '❌'
  if (label.includes('방법') || label.includes('제안') || label.includes('변경')) return '💡'
  if (label.includes('의견') || label.includes('입력') || label.includes('전달')) return '✏️'
  return '•'
}

// 텍스트 입력이 필요한 옵션인지 판단
const TEXT_INPUT_KEYWORDS = ['방법 변경', '제안', '의견', '입력', '전달', '기타']
function needsTextInput(label) {
  return TEXT_INPUT_KEYWORDS.some(k => label.includes(k))
}

async function showConfirmDialog({ confirm_id, question, options }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div')
    overlay.className = 'confirm-overlay'

    const optBtns = options.map((opt, i) => `
      <button class="confirm-opt-btn" data-index="${i}" data-label="${escapeHtml(opt)}">
        <span class="confirm-opt-icon">${getOptionIcon(opt)}</span>
        <span>${escapeHtml(opt)}</span>
      </button>
    `).join('')

    overlay.innerHTML = `
      <div class="confirm-dialog">
        <div class="confirm-header">⚠ 에이전트 확인 요청</div>
        <div class="confirm-question">${escapeHtml(question)}</div>
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
  el.innerHTML = `<div class="msg-role">나</div><div class="msg-bubble">${escapeHtml(text)}</div>`
  messagesEl.appendChild(el)
  scrollToBottom()
}

function appendAgentMessage() {
  const el = document.createElement('div')
  el.className = 'message agent'
  el.innerHTML = `<div class="msg-role">Agent</div><div class="msg-bubble"></div>`
  messagesEl.appendChild(el)
  scrollToBottom()
  return el
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
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
  } catch {}
}

// ── 사이드바 그룹 관리 ────────────────────────────────────────

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
        el.querySelector('.msg-bubble').textContent = m.content
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
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/messages`)
    const msgs = await res.json()
    if (msgs.length === 0) {
      showWelcome(taskType)
    } else {
      msgs.forEach(m => {
        if (m.role === 'user') appendUserMessage(m.content)
        else if (m.role === 'assistant') {
          const el = appendAgentMessage()
          el.querySelector('.msg-bubble').textContent = m.content
        }
      })
    }
  } catch {}

  const cfg = taskConfigs[taskType] || {}
  inputEl.placeholder = status === 'completed'
    ? '(완료된 스레드입니다)'
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

sendBtn.addEventListener('click', () => {
  const text = inputEl.value.trim()
  inputEl.value = ''
  sendMessage(text)
})

inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    const text = inputEl.value.trim()
    inputEl.value = ''
    sendMessage(text)
  }
})

document.querySelectorAll('.task-group-header').forEach(header => {
  header.addEventListener('click', (e) => {
    if (e.target.closest('.tg-new-btn')) return
    const taskType = header.closest('.task-group').dataset.task
    if (!expandedGroups.has(taskType) || currentTaskType !== taskType) {
      openTask(taskType)
    } else {
      collapseGroup(taskType)
    }
  })
})

document.querySelectorAll('.tg-new-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.stopPropagation()
    createNewThread(btn.closest('.task-group').dataset.task)
  })
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
      inputEl.focus()
      inputEl.setSelectionRange(prompt.length, prompt.length)
    }
  })
})

threadCloseCurrentBtn.addEventListener('click', closeCurrentThread)

messagesEl.addEventListener('click', () => {
  const isArchived = document.querySelector('.thread-item.selected.archived')
  if (currentTaskType && currentThreadId && !isArchived) inputEl.focus()
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

const PORT = window.electronAPI?.serverPort ?? 8000
const BASE_URL = `http://localhost:${PORT}`

const messagesEl = document.getElementById('messages')
const inputEl = document.getElementById('input')
const sendBtn = document.getElementById('send-btn')
const statusEl = document.getElementById('status')
const profileSwitcher = document.getElementById('profile-switcher')
const profileBtn = document.getElementById('profile-btn')
const profileMenu = document.getElementById('profile-menu')
const threadBar = document.getElementById('thread-bar')
const threadTaskLabel = document.getElementById('thread-task-label')
const threadTabsEl = document.getElementById('thread-tabs')
const threadCloseCurrentBtn = document.getElementById('thread-close-current-btn')
const threadBackBtn = document.getElementById('thread-back-btn')
const taskBtns = document.querySelectorAll('.task-btn')

// ── 스레드 상태 ──────────────────────────────────────────────
let currentTaskType = ''
let currentThreadId = ''
let taskConfigs = {}   // { syncade: { label, icon }, ... }

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

// 서버가 뜰 때까지 직접 폴링 (IPC 타이밍 문제 회피)
async function initWhenReady() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`${BASE_URL}/health`)
      if (res.ok) {
        statusEl.textContent = '● 준비됨'
        statusEl.className = 'status ready'
        setInputEnabled(true)
        await Promise.all([loadProfile(), loadTaskConfig()])
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
  taskBtns.forEach(btn => btn.disabled = !enabled)
}

// 메시지 전송
async function sendMessage(text) {
  if (!text.trim()) return
  setInputEnabled(false)

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

function handleEvent(event, agentEl, bubble) {
  switch (event.type) {
    case 'text':
      bubble.textContent += event.content
      scrollToBottom()
      break

    case 'tool_start': {
      const step = document.createElement('div')
      step.className = 'tool-step running'
      step.dataset.tool = event.tool
      step.innerHTML = `<span class="icon">⏳</span> ${event.label}`
      agentEl.querySelector('.msg-bubble').before(step)
      scrollToBottom()
      break
    }

    case 'tool_done': {
      const step = agentEl.querySelector(`.tool-step[data-tool="${event.tool}"]`)
      if (step) {
        step.className = 'tool-step done'
        step.querySelector('.icon').textContent = '✓'
      }
      if (event.result) {
        const result = document.createElement('div')
        result.className = 'tool-result'
        result.textContent = event.result
        agentEl.querySelector('.msg-bubble').before(result)
      }
      scrollToBottom()
      break
    }

    case 'done':
      if (!bubble.textContent) bubble.textContent = '완료되었습니다.'
      break

    case 'error':
      bubble.textContent = `오류: ${event.message}`
      break
  }
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

// ── 스레드 관리 ──────────────────────────────────────────────

async function loadTaskConfig() {
  try {
    const res = await fetch(`${BASE_URL}/task-config`)
    taskConfigs = await res.json()
  } catch {}
}

async function openTask(taskType) {
  currentTaskType = taskType
  currentThreadId = ''

  taskBtns.forEach(b => b.classList.toggle('active', b.dataset.task === taskType))

  const cfg = taskConfigs[taskType] || { label: taskType, icon: '' }
  threadTaskLabel.textContent = `${cfg.icon} ${cfg.label}`
  threadBar.classList.remove('hidden')
  threadCloseCurrentBtn.classList.add('hidden')

  // 입력창을 즉시 '스레드 없음' 상태로 초기화
  messagesEl.innerHTML = ''
  inputEl.placeholder = `${cfg.label} — 스레드를 선택하거나 새로 시작하세요`
  inputEl.disabled = true
  sendBtn.disabled = true

  const threads = await refreshThreadTabs(taskType)

  // 진행 중인 스레드가 있으면 첫 번째를 자동 선택
  const firstActive = threads.find(t => t.status === 'in_progress')
  if (firstActive) {
    await selectThread(taskType, firstActive.thread_id, firstActive.status)
  } else if (threads.length === 0) {
    // 스레드가 아예 없으면 자동으로 새 스레드 생성
    await createNewThread(taskType)
  } else {
    // 완료된 스레드만 있으면 입력 비활성 + 안내
    inputEl.placeholder = `${cfg.label} — 새 스레드를 시작하거나 기존 탭을 클릭하세요`
    inputEl.disabled = false
    sendBtn.disabled = false
  }
}

async function refreshThreadTabs(taskType) {
  let threads = []
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}`)
    threads = await res.json()
  } catch {}

  threadTabsEl.innerHTML = ''

  // + 새 시작 버튼
  const newBtn = document.createElement('button')
  newBtn.className = 'thread-tab new-thread'
  newBtn.textContent = '+ 새 시작'
  newBtn.addEventListener('click', () => createNewThread(taskType))
  threadTabsEl.appendChild(newBtn)

  // 기존 스레드 탭
  threads.forEach(t => {
    const btn = document.createElement('button')
    btn.className = `thread-tab${t.status === 'completed' ? ' completed' : ''}${t.thread_id === currentThreadId ? ' active' : ''}`
    btn.dataset.threadId = t.thread_id
    const label = t.thread_id.slice(-3)
    const statusMark = t.status === 'completed' ? ' ✓' : ''
    const msgCount = t.message_count > 0 ? ` (${t.message_count})` : ''
    btn.textContent = `#${label}${msgCount}${statusMark}`
    btn.title = t.title
    btn.addEventListener('click', () => selectThread(taskType, t.thread_id, t.status))
    threadTabsEl.appendChild(btn)
  })

  return threads
}

async function createNewThread(taskType) {
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '' })
    })
    const { thread_id } = await res.json()
    await selectThread(taskType, thread_id, 'in_progress')
    await refreshThreadTabs(taskType)
  } catch (e) {
    console.error('스레드 생성 실패', e)
  }
}

async function selectThread(taskType, threadId, status) {
  currentThreadId = threadId

  // 탭 active 갱신
  threadTabsEl.querySelectorAll('.thread-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.threadId === threadId)
  })

  // 완료 버튼 표시 여부
  threadCloseCurrentBtn.classList.toggle('hidden', status === 'completed')

  // 대화 이력 로드
  messagesEl.innerHTML = ''
  try {
    const res = await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/messages`)
    const msgs = await res.json()
    msgs.forEach(m => {
      if (m.role === 'user') appendUserMessage(m.content)
      else if (m.role === 'assistant') {
        const el = appendAgentMessage()
        el.querySelector('.msg-bubble').textContent = m.content
      }
    })
  } catch {}

  // 입력창 placeholder 업데이트
  const cfg = taskConfigs[taskType] || {}
  inputEl.placeholder = status === 'completed'
    ? '(완료된 스레드입니다)'
    : `${cfg.label || taskType} 스레드에 메시지를 입력하세요...`
  inputEl.disabled = status === 'completed'
  sendBtn.disabled = status === 'completed'
}

async function closeCurrentThread() {
  if (!currentTaskType || !currentThreadId) return
  try {
    await fetch(`${BASE_URL}/threads/${currentTaskType}/${currentThreadId}/close`, { method: 'POST' })
    await selectThread(currentTaskType, currentThreadId, 'completed')
    await refreshThreadTabs(currentTaskType)
  } catch (e) {
    console.error('스레드 완료 처리 실패', e)
  }
}

function exitTaskMode() {
  currentTaskType = ''
  currentThreadId = ''
  taskBtns.forEach(b => b.classList.remove('active'))
  threadBar.classList.add('hidden')
  threadCloseCurrentBtn.classList.add('hidden')
  messagesEl.innerHTML = ''
  inputEl.placeholder = '지시사항을 입력하세요 (Enter: 전송, Shift+Enter: 줄바꿈)'
  setInputEnabled(true)
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

taskBtns.forEach(btn => {
  btn.addEventListener('click', () => openTask(btn.dataset.task))
})

threadCloseCurrentBtn.addEventListener('click', closeCurrentThread)
threadBackBtn.addEventListener('click', exitTaskMode)

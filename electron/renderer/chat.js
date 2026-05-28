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
const archiveToggleBtn = document.getElementById('archive-toggle-btn')
const openDeleteManagerBtn = document.getElementById('open-delete-manager-btn')
const deleteManagerOverlay = document.getElementById('delete-manager-overlay')
const deleteManagerBody = document.getElementById('delete-manager-body')
const deleteManagerClose = document.getElementById('delete-manager-close')
const taskBtns = document.querySelectorAll('.task-btn')

// ── 스레드 상태 ──────────────────────────────────────────────
let currentTaskType = ''
let currentThreadId = ''
let taskConfigs = {}   // { syncade: { label, icon }, ... }
let showingArchive = false

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
  taskBtns.forEach(btn => btn.disabled = !enabled)
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

    case 'confirm':
      showConfirmDialog(event).catch(console.error)
      break

    case 'done':
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

// thread_id 형식: YYYY-MM-DD-NNN → 오늘이면 '#001', 다른 날이면 '05/25 #001'
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

async function openTask(taskType) {
  currentTaskType = taskType
  currentThreadId = ''
  showingArchive = false
  archiveToggleBtn.textContent = '🗑️ 보관함'
  archiveToggleBtn.classList.remove('active')

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

  // 메시지 있는 가장 최근 스레드 우선 선택, 없으면 최근 스레드, 없으면 새로 생성
  const withMessages = threads.find(t => t.message_count > 0)
  if (withMessages) {
    await selectThread(taskType, withMessages.thread_id, withMessages.status)
  } else if (threads.length > 0) {
    await selectThread(taskType, threads[0].thread_id, threads[0].status)
  } else {
    await createNewThread(taskType)
  }
}

async function refreshThreadTabs(taskType) {
  let threads = []
  try {
    const url = showingArchive
      ? `${BASE_URL}/threads/${taskType}?archived=true`
      : `${BASE_URL}/threads/${taskType}`
    const res = await fetch(url)
    threads = await res.json()
  } catch {}

  threadTabsEl.innerHTML = ''
  threadBar.classList.toggle('archive-mode', showingArchive)

  if (!showingArchive) {
    // + 새 시작 버튼 (활성 모드에서만)
    const newBtn = document.createElement('button')
    newBtn.className = 'thread-tab new-thread'
    newBtn.textContent = '+ 새 시작'
    newBtn.addEventListener('click', () => createNewThread(taskType))
    threadTabsEl.appendChild(newBtn)
  }

  if (showingArchive && threads.length === 0) {
    const empty = document.createElement('span')
    empty.className = 'thread-empty-hint'
    empty.textContent = '보관된 스레드 없음'
    threadTabsEl.appendChild(empty)
  }

  threads.forEach(t => {
    const btn = document.createElement('button')
    const isActive = t.thread_id === currentThreadId
    let cls = 'thread-tab'
    if (showingArchive) cls += ' archived'
    else if (t.status === 'completed') cls += ' completed'
    if (isActive) cls += ' active'
    btn.className = cls
    btn.dataset.threadId = t.thread_id
    btn.title = t.title

    const labelSpan = document.createElement('span')
    if (showingArchive) {
      const label = formatThreadLabel(t.thread_id)
      const msgCount = t.message_count > 0 ? ` (${t.message_count})` : ''
      // archived_at에서 날짜만 표시
      const archivedDate = t.archived_at ? ` · ${t.archived_at.slice(5, 10)}` : ''
      labelSpan.textContent = `${label}${msgCount}${archivedDate}`
    } else {
      const label = formatThreadLabel(t.thread_id)
      const statusMark = t.status === 'completed' ? ' ✓' : ''
      const msgCount = t.message_count > 0 ? ` (${t.message_count})` : ''
      labelSpan.textContent = `${label}${msgCount}${statusMark}`
    }
    btn.appendChild(labelSpan)

    if (showingArchive) {
      // 보관 탭: ↑ (원래 상태로 복원) + × (영구 삭제)
      const unarchiveBtn = document.createElement('span')
      unarchiveBtn.className = 'tab-unarchive-btn'
      unarchiveBtn.textContent = '↑'
      unarchiveBtn.title = '보관 전 상태로 복원'
      unarchiveBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        restoreArchivedThread(taskType, t.thread_id)
      })
      btn.appendChild(unarchiveBtn)

      const delBtn = document.createElement('span')
      delBtn.className = 'tab-del-btn'
      delBtn.textContent = '×'
      delBtn.title = '영구 삭제'
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        deleteThreadFromTab(taskType, t.thread_id, true)
      })
      btn.appendChild(delBtn)
    } else {
      // 활성 탭: 완료 스레드만 ↺ (재개), 모두 ↓ (보관) + × (영구 삭제)
      if (t.status === 'completed') {
        const restoreBtn = document.createElement('span')
        restoreBtn.className = 'tab-restore-btn'
        restoreBtn.textContent = '↺'
        restoreBtn.title = '진행 중으로 재개'
        restoreBtn.addEventListener('click', (e) => {
          e.stopPropagation()
          restoreThread(taskType, t.thread_id)
        })
        btn.appendChild(restoreBtn)
      }
      const archiveBtn = document.createElement('span')
      archiveBtn.className = 'tab-archive-btn'
      archiveBtn.textContent = '↓'
      archiveBtn.title = '보관함으로 이동'
      archiveBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        archiveThread(taskType, t.thread_id)
      })
      btn.appendChild(archiveBtn)

      const delBtn = document.createElement('span')
      delBtn.className = 'tab-del-btn'
      delBtn.textContent = '×'
      delBtn.title = '영구 삭제'
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        deleteThreadFromTab(taskType, t.thread_id, false)
      })
      btn.appendChild(delBtn)
    }

    btn.addEventListener('click', () => {
      if (showingArchive) selectArchivedThread(taskType, t.thread_id)
      else selectThread(taskType, t.thread_id, t.status)
    })
    threadTabsEl.appendChild(btn)
  })

  return threads
}

async function archiveThread(taskType, threadId) {
  const wasActive = currentThreadId === threadId
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}`, { method: 'DELETE' })
    const threads = await refreshThreadTabs(taskType)

    if (wasActive) {
      currentThreadId = ''
      messagesEl.innerHTML = ''
      threadCloseCurrentBtn.classList.add('hidden')
      // 보관 후 다음 활성 스레드로 자동 이동
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
  } catch (e) {
    console.error('스레드 보관 실패', e)
  }
}

async function selectArchivedThread(taskType, threadId) {
  currentThreadId = threadId
  threadTabsEl.querySelectorAll('.thread-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.threadId === threadId)
  })
  threadCloseCurrentBtn.classList.add('hidden')

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
    // 서버 실제 status 기준으로 UI 갱신 (하드코딩 금지)
    const threads = await refreshThreadTabs(taskType)
    const t = threads.find(t => t.thread_id === threadId)
    await selectThread(taskType, threadId, t ? t.status : 'in_progress')
  } catch (e) {
    console.error('스레드 복원 실패', e)
  }
}

async function restoreArchivedThread(taskType, threadId) {
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/unarchive`, { method: 'POST' })
    // 보관함 뷰에서 활성 뷰로 전환 후 복원된 스레드(완료 상태) 선택
    showingArchive = false
    archiveToggleBtn.textContent = '🗑️ 보관함'
    archiveToggleBtn.classList.remove('active')
    threadBar.classList.remove('archive-mode')
    const threads = await refreshThreadTabs(taskType)
    const t = threads.find(t => t.thread_id === threadId)
    if (t) {
      await selectThread(taskType, threadId, t.status)
    }
  } catch (e) {
    console.error('보관 스레드 복원 실패', e)
  }
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
      delBtn.addEventListener('click', () =>
        permanentDeleteThread(taskType, t.thread_id, t.is_archived)
      )

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

    // 현재 열려있는 스레드면 UI 초기화
    if (currentThreadId === threadId && currentTaskType === taskType) {
      currentThreadId = ''
      messagesEl.innerHTML = ''
      threadCloseCurrentBtn.classList.add('hidden')
      const cfg = taskConfigs[taskType] || {}
      inputEl.placeholder = `${cfg.label} — 스레드를 선택하거나 새로 시작하세요`
      inputEl.disabled = true
      sendBtn.disabled = true
    }

    // 모달 새로고침
    await openDeleteManager()

    // 현재 태스크의 탭도 새로고침
    if (currentTaskType === taskType) {
      await refreshThreadTabs(taskType)
    }
  } catch (e) {
    console.error('영구 삭제 실패', e)
  }
}

async function deleteThreadFromTab(taskType, threadId, isArchived) {
  const wasActive = currentThreadId === threadId && currentTaskType === taskType
  const qs = isArchived ? '?archived=true' : ''
  try {
    await fetch(`${BASE_URL}/threads/${taskType}/${threadId}/permanent${qs}`, { method: 'DELETE' })
    const threads = await refreshThreadTabs(taskType)
    if (wasActive) {
      currentThreadId = ''
      messagesEl.innerHTML = ''
      threadCloseCurrentBtn.classList.add('hidden')
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
  } catch (e) {
    console.error('영구 삭제 실패', e)
  }
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
  const closingId = currentThreadId
  try {
    await fetch(`${BASE_URL}/threads/${currentTaskType}/${closingId}/close`, { method: 'POST' })
    // 서버 실제 status 기준으로 UI 갱신
    const threads = await refreshThreadTabs(currentTaskType)
    const t = threads.find(t => t.thread_id === closingId)
    await selectThread(currentTaskType, closingId, t ? t.status : 'completed')
  } catch (e) {
    console.error('스레드 완료 처리 실패', e)
  }
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

// 채팅 영역 클릭 → 입력창 포커스 (클릭해서 대화 시작 UX)
messagesEl.addEventListener('click', () => {
  if (currentTaskType && currentThreadId && !showingArchive) {
    inputEl.focus()
  }
})

openDeleteManagerBtn.addEventListener('click', openDeleteManager)
deleteManagerClose.addEventListener('click', () => deleteManagerOverlay.classList.add('hidden'))
deleteManagerOverlay.addEventListener('click', (e) => {
  if (e.target === deleteManagerOverlay) deleteManagerOverlay.classList.add('hidden')
})

archiveToggleBtn.addEventListener('click', async () => {
  showingArchive = !showingArchive
  archiveToggleBtn.textContent = showingArchive ? '← 활성 스레드' : '🗑️ 보관함'
  archiveToggleBtn.classList.toggle('active', showingArchive)

  currentThreadId = ''
  messagesEl.innerHTML = ''
  threadCloseCurrentBtn.classList.add('hidden')

  // 보관함 진입 시 즉시 입력 비활성 (스레드 미선택 상태)
  if (showingArchive) {
    inputEl.disabled = true
    sendBtn.disabled = true
    inputEl.placeholder = '보관함 — 스레드를 클릭해서 내용을 확인하세요'
  }

  const threads = await refreshThreadTabs(currentTaskType)

  if (!showingArchive) {
    const cfg = taskConfigs[currentTaskType] || {}
    const firstActive = threads.find(t => t.status === 'in_progress')
    if (firstActive) {
      await selectThread(currentTaskType, firstActive.thread_id, firstActive.status)
    } else {
      inputEl.placeholder = `${cfg.label} — 스레드를 선택하거나 새로 시작하세요`
      inputEl.disabled = true
      sendBtn.disabled = true
    }
  }
})

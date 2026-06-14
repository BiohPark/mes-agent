// Pure supervisor state reducer shared by the Electron renderer and Node tests.
(function (root, factory) {
  const api = factory()
  if (typeof module !== 'undefined' && module.exports) module.exports = api
  root.SupervisorState = api
})(typeof globalThis !== 'undefined' ? globalThis : window, function () {
  const INITIAL = Object.freeze({
    requestId: '',
    goal: '대기 중',
    step: '-',
    agentState: 'idle',
    phase: 'done',
    role: 'orchestrator',
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
  })

  function initialState(requestId = '') {
    return {
      ...INITIAL,
      requestId,
      phase: requestId ? 'planning' : INITIAL.phase,
      role: requestId ? 'planner' : INITIAL.role,
      evidence: [],
    }
  }

  function summarizeWorkflow(wf) {
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

  function appendEvidence(state, label, detail = '', now = new Date()) {
    const text = detail ? `${label}: ${detail}` : label
    return [
      { text, at: now.toTimeString().slice(0, 8) },
      ...(state.evidence || []),
    ].slice(0, 5)
  }

  function resetTerminalFields(state) {
    return {
      ...state,
      currentTool: '',
      currentToolLabel: '',
      toolStartedAt: 0,
      elapsedMs: 0,
      waitingApproval: false,
      approvalText: '대기 없음',
      risk: 'none',
    }
  }

  function phaseRoleForAgentState(agentState, previous = INITIAL) {
    if (agentState === 'thinking') return { phase: 'planning', role: 'planner' }
    if (agentState === 'running' || agentState === 'working') return { phase: 'executing', role: 'executor' }
    if (agentState === 'waiting') return { phase: 'waiting', role: 'safety' }
    if (agentState === 'idle') return { phase: 'done', role: 'orchestrator' }
    return { phase: previous.phase || 'planning', role: previous.role || 'orchestrator' }
  }

  function reduce(state, event, opts = {}) {
    const nowMs = opts.nowMs ?? Date.now()
    const now = opts.now instanceof Date ? opts.now : new Date(nowMs)
    const current = state || initialState()
    if (!event) return current
    if (event.request_id && !event.type) return initialState(event.request_id)

    switch (event.type) {
      case 'agent_state': {
        const next = {
          ...current,
          agentState: event.state || 'unknown',
          ...phaseRoleForAgentState(event.state, current),
        }
        return event.state === 'idle' ? resetTerminalFields(next) : next
      }

      case 'plan':
        return {
          ...current,
          agentState: 'thinking',
          phase: 'planning',
          role: 'planner',
          lastError: '',
        }

      case 'tool_start':
        return {
          ...current,
          agentState: 'working',
          phase: 'executing',
          role: 'executor',
          currentTool: event.tool || '',
          currentToolLabel: event.label || event.tool || '도구 실행 중',
          toolStartedAt: nowMs,
          elapsedMs: 0,
          waitingApproval: false,
          approvalText: '대기 없음',
          risk: 'none',
          lastError: '',
        }

      case 'tool_wait':
        return {
          ...current,
          agentState: 'waiting',
          phase: 'executing',
          role: 'executor',
          approvalText: `도구 지연: ${event.next || '?'}s까지 대기`,
        }

      case 'tool_done': {
        const clearCurrent = current.currentTool === event.tool
        const next = {
          ...current,
          evidence: appendEvidence(current, event.tool || 'tool', String(event.result || '').slice(0, 80), now),
        }
        if (clearCurrent) {
          next.currentTool = ''
          next.currentToolLabel = ''
          next.toolStartedAt = 0
          next.elapsedMs = 0
        }
        if (!current.waitingApproval) {
          next.agentState = 'running'
          next.phase = 'observing'
          next.role = 'observer'
          next.approvalText = '대기 없음'
          next.risk = 'none'
        }
        return next
      }

      case 'confirm':
        return {
          ...current,
          agentState: 'waiting',
          phase: 'waiting',
          role: 'safety',
          waitingApproval: true,
          approvalText: event.question || '사용자 승인 대기',
          risk: event.risk || 'confirm',
          evidence: event.command
            ? appendEvidence(current, '승인 대상 명령', event.command.slice(0, 80), now)
            : current.evidence,
        }

      case 'workflow_update': {
        const summary = summarizeWorkflow(event.workflow)
        return { ...current, goal: summary.goal, step: summary.step }
      }

      case 'context_usage':
        return { ...current, contextText: `${event.tokens_used || 0}/${event.tokens_total || 0}` }

      case 'vision_capture':
        return {
          ...current,
          phase: current.phase === 'executing' ? 'observing' : current.phase,
          role: current.role === 'executor' ? 'observer' : current.role,
          evidence: appendEvidence(current, '화면 캡처', event.image_b64 ? '이미지 수집됨' : '캡처 이벤트', now),
        }

      case 'done':
        return {
          ...resetTerminalFields(current),
          agentState: 'idle',
          phase: 'done',
          role: 'orchestrator',
          lastError: '',
        }

      case 'error':
        return {
          ...resetTerminalFields(current),
          agentState: 'error',
          phase: 'error',
          role: 'orchestrator',
          lastError: event.message || '알 수 없는 오류',
        }

      default:
        return current
    }
  }

  return {
    INITIAL,
    initialState,
    reduce,
    summarizeWorkflow,
  }
})

const assert = require('assert')
const SupervisorState = require('../../electron/renderer/supervisor-state.js')

function apply(events) {
  return events.reduce(
    (state, event, idx) => SupervisorState.reduce(state, event, {
      nowMs: 1000 + idx * 100,
      now: new Date(2026, 5, 15, 9, 0, idx),
    }),
    SupervisorState.initialState()
  )
}

{
  const state = apply([
    { request_id: 'req-1' },
    { type: 'agent_state', state: 'thinking' },
    { type: 'workflow_update', workflow: { title: '문서 작성', steps: [{ id: 's1', title: '초안', status: 'pending' }] } },
  ])
  assert.equal(state.requestId, 'req-1')
  assert.equal(state.phase, 'planning')
  assert.equal(state.role, 'planner')
  assert.equal(state.goal, '문서 작성')
}

{
  const state = apply([
    { request_id: 'req-2' },
    { type: 'tool_start', tool: 'excel_set_cells', label: 'Excel 입력' },
    { type: 'tool_done', tool: 'excel_set_cells', result: 'ok' },
  ])
  assert.equal(state.currentTool, '')
  assert.equal(state.phase, 'observing')
  assert.equal(state.role, 'observer')
  assert.equal(state.evidence[0].text, 'excel_set_cells: ok')
}

{
  const state = apply([
    { request_id: 'req-3' },
    { type: 'confirm', question: '파일을 덮어쓸까요?', risk: 'write', command: 'save report.xlsx' },
  ])
  assert.equal(state.agentState, 'waiting')
  assert.equal(state.phase, 'waiting')
  assert.equal(state.role, 'safety')
  assert.equal(state.waitingApproval, true)
  assert.equal(state.risk, 'write')
  assert.match(state.evidence[0].text, /승인 대상 명령/)
}

{
  const state = apply([
    { request_id: 'req-4' },
    { type: 'tool_start', tool: 'run_command' },
    { type: 'done' },
  ])
  assert.equal(state.agentState, 'idle')
  assert.equal(state.phase, 'done')
  assert.equal(state.role, 'orchestrator')
  assert.equal(state.currentTool, '')
}

{
  const state = apply([
    { request_id: 'req-5' },
    { type: 'tool_start', tool: 'run_command' },
    { type: 'error', message: 'boom' },
  ])
  assert.equal(state.agentState, 'error')
  assert.equal(state.phase, 'error')
  assert.equal(state.role, 'orchestrator')
  assert.equal(state.lastError, 'boom')
}

console.log('supervisor-state fixtures passed')

const assert = require('assert')
const LedgerHistory = require('../../electron/renderer/ledger-history.js')

{
  const entries = LedgerHistory.normalizeLedgerEntries({
    entries: [
      {
        event_type: 'run_started',
        timestamp: '2026-06-15T09:00:00+09:00',
        phase: 'planning',
        role: 'planner',
        summary: 'Run started',
        details: {},
      },
      {
        event_type: 'tool_finished',
        timestamp: '2026-06-15T09:02:00+09:00',
        phase: 'observing',
        role: 'observer',
        summary: 'ok',
        details: { tool: 'read_file', success: true, result_summary: 'ok' },
      },
    ],
  })

  assert.equal(entries.length, 2)
  assert.equal(entries[0].event, 'tool_finished')
  assert.equal(entries[0].label, '도구 완료')
  assert.equal(entries[0].phaseRole, 'observing · observer')
  assert.equal(entries[0].tone, 'success')
}

{
  const entries = LedgerHistory.normalizeLedgerEntries({
    entries: [
      { event_type: 'phase_changed', timestamp: '2026-06-15T09:00:00+09:00', summary: 'executing' },
      { event_type: 'role_changed', timestamp: '2026-06-15T09:00:01+09:00', summary: 'executor' },
      { event_type: 'tool_started', timestamp: '2026-06-15T09:00:02+09:00', details: { tool: 'run_command' } },
    ],
  })

  assert.deepEqual(entries.map(e => e.event), ['tool_started'])
}

{
  const entries = LedgerHistory.normalizeLedgerEntries({
    entries: [
      { event: 'done', ts: '2026-06-15T09:00:00+09:00', phase: 'done', detail: 'legacy ok' },
      { event: 'error', ts: '2026-06-15T09:01:00+09:00', phase: 'error', detail: 'legacy fail' },
      { event: 'ignored', ts: '2026-06-15T09:02:00+09:00', phase: 'done' },
    ],
  })

  assert.deepEqual(entries.map(e => e.event), ['error', 'done'])
  assert.equal(entries[0].label, '이전 오류')
  assert.equal(entries[0].tone, 'error')
}

{
  const payload = { entries: [] }
  for (let i = 0; i < 7; i += 1) {
    payload.entries.push({
      event_type: 'tool_started',
      timestamp: `2026-06-15T09:0${i}:00+09:00`,
      phase: 'executing',
      role: 'executor',
      details: { tool: `tool_${i}` },
    })
  }

  const entries = LedgerHistory.normalizeLedgerEntries(payload)
  assert.equal(entries.length, 5)
  assert.deepEqual(entries.map(e => e.summary), [
    'tool_6',
    'tool_5',
    'tool_4',
    'tool_3',
    'tool_2',
  ])
}

{
  const entries = LedgerHistory.normalizeLedgerEntries({
    entries: [
      {
        event_type: 'approval_resolved',
        timestamp: '2026-06-15T09:00:00+09:00',
        phase: 'waiting',
        role: 'safety',
        summary: '<img src=x onerror=alert(1)>',
        details: { choice: '<b>예</b>' },
      },
    ],
  })
  const html = LedgerHistory.renderLedgerHistoryHtml(entries)

  assert.match(html, /&lt;b&gt;예&lt;\/b&gt;/)
  assert.doesNotMatch(html, /<b>예<\/b>/)
  assert.doesNotMatch(html, /onerror=alert/)
}

{
  assert.deepEqual(LedgerHistory.normalizeLedgerEntries({}), [])
  assert.deepEqual(LedgerHistory.normalizeLedgerEntries(null), [])
  assert.deepEqual(LedgerHistory.normalizeLedgerEntries({ entries: [null, 'x', { details: {} }] }), [])
  assert.equal(LedgerHistory.renderLedgerHistoryHtml([]), '')
}

console.log('ledger-history fixtures passed')

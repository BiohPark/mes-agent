// Pure RunLedger history helpers shared by the Electron renderer and Node tests.
(function (root, factory) {
  const api = factory()
  if (typeof module !== 'undefined' && module.exports) module.exports = api
  root.LedgerHistory = api
})(typeof globalThis !== 'undefined' ? globalThis : window, function () {
  const STRUCTURED_EVENTS = new Set([
    'run_started',
    'tool_started',
    'tool_waited',
    'tool_finished',
    'approval_requested',
    'approval_resolved',
    'run_finished',
  ])

  const LEGACY_EVENTS = new Set(['done', 'error', 'stopped', 'max_steps'])

  const LABELS = Object.freeze({
    run_started: '실행 시작',
    tool_started: '도구 시작',
    tool_waited: '도구 지연',
    tool_finished: '도구 완료',
    approval_requested: '승인 요청',
    approval_resolved: '승인 응답',
    run_finished: '실행 종료',
    done: '이전 완료',
    error: '이전 오류',
    stopped: '이전 중단',
    max_steps: '이전 한도 도달',
  })

  function normalizeLedgerEntries(payload, limit = 5) {
    const source = Array.isArray(payload?.entries) ? payload.entries : []
    return source
      .map(normalizeLedgerEntry)
      .filter(Boolean)
      .sort((a, b) => timestampMs(b.ts) - timestampMs(a.ts))
      .slice(0, limit)
  }

  function normalizeLedgerEntry(entry) {
    if (!entry || typeof entry !== 'object') return null
    if (entry.event_type) return normalizeStructuredLedgerEntry(entry)
    if (entry.event) return normalizeLegacyLedgerEntry(entry)
    return null
  }

  function normalizeStructuredLedgerEntry(entry) {
    const event = String(entry.event_type || '')
    if (!STRUCTURED_EVENTS.has(event)) return null
    const details = isPlainObject(entry.details) ? entry.details : {}
    const phase = cleanText(entry.phase)
    const role = cleanText(entry.role)
    return {
      ts: cleanText(entry.timestamp),
      event,
      label: LABELS[event] || event,
      phaseRole: [phase, role].filter(Boolean).join(' · '),
      summary: structuredSummary(event, entry, details),
      tone: structuredTone(event, entry, details),
    }
  }

  function normalizeLegacyLedgerEntry(entry) {
    const event = String(entry.event || '')
    if (!LEGACY_EVENTS.has(event)) return null
    const phase = cleanText(entry.phase)
    return {
      ts: cleanText(entry.ts),
      event,
      label: LABELS[event] || `이전 ${event}`,
      phaseRole: phase || 'legacy',
      summary: cleanText(entry.detail) || '이전 실행 기록',
      tone: legacyTone(event),
    }
  }

  function renderLedgerHistoryHtml(entries) {
    const safeEntries = Array.isArray(entries) ? entries.filter(Boolean) : []
    if (!safeEntries.length) return ''
    return safeEntries.map(entry => {
      const tone = safeCssToken(entry.tone || 'default')
      const event = safeCssToken(entry.event || 'unknown')
      return (
        `<div class="sv-run-entry sv-run-${tone} sv-run-event-${event}">` +
          `<div class="sv-run-main">` +
            `<span class="sv-run-ts">${escapeHtml(formatTimestamp(entry.ts))}</span>` +
            `<span class="sv-run-ev">${escapeHtml(entry.label || entry.event || 'event')}</span>` +
            `<span class="sv-run-phase">${escapeHtml(entry.phaseRole || '-')}</span>` +
          `</div>` +
          `<div class="sv-run-summary">${escapeHtml(entry.summary || '-')}</div>` +
        `</div>`
      )
    }).join('')
  }

  function structuredSummary(event, entry, details) {
    const summary = cleanText(entry.summary)
    const tool = cleanText(details.tool)
    const label = cleanText(details.label)
    const choice = cleanText(details.choice)
    const failureClass = cleanText(details.failure_class || details.failureClass)

    if (event === 'tool_started') return [tool, label || summary].filter(Boolean).join(': ') || '도구 실행 시작'
    if (event === 'tool_finished') {
      const status = details.success === false ? '실패' : '완료'
      return [tool, status, failureClass || summary].filter(Boolean).join(' · ')
    }
    if (event === 'tool_waited') return summary || [tool, '예상보다 오래 걸리는 중'].filter(Boolean).join(' · ')
    if (event === 'approval_requested') return summary || '사용자 승인 대기'
    if (event === 'approval_resolved') return choice ? `선택: ${choice}` : (summary || '승인 응답 기록')
    if (event === 'run_finished') return summary || cleanText(details.status) || '실행 종료'
    if (event === 'run_started') return summary || '실행 시작'
    return summary || event
  }

  function structuredTone(event, entry, details) {
    if (event === 'tool_waited') return 'warning'
    if (event === 'approval_requested') return 'approval'
    if (event === 'tool_started' || event === 'run_started') return 'running'
    if (event === 'tool_finished') return details.success === false ? 'error' : 'success'
    if (event === 'run_finished') {
      const status = cleanText(details.status).toLowerCase()
      const phase = cleanText(entry.phase).toLowerCase()
      if (status === 'error' || phase === 'error') return 'error'
      if (status === 'stopped') return 'warning'
      return 'success'
    }
    return 'default'
  }

  function legacyTone(event) {
    if (event === 'done') return 'success'
    if (event === 'max_steps') return 'warning'
    if (event === 'error' || event === 'stopped') return 'error'
    return 'legacy'
  }

  function cleanText(value) {
    if (value == null) return ''
    return String(value).replace(/\s+/g, ' ').trim()
  }

  function formatTimestamp(ts) {
    const value = cleanText(ts)
    if (!value) return '-'
    return value.slice(0, 16).replace('T', ' ')
  }

  function timestampMs(ts) {
    const parsed = Date.parse(cleanText(ts))
    return Number.isFinite(parsed) ? parsed : 0
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  function safeCssToken(value) {
    const token = String(value || '').toLowerCase().replace(/[^a-z0-9_-]/g, '-')
    return token || 'unknown'
  }

  function isPlainObject(value) {
    return !!value && typeof value === 'object' && !Array.isArray(value)
  }

  return {
    normalizeLedgerEntries,
    normalizeLedgerEntry,
    normalizeStructuredLedgerEntry,
    normalizeLegacyLedgerEntry,
    renderLedgerHistoryHtml,
  }
})

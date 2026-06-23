# Company PC B-0 Checklist

> Status: ready for company-PC execution · Priority: P0 prep · Owner: human + computer-use agent

## Goal

Confirm the real document/backend path before implementing SharePoint or Office backend code. The result of this checklist decides whether the GMP evaluation uses existing local/COM tools, existing Graph tools, or a future on-prem SharePoint client.

## Preconditions

- MES Agent starts on the company PC.
- `HARNESS_ENABLED=true` is available for the evaluation run.
- Edge is installed and can access the corporate portal.
- Microsoft Office desktop apps are installed if the normal workflow uses local Office files.
- Obsidian Vault path and Local REST API settings are known, or direct Vault file access is configured.

## Checklist

- [ ] SharePoint or document portal opens in Edge.
- [ ] Login/SSO state is already valid, or the user can log in manually.
- [ ] A representative GMP function specification can be opened read-only.
- [ ] Opening method is recorded:
  - File Explorer path: `\\server\share\...`, mapped drive, OneDrive folder, or local path.
  - Browser URL: full address bar URL, including host and site path.
- [ ] Host type is classified:
  - Network/local/sync folder: use existing `office_locate_file` + COM path.
  - `*.sharepoint.com` or M365 endpoint: use existing Graph path if token/base URL is available.
  - `*.sbiologics.com` or on-prem SharePoint: plan `agent/tools/office_sp.py` in a later task.
  - Other portal/OnlyOffice: document as backend path D.
- [ ] Download or sync availability is recorded.
- [ ] Excel COM can open/read a local sample without prompt loops.
- [ ] Obsidian search/read/write works for a non-sensitive evaluation note.
- [ ] `GET /threads/{type}/{id}/ledger` returns entries after a test run.
- [ ] `GET /threads/{type}/{id}/harness/metrics` returns harness metrics after a harness-enabled run.

## Evidence To Record

- Company PC date/time.
- Document host and opening method.
- Sample document name or sanitized identifier.
- Whether original files were left unchanged.
- Login prompts encountered and whether the user had to intervene.
- Any blocked action, delay, repeated selector failure, or confusing UX moment.

## Result Recording Template

Fill in this table after running the checklist on the company PC. One row per run/date.

| Field | Value |
|-------|-------|
| Date/time | |
| Document host | (e.g. `*.sharepoint.com`, network share, OneDrive, other portal) |
| Opening method observed | (File Explorer path / browser URL — full address bar value) |
| Sample document identifier | (sanitized name or ID, no sensitive content) |
| Original files unchanged? | Yes / No — note any unexpected write |
| Login/SSO friction | (none / manual login required / prompt loop / other) |
| Backend path chosen (A/B/C/D) | |
| Why this path | |
| `GET /threads/{type}/{id}/ledger` check | Pass / Fail — note response shape or error |
| `GET /threads/{type}/{id}/harness/metrics` check | Pass / Fail — note response shape or error |

> Add one table (or one filled set of rows) per company-PC session. Keep raw sensitive content
> out of this file — sanitize document names/URLs before recording.

### 2026-06-23 local dry-run

| Field | Value |
|-------|-------|
| Date/time | 2026-06-23 21:40:22 +09:00 |
| Document host | local fixture only |
| Opening method observed | REST dry-run input; no browser or Office document opened |
| Sample document identifier | `tests/fixtures/gmp_function_spec_sample.csv` |
| Original files unchanged? | Yes; no original GMP document was accessed |
| Login/SSO friction | none; Computer Use bootstrap failed earlier with local `AppData` permission error, so UI automation was not used for this dry-run |
| Backend path chosen (A/B/C/D) | Path A dry-run only |
| Why this path | Local sanitized CSV fixture was selected to validate the MES server, RunLedger, and harness metrics flow without touching company documents |
| `GET /threads/{type}/{id}/ledger` check | Pass; baseline threads returned 5 entries, harness threads returned 6 entries including `harness_round` |
| `GET /threads/{type}/{id}/harness/metrics` check | Pass; harness threads `2026-06-23-005` to `2026-06-23-007` returned `total_reviews=1`, `retries=0`, `final_passed=true`, `self_corrected=false`, `max_history_tokens=1138` |

This row does not classify the real company document backend. Repeat B-0 with a representative
read-only GMP document before deciding Path B/C/D or implementing `agent/tools/office_sp.py`.

## Decision

- **Path A: local/network/sync file** — no new backend; run GMP evaluation via local copy + COM/OpenXML.
- **Path B: on-prem SharePoint** — add a future SharePoint REST roundtrip layer after this checklist is complete.
- **Path C: M365/Graph** — configure `GRAPH_BASE_URL`/`GRAPH_ACCESS_TOKEN` and reuse existing cloud Office tools.
- **Path D: other web editor** — keep browser/keyboard automation as fallback and prefer download/local roundtrip where allowed.

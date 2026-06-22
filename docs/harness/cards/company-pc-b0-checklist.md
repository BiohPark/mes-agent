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

## Decision

- **Path A: local/network/sync file** — no new backend; run GMP evaluation via local copy + COM/OpenXML.
- **Path B: on-prem SharePoint** — add a future SharePoint REST roundtrip layer after this checklist is complete.
- **Path C: M365/Graph** — configure `GRAPH_BASE_URL`/`GRAPH_ACCESS_TOKEN` and reuse existing cloud Office tools.
- **Path D: other web editor** — keep browser/keyboard automation as fallback and prefer download/local roundtrip where allowed.

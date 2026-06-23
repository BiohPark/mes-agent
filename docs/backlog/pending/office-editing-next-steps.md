# Office Editing Next Steps

> Status: implementation mostly complete for local/COM and Graph paths. Remaining backend work is
> blocked on real company document B-0 classification.

## Current Capability

Implemented:

- Local Office COM editing for Word, Excel, and PowerPoint.
- LibreOffice fallback conversion.
- `office_locate_file` roundtrip prompt/finder.
- Graph Excel range read/write with configurable `GRAPH_BASE_URL`.
- Browser entry fallback for web-only editors.
- Active Excel COM helpers for explicitly opened workbooks.

## Blocking Question

How do representative company GMP documents open in normal use?

Use `docs/harness/cards/company-pc-b0-checklist.md` and classify:

| Path | Observed backend | Implementation decision |
|------|------------------|-------------------------|
| A | Local path, network share, mapped drive, OneDrive/sync folder | Use existing locate + COM/OpenXML flow. No new backend. |
| B | On-prem SharePoint, usually company domain such as `*.sbiologics.com` | Plan `agent/tools/office_sp.py` SharePoint REST download/local-edit/upload roundtrip. |
| C | M365/Graph, usually `*.sharepoint.com` or configured internal Graph endpoint | Reuse `office_cloud.py`; configure token/base URL. |
| D | Other portal/OnlyOffice/web editor | Prefer download/local roundtrip where allowed; otherwise browser automation fallback. |

## Guardrails

- Do not implement Path B until B-0 confirms it.
- Do not upload or overwrite an original document without explicit approval.
- Do not store credentials in code.
- Keep backend-specific settings in `.env` (`SHAREPOINT_*`, `GRAPH_*`, `ONLYOFFICE_*`), not in
  source files.

## If Path B Is Confirmed

Create a focused SharePoint REST task with:

- `sp_download(server_relative_path)` and `sp_upload(server_relative_path, local_path)` shape.
- Auth strategy chosen from the actual environment: integrated auth, NTLM/Kerberos, ADFS, or
  approved token flow.
- Mocked HTTP tests for URL construction and failure handling.
- Roundtrip design: download -> local temp file -> COM/OpenXML edit/analysis -> explicit upload
  only after approval.

## If Path A Is Confirmed

No new tool is needed. Improve only configuration and docs:

- add relevant roots to `OFFICE_SEARCH_ROOTS` if needed,
- record known sync/download friction,
- run the GMP live Phase 4 procedure with local/sync input.

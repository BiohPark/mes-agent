# Office 편집 — 다음 작업 가이드 (환경 확인 후)

> 작성: 2026-06-08. 현재 Office 편집은 **로컬 COM + LibreOffice 폴백 + 라운드트립(`office_locate_file`) + MS Graph Excel + 브라우저 진입(`office_web_open`)** 까지 구현됨.
> 남은 결정은 **사내 문서 백엔드 확정**이며, 그에 따라 아래 경로 중 하나를 구현한다.

---

## 0. 먼저 확인할 것 (회사 PC에서)

사내 Office 문서(`sbiologics.com` 관련)가 **실제로 어디 사는지** 한 가지만 확정한다. 실제 문서를 평소처럼 연 뒤:

- **파일 탐색기 경로**로 열린다 → `\\서버\공유\...` 또는 `Z:\...` 또는 로컬 폴더 ⇒ **(A) 네트워크/로컬**
- **브라우저 주소창 URL**로 열린다 → 그 URL을 그대로 기록 (예: `https://xxx.sbiologics.com/sites/팀/_layouts/15/Doc.aspx?...`) ⇒ **(B) 온프렘 SharePoint** 또는 **(C) 사내 M365**
- **OneDrive 폴더**(구름 아이콘)에 있다 ⇒ **(A')** 동기화 로컬 → 이미 해결됨

> 판별 팁: 주소가 `*.sharepoint.com` 이면 공개 M365(현 Graph 그대로), `*.sbiologics.com`(사내 호스트)면 온프렘 SharePoint 가능성↑, MS 로그인 화면이 `login.microsoftonline.com`이 아니라 사내 ADFS면 사내/Sovereign M365.

---

## A. 네트워크 드라이브 / 로컬 / OneDrive 동기화  → **추가 작업 없음** ✅

문서가 UNC/매핑드라이브/동기화 폴더의 로컬 파일이면 **이미 만든 도구로 끝**이다.
- 찾기: `office_locate_file("문서명")`
- 편집: `word_edit_text` · `word_insert_text` · `excel_set_cells` · `ppt_replace_text` (COM, 완전충실도)
- 변환: `word_export_pdf` / `libre_convert`
- 저장 안전장치: 자동 백업(.bak) 내장.

**할 일**: `office_locate_file`의 탐색 루트에 사내 매핑드라이브(예: `Z:`, `\\nas\share`)를 추가할지 검토 → 필요 시 `_safety`/env로 루트 목록 확장.

---

## B. 온프렘 SharePoint Server  → **SharePoint REST 클라이언트 신규 구현**

`*.sbiologics.com` 사내 SharePoint면 **MS Graph(공개 클라우드)는 안 됨**. 그 호스트의 SharePoint REST API를 쓴다.

- 다운로드: `GET https://<host>/sites/<site>/_api/web/GetFileByServerRelativeUrl('/sites/<site>/문서/파일.docx')/$value`
- 체크아웃/인: `.../CheckOut()` · `.../CheckIn(comment='...',checkintype=0)` (POST)
- 업로드(덮어쓰기): `PUT .../GetFileByServerRelativeUrl('...')/$value` (본문=바이트)
- 인증(인트라넷): **NTLM/Kerberos** — `requests_ntlm` 또는 `requests-negotiate-sspi`(Windows 통합인증). 또는 ADFS 폼인증 토큰.
- **권장 패턴(라운드트립)**: 다운로드 → 로컬 임시파일 → **COM/LibreOffice로 편집** → 업로드. (in-browser 편집 회피)

**구현 스케치**: 새 모듈 `agent/tools/office_sp.py`
- `sp_download(site_url, server_relative_path)` → 로컬 경로
- `sp_upload(site_url, server_relative_path, local_path)` (체크아웃→업로드→체크인)
- env: `SP_BASE_URL`, 인증(`SP_AUTH=ntlm|negotiate`, 자격증명은 통합인증 우선)
- 테스트: 요청 URL/메서드 구성을 mock으로 검증(라이브 불필요).

---

## C. 사내 전용 / Sovereign M365  → **P4 Graph에 base URL만 추가** (거의 완료)

Graph는 되지만 엔드포인트가 공개(`graph.microsoft.com`)와 다를 수 있다.
- 이미 `office_cloud.py`가 `GRAPH_BASE_URL` 환경변수를 읽도록 처리됨 → `.env`에 사내 엔드포인트 지정하면 동작.
- 인증 토큰(`GRAPH_ACCESS_TOKEN`) 발급 절차만 사내 기준으로 확인(Azure AD/ADFS, device code, 또는 `az account get-access-token --resource <graph-resource>`).

**할 일**: 토큰 자동 취득(선택) — device code flow 또는 `az` 연동 헬퍼. 현재는 토큰 주입 방식.

---

## D. OnlyOffice Document Server 자체호스팅 (P3, 폐쇄망 최강 옵션)

사내에 OnlyOffice Docs를 띄우면 브라우저 협업 편집 + 헤드리스 API를 모두 얻는다.
- **변환 API**: `POST https://<onlyoffice>/ConvertService.ashx` (JSON, **JWT 서명 필수**). 입력 문서는 서버가 접근 가능한 URL이어야 함(우리 서버가 임시 파일 서빙 필요).
- **Document Builder**: `.docbuilder` 스크립트(JS)로 UI 없이 생성·편집·변환. 로컬 `docbuilder` 실행파일 또는 서버 빌더.
- 전제: 서버 호스팅 + `ONLYOFFICE_URL` + `ONLYOFFICE_JWT_SECRET`.

**구현 스케치**: `agent/tools/office_onlyoffice.py`
- `oo_convert(local_path, to_format)` — 임시 HTTP로 입력 서빙 → ConvertService 호출(JWT) → 결과 다운로드
- env: `ONLYOFFICE_URL`, `ONLYOFFICE_JWT_SECRET`, `ONLYOFFICE_CALLBACK_HOST`(우리 서버가 접근 가능한 주소)
- 테스트: JWT 서명·요청 바디 구성을 mock 검증.

---

## 브라우저 웹 편집의 한계 (현재 동작 방식)

`office_web_open`은 편집기 종류/편집가능 여부를 **진단**하고, 반환값 `known_limitation`·`recommended_next`로 **솔직히 한계를 고지**한다: 웹 편집기는 iframe+캔버스라 `browser_click` selector 편집이 거의 불가. 그래서 에이전트는 **① 로컬사본 COM → ② Graph → ③ 키보드(Ctrl+H)+UI Automation → ④ 실패 시 원인 보고** 순으로 폴백하도록 유도된다.

> 결론: 대부분의 사내 시나리오는 **A(네트워크/동기화 → COM)** 또는 **B(온프렘 SharePoint → 다운로드→COM→업로드)** 로 귀결될 가능성이 높다. 회사에서 위 0번을 확인한 뒤 해당 섹션을 구현하면 된다.

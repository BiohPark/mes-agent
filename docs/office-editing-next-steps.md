# Office 편집 — 다음 작업 가이드

> 작성: 2026-06-08. 현재 구현: **로컬 COM(Word·Excel·PPT) + LibreOffice 폴백 + 라운드트립(`office_locate_file`) + MS Graph Excel + 브라우저 진입(`office_web_open`)**.
> 남은 결정은 **사내 문서 백엔드 확정**(`sbiologics.com`은 일반 O365가 아닌 사내 전용). 회사 PC에서 아래 *개발자용* 체크리스트를 확인한 뒤 해당 경로를 구현한다.

이 문서는 두 독자로 나눠 적는다.
- **[A] 에이전트용** — 런타임에 문서 편집 요청을 받았을 때 따라야 할 행동 규칙.
- **[B] 개발자용** — 회사에서 무엇을 확인하고, 백엔드별로 무엇을 구현하는지.

---

# [A] 에이전트용 — 문서 편집 요청 시 행동 규칙

문서를 편집/작성하라는 요청을 받으면 **아래 사다리를 위에서부터** 시도한다. 위가 가능하면 아래로 내려가지 않는다.

1. **로컬/동기화 사본 먼저** — `office_locate_file("문서명")`으로 찾는다.
   - 찾으면: `word_edit_text`·`word_insert_text`·`excel_set_cells`·`ppt_replace_text`(COM, 완전충실도)로 편집. 새 문서는 `write_word`/`write_excel`/`ppt_add_slide`.
   - 변환·PDF: `word_export_pdf`/`ppt_export_pdf`(COM, 없으면 `libre_convert` 자동 폴백).
2. **M365 클라우드 Excel** — `GRAPH_ACCESS_TOKEN`이 있으면 `graph_find_item` → `graph_excel_set_range`/`get_range`로 셀·수식 직접 편집.
3. **웹에서만 열리는 문서** — `office_web_open(url 또는 상대경로)`.
   - 반환값의 **`known_limitation`을 인지**: 웹 편집기는 iframe+캔버스라 `browser_click` selector 편집이 거의 불가능하다. 절대 같은 클릭을 반복하지 마라.
   - 편집은 **키보드 중심**: 문서에 포커스 → `browser_press_key('Control+h')`(찾아바꾸기)·타이핑 → `Control+s`(자동저장이면 불필요).
   - 정확한 좌표가 필요하면 `analyze_screen`/`ui_inspect_window`로 위치를 먼저 확인(스크린샷·OCR).
4. **막히면 솔직히 보고** — 추측으로 망가뜨리지 말고, *무엇을 시도했는지·어디서 막혔는지(편집기 종류·로그인/권한·셀렉터 실패 등)·다음 선택지*를 정리해 `ask_user`로 사용자에게 선택지를 제시한다.

**안전 규칙(항상)**: 기존 파일을 덮어쓰는 비가역 저장 직전에는 `ask_user`로 확인한다. COM/편집 도구는 편집 전 자동 백업(.bak)을 만든다. 시스템 보호경로 쓰기는 차단된다.

> 핵심 원칙: **웹 직접 편집은 최후수단.** 같은 문서의 로컬/동기화 사본이나 Graph 경로가 거의 항상 더 정확하다. 먼저 그쪽을 찾아라.

---

# [B] 개발자용 — 회사에서 확인 & 백엔드별 구현

## B-0. 회사 PC에서 확인할 체크리스트 (구체적으로)

사내 Office 문서를 **평소처럼 한 번 연 뒤** 아래를 기록한다.

- [ ] **여는 방식**: 파일 탐색기 경로로 열리는가, 브라우저로 열리는가?
- [ ] **파일 경로**(탐색기인 경우): 정확한 형태 — `\\서버\공유\...` / 매핑드라이브 `Z:\...` / 로컬 `C:\Users\...` / OneDrive 폴더(구름 아이콘)?
- [ ] **브라우저 URL**(브라우저인 경우): 주소창 전체를 복사 — 예 `https://portal.sbiologics.com/sites/팀/_layouts/15/Doc.aspx?sourcedoc=...`
- [ ] **호스트 판별**: 주소가 `*.sharepoint.com`(공개 M365) vs `*.sbiologics.com`(사내 온프렘) vs 기타?
- [ ] **로그인 화면 도메인**: `login.microsoftonline.com`(공개 M365) vs 사내 ADFS(`sts.sbiologics.com` 등)?
- [ ] **다운로드 가능 여부**: 그 문서를 로컬로 다운로드/동기화할 수 있는가? (가능하면 라운드트립이 최선)

확인한 값은 **`.env`에 기입**한다(코드 하드코딩 금지):
- `SHAREPOINT_BASE_URL=https://portal.sbiologics.com` — 사내 포털/SharePoint 호스트
- `GRAPH_BASE_URL=...` — 사내 전용/Sovereign M365인 경우 그래프 엔드포인트
- `GRAPH_ACCESS_TOKEN=...` — M365 토큰(Files.ReadWrite)

## B-1. 결정 트리

| 확인 결과 | 경로 | 구현 |
|---|---|---|
| 파일 탐색기 경로(`\\`, `Z:`, OneDrive 폴더) | **A. 네트워크/동기화** | **추가작업 없음** — 기존 COM으로 끝 ✅ |
| 브라우저 URL이 `*.sbiologics.com` (온프렘) | **B. 온프렘 SharePoint** | SharePoint REST 클라이언트 신규 |
| 브라우저 URL이 `*.sharepoint.com` 또는 사내 M365 | **C. M365** | Graph(P4) — base URL/토큰만 |
| 사내 OnlyOffice 등 포털 | **D. OnlyOffice** | 변환/빌더 API |

## B-2. 경로 A — 네트워크/로컬/OneDrive 동기화 → 추가작업 없음 ✅

`office_locate_file`의 탐색 루트에 사내 매핑드라이브(예: `Z:`, `\\nas\share`)를 추가할지만 검토. 필요 시 env(`OFFICE_SEARCH_ROOTS`)로 루트 목록 확장.

## B-3. 경로 B — 온프렘 SharePoint Server → SharePoint REST 신규 (`agent/tools/office_sp.py`)

`*.sbiologics.com` 사내 SharePoint면 MS Graph(공개) 불가. 그 호스트의 REST API 사용:
- 다운로드: `GET {SHAREPOINT_BASE_URL}/sites/<site>/_api/web/GetFileByServerRelativeUrl('<server-rel-path>')/$value`
- 체크아웃/인: `.../CheckOut()` · `.../CheckIn(comment='',checkintype=0)` (POST)
- 업로드(덮어쓰기): `PUT .../GetFileByServerRelativeUrl('...')/$value` (본문=바이트)
- 인증: **NTLM/Kerberos 통합인증** — `requests_ntlm` 또는 `requests-negotiate-sspi`(Windows). 또는 ADFS 폼인증.
- **권장 패턴(라운드트립)**: 다운로드 → 로컬 임시파일 → COM/LibreOffice 편집 → 업로드.
- 구현: `sp_download(server_relative_path)`·`sp_upload(server_relative_path, local_path)`, env `SHAREPOINT_BASE_URL`·인증방식. 테스트는 요청 URL/메서드 mock 검증.

## B-4. 경로 C — 사내/Sovereign M365 → Graph (거의 완료)

`office_cloud.py`가 `GRAPH_BASE_URL` 환경변수를 읽도록 이미 처리됨. `.env`에 사내 엔드포인트와 `GRAPH_ACCESS_TOKEN`만 넣으면 `graph_*` 동작. 남은 것: 토큰 자동취득(device code / `az account get-access-token`) 헬퍼(선택).

## B-5. 경로 D — OnlyOffice Document Server 자체호스팅 (P3)

사내에 OnlyOffice Docs를 띄우면 브라우저 협업 편집 + 헤드리스 API 확보.
- 변환 API: `POST {ONLYOFFICE_URL}/ConvertService.ashx` (JSON, **JWT 서명 필수**, 입력은 서버가 접근 가능한 URL이어야 함).
- Document Builder: `.docbuilder` JS 스크립트로 UI 없이 생성·편집·변환.
- 구현: `agent/tools/office_onlyoffice.py`, env `ONLYOFFICE_URL`·`ONLYOFFICE_JWT_SECRET`·`ONLYOFFICE_CALLBACK_HOST`. 테스트는 JWT·바디 mock 검증.

## B-6. 환경변수 요약 (`.env`)

```ini
SHAREPOINT_BASE_URL=        # 사내 포털/SharePoint 호스트 (office_web_open 상대경로 해석에도 사용)
GRAPH_BASE_URL=             # 사내/Sovereign M365 그래프 엔드포인트 (공개면 비움)
GRAPH_ACCESS_TOKEN=         # M365 토큰 (Files.ReadWrite)
BROWSER_CHANNEL=msedge      # 사내 SSO·Office Online 호환 위해 실제 Edge 사용
LIBREOFFICE_PATH=           # MS Office 미설치 PC의 변환 폴백 (표준경로면 자동탐지)
# ONLYOFFICE_URL / ONLYOFFICE_JWT_SECRET  # 경로 D 선택 시
```

> 결론: 사내 시나리오는 **A(네트워크/동기화 → COM)** 또는 **B(온프렘 SharePoint → 다운로드→COM→업로드)** 로 귀결될 가능성이 높다. B-0를 확인해 `.env`를 채운 뒤 해당 섹션을 구현하면 된다.

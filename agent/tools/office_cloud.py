"""클라우드 Office 편집 — Microsoft Graph Excel REST 클라이언트 (P4).

M365(OneDrive/SharePoint)에 있는 Excel 워크북을 셀/수식 단위로 직접 편집한다.
MS Graph의 Excel API는 범위(range) 단위 값·수식 읽기/쓰기를 지원하며 Excel 엔진으로 재계산된다.

인증: 환경변수 GRAPH_ACCESS_TOKEN(Bearer 액세스 토큰). 미설정 시 명확한 안내를 반환한다.
  토큰 발급: Azure AD 앱 등록 후 위임/앱 권한(Files.ReadWrite) 토큰. (az account get-access-token,
  device code flow, 또는 사내 발급 절차)
의존성 없이 표준 라이브러리(urllib)만 사용한다(폐쇄망/추가설치 불필요).

문서 식별:
- item_id: 드라이브 아이템 ID (Graph로 조회한 파일 ID)
- drive: 'me'(기본, 내 OneDrive) 또는 'drives/{driveId}' 또는 'sites/{siteId}/drive' 형태의 경로 조각
"""

import os
import json
import urllib.request
import urllib.error

# 사내 전용/Sovereign M365는 그래프 엔드포인트가 다를 수 있어 환경변수로 재정의 가능
_GRAPH_BASE = os.environ.get("GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0").rstrip("/")


def _token() -> str:
    return os.environ.get("GRAPH_ACCESS_TOKEN", "").strip()


def _no_token() -> str:
    return json.dumps({
        "error": "GRAPH_ACCESS_TOKEN 환경변수가 없습니다. M365 액세스 토큰(Files.ReadWrite)을 설정하세요.",
        "engine": "none",
    }, ensure_ascii=False)


def _graph_request(method: str, path: str, body: dict | None = None, token: str = "") -> dict:
    """Graph REST 호출. 성공 시 파싱된 dict, 실패 시 {'error':...} 반환."""
    url = path if path.startswith("http") else f"{_GRAPH_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            pass
        return {"error": f"Graph HTTP {e.code}: {detail or e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _range_path(drive: str, item_id: str, worksheet: str, address: str) -> str:
    drive = (drive or "me").strip("/")
    return (f"/{drive}/items/{item_id}/workbook/worksheets('{worksheet}')"
            f"/range(address='{address}')")


def graph_excel_get_range(item_id: str, worksheet: str, address: str, drive: str = "me") -> str:
    """M365 클라우드 Excel의 범위 값을 읽습니다(MS Graph). 예: address='A1:C10'."""
    token = _token()
    if not token:
        return _no_token()
    res = _graph_request("GET", _range_path(drive, item_id, worksheet, address), None, token)
    if "error" in res:
        return json.dumps(res, ensure_ascii=False)
    return json.dumps({
        "engine": "graph", "address": res.get("address", address),
        "values": res.get("values"), "formulas": res.get("formulas"),
    }, ensure_ascii=False, default=str)


def graph_excel_set_range(item_id: str, worksheet: str, address: str,
                          values: list | None = None, formulas: list | None = None,
                          drive: str = "me") -> str:
    """M365 클라우드 Excel의 범위에 값 또는 수식을 씁니다(MS Graph, Excel 엔진 재계산).
    values 또는 formulas는 2차원 배열. 예: address='B2', formulas=[['=A2+A3']]."""
    token = _token()
    if not token:
        return _no_token()
    if values is None and formulas is None:
        return json.dumps({"error": "values 또는 formulas 중 하나는 필요합니다."}, ensure_ascii=False)
    body: dict = {}
    if values is not None:
        body["values"] = values
    if formulas is not None:
        body["formulas"] = formulas
    res = _graph_request("PATCH", _range_path(drive, item_id, worksheet, address), body, token)
    if "error" in res:
        return json.dumps(res, ensure_ascii=False)
    return json.dumps({"engine": "graph", "address": res.get("address", address),
                       "message": "클라우드 Excel 범위 업데이트 완료"}, ensure_ascii=False, default=str)


def graph_find_item(name: str, drive: str = "me") -> str:
    """이름으로 M365 드라이브의 파일 item_id를 검색합니다(편집 전 ID 확보용)."""
    token = _token()
    if not token:
        return _no_token()
    drive = (drive or "me").strip("/")
    # Graph search: /me/drive/root/search(q='name')
    res = _graph_request("GET", f"/{drive}/drive/root/search(q='{name}')", None, token) \
        if drive == "me" else _graph_request("GET", f"/{drive}/root/search(q='{name}')", None, token)
    if "error" in res:
        return json.dumps(res, ensure_ascii=False)
    items = [{"id": it.get("id"), "name": it.get("name"),
              "lastModified": it.get("lastModifiedDateTime")}
             for it in res.get("value", [])]
    return json.dumps({"engine": "graph", "count": len(items), "items": items},
                      ensure_ascii=False)


MANIFEST = [
    {
        "name": "graph_excel_get_range",
        "label": "클라우드 Excel 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "graph_excel_get_range",
                "description": ("M365(OneDrive/SharePoint) 클라우드 Excel 범위 값을 읽습니다(MS Graph). "
                                "GRAPH_ACCESS_TOKEN 필요. item_id는 graph_find_item으로 확보."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string", "description": "드라이브 아이템 ID"},
                        "worksheet": {"type": "string", "description": "시트 이름"},
                        "address": {"type": "string", "description": "예: 'A1:C10'"},
                        "drive": {"type": "string", "description": "'me'(기본)/'drives/{id}'/'sites/{id}/drive'"},
                    },
                    "required": ["item_id", "worksheet", "address"],
                },
            },
        },
        "handler": lambda a: graph_excel_get_range(a["item_id"], a["worksheet"], a["address"], a.get("drive", "me")),
    },
    {
        "name": "graph_excel_set_range",
        "label": "클라우드 Excel 편집",
        "schema": {
            "type": "function",
            "function": {
                "name": "graph_excel_set_range",
                "description": ("M365 클라우드 Excel 범위에 값/수식을 씁니다(MS Graph, Excel 엔진 재계산). "
                                "values 또는 formulas는 2차원 배열. GRAPH_ACCESS_TOKEN 필요."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string"},
                        "worksheet": {"type": "string"},
                        "address": {"type": "string", "description": "예: 'B2' 또는 'A1:B3'"},
                        "values": {"type": "array", "description": "2차원 값 배열", "items": {"type": "array"}},
                        "formulas": {"type": "array", "description": "2차원 수식 배열", "items": {"type": "array"}},
                        "drive": {"type": "string"},
                    },
                    "required": ["item_id", "worksheet", "address"],
                },
            },
        },
        "handler": lambda a: graph_excel_set_range(a["item_id"], a["worksheet"], a["address"],
                                                   a.get("values"), a.get("formulas"), a.get("drive", "me")),
    },
    {
        "name": "graph_find_item",
        "label": "클라우드 파일 검색",
        "schema": {
            "type": "function",
            "function": {
                "name": "graph_find_item",
                "description": "이름으로 M365 드라이브 파일의 item_id를 검색합니다(클라우드 편집 전 ID 확보). GRAPH_ACCESS_TOKEN 필요.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "파일명 일부"},
                        "drive": {"type": "string", "description": "'me'(기본) 또는 드라이브 경로"},
                    },
                    "required": ["name"],
                },
            },
        },
        "handler": lambda a: graph_find_item(a["name"], a.get("drive", "me")),
    },
]

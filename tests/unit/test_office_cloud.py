"""MS Graph Excel 클라우드 편집(P4) 단위 테스트.

라이브 Graph 없이, 토큰 미설정 안내와 요청(메서드/경로/바디) 구성을 mock으로 검증한다.
"""

import json
import pytest

from agent.tools import office_cloud as oc


def test_no_token_message(monkeypatch):
    monkeypatch.delenv("GRAPH_ACCESS_TOKEN", raising=False)
    res = json.loads(oc.graph_excel_get_range("item1", "Sheet1", "A1:B2"))
    assert res["engine"] == "none"
    assert "GRAPH_ACCESS_TOKEN" in res["error"]


def test_set_range_builds_patch(monkeypatch):
    monkeypatch.setenv("GRAPH_ACCESS_TOKEN", "tkn")
    captured = {}

    def fake(method, path, body=None, token=""):
        captured.update(method=method, path=path, body=body, token=token)
        return {"address": "Sheet1!B2"}

    monkeypatch.setattr(oc, "_graph_request", fake)
    res = json.loads(oc.graph_excel_set_range("itemX", "Sheet1", "B2", formulas=[["=A2+A3"]]))
    assert res["engine"] == "graph"
    assert captured["method"] == "PATCH"
    assert "items/itemX/workbook/worksheets('Sheet1')/range(address='B2')" in captured["path"]
    assert captured["body"] == {"formulas": [["=A2+A3"]]}
    assert captured["token"] == "tkn"


def test_get_range_builds_get(monkeypatch):
    monkeypatch.setenv("GRAPH_ACCESS_TOKEN", "tkn")
    captured = {}

    def fake(method, path, body=None, token=""):
        captured.update(method=method, path=path)
        return {"address": "Sheet1!A1:B2", "values": [[1, 2], [3, 4]]}

    monkeypatch.setattr(oc, "_graph_request", fake)
    res = json.loads(oc.graph_excel_get_range("itemX", "Sheet1", "A1:B2"))
    assert captured["method"] == "GET"
    assert res["values"] == [[1, 2], [3, 4]]


def test_set_range_requires_values_or_formulas(monkeypatch):
    monkeypatch.setenv("GRAPH_ACCESS_TOKEN", "tkn")
    res = json.loads(oc.graph_excel_set_range("itemX", "Sheet1", "B2"))
    assert "error" in res


def test_graph_base_url_override(monkeypatch):
    """사내 전용 M365 대비 — GRAPH_BASE_URL 재정의가 요청 URL에 반영되는지."""
    import contextlib

    monkeypatch.setattr(oc, "_GRAPH_BASE", "https://graph.internal.example/v1.0")
    captured = {}

    class _Resp:
        def read(self):
            return b"{}"

    @contextlib.contextmanager
    def fake_urlopen(req, timeout=30):
        captured["url"] = req.full_url
        yield _Resp()

    monkeypatch.setattr(oc.urllib.request, "urlopen", fake_urlopen)
    oc._graph_request("GET", "/me/items/x", None, "tkn")
    assert captured["url"].startswith("https://graph.internal.example/v1.0/me/items/x")


def test_find_item_parses(monkeypatch):
    monkeypatch.setenv("GRAPH_ACCESS_TOKEN", "tkn")
    monkeypatch.setattr(oc, "_graph_request",
                        lambda *a, **k: {"value": [{"id": "abc", "name": "예산.xlsx",
                                                     "lastModifiedDateTime": "2026-06-08"}]})
    res = json.loads(oc.graph_find_item("예산"))
    assert res["count"] == 1
    assert res["items"][0]["id"] == "abc"

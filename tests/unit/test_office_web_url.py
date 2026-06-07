"""office_web_open의 상대경로 → SHAREPOINT_BASE_URL 합성(.env 분리) 검증."""

import json

from agent.tools.browser import _resolve_doc_url, office_web_open


def test_absolute_url_unchanged(monkeypatch):
    monkeypatch.setenv("SHAREPOINT_BASE_URL", "https://portal.sbiologics.com")
    assert _resolve_doc_url("https://x.com/a") == "https://x.com/a"


def test_relative_joined_with_base(monkeypatch):
    monkeypatch.setenv("SHAREPOINT_BASE_URL", "https://portal.sbiologics.com/")
    assert _resolve_doc_url("/sites/팀/Doc.aspx") == "https://portal.sbiologics.com/sites/팀/Doc.aspx"
    assert _resolve_doc_url("sites/팀/Doc.aspx") == "https://portal.sbiologics.com/sites/팀/Doc.aspx"


def test_relative_without_base_errors(monkeypatch):
    monkeypatch.delenv("SHAREPOINT_BASE_URL", raising=False)
    res = json.loads(office_web_open("sites/팀/Doc.aspx"))
    assert "error" in res
    assert "SHAREPOINT_BASE_URL" in res["error"]

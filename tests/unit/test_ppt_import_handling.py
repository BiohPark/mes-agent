import json
import os
import sys
import tempfile
import pytest


def test_ppt_replace_returns_install_hint_when_pptx_missing(monkeypatch):
    """python-pptx 미설치 시 설치 방법을 포함한 error 반환"""
    # pptx 모듈 마스킹
    monkeypatch.setitem(sys.modules, "pptx", None)
    # 서브모듈도 마스킹 (함수가 submodule을 임포트할 경우 대비)
    for submod in list(sys.modules.keys()):
        if submod.startswith("pptx"):
            monkeypatch.setitem(sys.modules, submod, None)

    import agent.tools.office_com as mod
    monkeypatch.setattr(mod, "_HAS_PYWIN32", False)
    # _validate_ooxml이 먼저 실패하지 않도록 통과시킴
    monkeypatch.setattr(mod, "_validate_ooxml", lambda path: None)

    with tempfile.TemporaryDirectory() as tmpdir:
        pptx_path = os.path.join(tmpdir, "test.pptx")
        with open(pptx_path, "wb") as f:
            f.write(b"dummy")

        from agent.tools.office_com import ppt_replace_text
        result = json.loads(ppt_replace_text(pptx_path, "old", "new"))

    assert "error" in result, f"error 키 없음: {result}"
    error_msg = result["error"]
    assert "python-pptx" in error_msg, f"패키지명 누락: {error_msg}"
    assert "pip install" in error_msg, f"설치 명령 누락: {error_msg}"

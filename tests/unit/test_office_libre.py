"""LibreOffice 헤드리스 변환 엔진(오프라인 폴백) 단위 테스트.

- LibreOffice 미설치 환경: 명확한 안내(engine=none) 반환을 검증
- 설치 환경: 실제 docx→pdf 변환 검증(skipif)
"""

import json
import pytest

from agent.tools import office_libre as ol
from agent.tools.document import write_word


def test_find_soffice_returns_path_or_none():
    # 머신에 따라 경로 또는 None — 호출이 예외 없이 동작하는지만 확인
    val = ol.find_soffice()
    assert val is None or isinstance(val, str)


@pytest.mark.skipif(ol.is_available(), reason="LibreOffice 설치 환경 — 미설치 경로 테스트 생략")
def test_libre_convert_reports_missing(tmp_path):
    path = tmp_path / "d.docx"
    write_word(str(path), "내용", "T")
    res = json.loads(ol.libre_convert(str(path), "pdf"))
    assert res["engine"] == "none"
    assert "soffice" in res["error"].lower() or "libreoffice" in res["error"]
    assert ol.to_pdf(str(path)) is None


@pytest.mark.skipif(not ol.is_available(), reason="LibreOffice 미설치 환경")
def test_libre_convert_to_pdf(tmp_path):
    path = tmp_path / "d.docx"
    write_word(str(path), "내용 테스트", "T")
    res = json.loads(ol.libre_convert(str(path), "pdf"))
    assert "error" not in res
    assert res["engine"] == "libreoffice"
    import os
    assert os.path.exists(res["path"])

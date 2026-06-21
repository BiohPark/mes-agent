"""AA-1: Excel 저장 후 무결성 검증 테스트

저장 직후 _verify_xlsx()를 호출해 손상된 파일을 "완료" 대신 error JSON으로
반환하는지 검증한다.
"""

import zipfile
import json
import tempfile
import pytest
from pathlib import Path


from agent.tools.office_com import _verify_xlsx


@pytest.fixture()
def td():
    """Windows에서 tmp_path 권한 문제를 우회하기 위해 tempfile 모듈 직접 사용."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def test_verify_xlsx_raises_on_non_zip(td):
    bad = td / "corrupt.xlsx"
    bad.write_bytes(b"this is not a zip file at all")
    with pytest.raises(RuntimeError, match="손상"):
        _verify_xlsx(str(bad))


def test_verify_xlsx_raises_on_zip_missing_workbook(td):
    path = td / "empty.xlsx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("random.txt", "content")
    with pytest.raises(RuntimeError, match="workbook.xml"):
        _verify_xlsx(str(path))


def test_verify_xlsx_passes_for_valid_openpyxl_file(td):
    import openpyxl
    path = td / "valid.xlsx"
    wb = openpyxl.Workbook()
    wb.save(path)
    _verify_xlsx(str(path))  # 예외 없어야 함


def test_excel_set_cells_returns_error_on_corrupted_save(td, monkeypatch):
    """openpyxl 저장 후 파일이 손상되면 error JSON 반환 (completed 아님)"""
    import openpyxl
    path = td / "test.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "원본"
    wb.save(path)

    original_save = openpyxl.Workbook.save

    def broken_save(self, filename):
        original_save(self, filename)
        Path(filename).write_bytes(b"CORRUPTED")

    monkeypatch.setattr(openpyxl.Workbook, "save", broken_save)

    import agent.tools.office_com as mod
    monkeypatch.setattr(mod, "_HAS_PYWIN32", False)

    from agent.tools.office_com import excel_set_cells
    result = json.loads(excel_set_cells(str(path), {"A1": "변경값"}))
    assert "error" in result, f"expected 'error' key in result: {result}"
    error_msg = result["error"].lower()
    assert "손상" in result["error"] or "corrupt" in error_msg, (
        f"expected '손상' or 'corrupt' in error message: {result['error']}"
    )

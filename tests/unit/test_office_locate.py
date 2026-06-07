"""office_locate_file(라운드트립 P2) 단위 테스트.

OneDrive/사용자 폴더 대신 임시 디렉터리를 HOME으로 잡아 탐색 동작을 검증한다.
"""

import json
import os

from agent.tools.document import office_locate_file


def test_locate_finds_office_files(tmp_path, monkeypatch):
    # HOME을 임시 폴더로 바꾸고 Documents/하위에 파일 생성
    docs = tmp_path / "Documents" / "팀"
    docs.mkdir(parents=True)
    (docs / "분기보고서_v2.docx").write_text("x", encoding="utf-8")
    (docs / "예산.xlsx").write_text("x", encoding="utf-8")
    (docs / "메모.txt").write_text("x", encoding="utf-8")  # Office 아님 → 제외

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # OneDrive 환경변수 제거(테스트 격리)
    monkeypatch.delenv("OneDrive", raising=False)
    monkeypatch.delenv("OneDriveCommercial", raising=False)
    monkeypatch.delenv("OneDriveConsumer", raising=False)

    res = json.loads(office_locate_file("보고서"))
    paths = [m["path"] for m in res["matches"]]
    assert any("분기보고서_v2.docx" in p for p in paths)
    # 부분일치 아닌 것/비-Office는 제외
    assert not any("메모.txt" in p for p in paths)


def test_locate_empty_when_no_match(tmp_path, monkeypatch):
    (tmp_path / "Documents").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("OneDrive", raising=False)
    res = json.loads(office_locate_file("존재하지않는이름zzz"))
    assert res["count"] == 0

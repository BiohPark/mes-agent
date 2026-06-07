"""write_word 단위 테스트 — 마크다운을 진짜 docx로 저장하는지 검증.

회귀 방지 대상(3.2 버그): '파일만 .docx이고 내부는 markdown이라 읽지도 못함'.
write_word는 반드시 유효한 OOXML(zip) 파일을 만들어야 하고,
read_word로 다시 읽을 수 있어야 한다.
"""

import json
import zipfile

import pytest

from agent.tools.document import write_word, read_word


_MD = """# 보고서 제목

## 개요
이것은 **굵은** 텍스트와 `코드` 입니다.

- 항목 하나
- 항목 둘

1. 첫째
2. 둘째

| 이름 | 값 |
| --- | --- |
| A | 1 |
| B | 2 |
"""


def test_write_word_creates_valid_ooxml(tmp_path):
    path = tmp_path / "report.docx"
    res = json.loads(write_word(str(path), _MD, "Q2 리포트"))
    assert "error" not in res, res
    assert path.exists()
    # 진짜 docx는 zip 컨테이너이며 word/document.xml 을 포함한다 (마크다운 텍스트 파일이면 실패)
    assert zipfile.is_zipfile(path)
    with zipfile.ZipFile(path) as z:
        assert "word/document.xml" in z.namelist()


def test_write_word_roundtrips_text(tmp_path):
    path = tmp_path / "report.docx"
    write_word(str(path), _MD, "Q2 리포트")
    text = read_word(str(path))
    # 마크다운 기호(**, |, #)가 본문 텍스트로 남지 않고 내용만 보존되어야 한다
    assert "굵은" in text
    assert "항목 하나" in text
    assert "**" not in text
    assert "Q2 리포트" in text


def test_write_word_plain_paragraph(tmp_path):
    path = tmp_path / "plain.docx"
    res = json.loads(write_word(str(path), "그냥 한 줄 텍스트", ""))
    assert "error" not in res
    assert zipfile.is_zipfile(path)
    assert "그냥 한 줄 텍스트" in read_word(str(path))

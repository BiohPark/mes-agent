"""LibreOffice 헤드리스 변환 엔진 (오프라인 폴백).

MS Office가 없는 PC에서도 고품질 문서 변환(docx/xlsx/pptx ↔ pdf 등)을 제공한다.
설치된 LibreOffice의 `soffice --headless --convert-to` 를 호출한다(추가 라이브러리 불필요).
- LibreOffice 미설치 시 명확한 안내를 반환(차단형 아님).
- office_com 의 PDF 내보내기가 COM 불가 시 이 엔진으로 자동 폴백한다.

설치 경로 탐지: 환경변수 LIBREOFFICE_PATH → 표준 설치 경로 → PATH.
"""

import os
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

_COMMON_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/opt/libreoffice/program/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def find_soffice() -> str | None:
    """LibreOffice 실행 파일 경로를 찾는다. 없으면 None."""
    env = os.environ.get("LIBREOFFICE_PATH", "").strip()
    if env and Path(env).exists():
        return env
    for name in ("soffice", "soffice.exe", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for p in _COMMON_PATHS:
        if Path(p).exists():
            return p
    return None


def is_available() -> bool:
    return find_soffice() is not None


def libre_convert(path: str, to_format: str = "pdf", outdir: str = "") -> str:
    """LibreOffice 헤드리스로 문서를 다른 포맷으로 변환합니다(MS Office 불필요).
    to_format 예: 'pdf', 'docx', 'xlsx', 'pptx', 'txt', 'html', 'csv'.
    outdir 생략 시 원본과 같은 폴더에 저장됩니다."""
    soffice = find_soffice()
    if not soffice:
        return json.dumps({
            "error": "LibreOffice(soffice)를 찾을 수 없습니다. 설치 후 LIBREOFFICE_PATH 환경변수로 경로를 지정하세요.",
            "engine": "none",
        }, ensure_ascii=False)

    src = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(src):
        return json.dumps({"error": f"파일이 존재하지 않습니다: {src}"}, ensure_ascii=False)

    out_dir = os.path.abspath(os.path.expanduser(outdir)) if outdir else str(Path(src).parent)
    os.makedirs(out_dir, exist_ok=True)
    # 동시 실행 충돌 방지를 위한 임시 사용자 프로필
    profile = tempfile.mkdtemp(prefix="lo_profile_")
    try:
        args = [
            soffice,
            f"-env:UserInstallation=file:///{profile.replace(os.sep, '/')}",
            "--headless", "--norestore", "--nolockcheck",
            "--convert-to", to_format,
            "--outdir", out_dir,
            src,
        ]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=120,
                              encoding="utf-8", errors="replace")
        ext = to_format.split(":")[0]
        out_path = os.path.join(out_dir, Path(src).stem + "." + ext)
        if os.path.exists(out_path):
            return json.dumps({"path": out_path, "engine": "libreoffice",
                               "message": f"{ext.upper()} 변환 완료"}, ensure_ascii=False)
        return json.dumps({
            "error": "변환 결과 파일을 찾지 못했습니다.",
            "engine": "libreoffice",
            "stdout": (proc.stdout or "")[:300],
            "stderr": (proc.stderr or "")[:300],
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "LibreOffice 변환 시간 초과(120초)", "engine": "libreoffice"},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "engine": "libreoffice"}, ensure_ascii=False)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def to_pdf(path: str, pdf_path: str = "") -> str | None:
    """PDF 변환 결과 경로를 반환(office_com PDF 폴백용). 실패/미설치면 None."""
    if not is_available():
        return None
    outdir = str(Path(pdf_path).parent) if pdf_path else ""
    res = json.loads(libre_convert(path, "pdf", outdir))
    out = res.get("path")
    if not out:
        return None
    if pdf_path and os.path.abspath(out) != os.path.abspath(pdf_path):
        try:
            shutil.move(out, pdf_path)
            out = pdf_path
        except Exception:
            pass
    return out


MANIFEST = [
    {
        "name": "libre_convert",
        "label": "LibreOffice 변환",
        "schema": {
            "type": "function",
            "function": {
                "name": "libre_convert",
                "description": (
                    "LibreOffice 헤드리스로 문서를 다른 포맷으로 변환합니다(MS Office 불필요, 오프라인). "
                    "to_format 예: pdf, docx, xlsx, pptx, txt, html, csv. "
                    "MS Office가 없는 PC에서 PDF 내보내기·포맷 변환에 사용하세요. LibreOffice 설치 필요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "원본 파일 경로"},
                        "to_format": {"type": "string", "description": "대상 포맷(기본 pdf)"},
                        "outdir": {"type": "string", "description": "출력 폴더(생략 시 원본 폴더)"},
                    },
                    "required": ["path"],
                },
            },
        },
        "handler": lambda a: libre_convert(a["path"], a.get("to_format", "pdf"), a.get("outdir", "")),
    },
]

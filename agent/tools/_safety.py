"""파괴적 작업 가드 (S2/S4/S5).

이 모듈은 `_` 로 시작하므로 툴 자동 디스커버리에서 제외된다(툴이 아님).
- is_dangerous_command: 치명적 셸 명령 패턴 탐지
- is_protected_path: 시스템 핵심 경로(쓰기 금지) 탐지
- backup_file: 기존 파일 덮어쓰기 전 백업
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

# ── 치명적 명령 패턴 ──────────────────────────────────────────
# 되돌릴 수 없는 대량 파괴(재귀 삭제·포맷·디스크/레지스트리 조작·종료 등)
_DANGEROUS_PATTERNS = [
    r"Remove-Item\b.*-Recurse",          # PowerShell 재귀 삭제
    r"\brm\b.*-[a-z]*r[a-z]*f|\brm\b.*-[a-z]*f[a-z]*r",  # rm -rf / -fr
    r"\bdel\b.*/s",                       # cmd del /s
    r"\brd\b.*/s|\brmdir\b.*/s",          # rd/rmdir /s
    r"\bformat\b\s+[a-z]:",               # format C:
    r"Format-Volume\b",
    r"\bdiskpart\b",
    r"Clear-Disk\b",
    r"\bbcdedit\b",
    r"\bcipher\b.*/w",                    # 디스크 와이프
    r"vssadmin\b.*delete",                # 섀도 카피 삭제(랜섬웨어 패턴)
    r"reg\s+delete\b.*HK(LM|EY_LOCAL)",  # 레지스트리 하이브 삭제
    r"Remove-Item\b.*HK(LM|CU):",
    r"\bshutdown\b|Stop-Computer\b|Restart-Computer\b",
    r"\bmkfs|>\s*/dev/sd",                # (혹시 모를) POSIX 파괴
]
_DANGEROUS_RE = re.compile("|".join(_DANGEROUS_PATTERNS), re.IGNORECASE)


def is_dangerous_command(cmd: str) -> bool:
    return bool(_DANGEROUS_RE.search(cmd or ""))


# ── 보호 경로 (쓰기 금지) ─────────────────────────────────────
def _protected_roots() -> list[Path]:
    roots = []
    for env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        v = os.environ.get(env)
        if v:
            roots.append(Path(v))
    # 시작프로그램(Startup) 폴더 — 악성 자동실행 등록 방지
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup")
    programdata = os.environ.get("ProgramData")
    if programdata:
        roots.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "StartUp")
    return roots


def is_protected_path(path: str) -> bool:
    """대상 경로가 시스템 핵심/자동실행 영역이면 True(쓰기 금지)."""
    try:
        target = Path(os.path.abspath(os.path.expanduser(path))).resolve()
    except Exception:
        return False
    for root in _protected_roots():
        try:
            rr = root.resolve()
        except Exception:
            rr = root
        try:
            target.relative_to(rr)
            return True
        except ValueError:
            continue
    return False


# ── 백업 ──────────────────────────────────────────────────────
def backup_file(path: str) -> str | None:
    """기존 파일을 타임스탬프 백업본으로 복사하고 경로를 반환한다."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    bak = p.with_name(f"{p.stem}.{datetime.now():%Y%m%d_%H%M%S}{p.suffix}.bak")
    shutil.copy2(p, bak)
    return str(bak)


# ── 공통 안내 메시지 ──────────────────────────────────────────
def danger_block_message(cmd: str) -> str:
    return (
        "⚠ 되돌릴 수 없는 위험 명령으로 판단되어 차단했습니다.\n"
        f"명령: {cmd[:200]}\n"
        "정말 실행하려면 먼저 ask_user로 사용자 확인을 받고, 확인되면 force=true 로 다시 호출하세요."
    )

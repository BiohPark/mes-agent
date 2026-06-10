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


# ── G3: 중앙 집중 위험도 분류 (APPROVE1) ──────────────────────────
# 루프(server.generate)가 run_tool 직전에 호출해 강제하는 게이트의 판정부.
# 철학: "막지 않고 게이팅" — 읽기/관찰/입력형은 그대로 실행(safe),
#       상태를 바꾸는 것만 사용자 확인(mutate), 비가역 대량파괴는 강조 확인(destructive).
# 균형형 기본: 명시적 변형 동사/명령에만 확인을 요구하고 나머지는 safe.

import json as _json

# 명령·경로가 담기는 대표 인자 키
_CMD_ARG_KEYS = ("command", "cmd", "script", "powershell", "query", "sql")
_PATH_ARG_KEYS = (
    "path", "file_path", "out", "outdir", "dest", "destination", "target", "save_path",
)

# 읽기 전용으로 단정할 수 있는 명령 시작 패턴
_READONLY_CMD_RE = re.compile(
    r"^\s*(Get-\w+|Test-Path|Select-\w+|Measure-\w+|Resolve-Path|Out-String|"
    r"SELECT\b|dir\b|ls\b|cat\b|type\b|echo\b|where\b|whoami|hostname|"
    r"ipconfig|systeminfo|findstr\b|Write-Host|Write-Output)",
    re.IGNORECASE,
)
# 복합 명령(여러 문장 연결)은 읽기전용으로 단정하지 않는다(뒤에 변형 명령이 숨을 수 있음).
_CMD_SEPARATOR_RE = re.compile(r";|&&|\n|`")

# 상태를 바꾸는 변형 동사(툴 이름 기반) — 미래 추가 툴도 명명규약으로 포착(fail-safe)
_MUTATE_NAME_RE = re.compile(
    r"(write|edit|delete|remove|set_|save|update|create|upload|move_|append|insert|"
    r"convert|export|replace|kill|accept|add_)",
    re.IGNORECASE,
)

# 확인 없이 실행해도 되는(읽기/관찰/입력형) 툴 이름 prefix
_SAFE_PREFIXES = (
    "read_", "get_", "list_", "search", "screen", "ocr", "ui_", "wait_for",
    "mouse_", "keyboard_", "key_", "scroll", "find_", "capture", "analyze",
    "pixel", "compare", "workflow_", "window_",
    "obsidian_search", "obsidian_read", "obsidian_list", "obsidian_get",
    "obsidian_follow", "obsidian_list_commands",
    "browser_get", "browser_open", "browser_navigate", "browser_screenshot",
    "browser_wait", "browser_eval", "browser_scroll",
)
_SAFE_EXACT = {"ask_user", "take_screenshot"}

_CMD_TOOLS = {"run_command", "start_process", "run_powershell"}


def _coerce_args(args) -> dict:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            obj = _json.loads(args)
            return obj if isinstance(obj, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _extract(args: dict, keys) -> list[str]:
    out = []
    for k in keys:
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v)
    return out


def classify_risk(tool_name: str, args, allowlist=None, risk_hint=None) -> str:
    """tool_call의 위험도를 'safe' | 'mutate' | 'destructive' 로 분류한다.

    server.generate()가 run_tool 직전에 호출하여 mutate/destructive면 사용자 승인을 강제한다.
    risk_hint: MCP 도구의 readOnlyHint 등 레지스트리 위험도 힌트(허용목록 다음 우선).
    """
    name = (tool_name or "").lower()
    args = _coerce_args(args)

    # 0) 세션 허용목록("항상 허용") → safe
    if allowlist and tool_name in allowlist:
        return "safe"
    if name in _SAFE_EXACT:
        return "safe"

    # 0.5) 레지스트리 위험도 힌트(MCP readOnlyHint 등) — 이름/내용 휴리스틱보다 신뢰
    if risk_hint in ("safe", "mutate", "destructive"):
        return risk_hint

    cmds = _extract(args, _CMD_ARG_KEYS)
    paths = _extract(args, _PATH_ARG_KEYS)

    # 1) destructive: 위험 명령 또는 보호경로 쓰기 (모델 협조 무관, 내용 기반)
    if any(is_dangerous_command(c) for c in cmds):
        return "destructive"
    if any(is_protected_path(p) for p in paths):
        return "destructive"

    # 2) 명령 실행 툴: 내용 기반 — 읽기전용이면 safe, 아니면 mutate
    if name in _CMD_TOOLS:
        if not cmds:
            return "mutate"
        for c in cmds:
            if _CMD_SEPARATOR_RE.search(c) or not _READONLY_CMD_RE.match(c):
                return "mutate"
        return "safe"

    # 3) 읽기/관찰/입력형 prefix → safe (균형형)
    if name.startswith(_SAFE_PREFIXES):
        return "safe"

    # 4) 변형 동사 이름 → mutate
    if _MUTATE_NAME_RE.search(name):
        return "mutate"

    # 5) 균형형 기본 = safe (위험만 게이팅)
    return "safe"


def command_excerpt(args) -> str:
    """승인 UI 강조용으로 명령/대상 첫 줄을 추출한다(없으면 빈 문자열)."""
    args = _coerce_args(args)
    cmd = next(iter(_extract(args, _CMD_ARG_KEYS)), "")
    if not cmd:
        cmd = next(iter(_extract(args, _PATH_ARG_KEYS)), "")
    return cmd[:300]


def risk_confirm_message(tool_name: str, risk: str, args) -> str:
    """승인 팝업에 띄울 질문 문구를 만든다."""
    args = _coerce_args(args)
    cmd = next(iter(_extract(args, _CMD_ARG_KEYS)), "")
    detail = f"\n명령/대상: {cmd[:300]}" if cmd else ""
    if risk == "destructive":
        return (
            f"⚠ 되돌릴 수 없는 위험 작업으로 판단됩니다: '{tool_name}'.{detail}\n"
            "정말 실행할까요?"
        )
    return f"'{tool_name}' 실행은 시스템/데이터를 변경할 수 있습니다.{detail}\n실행할까요?"

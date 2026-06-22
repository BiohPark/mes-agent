import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _dotenv_value(key: str) -> str:
    for name in (".env", ".env.example"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip()
    return ""


def _candidate_paths() -> list[str]:
    candidates: list[str] = []
    if os.environ.get("NODE_EXE"):
        candidates.append(os.environ["NODE_EXE"])
    found = shutil.which("node")
    if found:
        candidates.append(found)
    for key in ("NVM_SYMLINK", "NVM_HOME"):
        base = os.environ.get(key) or _dotenv_value(key)
        if base:
            candidates.append(str(Path(base) / "node.exe"))
    candidates.append(str(
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    ))
    return list(dict.fromkeys(candidates))


def node_command() -> str:
    for candidate in _candidate_paths():
        path = Path(candidate)
        try:
            exists = path.exists()
        except OSError:
            continue
        if not exists:
            continue
        try:
            result = subprocess.run(
                [str(path), "--version"],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return str(path)
    pytest.skip("Node.js executable is not available")

"""
프로세스/시스템 제어 도구
- 명령 실행 (PowerShell, CMD)
- 프로세스 목록/종료/실행
- 파일 시스템 기본 조작
"""

import os
import json
import subprocess
import shlex
from pathlib import Path

import psutil

from agent.core.timeouts import LivenessObservation, classify_liveness, timeout_error_text


def _timeout_stream_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _timeout_observation(exc: subprocess.TimeoutExpired, timeout: int) -> LivenessObservation:
    stdout = _timeout_stream_text(getattr(exc, "stdout", ""))
    stderr = _timeout_stream_text(getattr(exc, "stderr", ""))
    stdout_bytes = len(stdout.encode("utf-8", errors="replace"))
    stderr_bytes = len(stderr.encode("utf-8", errors="replace"))
    progressed = (stdout_bytes + stderr_bytes) > 0
    return LivenessObservation(
        elapsed_seconds=float(timeout),
        process_alive=True,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        no_progress_count=0 if progressed else 2,
    )


def run_command(cmd: str, timeout: int = 30, shell: str = "powershell",
                force: bool = False) -> str:
    """명령어를 실행하고 결과(stdout, stderr, returncode)를 반환합니다.
    shell: 'powershell' (기본) 또는 'cmd'
    복잡한 배포 스크립트, 빌드 명령, 서버 상태 확인 등에 사용합니다.
    되돌릴 수 없는 위험 명령(재귀삭제·포맷·종료 등)은 차단되며, 사용자 확인 후 force=true로 실행합니다."""
    from agent.tools._safety import is_dangerous_command, danger_block_message
    if not force and is_dangerous_command(cmd):
        return json.dumps({"blocked": True, "message": danger_block_message(cmd),
                           "success": False}, ensure_ascii=False)
    try:
        if shell == "powershell":
            args = ["powershell", "-NonInteractive", "-Command", cmd]
        else:
            args = ["cmd", "/c", cmd]

        result = subprocess.run(
            args,
            capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace"
        )
        return json.dumps({
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[:2000],
            "stderr": result.stderr.strip()[:500],
            "success": result.returncode == 0
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired as e:
        observation = _timeout_observation(e, timeout)
        timeout_info = classify_liveness("run_command", timeout, observation)
        return json.dumps({
            "error": timeout_error_text("run_command", timeout, observation=observation),
            "stdout": _timeout_stream_text(getattr(e, "stdout", "")).strip()[:2000],
            "stderr": _timeout_stream_text(getattr(e, "stderr", "")).strip()[:500],
            "timeout": timeout_info,
            "success": False,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "success": False})


def list_processes(name_filter: str = "") -> str:
    """실행 중인 프로세스 목록을 반환합니다.
    name_filter로 특정 프로세스만 검색할 수 있습니다. 예: 'chrome', 'python'"""
    try:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_info"]):
            try:
                info = proc.info
                if name_filter and name_filter.lower() not in info["name"].lower():
                    continue
                mem_mb = round(info["memory_info"].rss / 1024 / 1024, 1) if info["memory_info"] else 0
                processes.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "status": info["status"],
                    "cpu_percent": info["cpu_percent"],
                    "memory_mb": mem_mb
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        processes.sort(key=lambda p: p["memory_mb"], reverse=True)
        return json.dumps(processes[:50], ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def kill_process(name_or_pid: str) -> str:
    """프로세스를 종료합니다. 이름 또는 PID로 지정할 수 있습니다."""
    try:
        killed = []
        if name_or_pid.isdigit():
            pid = int(name_or_pid)
            proc = psutil.Process(pid)
            proc.terminate()
            killed.append(f"PID {pid} ({proc.name()})")
        else:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if name_or_pid.lower() in proc.info["name"].lower():
                        proc.terminate()
                        killed.append(f"PID {proc.pid} ({proc.name()})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        if killed:
            return f"종료 완료: {', '.join(killed)}"
        return f"'{name_or_pid}' 프로세스를 찾지 못했습니다."
    except Exception as e:
        return f"프로세스 종료 실패: {e}"


def is_process_running(name: str) -> str:
    """특정 이름의 프로세스가 실행 중인지 확인합니다."""
    name_lower = name.lower()
    for proc in psutil.process_iter(["name"]):
        try:
            if name_lower in proc.info["name"].lower():
                return json.dumps({"running": True, "name": proc.name(), "pid": proc.pid})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return json.dumps({"running": False, "name": name})


def start_process(cmd: str, wait: bool = False, force: bool = False) -> str:
    """프로세스를 실행합니다.
    wait=True 시 완료될 때까지 기다립니다 (최대 30초).
    되돌릴 수 없는 위험 명령은 차단되며, 사용자 확인 후 force=true로 실행합니다."""
    from agent.tools._safety import is_dangerous_command, danger_block_message
    if not force and is_dangerous_command(cmd):
        return json.dumps({"blocked": True, "message": danger_block_message(cmd),
                           "success": False}, ensure_ascii=False)
    try:
        if wait:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, encoding="utf-8", errors="replace"
            )
            return json.dumps({
                "returncode": result.returncode,
                "stdout": result.stdout.strip()[:1000],
                "success": result.returncode == 0
            }, ensure_ascii=False)
        else:
            proc = subprocess.Popen(cmd, shell=True)
            return json.dumps({"pid": proc.pid, "message": f"프로세스 시작: {cmd[:60]}"})
    except Exception as e:
        return json.dumps({"error": str(e), "success": False})


def open_file(path: str) -> str:
    """파일을 연결된 기본 프로그램으로 엽니다. Excel, Word, PDF, 이미지 등에 사용합니다."""
    try:
        os.startfile(path)
        return f"파일 열기: {path}"
    except Exception as e:
        return f"파일 열기 실패: {e}"


def list_directory(path: str) -> str:
    """폴더의 내용(파일 및 하위 폴더)을 반환합니다."""
    try:
        p = Path(path)
        if not p.exists():
            return json.dumps({"error": f"경로가 존재하지 않습니다: {path}"})
        items = []
        for item in sorted(p.iterdir()):
            stat = item.stat()
            items.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size_bytes": stat.st_size if item.is_file() else None,
                "modified": stat.st_mtime
            })
        return json.dumps({"path": str(p.resolve()), "count": len(items), "items": items},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def file_exists(path: str) -> str:
    """파일 또는 폴더가 존재하는지 확인합니다."""
    p = Path(path)
    return json.dumps({"exists": p.exists(), "is_file": p.is_file(),
                       "is_dir": p.is_dir(), "path": str(p.resolve())})


def get_system_info() -> str:
    """CPU, 메모리, 디스크 사용량 등 시스템 상태를 반환합니다."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        return json.dumps({
            "cpu_percent": cpu,
            "memory": {
                "total_gb": round(mem.total / 1e9, 1),
                "used_gb": round(mem.used / 1e9, 1),
                "percent": mem.percent
            },
            "disk_c": {
                "total_gb": round(disk.total / 1e9, 1),
                "free_gb": round(disk.free / 1e9, 1),
                "percent": disk.percent
            }
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


MANIFEST = [
    {
        "name": "run_command",
        "label": "명령 실행",
        "schema": {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "PowerShell 또는 CMD 명령어를 실행하고 stdout, stderr, returncode를 반환합니다. 위험 명령은 차단되며 사용자 확인 후 force=true로 실행합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string"},
                        "timeout": {"type": "integer", "description": "초 (기본 30)"},
                        "shell": {"type": "string", "enum": ["powershell", "cmd"]},
                        "force": {"type": "boolean", "description": "위험 명령 차단 우회 (사용자 확인 후에만)"}
                    },
                    "required": ["cmd"]
                }
            }
        },
        "handler": lambda a: run_command(a["cmd"], a.get("timeout", 30), a.get("shell", "powershell"), a.get("force", False))
    },
    {
        "name": "list_processes",
        "label": "프로세스 목록 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "list_processes",
                "description": "실행 중인 프로세스 목록을 반환합니다. name_filter로 검색 가능합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name_filter": {"type": "string", "description": "프로세스 이름 검색어"}
                    }
                }
            }
        },
        "handler": lambda a: list_processes(a.get("name_filter", ""))
    },
    {
        "name": "kill_process",
        "label": "프로세스 종료",
        "schema": {
            "type": "function",
            "function": {
                "name": "kill_process",
                "description": "프로세스 이름 또는 PID로 프로세스를 종료합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name_or_pid": {"type": "string", "description": "프로세스 이름 또는 PID"}
                    },
                    "required": ["name_or_pid"]
                }
            }
        },
        "handler": lambda a: kill_process(a["name_or_pid"])
    },
    {
        "name": "is_process_running",
        "label": "프로세스 실행 확인",
        "schema": {
            "type": "function",
            "function": {
                "name": "is_process_running",
                "description": "특정 프로세스가 실행 중인지 확인합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"]
                }
            }
        },
        "handler": lambda a: is_process_running(a["name"])
    },
    {
        "name": "start_process",
        "label": "프로세스 시작",
        "schema": {
            "type": "function",
            "function": {
                "name": "start_process",
                "description": "명령어로 프로세스를 실행합니다. wait=true 시 완료 대기합니다. 위험 명령은 차단되며 사용자 확인 후 force=true로 실행합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string"},
                        "wait": {"type": "boolean"},
                        "force": {"type": "boolean", "description": "위험 명령 차단 우회 (사용자 확인 후에만)"}
                    },
                    "required": ["cmd"]
                }
            }
        },
        "handler": lambda a: start_process(a["cmd"], a.get("wait", False), a.get("force", False))
    },
    {
        "name": "open_file",
        "label": "파일 열기",
        "schema": {
            "type": "function",
            "function": {
                "name": "open_file",
                "description": "파일을 연결된 기본 프로그램으로 엽니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: open_file(a["path"])
    },
    {
        "name": "list_directory",
        "label": "폴더 목록 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "폴더의 파일 및 하위 폴더 목록을 반환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: list_directory(a["path"])
    },
    {
        "name": "file_exists",
        "label": "파일 존재 확인",
        "schema": {
            "type": "function",
            "function": {
                "name": "file_exists",
                "description": "파일 또는 폴더가 존재하는지 확인합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        },
        "handler": lambda a: file_exists(a["path"])
    },
    {
        "name": "get_system_info",
        "label": "시스템 정보 확인",
        "schema": {
            "type": "function",
            "function": {
                "name": "get_system_info",
                "description": "CPU, 메모리, 디스크 사용량 등 현재 시스템 상태를 반환합니다.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "handler": lambda a: get_system_info()
    },
]

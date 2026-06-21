"""get_system_info — SYSTEM_DISK_PATH env override가 하드코딩을 대체하는지 확인."""

import json

import agent.tools.process as process_module
from agent.tools.process import get_system_info


def test_get_system_info_default_disk_unchanged_when_env_unset(monkeypatch):
    monkeypatch.delenv("SYSTEM_DISK_PATH", raising=False)
    seen_paths = []
    original_disk_usage = process_module.psutil.disk_usage

    def _spy_disk_usage(path):
        seen_paths.append(path)
        return original_disk_usage(path)

    monkeypatch.setattr(process_module.psutil, "disk_usage", _spy_disk_usage)

    res = json.loads(get_system_info())

    assert "error" not in res
    assert "disk_c" in res
    assert set(res["disk_c"].keys()) == {"total_gb", "free_gb", "percent"}
    assert seen_paths == ["C:\\"]


def test_get_system_info_respects_system_disk_path_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SYSTEM_DISK_PATH", str(tmp_path))
    seen_paths = []
    original_disk_usage = process_module.psutil.disk_usage

    def _spy_disk_usage(path):
        seen_paths.append(path)
        return original_disk_usage(path)

    monkeypatch.setattr(process_module.psutil, "disk_usage", _spy_disk_usage)

    res = json.loads(get_system_info())

    assert "error" not in res
    assert "disk_c" in res
    assert set(res["disk_c"].keys()) == {"total_gb", "free_gb", "percent"}
    assert seen_paths == [str(tmp_path)]

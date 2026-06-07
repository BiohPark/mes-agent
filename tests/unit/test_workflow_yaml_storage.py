"""워크플로우 YAML frontmatter 스토리지 단위 테스트 (Phase 4-C)."""

import json
import yaml
import pytest
from pathlib import Path

from agent.workflow.model import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowConnection,
)
from agent.workflow.storage import (
    load_definition,
    save_definition,
    _def_path,
)


def _defn(tid="t1", task_type="general"):
    return WorkflowDefinition(
        id=tid, task_type=task_type, title="YAML 테스트",
        nodes=[
            WorkflowNode(id="n1", title="첫 단계", type="auto"),
            WorkflowNode(id="n2", title="둘째 단계", type="semi_auto"),
        ],
        connections=[WorkflowConnection(from_node="n1", to_node="n2")],
    )


class TestSaveDefinitionYAML:
    def test_creates_md_file(self, vault):
        defn = _defn(tid="yaml-save")
        save_definition(defn)
        path = vault / "agent" / "workflows" / "general" / "yaml-save.md"
        assert path.exists(), ".md 파일이 생성되어야 한다"

    def test_file_has_yaml_frontmatter(self, vault):
        defn = _defn(tid="yaml-fmt")
        save_definition(defn)
        path = vault / "agent" / "workflows" / "general" / "yaml-fmt.md"
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n"), "YAML frontmatter로 시작해야 한다"

    def test_frontmatter_parses_cleanly(self, vault):
        defn = _defn(tid="yaml-parse")
        save_definition(defn)
        path = vault / "agent" / "workflows" / "general" / "yaml-parse.md"
        content = path.read_text(encoding="utf-8")
        _, fm, *_ = content.split("---", 2)
        data = yaml.safe_load(fm)
        assert data["id"] == "yaml-parse"
        assert data["task_type"] == "general"
        assert len(data["nodes"]) == 2

    def test_nodes_preserved_in_yaml(self, vault):
        defn = _defn(tid="yaml-nodes")
        save_definition(defn)
        path = vault / "agent" / "workflows" / "general" / "yaml-nodes.md"
        content = path.read_text(encoding="utf-8")
        _, fm, *_ = content.split("---", 2)
        data = yaml.safe_load(fm)
        assert data["nodes"][0]["id"] == "n1"
        assert data["nodes"][0]["title"] == "첫 단계"
        assert data["nodes"][1]["type"] == "semi_auto"

    def test_connections_preserved_in_yaml(self, vault):
        defn = _defn(tid="yaml-conn")
        save_definition(defn)
        path = vault / "agent" / "workflows" / "general" / "yaml-conn.md"
        content = path.read_text(encoding="utf-8")
        _, fm, *_ = content.split("---", 2)
        data = yaml.safe_load(fm)
        assert data["connections"][0]["from_node"] == "n1"
        assert data["connections"][0]["to_node"] == "n2"

    def test_no_vault_is_noop(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "")
        save_definition(_defn())  # 오류 없이 종료


class TestLoadDefinitionYAML:
    def test_load_reads_md_format(self, vault):
        defn = _defn(tid="load-md")
        save_definition(defn)
        loaded = load_definition("general", "load-md")
        assert loaded.id == "load-md"
        assert len(loaded.nodes) == 2
        assert loaded.nodes[0].title == "첫 단계"

    def test_roundtrip_preserves_connections(self, vault):
        defn = _defn(tid="rt-conn")
        save_definition(defn)
        loaded = load_definition("general", "rt-conn")
        assert loaded.connections[0].from_node == "n1"
        assert loaded.connections[0].to_node == "n2"

    def test_load_migrates_json_to_md(self, vault):
        """구 .json 파일을 로드하면 .md로 자동 마이그레이션된다."""
        wf_dir = vault / "agent" / "workflows" / "general"
        wf_dir.mkdir(parents=True, exist_ok=True)
        json_path = wf_dir / "migr-yaml.json"
        json_path.write_text(json.dumps({
            "id": "migr-yaml",
            "task_type": "general",
            "title": "구 포맷",
            "nodes": [{"id": "x1", "title": "X", "type": "auto", "retry": 0, "on_error": "stop"}],
            "connections": [],
        }), encoding="utf-8")

        defn = load_definition("general", "migr-yaml")
        assert defn.id == "migr-yaml"

        md_path = wf_dir / "migr-yaml.md"
        assert md_path.exists(), "마이그레이션 후 .md 파일이 생성되어야 한다"

    def test_json_deleted_after_migration(self, vault):
        """마이그레이션 후 구 .json 파일이 삭제된다."""
        wf_dir = vault / "agent" / "workflows" / "general"
        wf_dir.mkdir(parents=True, exist_ok=True)
        json_path = wf_dir / "del-json.json"
        json_path.write_text(json.dumps({
            "id": "del-json", "task_type": "general", "title": "삭제 테스트",
            "nodes": [{"id": "y1", "title": "Y", "type": "auto", "retry": 0, "on_error": "stop"}],
            "connections": [],
        }), encoding="utf-8")

        load_definition("general", "del-json")
        assert not json_path.exists(), "마이그레이션 후 .json 파일이 삭제되어야 한다"

    def test_default_creates_md_not_json(self, vault):
        """파일이 없으면 기본 템플릿을 .md로 저장한다."""
        load_definition("general", "new-yaml-thread")
        md_path = vault / "agent" / "workflows" / "general" / "new-yaml-thread.md"
        json_path = vault / "agent" / "workflows" / "general" / "new-yaml-thread.json"
        assert md_path.exists(), ".md 파일이 생성되어야 한다"
        assert not json_path.exists(), ".json 파일은 생성되지 않아야 한다"

    def test_def_path_returns_md_extension(self, vault):
        path = _def_path("general", "test-t")
        assert path is not None
        assert path.suffix == ".md"

import json

from agent.obsidian_session import (
    _DEFAULT_TASK_CONFIGS,
    get_session_manager,
    get_task_configs,
)


def _read_task_types_file():
    return json.loads(get_session_manager()._read("agent/task_types.json"))


class TestGetTaskConfigs:
    def test_returns_defaults_when_vault_file_missing(self, vault):
        configs = get_task_configs()

        assert set(_DEFAULT_TASK_CONFIGS).issubset(configs)
        assert "general" in configs
        assert "gmp-validation" in configs
        assert (vault / "agent" / "task_types.json").exists() is False

    def test_merges_vault_custom_type(self, vault):
        get_session_manager()._write(
            "agent/task_types.json",
            json.dumps(
                {
                    "qa": {
                        "label": "QA",
                        "icon": "Q",
                        "description": "quality",
                        "system_prompt": "check carefully",
                    }
                },
                ensure_ascii=False,
            ),
        )

        configs = get_task_configs()

        assert "general" in configs
        assert configs["qa"]["label"] == "QA"
        assert configs["qa"]["system_prompt"] == "check carefully"

    def test_vault_can_override_default_type(self, vault):
        get_session_manager()._write(
            "agent/task_types.json",
            json.dumps(
                {
                    "general": {
                        "label": "Custom General",
                        "icon": "G",
                        "description": "override",
                        "system_prompt": "custom prompt",
                    }
                },
                ensure_ascii=False,
            ),
        )

        configs = get_task_configs()

        assert configs["general"]["label"] == "Custom General"
        assert configs["general"]["system_prompt"] == "custom prompt"


class TestTaskTypeTools:
    def test_create_rejects_duplicate_name(self, vault):
        from agent.tools.task_type import _task_type_create

        result = json.loads(
            _task_type_create(
                {
                    "name": "general",
                    "label": "General",
                    "icon": "G",
                    "description": "duplicate",
                    "system_prompt": "prompt",
                }
            )
        )

        assert result["status"] == "error"
        assert "이미 존재" in result["reason"]

    def test_create_saves_custom_type_to_vault(self, vault):
        from agent.tools.task_type import _task_type_create

        result = json.loads(
            _task_type_create(
                {
                    "name": "qa",
                    "label": "QA",
                    "icon": "Q",
                    "description": "quality",
                    "system_prompt": "check carefully",
                }
            )
        )

        assert result == {"status": "ok", "name": "qa"}
        saved = _read_task_types_file()
        assert saved["qa"]["label"] == "QA"
        assert get_task_configs()["qa"]["system_prompt"] == "check carefully"

    def test_remove_rejects_default_type(self, vault):
        from agent.tools.task_type import _task_type_remove

        result = json.loads(_task_type_remove({"name": "general"}))

        assert result["status"] == "error"
        assert "기본 업무 타입" in result["reason"]

    def test_remove_deletes_custom_type(self, vault):
        from agent.tools.task_type import _task_type_create, _task_type_remove

        _task_type_create(
            {
                "name": "qa",
                "label": "QA",
                "icon": "Q",
                "description": "quality",
                "system_prompt": "check carefully",
            }
        )

        result = json.loads(_task_type_remove({"name": "qa"}))

        assert result == {"status": "ok", "name": "qa"}
        assert "qa" not in _read_task_types_file()
        assert "qa" not in get_task_configs()

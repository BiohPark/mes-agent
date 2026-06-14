import json


class TestDynamicTaskConfigApi:
    async def test_default_task_config_includes_builtins(self, client):
        resp = await client.get("/task-config")

        assert resp.status_code == 200
        data = resp.json()
        for task_type in ("general", "syncade", "obsidian", "unscript", "knox"):
            assert task_type in data
            assert {"label", "icon", "description"}.issubset(data[task_type])
            assert "system_prompt" not in data[task_type]

    async def test_task_config_includes_vault_custom_type(self, client):
        from agent.obsidian_session import get_session_manager

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

        resp = await client.get("/task-config")

        assert resp.status_code == 200
        data = resp.json()
        assert "general" in data
        assert data["qa"] == {
            "label": "QA",
            "icon": "Q",
            "description": "quality",
        }

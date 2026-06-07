"""툴 레지스트리 스모크 테스트.

새 툴 추가 시 MANIFEST 구조가 올바른지, 이름 중복이 없는지 자동으로 검증한다.
실제 툴을 실행하지 않으므로 하드웨어 없이도 동작한다.
"""

import pytest
from agent.tools import _registry, TOOLS, TOOL_LABELS


EXPECTED_TOOL_COUNT = 89
REQUIRED_MANIFEST_KEYS = {"name", "label", "schema", "handler"}


class TestRegistry:
    def test_registry_not_empty(self):
        assert len(_registry) > 0

    def test_total_tool_count(self):
        """툴 수가 예상값과 다르면 CLAUDE.md의 '총 툴 수'도 업데이트 필요."""
        assert len(_registry) == EXPECTED_TOOL_COUNT, (
            f"툴 수 불일치: 예상 {EXPECTED_TOOL_COUNT}, 실제 {len(_registry)}\n"
            "새 툴 추가/삭제 시 이 상수와 CLAUDE.md를 함께 수정하세요."
        )

    def test_no_duplicate_tool_names(self):
        names = list(_registry.keys())
        assert len(names) == len(set(names)), "중복 툴 이름 발견"

    def test_all_tools_have_required_keys(self):
        for name, tool in _registry.items():
            missing = REQUIRED_MANIFEST_KEYS - set(tool.keys())
            assert not missing, f"{name}: 누락 키 {missing}"

    def test_all_handlers_are_callable(self):
        for name, tool in _registry.items():
            assert callable(tool["handler"]), f"{name}.handler가 callable이 아님"

    def test_all_labels_are_non_empty_strings(self):
        for name, tool in _registry.items():
            assert isinstance(tool["label"], str) and tool["label"], f"{name}.label 비어있음"


class TestSchemas:
    def test_tools_list_length_matches_registry(self):
        assert len(TOOLS) == len(_registry)

    def test_tool_labels_dict_length_matches(self):
        assert len(TOOL_LABELS) == len(_registry)

    def test_all_schemas_are_function_type(self):
        for schema in TOOLS:
            assert schema.get("type") == "function", (
                f"schema type이 'function'이 아님: {schema}"
            )

    def test_all_schemas_have_function_block(self):
        for schema in TOOLS:
            assert "function" in schema, f"'function' 블록 누락: {schema}"
            fn = schema["function"]
            assert "name" in fn, f"function.name 누락: {fn}"
            assert "description" in fn, f"function.description 누락: {fn}"
            assert "parameters" in fn, f"function.parameters 누락: {fn}"

    def test_all_parameters_are_object_type(self):
        for schema in TOOLS:
            params = schema["function"]["parameters"]
            assert params.get("type") == "object", (
                f"{schema['function']['name']}.parameters.type이 'object'가 아님"
            )

    def test_schema_names_match_registry_names(self):
        schema_names = {s["function"]["name"] for s in TOOLS}
        registry_names = set(_registry.keys())
        assert schema_names == registry_names, (
            f"불일치: schema에만 있음={schema_names - registry_names}, "
            f"registry에만 있음={registry_names - schema_names}"
        )

    def test_tool_labels_keys_match_registry(self):
        assert set(TOOL_LABELS.keys()) == set(_registry.keys())


class TestModuleCoverage:
    """각 모듈에서 기대하는 툴이 등록되어 있는지 확인한다."""

    @pytest.mark.parametrize("tool_name", [
        "workflow_init",
        "workflow_set_step",
        "workflow_add_step",
        "workflow_update_step",
        "workflow_remove_step",
        "workflow_reorder",
    ])
    def test_workflow_tools_registered(self, tool_name):
        assert tool_name in _registry

    @pytest.mark.parametrize("tool_name", [
        "mouse_click",
        "key_press",
        "clipboard_set",
        "type_text",
    ])
    def test_desktop_tools_registered(self, tool_name):
        assert tool_name in _registry

    @pytest.mark.parametrize("tool_name", [
        "obsidian_search",
        "obsidian_read_note",
        "obsidian_write_note",
    ])
    def test_obsidian_tools_registered(self, tool_name):
        assert tool_name in _registry

    @pytest.mark.parametrize("tool_name", [
        "read_excel",
        "read_pdf",
        "write_file",
    ])
    def test_document_tools_registered(self, tool_name):
        assert tool_name in _registry

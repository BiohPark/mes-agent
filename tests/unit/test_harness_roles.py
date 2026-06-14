"""하네스 역할 정의 단위 테스트."""

import pytest
from agent.harness.roles import (
    HarnessRole,
    EXECUTOR,
    REVIEWER,
    get_role,
    HARNESS_ROLES,
)


class TestHarnessRole:
    def test_executor_has_all_tools(self):
        assert EXECUTOR.allowed_modules is None

    def test_executor_name(self):
        assert EXECUTOR.name == "executor"

    def test_executor_system_suffix_nonempty(self):
        assert len(EXECUTOR.system_suffix) > 10

    def test_reviewer_name(self):
        assert REVIEWER.name == "reviewer"

    def test_reviewer_has_read_only_modules(self):
        assert REVIEWER.allowed_modules is not None
        assert isinstance(REVIEWER.allowed_modules, frozenset)

    def test_reviewer_allowed_modules_read_only(self):
        """Reviewer는 읽기·관찰 모듈만 허용한다."""
        write_modules = {"desktop", "browser", "workflow", "obsidian_session", "office_com"}
        intersection = REVIEWER.allowed_modules & write_modules
        assert intersection == frozenset(), f"쓰기 모듈이 포함됨: {intersection}"

    def test_reviewer_system_suffix_mentions_json(self):
        assert "passed" in REVIEWER.system_suffix.lower() or "json" in REVIEWER.system_suffix.lower()

    def test_reviewer_system_suffix_mentions_true_false(self):
        suffix = REVIEWER.system_suffix
        assert "true" in suffix.lower() or "false" in suffix.lower()

    def test_roles_are_frozen(self):
        with pytest.raises((AttributeError, TypeError)):
            EXECUTOR.name = "changed"  # type: ignore[misc]

    def test_harness_roles_dict_contains_both(self):
        assert "executor" in HARNESS_ROLES
        assert "reviewer" in HARNESS_ROLES

    def test_get_role_executor(self):
        role = get_role("executor")
        assert role is EXECUTOR

    def test_get_role_reviewer(self):
        role = get_role("reviewer")
        assert role is REVIEWER

    def test_get_role_unknown_raises(self):
        with pytest.raises(KeyError):
            get_role("unknown_role")

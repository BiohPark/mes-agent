from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "harness" / "run-plan-critics.ps1"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _extract_here_string(text: str, variable: str) -> str:
    start_marker = f"${variable} = @\""
    start = text.index(start_marker) + len(start_marker)
    end = text.index('"@', start)
    return text[start:end]


def test_claude_mode_repo_is_blocked():
    text = _script_text()

    assert '[ValidateSet("None", "Smoke", "Generic", "Sanitized", "Repo")]' in text
    assert 'if ($ClaudeMode -eq "Repo")' in text
    assert "Refusing ClaudeMode Repo" in text


def test_generic_claude_prompt_has_no_repo_specific_context():
    text = _script_text()
    prompt = _extract_here_string(text, "claudePrompt")

    forbidden_terms = [
        "mes-agent",
        "agent/",
        "agent\\",
        "electron/",
        "electron\\",
        "docs/",
        "docs\\",
        "Task T",
        "task-T",
        "TASK_CONFIGS",
        "RunSnapshot",
        "RunLedger",
    ]
    for term in forbidden_terms:
        assert term not in prompt

    assert "Do not assume or mention any specific repository" in prompt
    assert "Resolve-CommandPath -CommandName \"claude\"" in text
    assert "claude.cmd" not in text
    assert '--tools ""' not in text


def test_smoke_checks_cover_codex_claude_and_agy_with_bounded_budgets():
    text = _script_text()

    assert "[switch]$SkipCodex" in text
    assert "[switch]$SkipAgy" in text
    assert "ClaudeMaxBudgetUsd" not in text
    assert "--max-budget-usd" not in text
    assert "function Quote-ProcessArgument" in text
    assert "$psi.Arguments" in text
    assert "Invoke-CodexSmoke" in text
    assert "Invoke-ClaudeSmoke" in text
    assert "Invoke-AgySmoke" in text
    assert "harness integration test" in text
    assert "does not authorize any action" in text
    assert "AGY_EXEC_OK" in text
    assert "AGY_TIMEOUT" in text


def test_allow_external_send_is_deprecated_not_a_repo_export_gate():
    text = _script_text()

    assert "-AllowExternalSend is deprecated" in text
    assert "does not permit repo-derived Claude prompts" in text
    assert "Re-run with -AllowExternalSend after explicit approval" not in text


def test_external_send_docs_use_levels_not_boolean_false():
    docs = [
        ROOT / "docs" / "harness" / "task-card-template.md",
        ROOT / "docs" / "ORCHESTRATION_GUIDE.md",
        ROOT / "docs" / "specs" / "development-harness.md",
        ROOT / "docs" / "harness" / "phase-report.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "none | generic | sanitized | repo" in combined
    assert "L0 Smoke" in combined
    assert "L1 Generic Critic" in combined
    assert "L2 Sanitized Summary" in combined
    assert "L3 Repo Context/Code" in combined
    assert "external_send: false" not in combined

param(
    [switch]$AllowExternalSend,
    [switch]$Smoke,
    [switch]$SkipClaude,
    [switch]$Help,
    [string]$OutputDir = "C:\tmp\mes-agent-harness-reviews"
)

if ($Help) {
    @"
Usage:
  .\scripts\harness\run-plan-critics.ps1 -Smoke
  .\scripts\harness\run-plan-critics.ps1 -Smoke -SkipClaude
  .\scripts\harness\run-plan-critics.ps1 -AllowExternalSend
  .\scripts\harness\run-plan-critics.ps1 -AllowExternalSend -SkipClaude

Purpose:
  Runs local Codex CLI and Claude Code as read-only critics for the mes-agent
  development harness plans.

Safety:
  This sends repository context to external model providers. The script refuses
  to run critic mode unless -AllowExternalSend is provided.

  -Smoke sends only minimal health prompts and does not ask the agents to read
  repository files. Use -SkipClaude when Claude Code network access is not
  approved for the current shell.
"@
    exit 0
}

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path ".").Path

if ($Smoke) {
    Write-Host "[harness] Running Codex CLI smoke check..."
    $smokeOut = Join-Path ([System.IO.Path]::GetTempPath()) "mes-agent-codex-smoke.txt"
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    cmd /c codex -a never exec -C "$repo" -s read-only --ephemeral --ignore-user-config --ignore-rules --output-last-message "$smokeOut" "Do not edit files. Reply with exactly: CODEX_EXEC_OK" *> $null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $oldErrorActionPreference
    if ($code -ne 0) {
        Write-Error "Codex CLI smoke command failed with exit code $code"
        exit $code
    }
    if ((Test-Path $smokeOut) -and ((Get-Content -Raw -Path $smokeOut).Trim() -eq "CODEX_EXEC_OK")) {
        Write-Host "[harness] Codex CLI smoke: CODEX_EXEC_OK"
    } else {
        Write-Error "Codex CLI smoke did not produce CODEX_EXEC_OK"
        exit $LASTEXITCODE
    }

    if (-not $SkipClaude) {
        Write-Host "[harness] Running Claude Code smoke check..."
        $claudeSmoke = (claude -p "Reply exactly CLAUDE_EXEC_OK" --safe-mode --permission-mode plan --tools "" --no-session-persistence)
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Claude Code smoke command failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        if ($claudeSmoke.Trim() -ne "CLAUDE_EXEC_OK") {
            Write-Error "Claude Code smoke did not produce CLAUDE_EXEC_OK"
            exit 3
        }
        Write-Host "[harness] Claude Code smoke: CLAUDE_EXEC_OK"
    }

    exit 0
}

if (-not $AllowExternalSend) {
    Write-Error "Refusing to run: this sends repository context to external model providers. Re-run with -AllowExternalSend after explicit approval."
    exit 2
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$codexOut = Join-Path $OutputDir "$stamp-codex-implementation-critic.txt"
$claudeOut = Join-Path $OutputDir "$stamp-claude-risk-test-critic.txt"

$codexPrompt = @"
You are Implementation Critic for mes-agent.
Do not edit files.
Read docs/ORCHESTRATION_GUIDE.md and docs/specs/development-harness.md.
Critique the existing development harness plan only for feasibility, file ownership,
step decomposition, dependency risk, and how to use local Codex CLI as a normal
agent with Claude Code.
Return concise Korean findings with BLOCKER/RISK/SUGGESTION.
"@

$claudePrompt = @"
Risk/Test Critic. Korean only.
Approved repo docs summary: mes-agent is a Windows closed-network desktop
automation agent. Critical constraints: OpenAI tool-pair invariant, safety
approvals, max 128 tools, no runtime downloads, worktree spec must exist, tests
include test.ps1 ci and smoke EXPECTED_TOOL_COUNT. Development harness plan:
Codex Desktop orchestrates, Codex CLI runs implementation critic read-only,
Claude Code runs risk/test critic, Claude/Ralph or Codex worktree workers
implement task cards, code-reviewer performs diff review. Every task card needs
task_id, title, spec, branch, worktree, owner, reviewer, scope.in, scope.out,
gates, completion_promise. Worker must not start if spec is absent in target
worktree. External OSS patterns are functional contracts only, no code copying.
First card supervisor-phase1-reducer modifies only Electron renderer and docs,
no server RunSnapshot.
Critique only L1 loop invariant risk, safety gate risk, missing tests, docs
update omissions, closed-network constraints, and completion gates.
Return exactly 6 Korean bullets: 2 BLOCKER, 2 RISK, 2 SUGGESTION.
"@

$codexPromptArg = ($codexPrompt -replace "\s+", " ").Trim()
$claudePromptArg = ($claudePrompt -replace "\s+", " ").Trim()

Write-Host "[harness] Running Codex CLI Implementation Critic..."
$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
cmd /c codex -a never exec -C "$repo" -s read-only --ephemeral --ignore-user-config --ignore-rules --output-last-message "$codexOut" "$codexPromptArg" *> $null
$code = $LASTEXITCODE
$ErrorActionPreference = $oldErrorActionPreference
if ($code -ne 0) {
    Write-Error "Codex CLI critic failed with exit code $code"
    exit $code
}

if (-not $SkipClaude) {
    Write-Host "[harness] Running Claude Code Risk/Test Critic..."
    $claudeErr = Join-Path $OutputDir "$stamp-claude-risk-test-critic.err.txt"
    $claudeArgs = @(
        "-p", $claudePromptArg,
        "--safe-mode",
        "--permission-mode", "plan",
        "--no-session-persistence",
        "--max-budget-usd", "0.50"
    )
    $proc = Start-Process -FilePath "claude" -ArgumentList $claudeArgs -WindowStyle Hidden -RedirectStandardOutput $claudeOut -RedirectStandardError $claudeErr -PassThru
    if (-not $proc.WaitForExit(120000)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        @"
CLAUDE_CRITIC_TIMEOUT
Claude Code Risk/Test Critic exceeded 120 seconds and was stopped.
Use -SkipClaude or run a shorter prompt manually, then record the output in docs/harness.
"@ | Set-Content -Encoding UTF8 -Path $claudeOut
        Write-Warning "Claude Code critic timed out after 120 seconds; timeout note written to $claudeOut"
    } elseif ($proc.ExitCode -ne 0) {
        Write-Warning "Claude Code critic exited with code $($proc.ExitCode); see $claudeErr"
    }
    if (Test-Path $claudeOut) {
        Get-Content -Encoding UTF8 -Path $claudeOut | Write-Host
    }
}

Write-Host "[harness] Outputs:"
Write-Host "  Codex:  $codexOut"
if (-not $SkipClaude) {
    Write-Host "  Claude: $claudeOut"
}

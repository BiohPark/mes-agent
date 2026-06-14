param(
    [switch]$Smoke,
    [switch]$SkipClaude,
    [ValidateSet("None", "Smoke", "Generic", "Sanitized", "Repo")]
    [string]$ClaudeMode = "None",
    [switch]$AllowExternalSend,
    [switch]$Help,
    [string]$OutputDir = "C:\tmp\mes-agent-harness-reviews"
)

if ($Help) {
    @"
Usage:
  .\scripts\harness\run-plan-critics.ps1 -Smoke
  .\scripts\harness\run-plan-critics.ps1 -Smoke -SkipClaude
  .\scripts\harness\run-plan-critics.ps1
  .\scripts\harness\run-plan-critics.ps1 -ClaudeMode Generic
  .\scripts\harness\run-plan-critics.ps1 -ClaudeMode Sanitized
  .\scripts\harness\run-plan-critics.ps1 -ClaudeMode Repo

  If PowerShell execution policy blocks direct script execution:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\harness\run-plan-critics.ps1 -Smoke

Purpose:
  Runs Codex CLI as a read-only critic for mes-agent development harness plans.
  Claude Code is optional and separated by external-send sensitivity level.
  Claude Code is invoked through cmd.exe, not PowerShell-native argument
  parsing, so Windows quoting is exercised the same way in smoke and critic
  runs.

Safety:
  -Smoke sends only minimal health prompts and does not ask the agents to read
  repository files. Use -SkipClaude when Claude Code network access is not
  approved for the current shell.

  ClaudeMode values:
    None      Do not call Claude Code. This is the default for critic mode.
    Smoke     Send only CLAUDE_EXEC_OK health prompt. No repo information.
    Generic   Send a generic risk/test checklist prompt. No repo name, files,
              code, internal task names, or project structure.
    Sanitized Use only a human-redacted prompt supplied in
              MES_AGENT_SANITIZED_CLAUDE_PROMPT. Record explicit approval.
    Repo      Blocked here. Use only a separately approved ZDR/gateway path.

  -AllowExternalSend is kept only as a deprecated compatibility flag. It no
  longer permits repo-derived Claude prompts.
"@
    exit 0
}

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path ".").Path
$claudeSmokeCommand = 'claude.cmd -p "Reply exactly CLAUDE_EXEC_OK" --permission-mode plan --tools "" --no-session-persistence'
$claudeFailureLog = Join-Path ([System.IO.Path]::GetTempPath()) "mes-agent-claude-failure-analysis.txt"
$repoDerivedClaudePatterns = @(
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
    "OpenAI tool-pair"
)

function Assert-GenericClaudePrompt {
    param([string]$Prompt)

    foreach ($pattern in $repoDerivedClaudePatterns) {
        if ($Prompt -match [regex]::Escape($pattern)) {
            throw "Generic Claude prompt contains repo-derived term: $pattern"
        }
    }
}

function Get-ClaudeFailureClass {
    param(
        [int]$ExitCode,
        [string]$StdOut,
        [string]$StdErr
    )

    $text = "$StdOut`n$StdErr"
    if ($text -match "terminator|ParserError|Unexpected token|The string is missing") {
        return "quoting/powershell"
    }
    if ($text -match "auth|login|not authenticated|unauthorized|OAuth|session") {
        return "auth/session"
    }
    if ($text -match "permission-mode|--tools|unknown option|invalid option|not allowed") {
        return "permission-mode/tools"
    }
    if ($text -match "hook|plugin|SessionEnd|Hook cancelled") {
        return "hook/plugin"
    }
    if ($text -match "Permission denied|Access is denied|EACCES|EPERM|sandbox|file access") {
        return "sandbox/file-permission"
    }
    if ($text -match "CLAUDE_TIMEOUT|timed out|timeout" -or $ExitCode -eq 124) {
        return "timeout/model-call"
    }
    if ($ExitCode -ne 0) {
        return "unknown-nonzero-exit"
    }
    return "unknown-output-mismatch"
}

function Write-ClaudeFailureAnalysis {
    param(
        [string]$Context,
        [int]$ExitCode,
        [string]$StdOut,
        [string]$StdErr
    )

    $failureClass = Get-ClaudeFailureClass -ExitCode $ExitCode -StdOut $StdOut -StdErr $StdErr
    $analysis = @(
        "[harness] Claude Code failure context: $Context",
        "[harness] Claude Code failure class: $failureClass",
        "[harness] Claude Code exit code: $ExitCode",
        "[harness] Claude stderr:",
        $StdErr,
        "[harness] Claude stdout:",
        $StdOut
    ) -join "`n"
    $analysis | Set-Content -Encoding UTF8 -Path $claudeFailureLog
    Write-Host "[harness] Claude Code failure context: $Context"
    Write-Host "[harness] Claude Code failure class: $failureClass"
    Write-Host "[harness] Claude Code failure log: $claudeFailureLog"
    if (-not [string]::IsNullOrWhiteSpace($StdErr)) {
        Write-Host "[harness] Claude stderr:"
        Write-Host $StdErr
    }
    if (-not [string]::IsNullOrWhiteSpace($StdOut)) {
        Write-Host "[harness] Claude stdout:"
        Write-Host $StdOut
    }
}

function Invoke-ClaudeCmd {
    param(
        [string]$CommandLine,
        [string]$OutputPath,
        [string]$ErrorPath,
        [int]$TimeoutMs = 120000
    )

    $cmdArgs = @("/d", "/s", "/c", $CommandLine)
    $proc = Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -WindowStyle Hidden -RedirectStandardOutput $OutputPath -RedirectStandardError $ErrorPath -PassThru
    if (-not $proc.WaitForExit($TimeoutMs)) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        "CLAUDE_TIMEOUT`nClaude Code command exceeded $TimeoutMs ms and was stopped." | Set-Content -Encoding UTF8 -Path $ErrorPath
        return 124
    }
    $proc.Refresh()
    return [int]$proc.ExitCode
}

function Invoke-ClaudeSmoke {
    Write-Host "[harness] Running Claude Code smoke check..."
    Write-Host "[harness] Claude Code standard command: cmd /d /s /c $claudeSmokeCommand"
    $stdout = Join-Path ([System.IO.Path]::GetTempPath()) "mes-agent-claude-smoke.out.txt"
    $stderr = Join-Path ([System.IO.Path]::GetTempPath()) "mes-agent-claude-smoke.err.txt"
    $code = Invoke-ClaudeCmd -CommandLine $claudeSmokeCommand -OutputPath $stdout -ErrorPath $stderr -TimeoutMs 120000
    $claudeSmoke = if (Test-Path $stdout) { Get-Content -Raw -Encoding UTF8 -Path $stdout } else { "" }
    $claudeError = if (Test-Path $stderr) { Get-Content -Raw -Encoding UTF8 -Path $stderr } else { "" }
    if ($code -ne 0) {
        Write-ClaudeFailureAnalysis -Context "smoke" -ExitCode $code -StdOut $claudeSmoke -StdErr $claudeError
        Write-Error "Claude Code smoke command failed with exit code $code"
        exit $code
    }
    if ($claudeSmoke.Trim() -ne "CLAUDE_EXEC_OK") {
        Write-ClaudeFailureAnalysis -Context "smoke-output" -ExitCode $code -StdOut $claudeSmoke -StdErr $claudeError
        Write-Error "Claude Code smoke did not produce CLAUDE_EXEC_OK"
        exit 3
    }
    Write-Host "[harness] Claude Code smoke: CLAUDE_EXEC_OK"
}

function Invoke-ClaudePrompt {
    param(
        [string]$Prompt,
        [string]$OutputPath,
        [string]$ErrorPath
    )

    $promptArg = (($Prompt -replace "\s+", " ").Trim() -replace '"', '\"')
    $commandLine = 'claude.cmd -p "' + $promptArg + '" --permission-mode plan --tools "" --no-session-persistence --max-budget-usd 0.50'
    Write-Host "[harness] Claude Code standard command: cmd /d /s /c claude.cmd -p <prompt> --permission-mode plan --tools """" --no-session-persistence --max-budget-usd 0.50"
    $code = Invoke-ClaudeCmd -CommandLine $commandLine -OutputPath $OutputPath -ErrorPath $ErrorPath -TimeoutMs 120000
    if ($code -eq 124) {
        @"
CLAUDE_CRITIC_TIMEOUT
Claude Code critic exceeded 120 seconds and was stopped.
Do not route around Claude Code with a hidden implementation path. Switch to Claude Code setup/root-cause analysis, then rerun this gate.
"@ | Set-Content -Encoding UTF8 -Path $OutputPath
        Write-Warning "Claude Code critic timed out after 120 seconds; timeout note written to $OutputPath"
    } elseif ($code -ne 0) {
        $claudeOutText = if (Test-Path $OutputPath) { Get-Content -Raw -Encoding UTF8 -Path $OutputPath } else { "" }
        $claudeErrText = if (Test-Path $ErrorPath) { Get-Content -Raw -Encoding UTF8 -Path $ErrorPath } else { "" }
        Write-ClaudeFailureAnalysis -Context "critic" -ExitCode $code -StdOut $claudeOutText -StdErr $claudeErrText
        Write-Warning "Claude Code critic exited with code $code; see $ErrorPath"
    }
    if (Test-Path $OutputPath) {
        Get-Content -Encoding UTF8 -Path $OutputPath | Write-Host
    }
}

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
        Invoke-ClaudeSmoke
    }

    exit 0
}

if ($AllowExternalSend) {
    Write-Warning "-AllowExternalSend is deprecated and does not permit repo-derived Claude prompts. Use -ClaudeMode Generic or -ClaudeMode Sanitized."
}

if ($SkipClaude -and $ClaudeMode -ne "None") {
    Write-Warning "-SkipClaude overrides -ClaudeMode $ClaudeMode. Claude Code will not be called."
    $ClaudeMode = "None"
}

if ($ClaudeMode -eq "Repo") {
    Write-Error "Refusing ClaudeMode Repo: repo context/code export is blocked in this script. Use only a separately approved Enterprise ZDR or company gateway path and record that approval." -ErrorAction Continue
    exit 2
}

if ($ClaudeMode -eq "Sanitized" -and [string]::IsNullOrWhiteSpace($env:MES_AGENT_SANITIZED_CLAUDE_PROMPT)) {
    Write-Error "ClaudeMode Sanitized requires MES_AGENT_SANITIZED_CLAUDE_PROMPT with a human-redacted, approved prompt." -ErrorAction Continue
    exit 2
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$codexOut = Join-Path $OutputDir "$stamp-codex-implementation-critic.txt"
$claudeOut = Join-Path $OutputDir "$stamp-claude-$($ClaudeMode.ToLowerInvariant())-critic.txt"

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
For a Python API plus desktop UI automation project, list a risk/test checklist
for adding a new state-mutating tool and a dynamic configuration endpoint.
Focus on assistant/tool message pairing invariants, user approval gates,
bounded tool schemas/count checks, no runtime dependency downloads,
unit/integration/smoke tests, documentation updates, and backend-before-UI
sequencing.
Do not assume or mention any specific repository, file path, product name,
internal task name, code, or project structure.
Return exactly 6 Korean bullets: 2 BLOCKER, 2 RISK, 2 SUGGESTION.
"@

$codexPromptArg = ($codexPrompt -replace "\s+", " ").Trim()

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

if ($ClaudeMode -eq "Smoke") {
    Invoke-ClaudeSmoke
} elseif ($ClaudeMode -eq "Generic") {
    Assert-GenericClaudePrompt -Prompt $claudePrompt
    Write-Host "[harness] Running Claude Code Generic Risk/Test Critic..."
    $claudeErr = Join-Path $OutputDir "$stamp-claude-generic-critic.err.txt"
    Invoke-ClaudePrompt -Prompt $claudePrompt -OutputPath $claudeOut -ErrorPath $claudeErr
} elseif ($ClaudeMode -eq "Sanitized") {
    Write-Host "[harness] Running Claude Code Sanitized Risk/Test Critic..."
    $claudeErr = Join-Path $OutputDir "$stamp-claude-sanitized-critic.err.txt"
    Invoke-ClaudePrompt -Prompt $env:MES_AGENT_SANITIZED_CLAUDE_PROMPT -OutputPath $claudeOut -ErrorPath $claudeErr
}

Write-Host "[harness] Outputs:"
Write-Host "  Codex:  $codexOut"
if ($ClaudeMode -ne "None" -and $ClaudeMode -ne "Smoke") {
    Write-Host "  Claude: $claudeOut"
} elseif ($ClaudeMode -eq "None") {
    Write-Host "  Claude: skipped (ClaudeMode None)"
}

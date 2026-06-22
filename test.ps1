# MES Agent 테스트 실행 스크립트
# 사용법: .\test.ps1 [옵션]
#   .\test.ps1              — 전체 테스트 + 커버리지 리포트
#   .\test.ps1 unit         — 단위 테스트만
#   .\test.ps1 integration  — 통합 테스트만
#   .\test.ps1 smoke        — 스모크 테스트만
#   .\test.ps1 fast         — 커버리지 없이 빠르게
#   .\test.ps1 ci           — 사외망 CI 재현 (requires_office 제외)
#   .\test.ps1 no-llm       — 실제 LLM 없이 실행 가능한 테스트만

param(
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

# 한글 출력 깨짐 방지: 콘솔 코드페이지 + PowerShell 출력 인코딩을 UTF-8로 통일
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== MES Agent 테스트 ===" -ForegroundColor Cyan

function Get-DotEnvValue {
    param([string]$Key)
    $envPaths = @(
        (Join-Path $PSScriptRoot ".env"),
        (Join-Path $PSScriptRoot ".env.example")
    )
    foreach ($envPath in $envPaths) {
        if (-not (Test-Path $envPath)) {
            continue
        }
        foreach ($line in Get-Content $envPath) {
            if ($line -notmatch '^\s*[^#=\s][^=]*=') {
                continue
            }
            $k, $v = $line -split '=', 2
            if ($k.Trim() -eq $Key) {
                return $v.Trim()
            }
        }
    }
    return ""
}

$PythonExe = "python"
$condaEnv = $env:CONDA_ENV
if (-not $condaEnv) { $condaEnv = Get-DotEnvValue "CONDA_ENV" }
$minicondaHome = $env:MINICONDA_HOME
if (-not $minicondaHome) { $minicondaHome = Get-DotEnvValue "MINICONDA_HOME" }
if ($condaEnv -and $minicondaHome) {
    $candidate = Join-Path $minicondaHome "envs\$condaEnv\python.exe"
    if (Test-Path $candidate) {
        $PythonExe = $candidate
    }
}

$pytestTempRoot = Join-Path $PSScriptRoot ".tmp"
New-Item -ItemType Directory -Force -Path $pytestTempRoot | Out-Null
$pytestBaseTemp = Join-Path $pytestTempRoot "pytest"

function Invoke-Pytest {
    param([string[]]$PytestArgs)
    & $PythonExe -m pytest @PytestArgs "--basetemp=$pytestBaseTemp"
}

Write-Host "Python: $(& $PythonExe --version 2>&1)"
Write-Host "pytest basetemp: $pytestBaseTemp"

switch ($Target) {
    "unit" {
        Write-Host "[ 단위 테스트 ]" -ForegroundColor Yellow
        Invoke-Pytest @("tests/unit", "-v", "--tb=short")
    }
    "integration" {
        Write-Host "[ 통합 테스트 ]" -ForegroundColor Yellow
        Invoke-Pytest @("tests/integration", "-v", "--tb=short")
    }
    "smoke" {
        Write-Host "[ 스모크 테스트 ]" -ForegroundColor Yellow
        Invoke-Pytest @("tests/smoke", "-v", "--tb=short")
    }
    "fast" {
        Write-Host "[ 전체 테스트 (커버리지 제외) ]" -ForegroundColor Yellow
        Invoke-Pytest @("tests/", "-v", "--tb=short")
    }
    "ci" {
        # 사외망 CI 재현: 전체 실행 (각 테스트가 skipif로 자체 처리)
        Write-Host "[ CI 모드 — 전체 실행 (skipif 자동 처리) ]" -ForegroundColor Yellow
        $env:CI = "true"
        $env:INTERNAL_CI = ""
        Invoke-Pytest @("-v", "--tb=short")
    }
    "no-llm" {
        # LLM 없이 실행: requires_llm 마커가 붙은 테스트 제외
        Write-Host "[ LLM 없이 실행 ]" -ForegroundColor Yellow
        Invoke-Pytest @("-m", "not requires_llm", "-v", "--tb=short")
    }
    default {
        Write-Host "[ 전체 테스트 + 커버리지 ]" -ForegroundColor Yellow
        Invoke-Pytest @(
            "tests/",
            "--cov=agent",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "-v",
            "--tb=short"
        )
        Write-Host ""
        Write-Host "커버리지 HTML 리포트: htmlcov/index.html" -ForegroundColor Green
    }
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ 모든 테스트 통과" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "✗ 테스트 실패" -ForegroundColor Red
    exit $LASTEXITCODE
}

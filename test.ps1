# MES Agent 테스트 실행 스크립트
# 사용법: .\test.ps1 [옵션]
#   .\test.ps1              — 전체 테스트 + 커버리지 리포트
#   .\test.ps1 unit         — 단위 테스트만
#   .\test.ps1 integration  — 통합 테스트만
#   .\test.ps1 smoke        — 스모크 테스트만
#   .\test.ps1 fast         — 커버리지 없이 빠르게

param(
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

Write-Host "=== MES Agent 테스트 ===" -ForegroundColor Cyan

switch ($Target) {
    "unit" {
        Write-Host "[ 단위 테스트 ]" -ForegroundColor Yellow
        python -m pytest tests/unit -v --tb=short
    }
    "integration" {
        Write-Host "[ 통합 테스트 ]" -ForegroundColor Yellow
        python -m pytest tests/integration -v --tb=short
    }
    "smoke" {
        Write-Host "[ 스모크 테스트 ]" -ForegroundColor Yellow
        python -m pytest tests/smoke -v --tb=short
    }
    "fast" {
        Write-Host "[ 전체 테스트 (커버리지 제외) ]" -ForegroundColor Yellow
        python -m pytest tests/ -v --tb=short
    }
    default {
        Write-Host "[ 전체 테스트 + 커버리지 ]" -ForegroundColor Yellow
        python -m pytest tests/ `
            --cov=agent `
            --cov-report=term-missing `
            --cov-report=html:htmlcov `
            -v --tb=short
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

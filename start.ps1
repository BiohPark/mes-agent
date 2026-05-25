# mes-agent 개발 환경 시작 스크립트
# 사용법: .\start.ps1

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Set-Location $PSScriptRoot

# .env 파일 읽기
if (-not (Test-Path ".env")) {
    Write-Error ".env 파일이 없습니다. .env.example을 복사해서 설정하세요."
    exit 1
}

Get-Content ".env" | Where-Object { $_ -match '^\s*[^#=\s]' } | ForEach-Object {
    $key, $value = $_ -split '=', 2
    $key = $key.Trim()
    $value = $value.Trim()
    Set-Item -Path "env:$key" -Value $value
}

# nvm + Node.js PATH 설정
$env:PATH = "$env:NVM_HOME;$env:NVM_SYMLINK;$env:PATH"

# Node 버전 전환
Write-Host "Node.js $env:NODE_VERSION 설정 중..."
& "$env:NVM_HOME\nvm.exe" use $env:NODE_VERSION
if ($LASTEXITCODE -ne 0) {
    Write-Warning "nvm use 실패. 현재 Node 버전을 그대로 사용합니다."
}

# node/npm 확인
Write-Host "Node: $(node --version 2>&1)"
Write-Host "npm:  $(npm --version 2>&1)"

# conda 환경 활성화
Write-Host "conda 환경 '$env:CONDA_ENV' 활성화 중..."

# condabin을 PATH에 추가해 conda 명령어 자체를 사용 가능하게
$env:PATH = "$env:MINICONDA_HOME\condabin;$env:PATH"

$condaHook = "$env:MINICONDA_HOME\shell\condabin\conda-hook.ps1"
if (Test-Path $condaHook) {
    & $condaHook
    conda activate $env:CONDA_ENV
} else {
    $condaEnvPath = "$env:MINICONDA_HOME\envs\$env:CONDA_ENV"
    $env:PATH = "$condaEnvPath;$condaEnvPath\Scripts;$condaEnvPath\Library\bin;$env:PATH"
    $env:CONDA_DEFAULT_ENV = $env:CONDA_ENV
    Write-Warning "conda hook 없음 — PATH에 직접 추가했습니다."
}

# Python 확인
Write-Host "Python: $(python --version 2>&1)"

Write-Host ""
Write-Host "환경 준비 완료. 다음 명령으로 시작하세요:"
Write-Host "  npm start        — Electron 앱 실행"
Write-Host "  python agent\server.py  — FastAPI 서버 실행"


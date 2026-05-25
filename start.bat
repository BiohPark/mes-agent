@echo off
call conda activate mes-agent
if errorlevel 1 (
    echo [오류] conda 환경 "mes-agent"를 찾을 수 없습니다.
    pause
    exit /b 1
)
npm start

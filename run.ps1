# C.Futures 로컬 실행 스크립트
# 사용법: PowerShell에서 .\run.ps1

$BackendDir = Join-Path $PSScriptRoot "backend"
$FrontendDir = Join-Path $PSScriptRoot "frontend"

Write-Host "=== 1. 백엔드 의존성 확인 ===" -ForegroundColor Cyan
Set-Location $BackendDir
& .\venv\Scripts\pip.exe install -q -r requirements.txt 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "백엔드 pip 설치 실패. 수동 실행: cd backend; .\venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
}

Write-Host "`n=== 2. 백엔드 서버 시작 (새 창) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendDir'; .\venv\Scripts\python.exe main.py"

Start-Sleep -Seconds 4

Write-Host "`n=== 3. 프론트엔드 빌드 및 실행 (새 창) ===" -ForegroundColor Cyan
Remove-Item -Recurse -Force (Join-Path $FrontendDir ".next") -ErrorAction SilentlyContinue
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendDir'; npm run build; npm run start"

Write-Host "`n백엔드: http://localhost:8000/health" -ForegroundColor Green
Write-Host "프론트: http://localhost:3001 (빌드 완료 후 열기)" -ForegroundColor Green
Write-Host "`n열린 두 창을 닫으면 서버가 종료됩니다." -ForegroundColor Gray

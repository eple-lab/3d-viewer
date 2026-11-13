# 로컬 미리보기 서버
# file:// 로 열면 브라우저가 .sog 읽기를 막는다. 반드시 http 로 열어야 한다.
# 사용:  powershell -File scripts\serve.ps1
#        powershell -File scripts\serve.ps1 -Port 8000
param([int]$Port = 8777)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "http://localhost:$Port" -ForegroundColor Cyan
Write-Host "확인: http://localhost:$Port/scene.sog 가 내려오는지" -ForegroundColor DarkGray
python -m http.server $Port

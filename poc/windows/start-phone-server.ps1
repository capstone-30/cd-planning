# Start the PoC server on this PC's Wi-Fi address for the phone web page.
# Usage (PowerShell, in windows):  .\start-phone-server.ps1 [-Port 8080] [-WebPage path\to\index.html]
param([int]$Port = 8080, [string]$WebPage)
$ErrorActionPreference = 'Stop'
if ($WebPage) { $WebPage = (Resolve-Path -LiteralPath $WebPage).Path }
$poc = Join-Path $PSScriptRoot '..\shared-poc\poc'
Set-Location $poc

# COLMAP/Brush installed under %USERPROFILE%\Tools; add them in case this shell predates the PATH change.
foreach ($dir in @("$env:USERPROFILE\Tools\colmap\bin", "$env:USERPROFILE\Tools\brush")) {
    if ((Test-Path $dir) -and -not (($env:Path -split ';') -contains $dir)) { $env:Path = "$dir;$env:Path" }
}

$python = Join-Path $poc '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw ".venv 가 없습니다. 'python -m venv .venv' 후 '.venv\Scripts\pip install -r requirements-dev.txt' 를 먼저 실행하세요." }

# Private IPv4 of the Wi-Fi adapter (skips Tailscale/virtual adapters).
$ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.InterfaceAlias -match 'Wi-?Fi|WLAN|무선' -and $_.IPAddress -match '^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)' } |
    Select-Object -First 1 -ExpandProperty IPAddress
if (-not $ip) { throw 'Wi-Fi 사설 IP를 찾지 못했습니다. PC가 Wi-Fi에 연결되어 있는지 확인하세요.' }

# Short token that is easy to type on a phone (16 chars, server minimum).
$alphabet = 'abcdefghjkmnpqrstuvwxyz23456789'
$env:POC_TOKEN = -join (1..16 | ForEach-Object { $alphabet[(Get-Random -Maximum $alphabet.Length)] })
$env:PYTHONIOENCODING = 'utf-8'

Write-Host ''
Write-Host '========================================================' -ForegroundColor DarkYellow
Write-Host "  클라이언트 접속 주소:  http://${ip}:$Port" -ForegroundColor Yellow
Write-Host "  토큰:                  $($env:POC_TOKEN)" -ForegroundColor Yellow
Write-Host '  (폰과 PC가 같은 Wi-Fi여야 합니다. 종료: Ctrl+C)' -ForegroundColor DarkYellow
Write-Host '========================================================' -ForegroundColor DarkYellow
Write-Host ''

$serverArgs = @('-m', 'server', '--host', $ip, '--port', $Port)
if ($WebPage) { $serverArgs += @('--web-page', $WebPage) }
& $python @serverArgs

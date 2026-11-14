# Open the trained 3D scenes (A and A+B) of the most recent project in the Brush viewer.
# Usage (PowerShell, in the poc folder):  .\view-3d.ps1            # both, side by side windows
#                                          .\view-3d.ps1 -Only A     # or -Only AB
param([ValidateSet('both', 'A', 'AB')][string]$Only = 'both')
$ErrorActionPreference = 'Stop'
$brush = "$env:USERPROFILE\Tools\brush\brush_app.exe"
if (-not (Test-Path $brush)) { throw "Brush가 없습니다: $brush" }

$data = Join-Path $PSScriptRoot 'data'
$runs = Get-ChildItem $data -Directory | ForEach-Object { Get-ChildItem (Join-Path $_.FullName 'runs') -Directory -ErrorAction SilentlyContinue } |
    Where-Object { Test-Path (Join-Path $_.FullName 'splats\result.ply') } |
    ForEach-Object {
        $s = Get-Content (Join-Path $_.FullName 'status.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        [pscustomobject]@{ Mode = $s.mode; Ply = (Join-Path $_.FullName 'splats\result.ply'); Time = (Get-Item (Join-Path $_.FullName 'splats\result.ply')).LastWriteTime }
    }
$latest = @{
    A  = $runs | Where-Object Mode -eq 'initial'  | Sort-Object Time -Descending | Select-Object -First 1
    AB = $runs | Where-Object Mode -eq 'combined' | Sort-Object Time -Descending | Select-Object -First 1
}
foreach ($key in 'A', 'AB') {
    if ($Only -ne 'both' -and $Only -ne $key) { continue }
    $r = $latest[$key]
    if (-not $r) { Write-Host "$key 결과(result.ply)가 아직 없습니다." -ForegroundColor Yellow; continue }
    Write-Host "$key 열기: $($r.Ply)"
    Start-Process -FilePath $brush -ArgumentList '--with-viewer', "`"$($r.Ply)`""
}

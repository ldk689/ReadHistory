param(
    [string]$Version = (Get-Content (Join-Path $PSScriptRoot "..\VERSION") -Raw).Trim()
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dist = Join-Path $root "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path $git)) {
    $git = "git"
}

Set-Location $root
$zipName = "ReadHistory-$Version.zip"
$zipPath = Join-Path $dist $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

& $git archive --format=zip --prefix="ReadHistory-$Version/" --output="$zipPath" HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }

$hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
$sumPath = Join-Path $dist "SHA256SUMS.txt"
"$hash  $zipName" | Set-Content -Path $sumPath -Encoding ascii

Write-Host "Package: $zipPath" -ForegroundColor Green
Write-Host "SHA256:  $hash"
Get-Item $zipPath | Select-Object Name, Length

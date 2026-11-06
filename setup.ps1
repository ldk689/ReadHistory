$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$bundled = "C:\Users\ManifestDK\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if (Test-Path $bundled) {
    $python = $bundled
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} else {
    Write-Host "未找到 Python。请安装 Python 3.11/3.12 后再运行。" -ForegroundColor Red
    exit 1
}

$venv = Join-Path $root ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "创建虚拟环境 .venv …" -ForegroundColor DarkGray
    & $python -m venv $venv
}

$venvPython = Join-Path $venv "Scripts\python.exe"
Write-Host "安装依赖（首次约需下载 300–500 MB）…" -ForegroundColor DarkGray
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

Write-Host ""
Write-Host "安装完成。双击 start.bat 启动青简。" -ForegroundColor Green

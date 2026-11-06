$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$bundled = "C:\Users\ManifestDK\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if ((Test-Path (Join-Path $root ".pdfium")) -and (Test-Path $bundled)) {
    # 当前工作区的离线依赖（开发/演示环境）
    $python = $bundled
} elseif (Test-Path $venvPython) {
    $python = $venvPython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} else {
    Write-Host "未找到 Python。请先运行 setup.bat，或安装 Python 3.11/3.12。" -ForegroundColor Red
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"
Write-Host ""
Write-Host "  青简 · ReadHistory" -ForegroundColor DarkRed
Write-Host "  正在启动本地服务…" -ForegroundColor DarkGray
Write-Host ""
& $python run.py --open

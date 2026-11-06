param(
    [string]$Version = (Get-Content (Join-Path $PSScriptRoot "..\VERSION") -Raw).Trim()
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$build = Join-Path $root ".build"
$payload = Join-Path $build "payload"
$dist = Join-Path $root "dist"
$folder = Join-Path $dist "Qingjian_ReadHistory"
$runtime = Join-Path $folder "runtime"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$icon = Join-Path $root "tools\launcher\QingJian.ico"
$launcherSrc = Join-Path $root "tools\launcher\QingJianLauncher.cs"
$assembly = Join-Path $root "tools\launcher\AssemblyInfo.cs"
$manifest = Join-Path $root "tools\launcher\app.manifest"
$wv2Core = Join-Path $build "webview2\lib\net462\Microsoft.Web.WebView2.Core.dll"
$wv2Forms = Join-Path $build "webview2\lib\net462\Microsoft.Web.WebView2.WinForms.dll"
$wv2Loader = Join-Path $build "webview2\runtimes\win-x64\native\WebView2Loader.dll"

if (-not (Test-Path (Join-Path $payload "python\pythonw.exe"))) {
    throw "缺少 .build/payload。請先執行 tools\build_exe.ps1 準備運行組件。"
}
if (-not (Test-Path $csc)) { throw "找不到 C# 編譯器：$csc" }
if (-not (Test-Path $wv2Core)) { throw "缺少 WebView2 SDK：$wv2Core" }

New-Item -ItemType Directory -Force -Path $dist | Out-Null
if (Test-Path $folder) { Remove-Item $folder -Recurse -Force }
New-Item -ItemType Directory -Force -Path $folder | Out-Null

Write-Host "1/4 複製運行組件…" -ForegroundColor Cyan
robocopy $payload $runtime /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "複製運行組件失敗（robocopy $LASTEXITCODE）" }
Remove-Item (Join-Path $runtime "使用說明.txt") -Force -ErrorAction SilentlyContinue
foreach ($item in @(
    ".ocr2\rapidocr\models\ch_PP-OCRv4_rec_server_infer.onnx",
    ".ocrdeps\cv2\opencv_videoio_ffmpeg500_64.dll"
)) {
    $p = Join-Path $runtime $item
    if (Test-Path $p) { Remove-Item $p -Force }
}

Write-Host "2/4 編譯小體積啟動器…" -ForegroundColor Cyan
& $csc /nologo /codepage:65001 /target:winexe /platform:x64 /optimize+ "/win32icon:$icon" "/win32manifest:$manifest" `
    "/out:$(Join-Path $folder 'Qingjian_ReadHistory.exe')" `
    /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll `
    "/r:$wv2Core" "/r:$wv2Forms" `
    $launcherSrc $assembly
if ($LASTEXITCODE -ne 0) { throw "啟動器編譯失敗" }
Copy-Item $wv2Core $folder -Force
Copy-Item $wv2Forms $folder -Force
Copy-Item $wv2Loader $folder -Force

Write-Host "3/4 寫入說明與診斷腳本…" -ForegroundColor Cyan
$readme = @"
青簡 / ReadHistory $Version · Windows 可攜版
================================================

【最重要】
請保持 Qingjian_ReadHistory.exe 與 runtime 文件夾在同一層目錄。
不要只把 EXE 單獨複製到別處，否則它找不到內置的 Python 與 OCR 組件。

【啟動】
雙擊 Qingjian_ReadHistory.exe。
首次啟動可能需要 10–30 秒載入組件；成功後會打開青簡自己的閱讀窗口，不再依賴外部 Edge。
右下角托盤會出現「青」圖標；右鍵可退出，也可選擇「在瀏覽器中打開」。

【如果無法啟動】
1. 雙擊「診斷.bat」。它會打開一個黑色窗口並顯示具體錯誤。
2. 把窗口中的文字，或 logs 文件夾裡的 launcher.log / server.log 發給開發者。
3. logs 文件夾就在本目錄下，程式不會自動刪除它。

【Windows 提示】
本程序未購買代碼簽名證書，Windows SmartScreen 可能提示「已保護你的電腦」。
確認文件來自本項目 Release 後，點「更多信息」→「仍要運行」。
這只是信任提示，不是缺少運行庫。

【數據位置】
data\        批註、閱讀進度、導入的 PDF、OCR 記錄
logs\        啟動與服務日誌
runtime\     內置 Python、OCR 模型、字體與程式本體（請勿刪除）

【許可】
程式碼 MIT；第三方組件與字體許可見 runtime\LICENSES 與
runtime\THIRD_PARTY_NOTICES.md。
"@
[IO.File]::WriteAllText((Join-Path $folder "使用說明.txt"), $readme, (New-Object Text.UTF8Encoding($true)))
[IO.File]::WriteAllText((Join-Path $folder "啟動青簡.bat"),
    "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" `"%~dp0Qingjian_ReadHistory.exe`"`r`n",
    (New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path $folder "備用啟動.bat"),
    "@echo off`r`ncd /d `"%~dp0runtime`"`r`nset READHISTORY_HOME=%~dp0`r`nset PYTHONIOENCODING=utf-8`r`nstart `"`" `"%~dp0runtime\python\pythonw.exe`" run.py --open`r`n",
    (New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path $folder "診斷.bat"),
    "@echo off`r`nchcp 65001 >nul`r`ntitle 青簡診斷`r`ncd /d `"%~dp0`"`r`nset READHISTORY_HOME=%~dp0`r`nset PYTHONIOENCODING=utf-8`r`necho.`r`necho 青簡診斷：下面會顯示啟動過程與錯誤。按 Ctrl+C 可停止。`r`necho.`r`n`"%~dp0runtime\python\python.exe`" `"%~dp0runtime\run.py`" --port 8799`r`necho.`r`necho 服務已停止。請把上面的錯誤文字發給開發者。`r`npause`r`n",
    (New-Object Text.UTF8Encoding($false)))

Write-Host "4/4 壓縮…" -ForegroundColor Cyan
$zip = Join-Path $dist "Qingjian_ReadHistory-$Version-win64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($folder, $zip, [System.IO.Compression.CompressionLevel]::Fastest, $true)

$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path $zip -Leaf)" | Set-Content (Join-Path $dist "SHA256SUMS-portable.txt") -Encoding ascii
Write-Host ""
Write-Host "完成：$zip" -ForegroundColor Green
Write-Host ("大小：{0:N1} MB" -f ((Get-Item $zip).Length / 1MB))
Write-Host "SHA256：$hash"

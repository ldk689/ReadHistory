param(
    [string]$Version = (Get-Content (Join-Path $PSScriptRoot "..\VERSION") -Raw).Trim(),
    [string]$OutName = "Qingjian_ReadHistory.exe"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$build = Join-Path $root ".build"
$payload = Join-Path $build "payload"
$dist = Join-Path $root "dist"
$rt = Join-Path $build "rt"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$icon = Join-Path $root "tools\launcher\QingJian.ico"
$launcherSrc = Join-Path $root "tools\launcher\QingJianLauncher.cs"

if (-not (Test-Path $csc)) { throw "找不到 C# 編譯器：$csc" }
if (-not (Test-Path (Join-Path $rt "python.exe"))) {
    throw "找不到可攜式 Python。請先把 dist/ReadHistory-0.1.0-win64-portable.zip 的 python/ 解壓到 .build/rt。"
}

New-Item -ItemType Directory -Force -Path $build, $dist | Out-Null
if (Test-Path $payload) { Remove-Item $payload -Recurse -Force }
New-Item -ItemType Directory -Force -Path $payload | Out-Null

Write-Host "1/6 複製程式與資源…" -ForegroundColor Cyan
foreach ($item in @("reader", "web", "run.py", "VERSION", "LICENSE", "README.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", "LICENSES")) {
    Copy-Item (Join-Path $root $item) (Join-Path $payload $item) -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $payload "data\seed"), (Join-Path $payload "data\assets") | Out-Null
Copy-Item (Join-Path $root "data\seed\jinshu_vol1.json") (Join-Path $payload "data\seed") -Force
Copy-Item (Join-Path $root "data\seed\NOTICE.md") (Join-Path $payload "data\seed") -Force
Copy-Item (Join-Path $root "data\assets\cover-jinshu.jpg") (Join-Path $payload "data\assets") -Force

Write-Host "2/6 複製內置 Python 與 OCR 依賴…" -ForegroundColor Cyan
$pyDst = Join-Path $payload "python"
Copy-Item $rt $pyDst -Recurse -Force
foreach ($pkg in @("pandas", "docx", "pptx", "openpyxl", "lxml", "xlsxwriter", "dateutil", "tzdata", "et_xmlfile", "pip", "setuptools", "pkg_resources")) {
    $p = Join-Path $pyDst "Lib\site-packages\$pkg"
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
Get-ChildItem (Join-Path $pyDst "Lib\site-packages") -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "(?i)(pandas|python_docx|python_pptx|openpyxl|et_xmlfile|lxml|pillow|numpy|xlsxwriter|dateutil|tzdata|pip)-" } |
    Where-Object { $_.Name -notmatch "(?i)numpy|pillow" } |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force }
foreach ($p in @("Lib\test", "Lib\idlelib", "Lib\tkinter", "tcl", "include", "libs", "Scripts")) {
    $full = Join-Path $pyDst $p
    if (Test-Path $full) { Remove-Item $full -Recurse -Force }
}
Get-ChildItem (Join-Path $pyDst "DLLs") -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "^(tk|tcl|_tkinter)" } | Remove-Item -Force

foreach ($dll in @("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll")) {
    $src = Join-Path $env:WINDIR "System32\$dll"
    if (Test-Path $src) { Copy-Item $src (Join-Path $pyDst $dll) -Force }
}

Copy-Item (Join-Path $root ".ocr2") (Join-Path $payload ".ocr2") -Recurse -Force
Copy-Item (Join-Path $root ".ocrdeps") (Join-Path $payload ".ocrdeps") -Recurse -Force
Copy-Item (Join-Path $root ".pdfium") (Join-Path $payload ".pdfium") -Recurse -Force
foreach ($junk in @(".ocrdeps\rapidocr_onnxruntime", ".ocrdeps\rapidocr_onnxruntime-1.4.4.dist-info")) {
    $p = Join-Path $payload $junk
    if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}
# Unused by the configured langs (chinese_cht_mobile / ch_doc_server) and
# only needed for video capture, respectively.
foreach ($item in @(
    ".ocr2\rapidocr\models\ch_PP-OCRv4_rec_server_infer.onnx",
    ".ocrdeps\cv2\opencv_videoio_ffmpeg500_64.dll"
)) {
    $p = Join-Path $payload $item
    if (Test-Path $p) { Remove-Item $p -Force }
}

# Package licenses alongside the third-party notices.
$licenseDir = Join-Path $payload "LICENSES"
New-Item -ItemType Directory -Force -Path (Join-Path $licenseDir "packages") | Out-Null
Copy-Item (Join-Path $pyDst "LICENSE.txt") (Join-Path $licenseDir "Python-3.12.txt") -Force
$licenseSources = @(
    @(".ocr2\requests-2.34.2.dist-info\licenses\LICENSE", "requests-LICENSE.txt"),
    @(".ocr2\omegaconf-2.4.0.dist-info\licenses\LICENSE", "omegaconf-LICENSE.txt"),
    @(".ocr2\colorlog-6.12.0.dist-info\licenses\LICENSE", "colorlog-LICENSE.txt"),
    @(".ocrdeps\onnxruntime\LICENSE", "onnxruntime-LICENSE.txt"),
    @(".ocrdeps\cv2\LICENSE.txt", "opencv-LICENSE.txt"),
    @(".ocrdeps\cv2\LICENSE-3RD-PARTY.txt", "opencv-LICENSE-3RD-PARTY.txt"),
    @(".ocrdeps\shapely-2.2.0.dist-info\licenses\LICENSE.txt", "shapely-LICENSE.txt"),
    @(".ocrdeps\pyclipper-1.4.0.dist-info\licenses\LICENSE", "pyclipper-LICENSE.txt"),
    @(".ocrdeps\pyyaml-6.0.3.dist-info\licenses\LICENSE", "pyyaml-LICENSE.txt"),
    @(".ocrdeps\tqdm-4.70.1.dist-info\licenses\LICENCE", "tqdm-LICENSE.txt")
)
foreach ($pair in $licenseSources) {
    $src = Join-Path $root $pair[0]
    if (Test-Path $src) { Copy-Item $src (Join-Path $licenseDir "packages\$($pair[1])") -Force }
}
$notice = @"
青簡 / ReadHistory $Version · Windows 單文件版
================================================

雙擊 Qingjian_ReadHistory.exe 即可使用，無需安裝 Python，也無需聯網。

第一次啟動會把執行組件展開到：
  %LOCALAPPDATA%\QingJian\app

閱讀數據、導入的 PDF、批註與 OCR 記錄保存在：
  %LOCALAPPDATA%\QingJian\data

程序只監聽 127.0.0.1（本機），不會上傳任何內容。
關閉：右鍵點擊右下角托盤中的「青」圖標 → 退出青簡。

許可證：程式碼 MIT；第三方組件與字體許可見 THIRD_PARTY_NOTICES.md
與 LICENSES 目錄。
"@
$notice | Set-Content -Path (Join-Path $payload "使用說明.txt") -Encoding UTF8

Write-Host "3/6 壓縮載荷…" -ForegroundColor Cyan
$zip = Join-Path $build "payload.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $payload, $zip, [System.IO.Compression.CompressionLevel]::Fastest, $false)

Write-Host "4/6 編譯啟動器…" -ForegroundColor Cyan
$launcher = Join-Path $build "QingJianLauncher.exe"
& $csc /nologo /codepage:65001 /target:winexe /platform:anycpu /optimize+ "/win32icon:$icon" "/out:$launcher" `
    /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll `
    "$launcherSrc" (Join-Path $root "tools\launcher\AssemblyInfo.cs")
if ($LASTEXITCODE -ne 0) { throw "啟動器編譯失敗" }

Write-Host "5/6 合成單文件 EXE…" -ForegroundColor Cyan
$outPath = Join-Path $dist $OutName
if (Test-Path $outPath) { Remove-Item $outPath -Force }
Copy-Item $launcher $outPath -Force
$offset = (Get-Item $outPath).Length
$buildId = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$payloadLength = (Get-Item $zip).Length

$outStream = [System.IO.File]::Open($outPath, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
try {
    $zipStream = [System.IO.File]::OpenRead($zip)
    try { $zipStream.CopyTo($outStream) } finally { $zipStream.Dispose() }
    $footer = New-Object byte[] 32
    [System.Text.Encoding]::ASCII.GetBytes("QJPAY001").CopyTo($footer, 0)
    [BitConverter]::GetBytes([int64]$offset).CopyTo($footer, 8)
    [BitConverter]::GetBytes([int64]$payloadLength).CopyTo($footer, 16)
    [BitConverter]::GetBytes([int64]$buildId).CopyTo($footer, 24)
    $outStream.Write($footer, 0, 32)
} finally {
    $outStream.Dispose()
}

Write-Host "6/6 校驗與清理…" -ForegroundColor Cyan
$file = Get-Item $outPath
$hash = (Get-FileHash $outPath -Algorithm SHA256).Hash.ToLower()
"$hash  $OutName" | Set-Content -Path (Join-Path $dist "SHA256SUMS-exe.txt") -Encoding ascii
Write-Host ""
Write-Host "完成：$outPath" -ForegroundColor Green
Write-Host ("大小：{0:N1} MB" -f ($file.Length / 1MB))
Write-Host "SHA256：$hash"

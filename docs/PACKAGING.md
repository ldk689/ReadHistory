# 青简 0.2.1 打包说明 / Packaging notes

## 默认发布：小 EXE + runtime

`tools/build_portable.ps1` 生成默认的 Windows 可携版：

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_exe.ps1   # 准备 .build/payload
powershell -ExecutionPolicy Bypass -File tools\build_portable.ps1
```

输出：

```
dist/Qingjian_ReadHistory/
  Qingjian_ReadHistory.exe   约 46 KB（x64，DPI-aware，WebView2 宿主）
  Microsoft.Web.WebView2.Core.dll
  Microsoft.Web.WebView2.WinForms.dll
  WebView2Loader.dll
  runtime/                   约 422 MB
  data/ logs/ webview-data/  首次启动生成
  使用說明.txt
  啟動青簡.bat / 備用啟動.bat / 診斷.bat
dist/Qingjian_ReadHistory-0.2.1-win64.zip   约 235 MB
```

编译启动器需要 WebView2 SDK（NuGet `Microsoft.Web.WebView2` 1.0.4314.35）：
`.build/webview2/lib/net462/Microsoft.Web.WebView2.Core.dll`、`...WinForms.dll`、
`.build/webview2/runtimes/win-x64/native/WebView2Loader.dll`。
脚本会把这三个 DLL 复制到 EXE 同级；WebView2 Runtime 本身由 Windows 提供，不随包分发。

内置窗口默认最大化，并使用 `tools/launcher/app.manifest` 的 PerMonitorV2 DPI 设置；关闭窗口只是隐藏到托盘，托盘「退出青簡」才真正结束服务。

启动器优先检测自身目录下的 `runtime\python\pythonw.exe`：存在则进入可携模式，数据与日志都放在 EXE 同级目录；不存在则回退到旧的单文件内嵌模式。

可携模式没有“首次解包”步骤，因此不会出现解包到一半被杀毒软件/磁盘/路径长度打断的问题；日志始终写在 `logs\`，不会被程序删除。

## 旧式单文件 EXE

`tools/build_exe.ps1` 也可以生成旧式单文件程序：

1. 从 `.build/rt` 复制便携式 Python 3.12；
2. 复制 `reader/`、`web/`、`.ocr2/`、`.ocrdeps/`、`.pdfium/`、样章与许可证；
3. 压缩为 `.build/payload.zip`；
4. 编译 `tools/launcher/QingJianLauncher.cs`；
5. 把 ZIP 附加到启动器尾部，写入 32 字节页脚（magic、offset、length、build id）；
6. 输出 `dist/Qingjian_ReadHistory.exe` 与 `dist/SHA256SUMS-exe.txt`。

启动器运行时：

- 读取自身尾部页脚；
- 首次启动把载荷展开到 `%LOCALAPPDATA%\QingJian\app`，写 `.build-id`；
- 设置 `READHISTORY_HOME=%LOCALAPPDATA%\QingJian`；
- 选择一个空闲的本机端口，启动 `python\pythonw.exe run.py --port N`；
- 轮询 `/api/health`，就绪后打开默认浏览器；
- 在托盘常驻，右键可退出并优雅关闭服务。

## 前置条件

`.build/rt` 需要是完整的 Python 3.12 运行时（来自 0.1.0 便携包或 python.org 的 embeddable/full 发行版），并带有 `pythonw.exe`、`Lib`、`DLLs`。

## 编码注意

`build_exe.ps1` 必须以 **UTF-8 with BOM** 保存，否则中文 Windows PowerShell 5.1 会把中文注释按 ANSI 解析而报语法错误。当前仓库中的文件已带 BOM。

## 体积

载荷约 400–500 MB（未压缩），EXE 约 300–400 MB。ONNX 模型和 OpenCV 占主要部分。若需要更小体积，可在打包脚本中删除未使用的 `ch_PP-OCRv4_rec_server_infer.onnx`（约 86 MB），但需先用 `RapidOCR` 的精校模式回归测试。

## 数据与升级

程序目录（`app`）可被新版本覆盖；用户数据在 `data`，两者分离。启动器用 `.build-id` 判断是否需要重新展开。

## 诊断模式

启动器支持无窗口的维护模式，用于确认载荷是否完整：

```powershell
$env:QINGJIAN_HOME = "D:\temp\qingjian-test"
.\Qingjian_ReadHistory.exe --extract-only
```

它会读取自身尾部页脚、展开载荷到 `$env:QINGJIAN_HOME\app`，打印路径后退出。`QINGJIAN_HOME` 也用于把安装根目录从 `%LOCALAPPDATA%\QingJian` 改到其他位置（调试或多用户测试）。

EXE 的文件属性中包含产品名「青简 · ReadHistory」、版本 `0.2.1.0`、版权与 MIT 许可说明。

## 代碼簽名 / Code signing

签名证书**不是运行前提**。它只影响 Windows SmartScreen 是否显示“未知发布者”提示，不能修复 Python 启动、路径、权限或杀毒软件拦截。

- 自签名证书（`New-SelfSignedCertificate`）只能让本机或已导入根证书的机器信任，对公众 SmartScreen 没有帮助。
- 要消除公众机器的 SmartScreen 提示，需要购买 OV 或 EV 代码签名证书，然后：
  ```powershell
  signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p password `
    dist\Qingjian_ReadHistory\Qingjian_ReadHistory.exe
  ```
- 没有证书时，发布页应提供 SHA256，并说明「更多信息 → 仍要运行」。

如果用户双击 EXE 后 Windows 直接拦截，**不会产生任何日志**，因为进程没有启动；这时应先确认 SmartScreen，再试 `備用啟動.bat`（直接调用 `runtime\python\pythonw.exe`，绕过启动器 EXE）。

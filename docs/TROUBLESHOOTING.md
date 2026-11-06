# 啟動失敗排查 / Troubleshooting

## 先看这里：可携版不会自动删除日志

可携版的日志固定在程序目录：

```
logs\launcher.log   启动器做了什么、错误异常
logs\server.log     Python 服务、OCR、HTTP 报错
```

它们**不会被程序删除**。如果启动失败，程序会弹出一个窗口，里面包含异常全文和 `server.log` 最后 30 行，可以点「複製錯誤」或「打開日誌文件夾」。

如果连弹窗都没有，说明 EXE 在进入程序之前就被 Windows 拦住了，见下面第 1 节。

## 1. Windows SmartScreen /「来自其他计算机」标记

未签名 EXE 第一次运行可能显示「Windows 已保护你的电脑」。

- 点「更多信息」→「仍要运行」。
- 如果 ZIP 的属性里有「解除封鎖」勾选框，**先勾选再解压**。否则 Windows 会把「来自其他计算机」标记传给解压出来的 `python.exe`、DLL，导致子进程被拦截。
- 命令行为整个目录解除锁定：
  ```powershell
  Get-ChildItem "D:\QingJian" -Recurse | Unblock-File
  ```

**代码签名证书不是运行前提。** 它只影响 SmartScreen 是否显示「未知发布者」，不能修复 Python 启动、路径、权限或杀毒软件拦截。自签名证书对公众机器也没有 SmartScreen 效果；要消除提示需要 OV/EV 代码签名证书。详见 `PACKAGING.md`。

## 2. 用 `診斷.bat` 取得真实错误

双击程序目录里的 `診斷.bat`。它会：

- 设置 `READHISTORY_HOME` 到程序目录；
- 用 `runtime\python\python.exe` 直接运行 `run.py --port 8799`；
- 保留控制台窗口，显示 Python traceback。

把窗口里的文字或 `logs\` 两个日志发出来即可定位。

## 3. 常见原因

| 现象 | 原因 | 处理 |
|---|---|---|
| 双击没有任何反应，也没有 logs | SmartScreen/杀毒软件在进程启动前拦截 | 解除封鎖、允许运行，或试 `備用啟動.bat` |
| 提示「找不到可攜版運行組件」 | 只复制了 EXE，没有带 `runtime` | 把整个文件夹一起解压/移动 |
| `pythonw.exe` 启动后立即退出 | 杀毒软件隔离了 `runtime\python` 或 `.ocrdeps` | 查看杀毒隔离区，恢复并加白名单 |
| 卡在「正在啟動閱讀服務」 | 端口被占用，或 Python 启动慢 | 关闭旧的青简/Python 进程；查看 `server.log` |
| 端口 8765 被别的软件占用 | 启动器会自动改用 8766–8799，无需处理 | 看 `logs\launcher.log` 的「服務就緒」URL |
| 浏览器没弹出但服务已就绪 | 默认浏览器关联异常 | 手动打开日志里的 `http://127.0.0.1:端口/` |

## 3.5 内置窗口 / WebView2

新版默认在程序自己的窗口里打开阅读界面，不再启动外部 Edge 标签页。这个窗口使用 Windows 的 **WebView2 Runtime**：

- Windows 11 默认已安装；Windows 10 如果缺失，可安装 “Microsoft Edge WebView2 Evergreen Runtime”。
- 如果初始化失败，窗口内会显示错误，并提供「重試」和「在瀏覽器中打開」；托盘菜单也有「在瀏覽器中打開」。
- 如果 Edge 浏览器本身卡死，但 `msedgewebview2.exe` 正常，内置窗口仍可工作；两者是不同的进程/用户数据目录。
- 若内置窗口也卡死，用 `備用啟動.bat` 走浏览器模式，或用 `診斷.bat` 看服务端是否正常。

## 4. 旁路启动器

如果 `Qingjian_ReadHistory.exe` 被拦，可以直接运行：

```
備用啟動.bat
```

它调用 `runtime\python\pythonw.exe run.py --open`，不经过启动器 EXE。若这个也失败，用 `診斷.bat` 看控制台错误。

## 5. 旧单文件版

旧式 `Qingjian_ReadHistory-single-0.2.0.exe` 会把约 500 MB 组件解包到 `%LOCALAPPDATA%\QingJian\app`。首次运行较慢，也更容易被杀毒软件、磁盘空间、长路径或 SmartScreen 打断。**推荐使用可携 ZIP 版**；它没有解包步骤。

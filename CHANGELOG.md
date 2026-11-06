# Changelog / 更新日志

All notable changes to this project will be documented in this file.

本文件记录青简 / ReadHistory 的重要变更。

## [0.2.2] — 2026-11-06

**整本导入的版面判断修复。**

- 修复从第 1 页导入整本《晋书》时，程序被封面/版权页/目录的 0°、270° 方向带偏，导致正文按错误方向识别的问题。
- 自动判断改为抽样正文页并加权投票：不再只看开头几页，会在书的前部与 10%/25%/50% 位置取多个样本，按文字量与置信度选择版式与方向。
- 新增逐页前置页分类：封面、版權頁、目錄自动识别并在导入时跳过；「前置頁」可选「自動略過 / 保留」。
- 对低置信度的封面、目录等页，自动尝试其他扫描方向并保留识别更好的一次。
- 导入范围超过 200 页时提示建议先识别 10–20 页，避免整本跑数小时。
- 版本号提升至 0.2.2。

## [0.2.1] — 2026-11-06

**设置与阅读体验更新。**

- 设置面板整体放大：标题 17px、标签 13px、说明 12px、输入框与分段按钮 12–14px，弹窗加宽至 820px。
- 新增「介面」设置：界面字号（小 / 標準 / 大）、减少动效；顶栏、侧栏、状态栏、面板与设置同步缩放，不改变阅读正文。
- 新增「閱讀」设置：行距、段距、正文宽度、竖排列距；均可在紧凑 / 標準 / 寬鬆之间切换。
- 新增「行為」设置：记住上次阅读、自动保存进度、OCR 默认模式（快速 / 精校）。
- 新增「恢復預設」按钮，只重置界面与阅读偏好，不影响批注、导入的 PDF 与 OCR 数据。
- 设置持久化到本机 SQLite；旧版设置自动兼容。
- 版本号提升至 0.2.1。

## [0.2.0] — 2026-11-06

### 中文

**面向普通读者的 Windows 可携版与 PDF 导入版。**

- Windows 发布改为**小体积 EXE + `runtime` 运行目录**：`Qingjian_ReadHistory.exe` 约 40 KB，Python 3.12、PDFium、RapidOCR、繁体中文模型与 Noto / 霞鹜文楷字体放在旁边；压缩包约 235 MB，不需要安装 Python，也不再在首次启动解包 300 多 MB 到用户目录。
- 自带窗口：阅读界面在程序自己的 WebView2 窗口中打开，不再依赖外部 Microsoft Edge 标签页；默认最大化并做高 DPI 适配。WebView2 初始化失败时窗口内提供「重試 / 在瀏覽器中打開」，托盘菜单也保留浏览器入口。
- 启动日志改为写在程序目录的 `logs/launcher.log`、`logs/server.log`，不会自动删除；启动失败弹窗可复制异常与 `server.log` 末尾，另附 `診斷.bat` 直接显示控制台错误。
- 删除运行组件中未使用的 86 MB `ch_PP-OCRv4_rec_server` 模型与 29 MB OpenCV ffmpeg DLL，并保留精校 OCR 所需的 `ch_doc_server` 模型；未压缩运行目录从约 537 MB 降到约 422 MB，压缩包约 235 MB。
- 保留旧式单文件构建脚本作为兼容选项，但默认下载改为可携 ZIP。
- 新增「导入 PDF」向导：选择文件、读取首頁预览、填写书名/撰者/卷名、选择页码范围、后台 OCR 入库。
- 新增版式自动识别：在 0°/90°/180°/270° 与横排/竖排两条管线之间试读比较，自动判断扫描方向与竖排/横排；识别不准时可手动指定版式。
- 新增竖排古籍 OCR：按直行切分、字格拟合、单字裁切后横向重排识别，保留右起阅读顺序；横排书继续整行识别。
- 新增 OCR 进度与增量阅读：导入后后台逐页识别，已识别的段落自动出现在阅读器中；重跑同一页范围会替换该范围正文。
- 移除现代汉语今译：删除今译面板、选段翻译、OpenAI 兼容客户端、API Key 设置、`reader/translate.py` 与样章译文数据；应用不再连接任何模型接口。
- 新增字体切换：宋体（Noto Serif SC）、黑体（Noto Sans SC）、楷体（霞鹜文楷 LXGW WenKai，随包 OFL 字体）；西文优先 Times New Roman，缺失时回退到 Tinos / Liberation Serif。
- 界面改为更古朴的纸纹、朱砂、双线边框风格；重做设置、书库、导入、批注与 OCR 校对台。
- 新增 `reader/paths.py`，区分只读程序目录与可写数据目录；新增数据库迁移，兼容 0.1.0 的 `reader.db`。
- 新增 C# 启动器（可携版小 EXE 与旧式单文件版共用）、打包脚本、图标与 SHA256 输出。
- 新增 `docs/LICENSING.md`：说明内置 Python/OCR/字体的再分发边界；更新 `THIRD_PARTY_NOTICES.md` 与 `LICENSES/`。
- 修正《晋书》样章扫描页方向迁移问题：数据库中的旧 `orientation=0` 不再阻止自动纠偏。
- 版本号提升至 `0.2.0`。

**已知限制**

- 竖排 OCR 对双行小注、朱批、行草、严重残缺的刻本仍不稳定，识别结果需对照原影校对。
- 自动版式判断依赖正文页；封面、牌记、空白页可能误判，可换起始页或手动选版式。
- 启动器 EXE 未签名，首次运行可能出现 SmartScreen 提示。
- 导入大 PDF 的整本 OCR 可能耗时数小时；建议先选 10–20 页试读。

### English

**A portable Windows build and PDF-import release for general readers.**

- Windows release now uses a **small launcher EXE plus a `runtime` folder**: `Qingjian_ReadHistory.exe` is about 40 KB, while Python 3.12, PDFium, RapidOCR, the traditional-Chinese model, and Noto / LXGW WenKai fonts live beside it. The ZIP is about 235 MB; no Python installation and no 300 MB first-run unpacking.
- The reader now opens in the app's own embedded WebView2 window instead of an external Edge tab, maximized and DPI-aware. If WebView2 fails to initialize, the window offers retry/browser buttons and the tray keeps a browser entry.
- Startup logs now live under the program folder (`logs/launcher.log`, `logs/server.log`) and are never auto-deleted. A failure dialog shows copyable exception details plus the tail of `server.log`, and `診斷.bat` shows console errors directly.
- Removed the unused 86 MB `ch_PP-OCRv4_rec_server` model and 29 MB OpenCV ffmpeg DLL; the high-quality OCR path using `ch_doc_server` still works. Uncompressed runtime dropped from about 537 MB to 422 MB.
- The legacy single-file build script remains available as a compatibility option, but the default download is the portable ZIP.
- Added a PDF import wizard: pick a file, preview the first page, set title/author/chapter/page range, and OCR it into the library in the background.
- Added automatic layout detection: candidate rotations (0°/90°/180°/270°) are tried with both horizontal and vertical pipelines, and the best-scoring reading is chosen; users can override the layout manually.
- Added vertical-typesetting OCR: columns are detected from ink projections, character cells are fitted and cropped, then laid out horizontally for recognition while preserving right-to-left reading order.
- Added OCR progress and incremental reading: recognised paragraphs appear while the job runs; re-running a page range replaces that range.
- Removed modern-Chinese translation entirely: UI panel, selection translation, OpenAI-compatible client, API-key settings, `reader/translate.py`, and sample translations. The app no longer contacts any model endpoint.
- Added font switching: Song (Noto Serif SC), Hei (Noto Sans SC), Kai (bundled LXGW WenKai, OFL 1.1); Latin text prefers Times New Roman with Tinos / Liberation Serif fallbacks.
- Refreshed the UI with paper grain, cinnabar seals, and double-rule borders; rebuilt settings, library, import, annotation, and OCR proofreading screens.
- Added `reader/paths.py` to separate the read-only app directory from writable data, plus a database migration compatible with 0.1.0.
- Added the C# launcher, build script, icon, and SHA256 output.
- Added `docs/LICENSING.md` analysing redistribution of the embedded runtime and fonts; refreshed `THIRD_PARTY_NOTICES.md` and `LICENSES/`.
- Fixed the sample-book rotation migration so an old `orientation=0` no longer disables auto-correction.
- Bumped the version to `0.2.0`.

**Known limitations**

- Vertical OCR remains unreliable for double-column notes, handwritten marks, cursive, and badly damaged prints; proofread against the scan.
- Automatic layout detection depends on body-text pages; covers, title pages, and blanks may be misclassified. Change the start page or choose the layout manually.
- The launcher executable is unsigned, so SmartScreen may warn on first run.
- OCR-ing a whole large PDF can take hours; start with 10–20 pages.

## [0.1.0] — 2026-11-06

### 中文

**首个公开可运行版本。**

- 确定软件名：中文「青简」，英文「ReadHistory」，版本号 `0.1.0`。
- 完成本地 Web 阅读器：Python 标准库 HTTP 服务 + 原生 HTML/CSS/JS，无需前端构建。
- 竖排阅读：按列切分、右侧起读、向左横滚；支持横排一键切换。
- 提供纸色、月白、墨夜三套主题，以及字号调节。
- 建立《晋书》卷一〈帝纪第一 · 宣帝〉校对本：15 段正文、2 条校勘记、15 段现代汉语今译。
- 支持正文选择与高亮、划线、批注、复制；批注与阅读进度持久化到本地 SQLite。
- 支持脚注标记点击查看校勘记，右侧「校勘记」页签集中展示。
- 支持原扫描页对照，点击图片可全屏放大；页面可缓存到 `data/pages/`。
- 支持全文检索与结果跳转。
- 接入本地 OCR 管线：
  - 自动判断扫描页 90° 旋转并纠偏；
  - RapidOCR 繁体中文识别；
  - 快速模式与精校模式；
  - 去页眉、页码，按缩进与句读重排；
  - 提供「OCR 校对台」，可查看每页初稿、置信度并保存校样。
- 完成《晋书》PDF 第 49–52 页 OCR 样张，平均置信度约 85%。
- 接入 OpenAI 兼容今译接口，支持 DeepSeek / OpenAI 及自建兼容服务；Key 仅保存在本机。
- 提供二十四史书库入口，当前完整开放《晋书》一卷，其余作为后续导入位。
- 增加 MIT 许可证、双语更新日志、README、启动脚本和发布打包脚本。
- PDF 渲染改用 Apache/BSD 许可的 pypdfium2，避免将 AGPL 依赖引入 MIT 项目。
- 样章正文参校维基文库《晋书》卷001（CC BY-SA 4.0），古籍原文本身属于公有领域。

**已知限制**

- 当前只开放《晋书》卷一；其余二十三史尚未导入。
- OCR 初稿仍需逐页对照原影校对；双行小注、朱批、异体字识别有限。
- 跨段落选择暂不支持，会提示在同一段内选择。
- 今译质量取决于所配置的模型；未配置接口时只能阅读样章人工今译。

### English

**First public runnable release.**

- Established the product names: **青简** in Chinese and **ReadHistory** in English, version `0.1.0`.
- Shipped a local web reader: Python standard-library HTTP server + vanilla HTML/CSS/JS, with no frontend build step.
- Added vertical reading: text is paginated into columns, read from right to left and scrolled horizontally; horizontal mode is one click away.
- Added three themes (Paper, Moon, Ink) and adjustable font size.
- Added a proofread sample of *Jin Shu* (晉書), Volume 1, “Annals 1: Emperor Xuan”: 15 paragraphs, 2 textual notes, and 15 modern-Chinese translations.
- Added text selection, highlight, underline, notes, and copy; annotations and reading progress are stored locally in SQLite.
- Added clickable footnote markers with a textual-notes panel.
- Added side-by-side original scan view with full-screen zoom; pages are cached under `data/pages/`.
- Added full-text search and jump-to-result.
- Added a local OCR pipeline:
  - automatic detection and correction of 90° rotated scans;
  - RapidOCR traditional-Chinese recognition;
  - fast and high-quality modes;
  - header/page-number removal and paragraph reconstruction from indentation and punctuation;
  - an “OCR proofreading desk” showing per-page drafts, confidence, and editable proof text.
- Processed OCR samples for PDF pages 49–52 of the *Jin Shu* scan, with an average confidence of about 85%.
- Added an OpenAI-compatible translation endpoint for DeepSeek, OpenAI, and self-hosted compatible services; the key is stored only on the local machine.
- Added a Twenty-Four Histories library entry point. *Jin Shu* Volume 1 is available; the remaining histories are placeholders for future imports.
- Added the MIT license, this bilingual changelog, README, launcher scripts, and release packaging.
- Switched PDF rendering to Apache/BSD-licensed pypdfium2 to avoid introducing an AGPL dependency into an MIT project.
- The sample text was proofread against *Jin Shu* Volume 001 on Chinese Wikisource (CC BY-SA 4.0); the ancient text itself is in the public domain.

**Known limitations**

- Only *Jin Shu* Volume 1 is available; the other twenty-three histories have not been imported yet.
- OCR drafts still require page-by-page proofreading against the scan; double-column notes, handwritten annotations, and variant characters remain difficult.
- Cross-paragraph selection is not supported; selections must stay within one paragraph.
- Translation quality depends on the configured model. Without an API key, only the proofread sample translations are available.

[0.1.0]: https://github.com/ldk689/ReadHistory/releases/tag/v0.1.0

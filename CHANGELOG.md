# Changelog / 更新日志

All notable changes to this project will be documented in this file.

本文件记录青简 / ReadHistory 的重要变更。

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

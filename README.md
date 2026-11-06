# 青简 · 二十四史阅读器

**青简（ReadHistory）** 是一个把扫描版古籍 PDF 变成可检索、可批注、可今译的竖排 / 横排阅读器的本地应用。

当前版本 **0.1.0**，以 **《晋书》中华书局 1974 年点校本** 的 PDF 为底本，开放 **卷一〈帝纪第一 · 宣帝〉** 作为完整样章；OCR、原影对照、脚注、划线、批注、全文检索与今译接口均已打通。

![青简阅读器](docs/screenshot-vertical.png)

横排模式：

![青简横排](docs/screenshot-horizontal.png)

## 已实现

- **扫描页自动纠偏**：识别到 PDF 正文被整体旋转 90° 时，先旋正再 OCR。
- **本地 OCR**：RapidOCR + 繁体中文识别模型；快速模式约 3–6 秒/页，精校模式更慢但更适合古籍字头。
- **重排阅读**：同一份正文可在 **竖排（右起横滚）** 与 **横排** 间切换，字号、主题（纸色 / 月白 / 墨夜）可调。
- **原影对照**：右侧打开对应扫描页，可点击放大。
- **脚注 / 校勘记**：正文中的 `〔一〕` 标记可点，悬停卡片显示校勘记原文；右侧「校勘记」页签列出全部条目。
- **选择与批注**：选中文字后可高亮、划线、写批注、复制、翻译选段；批注保存在本机 SQLite。
- **今译**：样章今译已人工校订；其余段落可在设置中接入 DeepSeek / OpenAI 兼容接口，按段生成并缓存。
- **全文检索**：按人名、地名或句子检索，跳转到对应段落。
- **OCR 校对台**：查看每页机器识别初稿、置信度，直接修改并保存校样。
- **二十四史书库**：预置二十四史书目；当前仅《晋书》可读，其余作为后续导入位。

## 快速开始

### 方式一：Windows 一键

首次使用，双击 `setup.bat` 安装依赖（会创建 `.venv`，首次约需下载 300–500 MB）；安装完成后双击 `start.bat`。

```powershell
.\setup.bat
.\start.bat
```

当前开发工作区已经装好离线依赖，可以直接运行 `start.bat`。脚本会启动本地服务并打开 <http://127.0.0.1:8765>。数据全部在 `data/` 下。

首次使用原影 / OCR 前，把你自己的《晋书》PDF 放到：

```
data/inbox/jinshu.pdf
```

或设置环境变量：

```powershell
$env:READHISTORY_PDF = "D:\books\jinshu.pdf"
```

PDF 不会被提交到 Git，也不会上传。没有 PDF 时，样章正文、批注与今译仍可阅读，只是原影和重新 OCR 不可用。

### 方式二：手动 Python 环境

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py --open
```

要求 Python 3.11 / 3.12。首次 OCR 时 RapidOCR 会自动下载繁体中文模型（约 100 MB）。

## 使用说明

1. 启动后默认进入《晋书》卷一。
2. 顶部「竖排 / 横排」切换版式；`A− / A＋` 调整字号。
3. 正文中拖动选择文字，会浮出工具条：
   - **高亮**：浅赭色底；
   - **划线**：朱砂色下划线；
   - **批注**：填写考证、疑问或对读线索；
   - **今译**：只翻译选中的一段；
   - **复制**：复制原文。
4. 点击正文里的 `〔一〕` 可查看该条校勘记；右侧「校勘记」列出全部。
5. 顶栏「原影」打开当前段对应的扫描页；点击图片可全屏放大。
6. 顶栏「今译」右侧面板显示当前段今译；没有今译时可点「生成此段今译」。
7. 设置中可配置今译接口、运行 OCR、查看识别初稿。

## 今译接口

支持任何 OpenAI 兼容的 `/chat/completions` 接口：

| 配置 | DeepSeek 示例 | OpenAI 示例 |
|---|---|---|
| Base URL | `https://api.deepseek.com` | `https://api.openai.com/v1` |
| 模型 | `deepseek-chat` | `gpt-4o-mini` |
| API Key | `sk-...` | `sk-...` |

Key 只写入本机 `data/reader.db` 的 `settings` 表，不上传、不写日志。也可以改用环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
```

未配置 Key 时，样章的人工校订今译仍可正常阅读；点击生成会提示去设置。

## OCR 说明

这本 PDF 的正文页在扫描时整体旋转了 90°。程序会：

1. 用墨迹投影判断文字行方向；
2. 旋正页面；
3. 用 RapidOCR 检测行框、识别繁体中文；
4. 去掉页眉、页码，按缩进与句读重排为段落；
5. 把每页识别结果写入 `data/reader.db` 的 `ocr_pages` 表。

两种模式：

- **快速**：`chinese_cht_mobile`，约 3–6 秒/页，适合先跑通全卷；
- **精校**：`ch_doc_server`，单页可能 2–4 分钟，对繁体、异体字更稳。

识别结果不是最终正文。古籍 OCR 对「曰 / 日」「詔 / 韶」「錮 / 鋼」「戌 / 戍」等字形极易出错，必须在「OCR 校对台」逐页对照原影校改。

样章正文以维基文库《晋书》卷001 为参校本做了人工校对；这一层校对与 OCR 管线是分开的，便于后续导入其他卷时保留「机器初稿 → 人工校样 → 定本」的状态。

## 添加其他史书（当前版本的扩展方式）

当前 UI 只接入了《晋书》的数据种子。数据模型与 OCR 管线是通用的，增加一部史书需要：

1. 在 `data/seed/` 新增书目 JSON，或直接向 `books` / `chapters` / `paragraphs` 表写入数据；
2. 在 `web/app.js` 的 `HISTORIES` 中把对应书目标记为可用；
3. 用 OCR 校对台逐页校对，或把已校对的正文按 `paragraphs` 结构导入。

后续版本会把「选择 PDF → 按卷切分 → OCR → 校对 → 入库」做成完整的导入向导。

## 目录

```
run.py                  启动入口
setup.bat / start.bat   Windows 安装与启动
LICENSE                 MIT 许可证
CHANGELOG.md            中英双语更新日志
VERSION                 0.1.0
THIRD_PARTY_NOTICES.md  第三方组件与文本来源
reader/
  server.py             HTTP 服务与 JSON API
  db.py                 SQLite 数据层与种子导入
  ocr.py                旋转检测、RapidOCR、重排、原影缓存
  translate.py          OpenAI 兼容今译接口
web/
  index.html            阅读器页面
  styles.css            纸色 / 月白 / 墨夜主题与竖排排版
  app.js                阅读、选择、批注、脚注、检索、设置
data/
  seed/jinshu_vol1.json 《晋书》卷一校对本与今译
  inbox/                放置自己的 PDF（不提交）
  reader.db             SQLite（批注、进度、OCR、设置）
  pages/                原影缓存（按需生成）
  assets/               原创封面
tools/
  ocr2_probe.py         RapidOCR 2.x 命令行探针
  ocr_probe.py          RapidOCR 1.x 命令行探针
  render_probe.py       PDF 渲染探针
  make_cover.py         生成原创演示封面
```

## 许可证

本项目代码以 [MIT License](LICENSE) 开源。

第三方组件、样章文本来源与许可证说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 隐私与版权

- PDF、扫描图、OCR 文本、批注、阅读进度都在本机；应用不包含远程统计或上传逻辑。
- 只有你主动点击「生成今译 / 翻译选段」时，所选文字才会发送到你配置的模型接口。
- 原扫描件版权归原出版者；本项目只读取你本机已有的 PDF，请确保在合法范围内使用。
- 样章正文参校维基文库《晋书》卷001（CC BY-SA 4.0），仅用于校对对照；古籍原文本身进入公有领域。

## English overview

**QingJian (ReadHistory)** is a local-first reader for the *Twenty-Four Histories* (二十四史). It turns scanned, rotated PDF pages into reflowable traditional Chinese text, supports vertical and horizontal reading, clickable textual notes, text selection with highlights/underlines/annotations, full-text search, and modern-Chinese translation through an optional OpenAI-compatible endpoint.

Version 0.1.0 ships a complete, proofread sample of *Jin Shu* (晉書), Volume 1, “Annals 1: Emperor Xuan”, plus an OCR proofreading workflow for PDF pages 49–52. The source code is MIT-licensed; third-party notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

```powershell
.\setup.bat   # first run: create .venv and install dependencies
.\start.bat   # start at http://127.0.0.1:8765
```

Put your own `jinshu.pdf` under `data/inbox/` (or set `READHISTORY_PDF`). PDFs, OCR text, annotations, and API keys stay on the local machine.

## 已知限制

- 当前只开放《晋书》卷一；其余二十三史尚未导入。
- OCR 快速模式对古籍异体字、双行小注、朱批的识别有限；精校模式更慢。
- 竖排采用按列切分的阅读方式；跨段选择会提示「请在同一段内选择」。
- 今译质量取决于所配置的模型；样章今译经过人工校订，其余为模型生成。

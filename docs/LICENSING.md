# 内置运行环境与再分发的许可分析

本文回答一个具体问题：**把 Python、OCR、图像库和字体一起打进 `Qingjian_ReadHistory.exe`，是否违反开源协议？**

结论先说：**可以，而且本项目的 0.2.0 Windows 发行版已经这样做。** 默认的可携版把运行环境放在 `runtime/`，旧式单文件版则附加在 EXE 尾部；两种形式都必须保留每个组件的版权声明与许可证文本，不冒充原作者，不把专有字体或扫描件一起打包。下面逐项说明。

> 本文是一份工程合规说明，不是正式法律意见。若用于商业发行或大规模分发，建议让律师复核。

## 1. 本项目自身的 MIT 许可证

`LICENSE` 是 MIT。MIT 允许任何人：

- 使用、复制、修改、合并、发布、再许可、销售本软件的副本；
- 以源代码或二进制形式分发；
- 把本软件与其他组件打包。

唯一条件是：在副本或实质性部分中保留版权声明和 MIT 许可文本。把程序编译成 EXE 属于“二进制形式分发”，只要 EXE 或其附带文件中能看到 `LICENSE`（本项目放在安装目录与仓库中），就满足 MIT。

MIT 不要求你公开修改后的源代码，也不要求下游必须开源。因此“闭源打包”本身不违反 MIT；本项目仍然在 GitHub 提供完整源码。

## 2. Python 运行时

Python 使用 PSF License 2.0。该许可证允许再分发 Python（包括二进制形式），要求保留版权声明与许可证文本，并遵守 PSF 的商标规则（不能暗示 Python 官方认可本软件）。

本项目的做法：

- 在 EXE 载荷中附带完整的 `LICENSES/Python-3.12.txt`；
- 不修改 Python 解释器本身；
- 不使用 “Python” 作为产品名或暗示官方背书；
- 安装目录的 `使用說明.txt` 说明这是内置运行时。

这属于常见的“应用程序嵌入 Python”场景，合规。

## 3. 第三方 Python 包

| 组件 | 许可证 | 再分发时通常需要做什么 |
|---|---|---|
| pypdfium2 / PDFium | Apache-2.0 / BSD-3-Clause | 保留许可证与 NOTICE；不得用其商标背书 |
| RapidOCR | Apache-2.0 | 保留 Apache-2.0 文本与版权声明 |
| ONNX Runtime | MIT | 保留 MIT 文本与版权声明 |
| OpenCV | Apache-2.0 | 保留 Apache-2.0 文本与第三方声明 |
| NumPy | BSD-3-Clause | 保留版权声明、条件与免责声明 |
| Pillow | HPND | 保留 HPND 文本 |
| Requests | Apache-2.0 | 保留许可证与 NOTICE |
| OmegaConf | BSD-3-Clause | 保留版权声明 |
| PyYAML | MIT | 保留版权声明 |
| colorlog | MIT | 保留版权声明 |
| Shapely / GEOS | BSD-3-Clause / LGPL-2.1（GEOS） | 保留声明；动态链接的 GEOS 按其许可使用 |
| pyclipper | MIT | 保留版权声明 |
| tqdm | MPL-2.0 / MIT | 保留许可证 |

这些许可证都属于宽松型（permissive）或弱 copyleft，**允许把库嵌进一个更大的应用程序并以你自己的许可证发布**，只要保留 notices。它们不会“传染”成要求你把青简的代码开源（MIT 本来也开源）。

Apache-2.0 的两个额外要求：

1. 分发时附上 Apache-2.0 许可证文本；
2. 如果原项目带 `NOTICE` 文件，要保留其中的归属声明（本项目在 `LICENSES/packages/` 中保留了 OpenCV、Requests 等的许可证与声明）。

本项目没有修改这些库的源代码，只是原样打包其 wheel 中的二进制与 Python 文件。

## 4. 字体：这里最容易被误解

### 可以打包的

- **Noto Serif SC / Noto Sans SC**：SIL Open Font License 1.1。OFL 明确允许字体“bundled, embedded, redistributed and/or sold with any software”，包括随商业软件分发。要求是：
  - 保留版权声明与 OFL 文本；
  - 不改用 Reserved Font Name 发布修改版；
  - 字体本身不能单独售卖。

  本项目原样附带这两个字体，并在 `LICENSES/OFL-1.1.txt`、`LICENSES/FONTS.md` 与 `web/fonts/OFL.txt` 中保留声明。合规。

- **霞鹜文楷（LXGW WenKai）**：同样是 OFL 1.1。本项目把 `LXGWWenKai-Regular.ttf` 原样打进 EXE（`web/fonts/`），并在 `LICENSES/LXGW-WenKai-OFL.txt` 中保留 OFL 文本与版权声明。OFL 明确允许随软件打包、嵌入与再分发，因此这样做合规。

### 不能打包的

- **Times New Roman**：Monotype 的商业字体，Windows 自带不等于可以随第三方软件再分发。把它复制进 EXE 会侵犯版权。
- **系统楷体 KaiTi / STKaiti，以及宋体 SimSun、微软雅黑**：Windows 系统字体，许可只允许在 Windows 上按系统方式使用，不允许随应用再分发。注意这与开源的霞鹜文楷是两回事。

所以本项目的处理是：

- 宋体、黑体：使用可再分发的 Noto Serif SC / Noto Sans SC；
- 楷体：使用随包分发的 LXGW WenKai（OFL 1.1），并保留其 OFL 文本；不再需要系统楷体；
- 西文：优先 `local("Times New Roman")`，没有时回退到 Tinos / Liberation Serif / 内置宋体；**不分发 Times New Roman 字体文件**。

如果将来想换用其他楷体，只要该字体的许可允许再分发（OFL 等），把 TTF 放进 `web/fonts/` 并在 CSS 里加 `@font-face`、同时保留许可证文本即可。

### “开源非商用”这个说法

OFL 允许商业使用。把字体标成“非商用”反而不符合 OFL 对“开源字体”的定义。若你看到某个字体写着“仅供非商业使用”，它就不是 OSI 意义上的开源字体，不能按 OFL 处理。本项目选用的 Noto 字体是允许商用的 OFL 字体。

## 5. 扫描件、古籍文本与样章

- **扫描 PDF、书影、出版社封面**：版权归原出版者。本项目不打包这些文件；用户导入自己合法持有的 PDF，程序只在本机读取。
- **古籍原文**：进入公有领域。
- **样章的标点、分段、校勘记**：参校维基文库《晉書》卷001，该部分以 **CC BY-SA 4.0** 发布。它和 MIT 代码是“不同作品放在同一发行包中”，可以共存，但：
  - 必须保留署名与 CC BY-SA 4.0 许可；
  - 对样章文本的修改/演绎仍需按 CC BY-SA 4.0 共享；
  - 不能把 CC BY-SA 文本说成 MIT。

  本项目把 `data/seed/jinshu_vol1.json` 单独标注为 CC BY-SA 4.0，并在 `data/seed/NOTICE.md` 与 `THIRD_PARTY_NOTICES.md` 中说明。EXE 是“代码 + 数据”的集合包，这样处理是常见的。

  如果你希望整个发行包只有 MIT，可以删掉样章 JSON，或换用你自己标点、自己撰写的公有领域文本。

- **今译**：0.2.0 已整体移除。没有模型权重、没有 API Key、没有远程调用，也就没有模型服务条款的合规问题。

## 6. 单文件 EXE 的特殊问题

1. **载荷可见性**：EXE 尾部的 ZIP 没有加密。这既是技术选择，也避免“技术保护措施”与 GPL/许可证兼容性的讨论。用户可以用解压工具取出 Python 与库文件。
2. **许可证文本必须随包**：本项目在 `LICENSES/` 中放 Python、OFL、Apache、MIT、BSD、HPND 等文本；安装目录的 `使用說明.txt` 指向它们。仅把许可证放在 GitHub 仓库是不够的，因为用户拿到的是 EXE。
3. **不得移除版权头**：打包脚本原样复制依赖，未修改源文件；没有删除 `dist-info` 中的版权信息。
4. **商标**：产品名“青简 / ReadHistory”不使用 Python、RapidOCR、PDFium、Google、Monotype 等名称背书；描述中只作事实性说明。
5. **代码签名**：未签名会触发 SmartScreen，这是信任问题，不是许可证问题。

## 7. 一句话回答

**把运行环境内置进 EXE 不违反 MIT，也不违反 Python、PDFium、RapidOCR、ONNX Runtime、OpenCV、NumPy、Pillow 等组件的许可证**，只要随包保留版权声明与许可证文本。**不能内置的是 Times New Roman、系统楷体等专有字体，以及扫描 PDF / 出版社封面 / 未授权文本**；本项目已经用开源 Noto 字体、系统字体引用和不打包扫描件的方式规避了这些风险。

# 第三方组件与许可证 / Third-Party Notices

青简 / ReadHistory 的源代码以 **MIT License** 发布。Windows 发行版还会分发 Python 运行时、OCR 组件、图像库与开源字体，它们分别适用自己的许可证。每一份发行包都在 `LICENSES/` 目录中附带对应许可证全文。

The source code of QingJian / ReadHistory is released under the **MIT License**. The Windows build also redistributes a Python runtime, OCR components, imaging libraries, and open-source fonts, each under its own license. Every release carries the corresponding license texts in `LICENSES/`.

## 内置运行时 / Bundled runtime

| Component | Version (build) | License | License file |
|---|---|---|---|
| Python | 3.12.14 | PSF License 2.0 | `LICENSES/Python-3.12.txt` |
| pypdfium2 / PDFium | 5.14.0 | Apache-2.0 / BSD-3-Clause | `LICENSES/Apache-2.0.txt`, `LICENSES/BSD-3-Clause-NumPy.txt`, `LICENSES/README.md` |
| RapidOCR | 2.1.0 | Apache-2.0 | `LICENSES/Apache-2.0.txt` |
| ONNX Runtime | 1.31.1 | MIT | `LICENSES/packages/onnxruntime-LICENSE.txt` |
| OpenCV | 5.0.0 | Apache-2.0 | `LICENSES/packages/opencv-LICENSE.txt` |
| NumPy | 2.3.5 | BSD-3-Clause | `LICENSES/BSD-3-Clause-NumPy.txt` |
| Pillow | 12.3.0 | HPND | `LICENSES/HPND-Pillow.txt` |
| Requests | 2.34.2 | Apache-2.0 | `LICENSES/packages/requests-LICENSE.txt` |
| OmegaConf | 2.4.0 | BSD-3-Clause | `LICENSES/packages/omegaconf-LICENSE.txt` |
| PyYAML | 6.0.3 | MIT | `LICENSES/packages/pyyaml-LICENSE.txt` |
| colorlog | 6.12.0 | MIT | `LICENSES/packages/colorlog-LICENSE.txt` |
| Shapely | 2.2.0 | BSD-3-Clause | `LICENSES/packages/shapely-LICENSE.txt` |
| pyclipper | 1.4.0 | MIT | `LICENSES/packages/pyclipper-LICENSE.txt` |
| tqdm | 4.70.1 | MPL-2.0 / MIT | `LICENSES/packages/tqdm-LICENSE.txt` |
| Protobuf runtime | 7.36.2 | BSD-3-Clause | upstream package metadata |
| FlatBuffers | 25.12.19 | Apache-2.0 | upstream package metadata |
| Microsoft WebView2 SDK | 1.0.4314.35 | BSD-3-Clause (Microsoft) | `LICENSES/WebView2-SDK-LICENSE.txt` |

The WebView2 **Runtime** itself is a Windows component and is not bundled; the release only ships the small SDK assemblies (`Microsoft.Web.WebView2.*.dll`, `WebView2Loader.dll`) needed to host the embedded window. If the runtime is missing, the launcher falls back to the default browser.

The Windows launcher (`tools/launcher/QingJianLauncher.cs`) is original code of this project, compiled with the .NET Framework compiler. It does **not** include PyInstaller or any GPL-licensed packer. The payload is a plain ZIP appended to the executable; it is not encrypted or DRM-protected.

Windows 启动器是本项目原创代码，使用 .NET Framework 编译器编译；**没有** 使用 PyInstaller 或任何 GPL 打包器。尾部载荷是普通 ZIP，未加密、未做 DRM。

## 字体 / Fonts

| Font | License | Bundled? |
|---|---|---|
| Noto Serif SC | SIL OFL 1.1 | Yes, `web/fonts/NotoSerifSC-VF.ttf` |
| Noto Sans SC | SIL OFL 1.1 | Yes, `web/fonts/NotoSansSC-VF.ttf` |
| LXGW WenKai / 霞鹜文楷 | SIL OFL 1.1 | Yes, `web/fonts/LXGWWenKai-Regular.ttf` |
| Times New Roman | Monotype proprietary | No; loaded from the local system if installed |
| KaiTi / STKaiti / Kaiti SC | Microsoft / Apple proprietary | No; loaded from the local system if installed |

See `LICENSES/OFL-1.1.txt`, `LICENSES/LXGW-WenKai-OFL.txt`, and `LICENSES/FONTS.md`. The bundled Noto and LXGW WenKai files are unmodified; the reserved font names are not used for modified versions.

## 样章文本 / Sample text

The ancient text of *Jin Shu* (晉書) is in the public domain, but this project's punctuation, paragraph division, and textual notes were checked against the Chinese Wikisource edition:

- 《晉書》卷001, Chinese Wikisource: <https://zh.wikisource.org/wiki/晉書/卷001>
- License: CC BY-SA 4.0, <https://creativecommons.org/licenses/by-sa/4.0/>

The file `data/seed/jinshu_vol1.json` is therefore distributed under **CC BY-SA 4.0**, separately from the MIT-licensed code. Its attribution and license notice are also stored in `data/seed/NOTICE.md`.

古籍原文属于公有领域；样章的标点、分段与校勘记参校维基文库《晉書》卷001，该数据文件以 **CC BY-SA 4.0** 单独发布，代码仍为 MIT。若再分发本程序，请保留 `data/seed/NOTICE.md` 与本说明。

## 扫描件、封面与 PDF / Scans and PDFs

The original PDF scans, page images, and scanned book covers are **not** included in this repository or in the executable. They remain the property of their respective rights holders. The demo cover `data/assets/cover-jinshu.jpg` is an original graphic generated for this project.

原始 PDF、扫描页和扫描版封面**不包含**在本仓库或 EXE 中，版权归各自权利人所有。演示封面为本项目生成的原创图形。

## 已移除的今译接口 / Removed translation endpoint

Version 0.2.0 removes the modern-Chinese translation feature, the `translate.py` module, the OpenAI-compatible client, and the API-key settings. The application no longer sends any selected text to a model endpoint. No DeepSeek, OpenAI, or other model weights are bundled.

0.2.0 已移除现代汉语今译、`translate.py`、OpenAI 兼容客户端与 API Key 设置。程序不再把选中的文字发送给任何模型接口，也不包含任何模型权重。

## 不在本项目分发范围内的内容 / Not distributed

- Times New Roman, KaiTi, SimSun, Microsoft YaHei and other proprietary system fonts.
- The scanned PDF, page scans, or publisher cover of any edition.
- DeepSeek / OpenAI / other model weights or endpoints.
- Any third-party book text that is not public domain or compatibly licensed.

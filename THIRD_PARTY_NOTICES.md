# Third-Party Notices / 第三方组件说明

青简 / ReadHistory 的源代码以 MIT License 发布。运行时依赖、样章校对文本与字体等第三方内容适用各自的许可证。

The source code of QingJian / ReadHistory is released under the MIT License. Runtime dependencies, proofread sample text, and fonts are covered by their own licenses.

## Runtime dependencies

| Component | License | Project |
|---|---|---|
| pypdfium2 / PDFium | Apache-2.0 / BSD-3-Clause | https://github.com/pypdfium2-team/pypdfium2 |
| RapidOCR | Apache-2.0 | https://github.com/RapidAI/RapidOCR |
| ONNX Runtime | MIT | https://github.com/microsoft/onnxruntime |
| OpenCV | Apache-2.0 | https://github.com/opencv/opencv |
| NumPy | BSD-3-Clause | https://github.com/numpy/numpy |
| Pillow | HPND | https://github.com/python-pillow/Pillow |
| PyYAML | MIT | https://github.com/yaml/pyyaml |
| OmegaConf | BSD-3-Clause | https://github.com/omry/omegaconf |
| Requests | Apache-2.0 | https://github.com/psf/requests |
| colorlog | MIT | https://github.com/borntyping/python-colorlog |

The project previously used PyMuPDF for PDF rendering. Version 0.1.0 uses pypdfium2 instead; PyMuPDF is **not** included and is not required.

本项目早期使用 PyMuPDF 渲染 PDF。0.1.0 已改用 pypdfium2；发布包不包含 PyMuPDF，也不要求安装它。

## Sample text / 样章文本

The ancient text of *Jin Shu* (晉書) is in the public domain. The proofread punctuation, paragraph division, and textual notes of the sample chapter were checked against the Chinese Wikisource edition:

- 《晉書》卷001, Chinese Wikisource: https://zh.wikisource.org/wiki/晉書/卷001
- License: CC BY-SA 4.0, https://creativecommons.org/licenses/by-sa/4.0/

The sample modern-Chinese translations were produced for this project and are released with the project code under MIT.

古籍原文属于公有领域。样章的标点、分段与校勘记参校维基文库《晉書》卷001（CC BY-SA 4.0）。样章今译由本项目编写，随项目代码以 MIT 发布。

## PDF scans and fonts / 扫描件与字体

The original PDF scan, page images, and the scanned book cover are **not** included in the source release. They remain the property of their respective rights holders; users are responsible for using their own copies lawfully.

The generated demo cover is an original graphic. The application uses fonts already installed on the user's system; no font files are bundled.

原始 PDF、扫描页和扫描版封面不包含在源码发布包中，版权归各自权利人所有。演示封面为本项目生成的原创图形；程序使用系统已安装字体，不打包字体文件。

## AI translation endpoints / AI 今译接口

The application can send selected text to an OpenAI-compatible endpoint configured by the user. That endpoint is not part of this project and is governed by its own terms and privacy policy.

程序可将所选文本发送给用户自行配置的 OpenAI 兼容接口。该接口不属于本项目，适用其自身的服务条款与隐私政策。

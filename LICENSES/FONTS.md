# Bundled fonts / 內置字體

The Windows build bundles these font files under `web/fonts/`:

| File | Family | Copyright | License |
|---|---|---|---|
| `NotoSerifSC-VF.ttf` | Noto Serif SC | Copyright 2012–2025 Google LLC | SIL Open Font License 1.1 |
| `NotoSansSC-VF.ttf` | Noto Sans SC | Copyright 2012–2025 Google LLC | SIL Open Font License 1.1 |
| `LXGWWenKai-Regular.ttf` | LXGW WenKai / 霞鹜文楷 | Copyright 2021–2025 LXGW and contributors | SIL Open Font License 1.1 |

The full text of the license is in `OFL-1.1.txt`. The fonts are bundled
unmodified; the reserved font names are therefore left untouched.

`Noto` is a trademark of Google LLC. Use of the fonts does not imply
endorsement by Google.

## Fonts that are referenced, not bundled / 只引用、不再分發的字體

* **Times New Roman** is proprietary software owned by Monotype. It is
  **not** bundled or redistributed. The application only asks the browser
  to use a locally installed copy first, then falls back to metric-compatible
  open fonts if the user has them installed (`Tinos`, `Liberation Serif`).
* **KaiTi / STKaiti / Kaiti SC** are proprietary system fonts on some
  Windows and macOS installations. They are **not** bundled. The 楷體 option
  uses the bundled 霞鶩文楷 (`LXGW WenKai`, SIL OFL 1.1) first, then any
  locally installed copy, then the system 楷體, then Noto Serif SC. No
  proprietary Kai font file is redistributed.

  The bundled LXGW WenKai is unmodified. Its OFL text is in
  `LXGW-WenKai-OFL.txt`; the font's own copyright/license metadata is kept
  intact.

# Bundled fonts / 內置字體

The Windows build bundles these font files under `web/fonts/`:

| File | Family | Copyright | License |
|---|---|---|---|
| `NotoSerifSC-VF.ttf` | Noto Serif SC | Copyright 2012–2025 Google LLC | SIL Open Font License 1.1 |
| `NotoSansSC-VF.ttf` | Noto Sans SC | Copyright 2012–2025 Google LLC | SIL Open Font License 1.1 |
| `AR-PL-UKai-TW.ttf` | AR PL UKai TW | Copyright 1999 Arphic Technology Co., Ltd. | Arphic Public License |

The Noto fonts are bundled unmodified; the OFL text is in `OFL-1.1.txt`.
The AR PL UKai file was extracted from the Debian `fonts-arphic-ukai` package
(`ukai.ttc`, face index 2, the Traditional Chinese face) so it can be used as
a web font. See `AR-PL-UKai-NOTICE.txt` for the modification notice and the
location of the original source; the full license is in `ARPHICPL.txt`.

`Noto` is a trademark of Google LLC. Use of the fonts does not imply
endorsement by Google.

## Fonts that are referenced, not bundled / 只引用、不再分發的字體

* **Times New Roman** is proprietary software owned by Monotype. It is
  **not** bundled or redistributed. The application only asks the browser
  to use a locally installed copy first, then falls back to metric-compatible
  open fonts if the user has them installed (`Tinos`, `Liberation Serif`).
* **KaiTi / STKaiti / Kaiti SC** are proprietary system fonts on some
  Windows and macOS installations. They are **not** bundled. The 楷體 option
  uses the bundled AR PL UKai TW first, then any locally installed copy, then
  the system 楷體, then Noto Serif SC. No proprietary Kai font file is
  redistributed.

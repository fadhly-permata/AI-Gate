# Third-Party Notices

This file lists the third-party components that **aigate** embeds or depends on,
and the license terms under which each is made available by its own copyright
holder. The MIT license of aigate itself (see [`LICENSE`](LICENSE)) covers aigate's
own source and does **not** extend to the components below; each of them remains
under its own terms.

---

## 1. xterm.js — vendored in this repository

Files copied into this repository, under `src/frontend/static/vendor/xterm/`:

| File | Role |
| --- | --- |
| `xterm.js` | terminal emulator core |
| `xterm.css` | terminal styles |
| `xterm-addon-fit.js` | fit addon (resize to container) |

**License: MIT.**

The upstream copyright notice and complete MIT permission text are reproduced
verbatim below:

```
Copyright (c) 2017-2019, The xterm.js authors (https://github.com/xtermjs/xterm.js)
Copyright (c) 2014-2016, SourceLair Private Company (https://www.sourcelair.com)
Copyright (c) 2012-2013, Christopher Jeffrey (https://github.com/chjj/)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

**Version note.** The exact xterm.js version of the vendored files is **not
recorded anywhere in this repository**, so no version number is stated here; it is
left unspecified rather than guessed. The JavaScript files are minified and carry no
version marker, and no `package.json`, `LICENSE`, or other upstream metadata was
committed alongside them — only `xterm.css` retains an inline license header. The
license text above is taken from the upstream xterm.js repository (`master` branch),
so it reflects that project's notice, not necessarily a pinned release of the
vendored copies.

---

## 2. Font Awesome Free 6.5.1 — vendored in this repository

Files copied into this repository, under `src/frontend/static/vendor/font-awesome/`:

| File | Bytes | Role | License layer |
| --- | ---: | --- | --- |
| `LICENSE.txt` | 7,427 | upstream license text, redistributed with the copies | the notice itself |
| `css/all.min.css` | 102,641 | icon classes, codepoints, `@font-face` rules | Code / MIT |
| `webfonts/fa-brands-400.woff2` | 117,372 | brand glyph face | Fonts / OFL 1.1 |
| `webfonts/fa-regular-400.woff2` | 25,452 | regular (400) glyph face | Fonts / OFL 1.1 |
| `webfonts/fa-solid-900.woff2` | 156,496 | solid (900) glyph face | Fonts / OFL 1.1 |

Total: 5 files, 409,388 bytes. The copies in this working tree are **byte-identical**
to the ones already committed on branch `docs/wiki` (same five git blob hashes), so
this is a move of an existing local copy, not a fresh download.

**Not loaded from a CDN.** `src/frontend/static/index.html:43` is the only reference:

```html
<link rel="stylesheet" href="vendor/font-awesome/css/all.min.css?v=20260919" />
```

The former `<link>` to `cdnjs.cloudflare.com` is gone — a search for `cdnjs`,
`cdn.jsdelivr`, `unpkg` and `@import url("http` across `src/frontend/static/**`
returns **0 matches** (checked 2026-09-11). The browser fetches these assets from
aigate's own origin, so icons render with no network access and no third-party
request leaves the device.

**Version note (provenance debt, stated honestly).** The version string comes from
the header comment inside the vendored stylesheet itself — the only provenance
record this repository holds:

```
/*!
 * Font Awesome Free 6.5.1 by @fontawesome - https://fontawesome.com
 * License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License)
 * Copyright 2023 Fonticons, Inc.
 */
```

There is **no** download record, upstream release URL, manifest, or checksum for
these files anywhere in the repository, so "6.5.1" is reported as what upstream
stamped into the files, and the copies have **not** been verified byte-for-byte
against a Font Awesome Free 6.5.1 release artifact. No claim of official
provenance is made here. This is the same class of gap the xterm.js note in
section 1 records, and it is tracked alongside `WL.4` (version pinning) in
`documents/plan/wiki-backlog.md`.

Font Awesome Free's licensing is **layered**, and it is not accurate to describe
the whole package as "MIT licensed". As written in the redistributed
`LICENSE.txt` (line numbers below refer to that file):

| Component | License | What upstream says | Applies to in this vendored copy |
| --- | --- | --- | --- |
| Icons (SVG / JS) | Creative Commons Attribution 4.0 International (CC BY 4.0) | "applies to all icons packaged as SVG and JS file types" (13–17) | nothing ships — the vendored subset holds no `.svg`/`.js` icon file |
| Font files | SIL Open Font License 1.1 (OFL 1.1), with Reserved Font Name "Font Awesome" | "applies to all icons packaged as web and desktop font files" (21–24); "Copyright (c) 2023 Fonticons, Inc. … with Reserved Font Name: 'Font Awesome'" (26–27) | the three `.woff2` files |
| Code / CSS | MIT | "applies to all non-font and non-icon files"; "Copyright 2023 Fonticons, Inc." (121–126) | `css/all.min.css` |

The complete OFL 1.1 text ("SIL OPEN FONT LICENSE / Version 1.1 - 26 February
2007", lines 33–117: PREAMBLE, DEFINITIONS, PERMISSION & CONDITIONS 1–5,
TERMINATION, DISCLAIMER), the MIT text (128–143), the Attribution section
(147–156) and the Brand Icons trademark notice (160–165) are all present in
`LICENSE.txt`. They are **not reproduced** in this document because the file that
contains them is now distributed with the copies:
`src/frontend/static/vendor/font-awesome/LICENSE.txt`.

**Compliance points that changed with vendoring.**

- OFL condition 2 (lines 80–85) allows bundling and redistributing the fonts
  "provided that each copy contains the above copyright notice and this license",
  which may be "stand-alone text files, human-readable headers or …
  machine-readable metadata". Vendoring satisfies this by shipping `LICENSE.txt`
  beside the fonts, plus the header comment quoted above. Linking over a CDN used
  to leave this obligation with the visitor's browser instead.
- Attribution is stated as **required** by all three layers, and the concrete
  attribution aigate gives is this one (upstream's own wording, lines 149–152:
  "Attribution is required by MIT, SIL OFL, and CC BY licenses. Downloaded Font
  Awesome Free files already contain embedded comments with sufficient
  attribution, so you shouldn't need to do anything additional when using these
  files normally."):

  > Font Awesome Free 6.5.1 — icons, fonts and code by Fonticons, Inc.,
  > <https://fontawesome.com>, used under the Font Awesome Free license
  > (<https://fontawesome.com/license/free>): icons CC BY 4.0, fonts SIL OFL 1.1,
  > code MIT.

  Upstream additionally asks that the embedded comments stay put: "we ask that you
  do not actively work to remove them from files, especially code" (154–156). The
  attribution header in `css/all.min.css` is preserved unchanged.
- Brand glyphs are trademarks of their respective owners (160–165), with the
  permitted use being "to represent the company, product, or service to which they
  refer". The only brand glyph aigate renders is `fa-brands fa-github`
  (`index.html:155` and `index.html:1373`), on the link to aigate's own GitHub
  repository — i.e. it labels the service it points to and claims no endorsement
  either way.

**Fallbacks deliberately NOT vendored.** `all.min.css` declares 10 `@font-face`
blocks, each with a two-entry `src` chain — a `.woff2` first (10
`format("woff2")`) then a `.ttf` (10 `format("truetype")`) — naming four distinct
`.woff2` and four distinct `.ttf` files. Only three `.woff2` are vendored. Not
vendored, and not fetched at runtime either:

- `fa-solid-900.ttf`, `fa-regular-400.ttf`, `fa-brands-400.ttf`,
  `fa-v4compatibility.ttf` — `woff2` wins every `src` chain in the browsers
  aigate targets, so the truetype entries are never requested.
- `fa-v4compatibility.woff2` — it belongs to the legacy font family
  `"FontAwesome"`. That string occurs 4 times in `all.min.css`, all of them inside
  `@font-face` blocks and none in a rule outside them (the selectors that would
  apply the legacy family live in Font Awesome's `v4-shims.css`, which is not part
  of the vendored subset — audit note recorded at
  `src/frontend/tests/vendor_assets.test.js:124-131`), and no file under
  `src/frontend/static/` sets that family. An `@font-face` nobody selects is never
  downloaded.

Vendoring those five files would add dead weight to every copy of this repo, so
the choice is to leave them out and record it here rather than let the missing
files look like an oversight.

**This is guarded automatically, not by luck.** `src/frontend/tests/vendor_assets.test.js`
(7 tests) walks `src/frontend/static/**` and fails if any `<link>`, `<script>`,
media tag or CSS `url()` points at an absolute host again, asserts that
`index.html` loads the vendored stylesheet and no longer mentions
`cdnjs.cloudflare.com`, and asserts that every `@font-face` `woff2` the app can
actually request resolves to a real file on disk — so removing a vendored font, or
bringing a CDN back, breaks the test suite instead of silently killing icons
offline.

---

## 3. Python dependencies

Declared in `pyproject.toml` under `[project] → dependencies`:

- FastAPI
- Pydantic (v1)
- Uvicorn
- WebSockets
- SQLAlchemy
- ptyprocess
- httpx
- anyio
- pywinpty (Windows only — marker `sys_platform == 'win32'`)

**The license of each of these packages is stated on its respective PyPI project
page.** No individual license is asserted for them in this document, because they
were not each read and verified for it. Consult each package's PyPI page — and the
`LICENSE` file in its own upstream repository — for authoritative terms.

Project dependencies used only for development (test tooling, linters) are declared
separately under `[project.optional-dependencies] → dev` and are not distributed as
part of aigate.

---

## 4. Scope and maintenance of this notice

- This file records third-party components as they were found in the repository at
  the time of writing.
- Vendored or added third-party components should be listed here at the time they
  are introduced, together with their version and upstream license text, so that
  gaps like the xterm.js version note above are not repeated.

# Third-Party Notices

This file lists the third-party components that **aigate** embeds or depends on,
and the license terms under which each is made available by its own copyright
holder. The MIT license of aigate itself (see [`LICENSE`](LICENSE)) covers aigate's
own source and does **not** extend to the components below; each of them remains
under its own terms.

---

## 1. xterm.js — vendored in this repository

Files copied into this repository, under `src/frontend/static/vendor/xterm/`:

| File | Bytes | Role | sha256 (this repo) |
| --- | ---: | --- | --- |
| `xterm.js` | 283,404 | terminal emulator core | `f0aea0f75f48559013ae6643c2479dd737d26da42d5524e6d2b70915ae6523c7` |
| `xterm.css` | 5,383 | terminal styles | `832f3f2c603b43ad4351ff04970150cc7a873014276db126a6065c6dd81e4872` |
| `xterm-addon-fit.js` | 1,503 | fit addon (resize to container) | `10f3194c5f17c1786fb7d5db865c1ec8539b6736a318063fd38bdaaf7c46848f` |

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

**Version note (provenance, verified 2026-09-11).** The vendored copies are
identified as **`xterm@5.3.0`** (core + css) and **`xterm-addon-fit@0.8.0`** (addon).
This identification is based on **hash equality against the official npm release
artifacts, not on any version string inside the files** — the minified JavaScript
carries only a `version="6"` marker (a protocol/version number, not a package release
number), and no `package.json` or upstream `LICENSE` was committed alongside the
copies. Each vendored file is byte-for-byte identical to a file in the corresponding
tarball:

| Vendored file | Identical to | Source tarball |
| --- | --- | --- |
| `xterm.js` | `lib/xterm.js` in `xterm@5.3.0` | <https://registry.npmjs.org/xterm/-/xterm-5.3.0.tgz> |
| `xterm.css` | `css/xterm.css` in `xterm@5.3.0` | <https://registry.npmjs.org/xterm/-/xterm-5.3.0.tgz> |
| `xterm-addon-fit.js` | `lib/xterm-addon-fit.js` in `xterm-addon-fit@0.8.0` | <https://registry.npmjs.org/xterm-addon-fit/-/xterm-addon-fit-0.8.0.tgz> |

Registry metadata for those tarballs, checked at verification time: `xterm@5.3.0`
sha1 `867daf9cc826f3d45b5377320aabd996cb0fce46` (license MIT); `xterm-addon-fit@0.8.0`
sha1 `48ca99015385141918f955ca7819e85f3691d35f` (license MIT).

Two caveats are stated honestly:

- The npm package name `xterm` is the predecessor of the scoped `@xterm/xterm`
  (the project was renamed). `@xterm/xterm@5.3.0` does **not** publish the same
  `lib/xterm.js`, so the match is against the legacy unscoped `xterm@5.3.0` artifact.
- The MIT text reproduced above is taken from the upstream xterm.js repository
  (`master` branch). It has **not** been compared line-by-line against the license
  file shipped inside the `xterm@5.3.0` / `xterm-addon-fit@0.8.0` tarballs, so it
  reflects the project's notice rather than a per-release license diff. The
  `@license MIT` header inline in `xterm.css` is consistent with it.

*Last verified 2026-09-11 against the npm registry; method: sha256 per file vs
official tarball.*

---

## 2. Font Awesome Free 6.5.1 — vendored in this repository

Files copied into this repository, under `src/frontend/static/vendor/font-awesome/`:

| File | Bytes | Role | License layer | sha256 (this repo) |
| --- | ---: | --- | --- | --- |
| `LICENSE.txt` | 7,427 | upstream license text, redistributed with the copies | the notice itself | `0aa8f86525273b2efa4f40f4272a188e187704252170e979dc06879adf68d43c` |
| `css/all.min.css` | 102,641 | icon classes, codepoints, `@font-face` rules | Code / MIT | `c22cfb6520a7fdbb738632834019acf47c78b1279462c0eb4cb83bae83ecb5a7` |
| `webfonts/fa-brands-400.woff2` | 117,372 | brand glyph face | Fonts / OFL 1.1 | `3a8924cd5203a28628716aedb5cef0943da4c3b44e3ffcee90ab06387b41c490` |
| `webfonts/fa-regular-400.woff2` | 25,452 | regular (400) glyph face | Fonts / OFL 1.1 | `2bccecf0bc7e96cd5ce4003abeb3ae9ee4a3d19158c4e6edfd2df32d2f0d5721` |
| `webfonts/fa-solid-900.woff2` | 156,496 | solid (900) glyph face | Fonts / OFL 1.1 | `9fc85f3a4544ab0d570c7f8f9bbb88db8d92c359b2707580ea8b07c75673eae2` |

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

**Version note (provenance, verified 2026-09-11).** The version string comes from
the header comment inside the vendored stylesheet:

```
/*!
 * Font Awesome Free 6.5.1 by @fontawesome - https://fontawesome.com
 * License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License)
 * Copyright 2023 Fonticons, Inc.
 */
```

That header is no longer the only provenance record. The five vendored files have
been checked **byte-for-byte against the official release artifact** and all five
match exactly, so "6.5.1" is now a verified release identity rather than an
unverified self-stamp:

- Source: the npm package `@fortawesome/fontawesome-free` version `6.5.1`, tarball
  <https://registry.npmjs.org/@fortawesome/fontawesome-free/-/fontawesome-free-6.5.1.tgz>
  (4,951,025 B). The downloaded tarball was matched to the registry metadata before
  any file comparison — `sha512-CNy5vSwN3fsUStPRLX7fUYojyuzoEMSXPl7zSLJ8TgtRfjv24LOnOWKT2zYwaHZCJGkdyRnTmstR0P+Ah503Gw==`
  and sha1 `55cc8410abf1003b726324661ce5b0d1c10de258`, both matching exactly — so the
  artifact compared is the official one, not a stray copy.
- Upstream `package.json` in that release: `name=@fortawesome/fontawesome-free`,
  `version=6.5.1`, `license=(CC-BY-4.0 AND OFL-1.1 AND MIT)` — consistent with the
  layered licensing recorded below.
- Result: 5/5 files identical (per-file sha256 in the table above).

The full release holds 2,126 files; aigate vendors only these 5, so this is a
partial redistribution of a subset, not a copy of the whole package. The remaining
Font Awesome files that `all.min.css` references but that were **deliberately not
vendored** — and why — are itemised under "Fallbacks deliberately NOT vendored"
below.

*Last verified 2026-09-11 against the npm registry; method: sha256 per file vs
official tarball.*

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

- `fa-solid-900.ttf` (419,720 B), `fa-brands-400.ttf` (207,972 B),
  `fa-regular-400.ttf` (68,004 B) and `fa-v4compatibility.ttf` — `woff2` wins every
  `src` chain in the browsers aigate targets, so the truetype entries are never
  requested. (Sizes are the files' byte counts in the 6.5.1 release; the
  `fa-v4compatibility.ttf` size was not recorded during verification.)
- `fa-v4compatibility.woff2` (4,792 B) — it belongs to the legacy font family
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
  gaps like the xterm.js version note are not repeated. The xterm.js (§1) and Font
  Awesome (§2) provenance gaps noted at first writing were later closed
  (2026-09-11, by matching each vendored file's sha256 against the official npm
  release artifacts); those sections now carry a dated verification note. Other
  sections — e.g. the Python dependencies in §3 — have not received the same
  per-file verification and their caveats still stand.

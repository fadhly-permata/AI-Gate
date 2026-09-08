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

| File | Role |
| --- | --- |
| `css/all.min.css` | the stylesheet linked from `src/frontend/static/index.html` |
| `webfonts/fa-solid-900.woff2` | solid icon font (weight 900) |
| `webfonts/fa-regular-400.woff2` | regular icon font (weight 400) |
| `webfonts/fa-brands-400.woff2` | brand-logo icon font |
| `LICENSE.txt` | upstream license text, unmodified |

**Version: 6.5.1**, taken verbatim from the official npm release
`@fortawesome/fontawesome-free@6.5.1`; the downloaded package's integrity was checked
against the registry metadata before the files were copied. Nothing was regenerated,
re-minified or edited — `css/all.min.css` still carries Fonticons' own header line
`Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License`.

Font Awesome Free's licensing is **layered**, and it is not accurate to describe the
whole package as "MIT licensed". Which layer applies to what aigate now ships:

| Component | License | Shipped by aigate? |
| --- | --- | --- |
| Code / CSS | MIT | **Yes** — `css/all.min.css` |
| Font files | SIL Open Font License 1.1 (OFL 1.1), with Reserved Font Name "Font Awesome" | **Yes** — the `.woff2` files listed above |
| Icons (SVG / JS) | Creative Commons Attribution 4.0 International (CC BY 4.0) | **No** — no `svg/` or `js/` files from the package are vendored, so this layer is not engaged |

The complete upstream license text — the MIT permission text, the full OFL 1.1 body
with its Reserved Font Name clause, and the CC BY 4.0 paragraph covering the parts that
are *not* distributed here — is reproduced verbatim in
[`src/frontend/static/vendor/font-awesome/LICENSE.txt`](src/frontend/static/vendor/font-awesome/LICENSE.txt),
so the notice travels with the distributed files as both MIT and OFL 1.1 require. It is
deliberately not re-typed into this document: that file is the single authoritative copy,
and this section only points at it. The vendored font files are unmodified, so the
Reserved Font Name "Font Awesome" is respected.

**Deliberately not vendored:** the package also ships `.ttf` copies of the same fonts, a
`fa-v4compatibility` font, and the SVG/JS icon sets. Only WOFF2 is shipped. In
`css/all.min.css` every `@font-face` lists its WOFF2 source first with a `.ttf` legacy
fallback, so a browser that supports WOFF2 — every browser aigate targets — never
requests the `.ttf`; and `fa-v4compatibility` is reached only through the legacy
`"FontAwesome"` font-family name, which FA 6's own CSS never applies to any class (the
classes aigate uses resolve to "Font Awesome 6 Free" / "Font Awesome 6 Brands"). No
`url(...)` in the vendored CSS points outside this repository, so the UI needs no network
request for icons.

Font Awesome additionally **requests attribution** where its icons are used. Full
upstream terms: <https://fontawesome.com/license/free>

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

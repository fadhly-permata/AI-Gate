#!/usr/bin/env python3
"""Selftest logika banding publish_wiki — TANPA jaringan, satu perintah.

Jalankan:  python3 .opencode/tools/docs/wiki/selftest.py
Uji plan_publish() + helper penyamaran token. Exit 0 semua lolos; exit 1 ada gagal.
Bukan wilayah tests/** (itu be-dev/qa): ini pemeriksaan mandiri alat wiki.
"""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_wiki as pw  # noqa: E402

FAILS = []


def check(name, got, want):
    ok = got == want
    print("%-4s %-34s got=%r want=%r" % ("PASS" if ok else "FAIL", name, got, want))
    if not ok:
        FAILS.append(name)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    A, B = sha(b"isi A"), sha(b"isi B")

    # 1 berkas baru: ada di sumber, belum di wiki
    check("baru",
          pw.plan_publish({"Home.md": A}, {}),
          [("Home.md", "new")])

    # 2 berkas berubah: sha beda
    check("berubah",
          pw.plan_publish({"Home.md": B}, {"Home.md": A}),
          [("Home.md", "changed")])

    # 3 identik -> tidak berubah
    check("identik/tidak-berubah",
          pw.plan_publish({"Home.md": A}, {"Home.md": A}),
          [("Home.md", "unchanged")])

    # 4 ada di wiki, hilang di sumber -> DITAHAN (default, bukan hapus)
    check("sumber-hilang/ditahan",
          pw.plan_publish({}, {"Old.md": A}),
          [("Old.md", "source-missing")])

    # 4b hanya dengan perintah eksplisit boleh hapus
    check("sumber-hilang/hapus-eksplisit",
          pw.plan_publish({}, {"Old.md": A}, delete_missing=True),
          [("Old.md", "delete")])

    # 5 campuran: urutan deterministik (sumber dulu terurut, lalu wiki-only)
    check("campuran",
          pw.plan_publish({"B.md": A, "A.md": A}, {"A.md": A, "C.md": A}),
          [("A.md", "unchanged"), ("B.md", "new"), ("C.md", "source-missing")])

    # 6 tidak ada perubahan sama sekali -> semua unchanged (idempoten)
    same = {"A.md": A, "B.md": B}
    check("idempoten/semua-identik",
          pw.plan_publish(dict(same), dict(same)),
          [("A.md", "unchanged"), ("B.md", "unchanged")])

    # 7 sha256_file baca bytes mentah (bukan teks) -> cocok dgn hashlib
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.md"
        p.write_bytes(b"\xff halo \xc3\xa9")
        check("sha256_file/bytes", pw.sha256_file(p), sha(b"\xff halo \xc3\xa9"))

    # 8 penyamaran token tak pernah bocor
    tok = "ghp_SECRETabc123"
    url = "https://x-access-token:%s@github.com/o/r.git" % tok
    check("mask_secret", pw.mask_secret("clone %s gagal" % tok, tok), "clone *** gagal")
    m = pw.mask_url(url)
    check("mask_url/no-leak", (tok not in m, "***@" in m), (True, True))

    print("\nHASIL: %s" % ("LOLOS" if not FAILS else "GAGAL %s" % FAILS))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())

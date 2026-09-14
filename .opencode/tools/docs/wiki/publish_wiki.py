#!/usr/bin/env python3
"""Penerbit wiki aigate — idempoten, default DRY-RUN.

Stdlib only (nol dependensi baru). Skrip mengklon repo wiki GitHub ke direktori
sementara DI LUAR repo utama, membandingkan sha256 per berkas, lalu (hanya
dengan --publish) menyalin berkas yang benar-benar berubah, commit, dan push.

Jaminan:
- Default = DRY-RUN. Menerbit nyata wajib tombol --publish.
- TIDAK pernah menyentuh repo utama (tidak git add / commit / ubah remote).
- Token tidak pernah dicetak; URL yang ditampilkan disamar.
- Halaman yang sumbernya hilang TIDAK dihapus tanpa --delete-removed eksplisit.
- Direktori sementara SELALU dihapus (try/finally), termasuk saat gagal.
- Produk ditulis "aigate" huruf kecil.

Gunakan:
  python3 publish_wiki.py                       # dry-run (default)
  python3 publish_wiki.py --publish             # terbit nyata
  python3 publish_wiki.py --pages Home.md,Quick-Start.md
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

WIKI_URL_DEFAULT = "https://github.com/fadhly-permata/AI-Gate.wiki.git"
SOURCE_DEFAULT = "documents/pm/wiki-drafts"
PRODUCT = "aigate"


def repo_root():
    """Cari akar repo (naik sampai ketemu .git) agar --source default stabil."""
    p = Path(__file__).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").is_dir():
            return cand
    return Path.cwd().resolve()


def mask_secret(text, token):
    if not token:
        return text
    return text.replace(token, "***")


def mask_url(url):
    return re.sub(r"(//[^/:@]+:)[^@/]+@", r"\1***@", url)


def get_token():
    """Kredensial dari GITHUB_TOKEN, lalu gh auth token. Return None bila tiada."""
    t = os.environ.get("GITHUB_TOKEN")
    if t and t.strip():
        return t.strip()
    try:
        cp = subprocess.run(["gh", "auth", "token"],
                            capture_output=True, text=True, timeout=20)
        if cp.returncode == 0 and cp.stdout.strip():
            return cp.stdout.strip()
    except Exception:
        pass
    return None


def auth_url(url, token):
    quoted = urllib.parse.quote(token, safe="")
    return url.replace("https://", f"https://x-access-token:{quoted}@", 1)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def source_files(source_dir, pages):
    """dict: nama_berkas -> sha256 isi."""
    out = {}
    wanted = None
    if pages:
        wanted = {p.strip() for p in pages.split(",") if p.strip()}
    for f in sorted(Path(source_dir).glob("*.md")):
        if wanted is not None and f.name not in wanted:
            continue
        out[f.name] = sha256_file(f)
    return out


def wiki_files(repo_dir):
    """dict: nama_berkas -> sha256 isi (dari klon wiki)."""
    out = {}
    for f in sorted(Path(repo_dir).glob("*.md")):
        out[f.name] = sha256_file(f)
    return out


def plan_publish(source, wiki, delete_missing=False):
    """Bandingkan sumber vs wiki. Return list (halaman, status) terurut.

    status: new | changed | unchanged | delete | source-missing
    - new/changed  : perlu ditulis (publish -> salin + commit + push)
    - unchanged    : identik, lewati
    - source-missing (default): ada di wiki, tiada di sumber -> DITAHAN
    - delete (hanya bila delete_missing=True): sumber hilang -> hapus
    """
    plan = []
    for page in sorted(source):
        if page not in wiki:
            plan.append((page, "new"))
        elif wiki[page] != source[page]:
            plan.append((page, "changed"))
        else:
            plan.append((page, "unchanged"))
    for page in sorted(wiki):
        if page not in source:
            plan.append((page, "delete" if delete_missing else "source-missing"))
    return plan


def STATUS_LABEL(st):
    return {
        "new": "BARU (akan tulis)",
        "changed": "BERUBAH (akan tulis)",
        "unchanged": "TIDAK BERUBAH",
        "delete": "DIHAPUS",
        "source-missing": "SUMBER HILANG (ditahan)",
    }.get(st, st)


def git(repo, args, token, check=True, timeout=120):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    cp = subprocess.run(["git", "-C", str(repo), *args],
                        capture_output=True, text=True, env=env, timeout=timeout)
    out = cp.stdout + cp.stderr
    if check and cp.returncode != 0:
        raise RuntimeError("git %s gagal (exit %d):\n%s"
                           % (" ".join(args), cp.returncode,
                              mask_secret(mask_url(out), token)))
    return cp


def main():
    ap = argparse.ArgumentParser(
        prog="publish_wiki.py",
        description="Penerbit wiki aigate (idempoten, default dry-run).")
    ap.add_argument("--source", default=None,
                    help="Direktori draft wiki (default: <root>/%s)" % SOURCE_DEFAULT)
    ap.add_argument("--pages", default=None,
                    help="Hanya halaman tertentu, koma-pisah (mis. Home.md,Quick-Start.md)")
    ap.add_argument("--wiki", default=WIKI_URL_DEFAULT,
                    help="URL git repo wiki (.wiki.git)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Mode diam (default bila tak ada --publish)")
    ap.add_argument("--publish", action="store_true",
                    help="Menerbit nyata: commit + push berkas berubah")
    ap.add_argument("--delete-removed", action="store_true",
                    help="Hapus halaman wiki yg sumbernya hilang (hanya dgn --publish)")
    args = ap.parse_args()

    publish = args.publish  # default = dry-run
    source_dir = Path(args.source) if args.source else (repo_root() / SOURCE_DEFAULT)
    if not source_dir.is_dir():
        print("FAIL: direktori sumber tidak ada: %s" % source_dir)
        return 2
    if args.pages:
        wanted = {p.strip() for p in args.pages.split(",") if p.strip()}
        avail = {f.name for f in source_dir.glob("*.md")}
        missing = wanted - avail
        if missing:
            print("FAIL: halaman tak ada di sumber: %s" % ", ".join(sorted(missing)))
            return 2

    token = get_token()
    if not token:
        print("FAIL: kredensial GitHub tiada. Set GITHUB_TOKEN atau pasang `gh auth login`.")
        return 3

    tmp = tempfile.mkdtemp(prefix="aigate-wiki-")
    clone = Path(tmp) / "wiki"
    try:
        aurl = auth_url(args.wiki, token)
        cp = subprocess.run(["git", "clone", "--depth", "1", aurl, str(clone)],
                            capture_output=True, text=True,
                            env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), timeout=180)
        if cp.returncode != 0:
            print("FAIL: clone wiki gagal (exit %d):\n%s"
                  % (cp.returncode, mask_secret(mask_url(cp.stdout + cp.stderr), token)))
            return 4
        # identitas commit LOKAL (hanya di klon sementara, tak sentuh repo utama)
        git(clone, ["config", "user.name", PRODUCT], token, check=False)
        git(clone, ["config", "user.email", PRODUCT + "@users.noreply.github.com"],
            token, check=False)

        src = source_files(source_dir, args.pages)
        wik = wiki_files(clone)
        plan = plan_publish(src, wik, delete_missing=args.delete_removed)

        print("aigate wiki publisher — %s" % ("PUBLISH (nyata)" if publish else "DRY-RUN"))
        print("sumber : %s" % source_dir)
        print("wiki   : %s" % mask_url(args.wiki))
        print("")
        print("%-30s %-26s %s" % ("HALAMAN", "STATUS", "sha sumber→wiki"))
        for page, st in plan:
            s_src = src.get(page, "-")
            s_wik = wik.get(page, "-")
            print("%-30s %-26s %s → %s" % (page, STATUS_LABEL(st), s_src[:12], s_wik[:12]))

        if not publish:
            print("")
            print("DRY-RUN: tak ada tulis/push. Pakai --publish untuk menerbit nyata.")
            return 0

        # mode publish: hanya berkas yang benar-benar berubah
        to_write = [p for p, st in plan if st in ("new", "changed")]
        to_delete = [p for p, st in plan if st == "delete"]
        if not to_write and not to_delete:
            print("")
            print("PUBLISH: nol perubahan — idempoten, tak ada push.")
            return 0
        for page in to_write:
            shutil.copyfile(str(source_dir / page), str(clone / page))
        staged = []
        for page in to_write:
            git(clone, ["add", page], token)
            staged.append(page)
        for page in to_delete:
            (clone / page).unlink(missing_ok=True)
            git(clone, ["rm", page], token)
            staged.append(page)
        msg = "%s wiki: perbarui %d halaman\n\n- %s" % (
            PRODUCT, len(staged), "\n- ".join(staged))
        git(clone, ["commit", "-m", msg], token)
        git(clone, ["push", "origin", "HEAD"], token)
        print("")
        print("PUBLISH: %d halaman diterbitkan: %s" % (len(staged), ", ".join(staged)))
        return 0
    except Exception as e:  # pagar: keluar rapi, nol traceback, tanpa input interaktif
        print("FAIL: %s" % mask_secret(mask_url(str(e)), token))
        return 5
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

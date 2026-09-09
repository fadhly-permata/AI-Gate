#!/usr/bin/env python3
"""Gate pemeriksa rule operasional (spesifikasi: documents/analysis/2026-09-10-rules-consolidation.md paruh 7).

Stdlib only (J1: no new dependency). Exit 0 = semua gate lolos; exit 1 = ada kegagalan.
Tidak pernah menulis file.
"""
import argparse
import json
import re
import sys
from pathlib import Path

RULES_DEFAULT = "documents/pm/OPERATING_RULES.md"
ARCHIVE_DEFAULT = "documents/pm/archive/OPERATING_RULES-v1-52rules.md"
MAP_DEFAULT = "documents/analysis/2026-09-10-rules-consolidation.md"
STALE_PM = re.compile(r"(^|[^./\w-])pm/[a-z]")
NEW_RULE = re.compile(r"^([A-J])(\d+)[ \t](.+)$")
OLD_HEAD = re.compile(r"^## (R\d+) — (.*)$")
MAP_ROW = re.compile(r"^\| (R\d+) \|", re.M)
ACTIVE_IDS = re.compile(r"(?<=[\[, ])R(\d+)(?=[\], :→\-])")
PATH_MENTION = re.compile(r"`([A-Za-z0-9_.\-/]+\.(?:md|py|js|json|ts))`")


def rule_lines(text):
    """Ambil baris rule v2: tema A1..J6 (termasuk baris lanjutan yang menjorok)."""
    out, cur = [], None
    for n, line in enumerate(text.splitlines(), 1):
        m = NEW_RULE.match(line)
        if m:
            if cur:
                out.append(cur)
            cur = {"id": m.group(1) + m.group(2), "theme": m.group(1),
                   "title": m.group(3)[:70], "start": n, "end": n, "lines": 1}
        elif cur is not None and (line.startswith("   ") or line.strip() == ""):
            if line.strip():
                cur["end"], cur["lines"] = n, cur["lines"] + 1
    if cur:
        out.append(cur)
    return out


def old_rules(text):
    out = {}
    for n, line in enumerate(text.splitlines(), 1):
        m = OLD_HEAD.match(line)
        if m:
            out[m.group(1)] = {"title": m.group(2)[:60], "start": n}
    keys = sorted(out, key=lambda k: int(k[1:]))
    for i, k in enumerate(keys):
        nxt = out[keys[i + 1]]["start"] if i + 1 < len(keys) else len(text.splitlines()) + 1
        out[k]["end"] = nxt - 1
        out[k]["bytes"] = len("\n".join(text.splitlines()[out[k]["start"] - 1:nxt - 1]).encode())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rules", nargs="?", default=RULES_DEFAULT)
    ap.add_argument("archive", nargs="?", default=ARCHIVE_DEFAULT)
    ap.add_argument("--map", default=MAP_DEFAULT)
    ap.add_argument("--max-bytes", type=int, default=20480)
    ap.add_argument("--themes", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rp, apth, mp = Path(a.rules), Path(a.archive), Path(a.map)
    for p in (rp, apth, mp):
        if not p.is_file():
            print("FAIL: berkas tidak ada: %s" % p)
            return 1
    rules_t, arch_t, map_t = rp.read_text(), apth.read_text(), mp.read_text()
    rules, olds = rule_lines(rules_t), old_rules(arch_t)
    checks = []

    def _fail(msg):
        print("FAIL: %s" % msg)
        return 1

    def gate(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    # 1 indeks
    gate("index", len(rules) > 0, "%d rule, %d tema" % (len(rules), len({r["theme"] for r in rules})))

    # 2 cakupan lama->baru: tiap ID lama muncul tepat 1x di PETA (§1 saja; tabel
    #   §2.1 'duplikat' memang mengulang ID dan bukan peta 1-ke-1), dan disebut di rule aktif
    sec1 = re.search(r"^## 1\. Peta.*?(?=^## 2\.)", map_t, re.S | re.M)
    if not sec1:
        return _fail("peta §1 tidak ditemukan di %s" % mp)
    mapped = MAP_ROW.findall(sec1.group(0))
    dup = [i for i in set(mapped) if mapped.count(i) > 1]
    miss_map = [k for k in olds if k not in mapped]
    active_ids = {"R" + x for x in ACTIVE_IDS.findall(rules_t)}
    miss_active = [k for k in olds if k not in active_ids]
    gate("coverage", not (dup or miss_map),
         "mapped=%d unique=%d dup=%s missing_in_map=%s" % (len(mapped), len(set(mapped)), dup, miss_map))
    if miss_active:
        print("INFO: ID lama tak disebut di rule aktif (wajar bila rumah tunggal = .opencode/rules/*): %s"
              % ",".join(miss_active))

    # 3 rentang numerik arsip
    nums = sorted(int(k[1:]) for k in olds)
    gaps = [n for n in range(1, max(nums) + 1) if n not in nums] if nums else []
    gate("range", not gaps, "R1..R%d gaps=%s" % (max(nums) if nums else 0, gaps))

    # 4 ukuran + tiap rule <=4 baris + tema
    over = [r["id"] for r in rules if r["lines"] > 4]
    gate("size", len(rules_t.encode()) <= a.max_bytes, "%d byte (maks %d)" % (len(rules_t.encode()), a.max_bytes))
    gate("themes", len({r["theme"] for r in rules}) <= a.themes,
         "%d tema (maks %d)" % (len({r["theme"] for r in rules}), a.themes))
    gate("rule_lines", not over, "rule >4 baris: %s" % (over or "tidak ada"))

    # 5 arsip utuh
    same_heads = all(h in arch_t for h in [OLD_HEAD.match(l).group(1) for l in arch_t.splitlines() if OLD_HEAD.match(l)])
    gate("archive", len(olds) == max(nums) if nums else False,
         "arsip: %d rule, %d byte (v1 sensed %d)" % (len(olds), len(arch_t.encode()), len(rules_t.encode()) + len(olds)))
    gate("archive_heads_unique", same_heads, "heading R# di arsip konsisten")

    # 6 rujukan hidup: path yang disebut rule aktif harus ada; tidak ada pm/ basi
    broken, stale = [], []
    for pth in sorted(set(PATH_MENTION.findall(rules_t))):
        if pth.startswith(("src/", "documents/", ".opencode/", "tests/")) and not Path(pth).exists():
            broken.append(pth)
    for n, line in enumerate(rules_t.splitlines(), 1):
        if STALE_PM.search(line):
            stale.append("%s:%d" % (rp, n))
    for f in sorted(Path(".opencode/rules").glob("*.md")):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if STALE_PM.search(line):
                stale.append("%s:%d" % (f, n))
    gate("live_paths", not broken, "path rusak: %s" % (broken or "tidak ada"))
    gate("no_stale_refs", not stale, "rujukan pm/ basi: %s" % (stale or "tidak ada"))

    # 8 sitatan R# di berkas hidup harus terselesaikan (exist di arsip v1 ATAU dipetakan rule aktif)
    cited, unresolved = set(), []
    live = [rp, Path("AGENTS.md")] + sorted(Path(".opencode/rules").glob("*.md")) \
        + sorted(Path(".opencode/commands").glob("*.md")) + sorted(Path(".opencode/skills").rglob("*.md")) \
        + sorted(Path(".opencode/agents").rglob("*.md"))
    for f in live:
        if not f.is_file():
            continue
        for tok in re.findall(r"(?<![\w-])R(\d{1,3})\b", f.read_text()):
            cited.add("R" + tok)
    unresolved = sorted(c for c in cited if c not in olds and c not in active_ids)
    gate("citations_resolve", not unresolved,
         "%d sitatan R# ; tak terselesaikan: %s" % (len(cited), unresolved or "tidak ada"))

    # 9 utang format laporan (dibuat di luar rule) -> peringatan, bukan kegagalan
    debt = []
    for f in Path(".opencode/reports").rglob("*.md"):
        s = str(f).replace("\\", "/")
        if not re.match(r"^\.opencode/reports/\d{8}/[^/]+/\d{4}_.+\.md$", s):
            debt.append(s)

    ok = all(c["pass"] for c in checks)
    if a.json:
        print(json.dumps({"rules": rules, "themes": sorted({r["theme"] for r in rules}),
                          "totals": {"rules": len(rules), "bytes": len(rules_t.encode()),
                                     "archive_bytes": len(arch_t.encode()), "legacy_rules": len(olds)},
                          "checks": checks, "report_format_debt": len(debt)}, indent=2))
    else:
        for c in checks:
            print("%s %-20s %s" % ("PASS" if c["pass"] else "FAIL", c["name"], c["detail"]))
        print("INFO laporan non-standar (utang K10): %d berkas" % len(debt))
        print("HASIL: %s" % ("LOLOS" if ok else "GAGAL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

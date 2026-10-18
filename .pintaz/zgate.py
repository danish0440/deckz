#!/usr/bin/env python3
"""Gates for the daily upstream sync of a Z fork (PINTAZ, 18 Oct 2026).

Everything is read from git objects (raw blobs), so the result is the same on Linux and Windows and
the gate can be tested locally with throw-away commits.

  zgate.py check  --base <rev> --up <rev> --merged <rev> [--out reason.md]
      base   = our main before the merge (the trusted records live in its .pintaz/)
      up     = the upstream commit being merged
      merged = the merge commit made by the sync (upstream tree + rebrand.py)
      exit 0 = all gates pass, 1 = a gate failed (reasons on stdout and in --out)

  zgate.py record --up <rev> --dir <worktree> [--report <path>]
      writes .pintaz/licence.sha256, .pintaz/workflows-allow.txt (from the upstream commit) and
      .pintaz/brand-allow.txt (from the worktree's .pintaz/rebrand-report.txt).

Gates:
  G-LICENCE   upstream licence files (root LICENSE*/COPYING*/NOTICE*, docs/brand/LICENSE-brand.txt) are
              byte-identical to .pintaz/licence.sha256; no licence file removed or added; our LICENSE-MIT /
              LICENSE-APACHE equal upstream's.
  G-BRAND     every "still naming ArtCraft/getartcraft/discord" line of the new rebrand report is in
              .pintaz/brand-allow.txt (line numbers ignored).
  G-WORKFLOWS the merged tree has exactly our *-z.yml workflows, same content as base (FONTS_REF line may
              differ); every upstream workflow file name is in .pintaz/workflows-allow.txt.
  G-NOTICE    our NOTICE keeps upstream's NOTICE text and adds the PINTAZ change statement + credit; README
              has the credit; the About credit was inserted; licence files present.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

OUR_WORKFLOWS = ("release-z.yml", "upstream-sync-z.yml")
LICENCE_RX = re.compile(r"^(licen[cs]e|copying|notice)", re.I)
BRAND_LICENCE = "docs/brand/LICENSE-brand.txt"
REPORT = ".pintaz/rebrand-report.txt"
LEFT_HEADER = "lines still naming ArtCraft/getartcraft/discord (non-doc):"


def git(*args, check=True) -> bytes:
    r = subprocess.run(["git", *args], capture_output=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if r.returncode == 0 else b""


def blob(rev: str, path: str) -> bytes | None:
    r = subprocess.run(["git", "cat-file", "blob", f"{rev}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def ls(rev: str, path: str = "") -> list[str]:
    """names directly under path (files and dirs) at rev"""
    out = git("ls-tree", "--name-only", f"{rev}:{path}" if path else rev, check=False)
    return [n for n in out.decode().splitlines() if n]


def text(b: bytes | None) -> str:
    return (b or b"").decode("utf-8", errors="replace").replace("\r\n", "\n")


def licence_paths(rev: str) -> list[str]:
    paths = [n for n in ls(rev) if LICENCE_RX.match(n) and blob(rev, n) is not None]
    if blob(rev, BRAND_LICENCE) is not None:
        paths.append(BRAND_LICENCE)
    return sorted(paths)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def report_lines(report: str) -> list[str]:
    """the leftover lines of a rebrand report, line numbers dropped: 'path: text'"""
    lines = report.split("\n")
    out, on = [], False
    for ln in lines:
        if ln.startswith(LEFT_HEADER):
            on = True
            continue
        if on and ln.strip():
            m = re.match(r"^(.*?):(\d+): ?(.*)$", ln)
            out.append(f"{m.group(1)}: {m.group(3).strip()}" if m else ln.strip())
    return out


def norm_wf(t: str) -> str:
    return re.sub(r'^(\s*FONTS_REF:).*$', r"\1 <ref>", t, flags=re.M)


# ---------------------------------------------------------------------------------------------
def check(base: str, up: str, merged: str) -> list[str]:
    fails: list[str] = []

    # G-LICENCE
    rec = text(blob(base, ".pintaz/licence.sha256"))
    recorded = {}
    for ln in rec.split("\n"):
        if ln.strip():
            h, p = ln.split(None, 1)
            recorded[p.strip()] = h
    if not recorded:
        fails.append("G-LICENCE: no .pintaz/licence.sha256 on main (record it first)")
    for p, h in sorted(recorded.items()):
        b = blob(up, p)
        if b is None:
            fails.append(f"G-LICENCE: upstream removed {p}")
        elif sha(b) != h:
            fails.append(f"G-LICENCE: upstream changed {p} (sha256 {sha(b)[:12]} != recorded {h[:12]})")
    for p in licence_paths(up):
        if p not in recorded:
            fails.append(f"G-LICENCE: new upstream licence file {p}")
    for p in ("LICENSE-MIT", "LICENSE-APACHE"):
        if p in recorded and blob(merged, p) != blob(up, p):
            fails.append(f"G-LICENCE: our {p} differs from upstream's")

    # G-BRAND
    allow = set(l for l in text(blob(base, ".pintaz/brand-allow.txt")).split("\n") if l.strip())
    rep = text(blob(merged, REPORT))
    if LEFT_HEADER not in rep:
        fails.append("G-BRAND: no rebrand report in the merged tree")
    new = [l for l in report_lines(rep) if l not in allow]
    for l in new[:40]:
        fails.append(f"G-BRAND: new line naming ArtCraft/getartcraft/discord: {l[:200]}")
    if len(new) > 40:
        fails.append(f"G-BRAND: ... and {len(new) - 40} more")

    # G-WORKFLOWS
    wf = sorted(ls(merged, ".github/workflows"))
    if wf != sorted(OUR_WORKFLOWS):
        fails.append(f"G-WORKFLOWS: merged tree workflows are {wf}, expected only {list(OUR_WORKFLOWS)}")
    for n in OUR_WORKFLOWS:
        a, b = blob(base, f".github/workflows/{n}"), blob(merged, f".github/workflows/{n}")
        if a is None or b is None or norm_wf(text(a)) != norm_wf(text(b)):
            fails.append(f"G-WORKFLOWS: {n} in the merged tree differs from main (only FONTS_REF may change)")
    wallow = set(l.strip() for l in text(blob(base, ".pintaz/workflows-allow.txt")).split("\n") if l.strip())
    if blob(base, ".pintaz/workflows-allow.txt") is None:
        fails.append("G-WORKFLOWS: no .pintaz/workflows-allow.txt on main (record it first)")
    for n in sorted(ls(up, ".github/workflows")):
        if n not in wallow:
            fails.append(f"G-WORKFLOWS: new upstream workflow .github/workflows/{n}")

    # G-NOTICE
    un, mn = text(blob(up, "NOTICE")), text(blob(merged, "NOTICE"))
    if not mn:
        fails.append("G-NOTICE: NOTICE missing in the merged tree")
    else:
        if un and not mn.startswith(un.rstrip("\n")):
            fails.append("G-NOTICE: our NOTICE no longer starts with upstream's NOTICE text")
        if "PINTAZ TECHNOLOGIES" not in mn or "Based on " not in mn:
            fails.append("G-NOTICE: NOTICE lacks the PINTAZ change statement / credit line")
    readme = text(blob(merged, "README.md"))
    if "Based on " not in readme or "PINTAZ" not in readme:
        fails.append("G-NOTICE: README.md lacks the credit line")
    # the launcher has no About window: its credit is the Settings patch (launcher patches line)
    launcher_credit = re.search(r"^launcher patches: \[.*crates/ui-egui/src/dialogs\.rs'\]", rep, flags=re.M)
    if "about credit inserted in: NOT FOUND" in rep and not launcher_credit:
        fails.append("G-NOTICE: rebrand.py could not insert the About credit")
    for p in ("LICENSE-MIT", "LICENSE-APACHE"):
        if p in recorded and blob(merged, p) is None:
            fails.append(f"G-NOTICE: {p} missing in the merged tree")
    return fails


def record(up: str, root: Path, report: Path | None):
    d = root / ".pintaz"
    d.mkdir(exist_ok=True)
    lic = "".join(f"{sha(blob(up, p))}  {p}\n" for p in licence_paths(up))
    (d / "licence.sha256").write_bytes(lic.encode())
    wf = "".join(f"{n}\n" for n in sorted(ls(up, ".github/workflows")))
    (d / "workflows-allow.txt").write_bytes(wf.encode())
    rp = report or (d / "rebrand-report.txt")
    lines = sorted(set(report_lines(rp.read_text(encoding="utf-8").replace("\r\n", "\n"))))
    (d / "brand-allow.txt").write_bytes("".join(f"{l}\n" for l in lines).encode("utf-8"))
    print(f"recorded: {len(lic.splitlines())} licence files, {len(wf.splitlines())} upstream workflows, {len(lines)} brand lines")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--base", required=True)
    c.add_argument("--up", required=True)
    c.add_argument("--merged", required=True)
    c.add_argument("--out")
    r = sub.add_parser("record")
    r.add_argument("--up", required=True)
    r.add_argument("--dir", required=True)
    r.add_argument("--report")
    a = ap.parse_args()
    if a.cmd == "record":
        record(a.up, Path(a.dir), Path(a.report) if a.report else None)
        return 0
    fails = check(a.base, a.up, a.merged)
    gates = ["G-LICENCE", "G-BRAND", "G-WORKFLOWS", "G-NOTICE"]
    lines = [f"- {g}: {'FAIL' if any(f.startswith(g) for f in fails) else 'pass'}" for g in gates]
    body = "\n".join(lines) + ("\n\nReasons:\n" + "\n".join(f"- {f}" for f in fails) if fails else "") + "\n"
    print(body)
    if a.out:
        Path(a.out).write_text(body, encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

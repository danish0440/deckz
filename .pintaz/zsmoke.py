#!/usr/bin/env python3
"""Windows smoke test for a Z release build (PINTAZ, 18 Oct 2026). Runs on the GitHub Windows runner
after packaging, BEFORE anything is published. Never starts the GUI app.

  python zsmoke.py <dist-dir> <zid> <version>

Checks: the MSI and the portable zip exist and are a sane size; the zip holds <zid>.exe (a real PE
file); no ArtCraft feed / site / Discord strings in the exes; if the app ships <zid>-cli.exe it is run
headless with --version (exit 0, prints the version) and --help (exit 0).
"""
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MIN_MSI = 2_000_000
MIN_ZIP = 2_000_000
BANNED = [b"getartcraft", b"discord.gg", b"api.storyteller.ai"]


def fail(msg):
    print(f"SMOKE FAIL: {msg}")
    sys.exit(1)


def main():
    dist, zid, version = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    files = sorted(p.name for p in dist.iterdir())
    print("dist:", files)
    msi = [p for p in dist.glob(f"{zid}-*-windows-x64.msi")]
    zips = [p for p in dist.glob(f"{zid}-*-windows-x64-portable.zip")]
    if len(msi) != 1 or msi[0].stat().st_size < MIN_MSI:
        fail(f"MSI missing or too small: {[(p.name, p.stat().st_size) for p in msi]}")
    if len(zips) != 1 or zips[0].stat().st_size < MIN_ZIP:
        fail(f"portable zip missing or too small: {[(p.name, p.stat().st_size) for p in zips]}")
    if version not in msi[0].name or version not in zips[0].name:
        fail(f"version {version} not in the package names")
    tmp = Path(tempfile.mkdtemp(prefix="zsmoke-"))
    with zipfile.ZipFile(zips[0]) as z:
        bad = z.testzip()
        if bad:
            fail(f"corrupt entry in zip: {bad}")
        z.extractall(tmp)
    exes = {p.name.lower(): p for p in tmp.rglob("*.exe")}
    print("exes:", sorted(exes))
    gui = exes.get(f"{zid}.exe")
    if not gui:
        fail(f"{zid}.exe not in the portable zip")
    for p in exes.values():
        b = p.read_bytes()
        if b[:2] != b"MZ" or len(b) < 1_000_000:
            fail(f"{p.name} is not a sane Windows exe ({len(b)} bytes)")
        for s in BANNED:
            if s in b:
                fail(f"{p.name} still contains {s.decode()}")
    cli = exes.get(f"{zid}-cli.exe")
    if cli:
        for args in (["--version"], ["--help"]):
            r = subprocess.run([str(cli), *args], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
            out = (r.stdout + r.stderr).strip()
            print(f"$ {cli.name} {' '.join(args)} -> exit {r.returncode}\n{out[:600]}")
            # some CLIs print their usage and exit 1 on --help (cadz-cli): that still proves it starts headless
            help_ok = args == ["--help"] and "usage" in out.lower()
            if not out or (r.returncode != 0 and not help_ok):
                fail(f"{cli.name} {' '.join(args)} failed (exit {r.returncode})")
            if args == ["--version"] and version not in out:
                fail(f"{cli.name} --version does not print {version}")
    else:
        print(f"no {zid}-cli.exe in this app: static checks only (the GUI is never started)")
    print(f"SMOKE PASS: {zid} {version}")


if __name__ == "__main__":
    main()

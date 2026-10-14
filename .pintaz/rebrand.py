#!/usr/bin/env python3
"""Rebrand one ArtCraft (storytold) app checkout into its PINTAZ "Z" copy.

Usage:  python rebrand.py <repo-dir> <upstream-id>      e.g.  python rebrand.py E:/devcache/appz/photoz photocraft

Deterministic and re-runnable on a FRESH upstream checkout (that is how the weekly upstream-sync
workflow uses it). Needs Pillow. Everything it needs besides the checkout lives next to this file
(templates/, icons/); inside a fork the same tree is copied to `.pintaz/`.

What it does (in order):
  1. renames the app's own id everywhere (all case forms: photocraft/PhotoCraft/Photocraft/PHOTOCRAFT
     -> photoz/PhotoZ/Photoz/PHOTOZ), files and folders too, plus `ai.storyteller.` -> `com.pintaz.`;
     other suite apps' display names (FilmCraft -> FilmZ) in text only (their crates stay upstream's);
  2. removes the ArtCraft marks (docs/brand images) and user-visible ArtCraft wording, repoints
     links (getartcraft.com / Discord / storytold repo) to our fork;
  3. new Z icons (from icons/<zid>-1024.png) in every size/format the build needs;
  4. About screen: "by PINTAZ" + credit line; NOTICE gets the Apache change statement;
  5. own workflows (release-z.yml, upstream-sync.yml); upstream's workflows removed;
  6. launcher only: release feed + screenshots off, catalogue points at our forks.
Writes `.pintaz/rebrand-report.txt` (what is left that still says ArtCraft).
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNER = "danish0440"

# upstream id -> (upstream repo, upstream display name, z id, z display name)
APPS = {
    "artcraft-launcher": ("craft-launcher", "ArtCraft Launcher", "appz", "AppZ"),
    "photocraft": ("photocraft", "PhotoCraft", "photoz", "PhotoZ"),
    "vectorcraft": ("vectorcraft", "VectorCraft", "vectorz", "VectorZ"),
    "pdfcraft": ("pdfcraft", "PdfCraft", "pdfz", "PdfZ"),
    "lightcraft": ("lightcraft", "LightCraft", "lightz", "LightZ"),
    "filmcraft": ("filmcraft", "FilmCraft", "filmz", "FilmZ"),
    "effectcraft": ("effectcraft", "EffectCraft", "effectz", "EffectZ"),
    "designcraft": ("designcraft", "DesignCraft", "designz", "DesignZ"),
    "figcraft": ("figcraft", "FigCraft", "figz", "FigZ"),
    "soundcraft": ("soundcraft", "SoundCraft", "soundz", "SoundZ"),
    "deckcraft": ("deckcraft", "DeckCraft", "deckz", "DeckZ"),
    "wordcraft": ("wordcraft", "WordCraft", "wordz", "WordZ"),
    "gridcraft": ("gridcraft", "GridCraft", "gridz", "GridZ"),
    "cadcraft": ("cadcraft", "CADCraft", "cadz", "CadZ"),
}
REPO_TO_ID = {v[0]: k for k, v in APPS.items()}

# Files never text-edited (legal text stays exactly as upstream wrote it) and never renamed.
PROTECT_NAMES = {"LICENSE", "LICENSE-MIT", "LICENSE-APACHE", "NOTICE", "ATTRIBUTION.md", "COPYRIGHT", "LICENSE-brand.txt"}
PROTECT_DIRS = {".git", ".pintaz", "contributors", "target", "node_modules"}
BIN_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".icns", ".ttf", ".otf", ".woff", ".woff2", ".psd", ".pdf",
           ".zip", ".gz", ".xz", ".zst", ".bin", ".wasm", ".mp4", ".mov", ".wav", ".mp3", ".flac", ".ogg", ".tif", ".tiff",
           ".heic", ".avif", ".exr", ".dng", ".cr2", ".nef", ".arw", ".docx", ".xlsx", ".pptx", ".dwg", ".dxf", ".idml", ".indd",
           ".kra", ".ai", ".eps", ".jxl", ".qoi", ".bmp", ".pcx", ".tga", ".hdr", ".dds", ".ktx2", ".spv", ".a", ".lib", ".so", ".dll"}
COPYRIGHT_LINE = re.compile(r"(?i)copyright\s*(\(c\)|©|\d{4})|©|\(c\) 20\d\d")

PALETTE = {"paper": (251, 246, 234), "cream": (244, 239, 230), "jade": (31, 77, 58), "mustard": (211, 162, 80), "ink": (26, 36, 34)}


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


# ---------------------------------------------------------------------------------------------
# name mapping
def case_like(matched: str, z_lower: str, z_display: str, up_display: str) -> str:
    """Map one matched spelling of the upstream id onto the same spelling of the Z id."""
    letters = re.sub(r"[^A-Za-z]", "", matched)
    sep = "_" if "_" in matched else ""
    if letters.islower():
        return z_lower.replace("-", "_") if sep else z_lower
    if letters.isupper():
        return z_lower.upper().replace("-", "_")
    if matched.replace("-", " ") == up_display or matched == up_display.replace(" ", ""):
        return z_display
    if letters[0].isupper() and letters[1:].islower():  # Photocraft / Artcraftlauncher
        return z_display[0] + z_display[1:].lower()
    return z_display


def id_regex(up_id: str) -> re.Pattern:
    if up_id == "artcraft-launcher":
        return re.compile(r"(?i)artcraft[-_ ]?launcher")
    return re.compile(r"(?i)" + re.escape(up_id))


def rename_own(text: str, up_id: str) -> str:
    _, up_display, zid, zname = APPS[up_id]
    rx = id_regex(up_id)
    return rx.sub(lambda m: case_like(m.group(0), zid, zname, up_display), text)


# ---------------------------------------------------------------------------------------------
# text rules
def phrase_rules(up_id: str, launcher: bool):
    up_repo, up_display, zid, zname = APPS[up_id]
    fork = f"https://github.com/{OWNER}/{zid}"
    rules = [
        # links first (they contain ids)
        (re.compile(r"https://getartcraft\.com/apps/([a-z0-9-]+)"),
         lambda m: f"https://github.com/{OWNER}/{APPS[m.group(1)][2]}" if m.group(1) in APPS else fork),
        # format-string placeholders (`/apps/{}`, `/apps/{slug}`) keep their argument
        (re.compile(r"https://getartcraft\.com/apps/(\{[^}]*\})"), lambda m: f"https://github.com/{OWNER}/{m.group(1)}"),
        (re.compile(r"https?://(www\.)?getartcraft\.com[^\s\"'<>(){}`]*"), lambda m: fork),
        (re.compile(r"https://discord\.gg/artcraft"), lambda m: fork + "/issues"),
        (re.compile(r" \(discord\.gg/artcraft\)"), lambda m: ""),
        (re.compile(r"discord\.gg/artcraft"), lambda m: f"github.com/{OWNER}/{zid}/issues"),
        (re.compile(r" on getartcraft\.com"), lambda m: " on GitHub"),
        (re.compile(r"Join Our Discord|Join our Discord|Join the Discord"), lambda m: "Get help on GitHub"),
        (re.compile(r"the ArtCraft community Discord"), lambda m: "this app's GitHub issues"),
        (re.compile(r"ArtCraft community"), lambda m: "community"),
        (re.compile(r"ArtCraft [Ww]ebsite"), lambda m: "Upstream project"),
        (re.compile(r"Part of ArtCraft\. ?"), lambda m: ""),
        (re.compile(r" ?Part of the ArtCraft family( of [a-z ]+)?\."), lambda m: ""),
        (re.compile(r"(?<![/\w.])getartcraft\.com/apps/([a-z0-9-]+)"),
         lambda m: f"github.com/{OWNER}/{APPS[m.group(1)][2]}" if m.group(1) in APPS else f"github.com/{OWNER}/{zid}"),
        (re.compile(r"\bon Discord\b"), lambda m: "on GitHub"),
        # our own repo (never a cargo git dependency on another storytold repo)
        (re.compile(r"(?<!git = \")(?<!git\+)(https://github\.com/)?storytold/" + re.escape(up_repo) + r"(?![-\w])"),
         lambda m: (m.group(1) or "") + f"{OWNER}/{zid}"),
        # wording
        (re.compile(r"Join the ArtCraft community on Discord"), lambda m: "Get help on GitHub"),
        (re.compile(r"Join the ArtCraft Discord"), lambda m: "Get help on GitHub"),
        (re.compile(r"Join us on Discord"), lambda m: "Get help on GitHub"),
        (re.compile(r"ArtCraft Website"), lambda m: "Upstream project"),
        (re.compile(r"ArtCraft on GitHub"), lambda m: "Source code on GitHub"),
        (re.compile(r" from the ArtCraft team"), lambda m: ""),
        (re.compile(r"ArtCraft API"), lambda m: "release feed"),
        (re.compile(r"ArtCraft App Page"), lambda m: "App Page"),
        (re.compile(r"ArtCraft — more creative apps"), lambda m: "More Z apps"),
        (re.compile(r" ?Part of the ArtCraft suite[^.\"]*\."), lambda m: ""),
        (re.compile(r"the ArtCraft team and community"), lambda m: "the upstream team and community"),
        (re.compile(r"the ArtCraft team"), lambda m: "the upstream team"),
        (re.compile(r'"getartcraft\.com"'), lambda m: '"Upstream"'),
        (re.compile(r"Craft App Suite"), lambda m: "Z App Suite"),
        (re.compile(r"Craft Apps\b"), lambda m: "Z Apps"),
        (re.compile(r"Craft App\b"), lambda m: "Z App"),
        (re.compile(r"\bcrafting apps\b"), lambda m: "Z apps"),
        (re.compile(r"\bCrafting Apps\b"), lambda m: "Z Apps"),
        (re.compile(r'tl!\("ArtCraft"\)'), lambda m: f'tl!("{"AppZ" if launcher else "Upstream"}")'),
        (re.compile(r'"ArtCraft"'), lambda m: f'"{"AppZ" if launcher else "Upstream"}"'),
        (re.compile(r"ArtCraft on \{name\}"), lambda m: "{name}"),
        (re.compile(r"Visit getartcraft\.com"), lambda m: "Visit the project page"),
        (re.compile(r'tl!\("Discord"\)'), lambda m: 'tl!("Help")'),
        (re.compile(r'(?<![\w(])"Discord"'), lambda m: '"Help"'),  # bare button label; the link goes to GitHub issues
        (re.compile(r"ArtCraft apps\b"), lambda m: "Z apps"),
        (re.compile(r"ArtCraft(?=[A-Z][a-z])(?!Launcher)"), lambda m: "Z"),  # identifiers: ArtCraftApi -> ZApi, ArtCraftInstallDirDlg -> ZInstallDirDlg
    ]
    if launcher:
        # every suite repo -> our fork; the launcher's own repo too (not craft-launcher-assets)
        rules += [
            (re.compile(r"storytold/craft-launcher(?![-\w])"), lambda m: f"{OWNER}/appz"),
            (re.compile(r"storytold/(" + "|".join(v[0] for v in APPS.values() if v[0] != "craft-launcher") + r")(?![-\w])"),
             lambda m: f"{OWNER}/{APPS[REPO_TO_ID[m.group(1)]][2]}"),
            (re.compile(r'GITHUB_OWNER: &str = "storytold"'), lambda m: f'GITHUB_OWNER: &str = "{OWNER}"'),
            (re.compile(r'"https://github\.com/storytold"'), lambda m: f'"https://github.com/{OWNER}"'),
        ]
    return rules


def other_display_rules(up_id: str, launcher: bool):
    """Other suite apps: in an app repo only the display name changes (their crates stay upstream's).
    In the launcher every id is renamed in full (it only names them, it never links their code)."""
    out = []
    for oid, (_, odisp, ozid, ozname) in APPS.items():
        if oid == up_id:
            continue
        if launcher:
            out.append(("full", oid))
        else:
            out.append((re.compile(r"(?<![A-Za-z])" + re.escape(odisp) + r"(?![a-z])"), ozname))
    return out


def transform_text(text: str, up_id: str, launcher: bool, path: Path) -> str:
    lines = text.split("\n")
    rules = phrase_rules(up_id, launcher)
    others = other_display_rules(up_id, launcher)
    out = []
    for line in lines:
        # Apache-2.0 4(d): ship NOTICE next to the licence files in every package
        if path.parts and "packaging" in path.parts and "LICENSE-APACHE" in line and "NOTICE" not in line:
            if "'LICENSE-APACHE'" in line:
                line = line.replace("'LICENSE-APACHE'", "'LICENSE-APACHE', 'NOTICE'")
            elif re.search(r"\bfor \w+ in .*LICENSE-APACHE", line):
                line = line.replace("LICENSE-APACHE", "LICENSE-APACHE NOTICE", 1)
        def tx(line):
            for rx, fn in rules:
                line = rx.sub(fn, line)
            for o in others:
                if o[0] == "full":
                    line = rename_own(line, o[1])
                else:
                    line = o[0].sub(o[1], line)
            line = rename_own(line, up_id)
            line = line.replace("ai.storyteller.", "com.pintaz.")
            line = line.replace("docs/brand/artcraft-", "assets/z-brand/")
            line = line.replace("docs\\brand\\artcraft-", "assets\\z-brand\\")
            line = line.replace("docs\\\\brand\\\\artcraft-", "assets\\\\z-brand\\\\")
            return line
        if COPYRIGHT_LINE.search(line) and not re.search(r"\bfor \w+ in ", line):
            if path.suffix == ".rs":
                # a copyright notice inside code: the notice text (string literals) stays, the code is renamed
                parts, pos = [], 0
                for m in _STR.finditer(line):
                    parts.append(tx(line[pos:m.start()]))
                    parts.append(m.group(0))
                    pos = m.end()
                parts.append(tx(line[pos:]) if not line[pos:].lstrip().startswith("//") else line[pos:])
                out.append("".join(parts))
            else:
                out.append(line)
            continue
        out.append(tx(line))
    text = "\n".join(out)
    if path.suffix == ".tsv":
        text = fix_tsv(text).replace("ArtCraft", "Upstream")
    posix = path.as_posix()
    if path.suffix != ".tsv" and ("/i18n" in posix or "/locales/" in posix or "/locale/" in posix or path.stem in ("i18n", "l10n")):
        # translated text: no ArtCraft name, and the old Discord links now go to GitHub
        text = re.sub(r"ArtCraft Z Apps|ArtCraft", "Z", text).replace("Discord", "GitHub")
    text = text.replace("ArtCraft Z Apps", "Z Apps")
    # an ArtCraft "A" mark hard-coded as a path (DesignCraft): our Z in the same view box
    text = re.sub(r'(const MARK_PATH: &str = )"[^"]*"', lambda m: m.group(1) + '"M10,0H106V20L40,77H106V97H10V77L76,20H10Z"', text)
    if path.suffix == ".wxs":
        # new MSI identity: an upstream MSI must never be "upgraded" (replaced) by ours, or vice versa
        import uuid
        text = re.sub(r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                      lambda m: str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/{OWNER}/{APPS[up_id][2]}#{m.group(0).lower()}")).upper()
                      if m.group(0).isupper() else str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/{OWNER}/{APPS[up_id][2]}#{m.group(0).lower()}")),
                      text)
    # the "Upstream project" link goes to the upstream repo (plain-text credit, no ArtCraft mark)
    text = re.sub(r'(ARTCRAFT_WEBSITE: &str = )"[^"]*"', lambda m: m.group(1) + f'"https://github.com/storytold/{APPS[up_id][0]}"', text)
    return text


def fix_tsv(text: str) -> str:
    """A translation that still names ArtCraft/Discord is stale once its English source changed:
    show the (new) English instead."""
    out = []
    for line in text.split("\n"):
        cols = line.split("\t")
        if not line.startswith("#") and len(cols) >= 3 and re.search(r"ArtCraft|Discord|getartcraft", cols[2]) and not re.search(r"ArtCraft|Discord|getartcraft", cols[1]):
            cols[2] = cols[1]
            line = "\t".join(cols)
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------
def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PROTECT_DIRS]
        for f in filenames:
            yield Path(dirpath) / f


def is_text(p: Path) -> bool:
    if p.suffix.lower() in BIN_EXT or p.stat().st_size > 8_000_000:
        return False
    try:
        b = p.read_bytes()
    except OSError:
        return False
    if b"\0" in b[:65536] and p.suffix.lower() not in (".rs", ".toml", ".ps1", ".sh", ".wxs", ".plist", ".in"):
        return False
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def protected(p: Path, root: Path) -> bool:
    rel = p.relative_to(root)
    return p.name in PROTECT_NAMES or p.name.startswith("LICENSE") or p.name.startswith("OFL") or (
        len(rel.parts) > 1 and rel.parts[-2] == "app-icon" and p.name == "LICENSE.txt")


def rename_paths(root: Path, up_id: str, launcher: bool):
    """git mv every file/folder whose name carries the upstream id or `ai.storyteller.`."""
    ids = [up_id] + ([k for k in APPS if k != up_id] if launcher else [])
    def new_name(name: str) -> str:
        n = name.replace("ai.storyteller.", "com.pintaz.")
        for i in ids:
            n = rename_own(n, i)
        return n
    # deepest first
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PROTECT_DIRS]
        for n in dirnames + filenames:
            entries.append(Path(dirpath) / n)
    entries.sort(key=lambda p: len(p.parts), reverse=True)
    for p in entries:
        nn = new_name(p.name)
        if nn != p.name and not protected(p, root):
            dst = p.with_name(nn)
            run("git", "mv", str(p.relative_to(root)), str(dst.relative_to(root)), cwd=root)


# ---------------------------------------------------------------------------------------------
# icons
def master_icon(zid: str):
    from PIL import Image
    p = HERE / "icons" / f"{zid}-1024.png"
    if not p.exists():
        make_master(zid, p)
    return Image.open(p).convert("RGBA")


def make_master(zid: str, out: Path):
    """Flat Z icon: cream rounded square, jade initial, mustard Z tab. Run once on the laptop;
    the PNG is committed so CI never re-draws it with other fonts."""
    from PIL import Image, ImageDraw, ImageFont
    S = 1024
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = 72
    if zid == "appz":
        d.rounded_rectangle([m, m, S - m, S - m], radius=200, fill=PALETTE["jade"])
        f = ImageFont.truetype(str(FONT_SERIF_BOLD), 700)
        d.text((S / 2, S / 2 + 20), "Z", font=f, fill=PALETTE["mustard"], anchor="mm")
    else:
        d.rounded_rectangle([m, m, S - m, S - m], radius=200, fill=PALETTE["cream"], outline=PALETTE["jade"], width=36)
        letter = zid[0].upper()
        f = ImageFont.truetype(str(FONT_SERIF_BOLD), 600)
        d.text((S / 2 - 70, S / 2 + 10), letter, font=f, fill=PALETTE["jade"], anchor="mm")
        # mustard Z tab, bottom right
        bx0, by0, bx1, by1 = S - m - 380, S - m - 380, S - m - 60, S - m - 60
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=70, fill=PALETTE["mustard"])
        fz = ImageFont.truetype(str(FONT_SANS_BOLD), 260)
        d.text(((bx0 + bx1) / 2, (by0 + by1) / 2 + 6), "Z", font=fz, fill=PALETTE["jade"], anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


FONT_SERIF_BOLD = Path(os.environ.get("Z_FONT_SERIF", "C:/Windows/Fonts/georgiab.ttf"))
FONT_SANS_BOLD = Path(os.environ.get("Z_FONT_SANS", "C:/Windows/Fonts/arialbd.ttf"))


def write_like(src_img, path: Path, key: str = ""):
    """Overwrite an existing image with the Z icon, same size and format. With `key` (the zid) the
    resized PNG is cached in icons/sized/, so every machine writes byte-identical files."""
    from PIL import Image
    ext = path.suffix.lower()
    if ext == ".png":
        try:
            with Image.open(path) as old:
                size = old.size
        except Exception:
            size = (512, 512)
        cache = HERE / "icons" / "sized" / f"{key}-{size[0]}x{size[1]}.png" if key else None
        if cache is not None and cache.exists():
            shutil.copyfile(cache, path)
            return
        src_img.resize(size, Image.LANCZOS).save(path, format="PNG")
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, cache)
    elif ext == ".ico":
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        src_img.resize((256, 256), Image.LANCZOS).save(path, format="ICO", sizes=sizes)
    elif ext == ".icns":
        src_img.save(path, format="ICNS")
    elif ext in (".jpg", ".jpeg", ".bmp"):
        with Image.open(path) as old:
            size = old.size
        bg = Image.new("RGB", size, PALETTE["paper"])
        s = min(size)
        ic = src_img.resize((s, s), Image.LANCZOS)
        bg.paste(ic, ((size[0] - s) // 2, (size[1] - s) // 2), ic)
        bg.save(path)


def _text_path(text: str, font: Path, size: float, x: float, baseline: float, anchor: str = "middle") -> str:
    """`text` as one SVG <path> (outlines, no font needed to show it)."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    f = TTFont(str(font))
    gs, cmap, upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    s = size / upm
    names = [cmap[ord(c)] for c in text]
    width = sum(gs[n].width for n in names) * s
    cx = x - (width / 2 if anchor == "middle" else 0)
    pen = SVGPathPen(gs)
    for n in names:
        gs[n].draw(TransformPen(pen, (s, 0, 0, -s, cx, baseline)))
        cx += gs[n].width * s
    return pen.getCommands()


def _cached_svg(name: str, make) -> str:
    p = HERE / "icons" / name
    if not p.exists():
        p.write_text(make(), encoding="utf-8")
    return p.read_text(encoding="utf-8")


def icon_svg(zid: str, small=False) -> str:
    jade, mustard, cream = "#1F4D3A", "#D3A250", "#F4EFE6"
    def make():
        if zid == "appz":
            z = _text_path("Z", FONT_SERIF_BOLD, 700, 512, 762)
            return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><rect x="72" y="72" width="880" height="880" rx="200" fill="{jade}"/>'
                    f'<path d="{z}" fill="{mustard}"/></svg>\n')
        L = _text_path(zid[0].upper(), FONT_SERIF_BOLD, 600, 442, 732)
        z = _text_path("Z", FONT_SANS_BOLD, 260, 732, 826)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><rect x="90" y="90" width="844" height="844" rx="190" fill="{cream}" stroke="{jade}" stroke-width="36"/>'
                f'<path d="{L}" fill="{jade}"/><rect x="572" y="572" width="320" height="320" rx="70" fill="{mustard}"/>'
                f'<path d="{z}" fill="{jade}"/></svg>\n')
    return _cached_svg(f"{zid}.svg", make)


def wordmark_svg(text: str, color: str) -> str:
    # 1038.05 x 108 keeps the aspect the launcher header was laid out for
    def make():
        d = _text_path(text, FONT_SERIF_BOLD, 104, 0, 88, anchor="start")
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1038.05 108"><path d="{d}" fill="{color}"/></svg>\n'
    return _cached_svg(f"wordmark-{text}-{color.strip('#')}.svg", make)


def replace_icons(root: Path, zid: str, launcher: bool):
    master = master_icon(zid)
    for d in [root / "assets" / "app-icon"]:
        if not d.exists():
            continue
        for p in walk(d):
            ext = p.suffix.lower()
            if ext in (".png", ".ico", ".icns", ".jpg", ".bmp"):
                write_like(master, p, zid)
            elif ext == ".svg":
                p.write_text(icon_svg(zid, "small" in p.name), encoding="utf-8")
    if launcher:
        d = root / "assets" / "app-icons"
        if d.exists():
            for p in d.glob("*.png"):
                write_like(master_icon(p.stem), p, p.stem)
    # any other picture named after an icon at the top of packaging/ (e.g. DMG backgrounds stay)
    readme = root / "assets" / "app-icon" / "README.md"
    if readme.exists():
        readme.write_text("Z app icon by PINTAZ TECHNOLOGIES (generated by .pintaz/rebrand.py; flat, cream / jade / mustard).\n", encoding="utf-8")


def replace_brand_assets(root: Path, zname: str, zid: str):
    """docs/brand/artcraft-*: the ArtCraft marks. Removed; our own Z art under assets/z-brand/
    (same file stems, so code that showed the mark now shows ours)."""
    from PIL import Image
    bd = root / "docs" / "brand"
    if not bd.exists():
        return
    zb = root / "assets" / "z-brand"
    zb.mkdir(parents=True, exist_ok=True)
    master = master_icon(zid if zid == "appz" else zid)
    # the upstream wordmark said "ArtCraft" (the suite); ours says "Z Apps" (AppZ keeps its own name)
    mark_text = zname if zid == "appz" else "Z Apps"
    for p in sorted(bd.iterdir()):
        if p.name == "LICENSE-brand.txt":
            continue
        stem = p.name.replace("artcraft-", "")
        dst = zb / stem
        if p.suffix == ".svg":
            if "logo" in stem:
                dst.write_text(wordmark_svg(mark_text, "#FFFFFF" if "white" in stem else "#1F4D3A"), encoding="utf-8")
            else:
                dst.write_text(icon_svg("appz" if zid == "appz" else zid), encoding="utf-8")
        elif p.suffix == ".png":
            with Image.open(p) as old:
                size = old.size
            if "logo" in stem:
                from PIL import ImageDraw, ImageFont
                im = Image.new("RGBA", size, (0, 0, 0, 0))
                dr = ImageDraw.Draw(im)
                f = ImageFont.truetype(str(FONT_SERIF_BOLD), max(10, int(size[1] * 0.8)))
                dr.text((0, size[1] / 2), mark_text, font=f, fill=(255, 255, 255) if "white" in stem else PALETTE["jade"], anchor="lm")
                im.save(dst)
            elif "black" in stem:
                # monochrome template icon (macOS menu bar): black Z on transparent
                from PIL import ImageDraw, ImageFont
                im = Image.new("RGBA", size, (0, 0, 0, 0))
                dr = ImageDraw.Draw(im)
                f = ImageFont.truetype(str(FONT_SANS_BOLD), int(size[1] * 0.9))
                dr.text((size[0] / 2, size[1] / 2), "Z", font=f, fill=(0, 0, 0, 255), anchor="mm")
                im.save(dst)
            else:
                master.resize(size, Image.LANCZOS).save(dst)
        run("git", "rm", "-q", "-f", str(p.relative_to(root)), cwd=root)
    note = bd / "README.md"
    note.write_text("The ArtCraft marks that upstream keeps here were removed from this fork, as "
                    "LICENSE-brand.txt requires for modified versions. Our own art is in assets/z-brand/.\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------
ABOUT_MARK = "PINTAZ-ABOUT"


def credit_line(up_id: str) -> str:
    return f"Based on {APPS[up_id][1]} by Storytold (ArtCraft), Apache-2.0. Changes by PINTAZ TECHNOLOGIES."


def add_about(root: Path, up_id: str, launcher: bool) -> list[str]:
    """Put "by PINTAZ" + the credit line under the About blurb ("<ZName> — …" label)."""
    zname = APPS[up_id][3]
    rx = re.compile(r'^(?P<ind>[ \t]*)ui\.label\(tl!\("' + re.escape(zname) + r' [—–-] [^"]*"\)\);[ \t]*$', re.M)
    hits = []
    for p in walk(root):
        if p.suffix != ".rs" or "test" in p.name:
            continue
        t = p.read_text(encoding="utf-8")
        if ABOUT_MARK in t:
            hits.append(str(p.relative_to(root)))
            continue
        def ins(m):
            ind = m.group("ind")
            return (m.group(0) + f"\n{ind}// {ABOUT_MARK}: required credit (Apache-2.0 change notice; ArtCraft brand licence)"
                    f"\n{ind}ui.label(egui::RichText::new(\"by PINTAZ\").strong());"
                    f"\n{ind}ui.weak(\"{credit_line(up_id)}\");")
        t2, n = rx.subn(ins, t, count=1)
        if n:
            p.write_text(t2, encoding="utf-8")
            hits.append(str(p.relative_to(root)))
    if not hits:
        hits = about_fallback(root, up_id)
    return hits


_STR = re.compile(r'r#"(?:.|\n)*?"#|"(?:\\.|[^"\\])*"')


def about_fallback(root: Path, up_id: str) -> list[str]:
    """Second anchor: in a file that draws "About <ZName>", the first `ui.…(` statement that shows
    the version (`{version}` / CARGO_PKG_VERSION / build_info). Insert the credit after that whole
    statement (parentheses matched outside string literals), at the statement's indent."""
    zname = APPS[up_id][3]
    cands = []
    for p in walk(root):
        if p.suffix != ".rs" or "test" in p.name or "/i18n" in p.as_posix():
            continue
        t = p.read_text(encoding="utf-8")
        if f"About {zname}" in t or p.name == "about.rs" or '"about_tab"' in t:
            cands.append((0 if p.name == "about.rs" else 1, p, t))
    start_rx = re.compile(r"^\s*(?:(?:ui|p|painter)\.\w+\(|crate::[\w:]+\()")
    for _, p, t in sorted(cands, key=lambda c: (c[0], str(c[1]))):
        lines = t.split("\n")
        for i, line in enumerate(lines):
            if not re.search(r"\{version\}|\{v\}|CARGO_PKG_VERSION|build_info|long_version|version_line\(", line):
                continue
            s = i
            while s >= 0 and not start_rx.match(lines[s]):
                if re.search(r"[;{}]\s*$", lines[s]) and s != i:
                    s = -1
                    break
                s -= 1
            if s < 0:
                continue
            depth, e = 0, s
            while e < len(lines):
                depth += _STR.sub('""', lines[e]).count("(") - _STR.sub('""', lines[e]).count(")")
                if depth <= 0 and lines[e].rstrip().endswith(";"):
                    break
                e += 1
            if e >= len(lines):
                continue
            ind = re.match(r"^(\s*)", lines[s]).group(1)
            rich = "egui::RichText::new(\"by PINTAZ\").strong()" if "egui::" in t else "\"by PINTAZ\""
            lines[e + 1:e + 1] = [f"{ind}// {ABOUT_MARK}: required credit (Apache-2.0 change notice; ArtCraft brand licence)",
                                  f"{ind}ui.label({rich});", f"{ind}ui.label(\"{credit_line(up_id)}\");"]
            p.write_text("\n".join(lines), encoding="utf-8")
            return [str(p.relative_to(root)) + f" (fallback, after line {e + 1})"]
    return []


def append_notice(root: Path, up_id: str):
    n = root / "NOTICE"
    t = n.read_text(encoding="utf-8") if n.exists() else ""
    if "PINTAZ TECHNOLOGIES" in t:
        return
    up_repo, up_display, zid, zname = APPS[up_id]
    t += (f"\n\n----------------------------------------------------------------------------------------\n"
          f"{zname} (github.com/{OWNER}/{zid})\n\n"
          f"{credit_line(up_id)}\n\n"
          f"{zname} is a modified version of {up_display} (https://github.com/storytold/{up_repo}). Changes made by\n"
          f"PINTAZ TECHNOLOGIES (Malaysia), applied by .pintaz/rebrand.py on top of each upstream version:\n"
          f"  - renamed to {zname} (binaries, installers, bundle ids com.pintaz.*, data folders);\n"
          f"  - the ArtCraft name, wordmark and marks removed (docs/brand/LICENSE-brand.txt), new Z icons;\n"
          f"  - help/website links point to this fork; the About screen states the credit above;\n"
          f"  - our own release and upstream-sync workflows (.github/workflows/*-z.yml).\n"
          f"The licence files (LICENSE-MIT, LICENSE-APACHE) and all upstream copyright notices are unchanged.\n")
    n.write_text(t, encoding="utf-8")


def write_readme(root: Path, up_id: str):
    up_repo, up_display, zid, zname = APPS[up_id]
    up = root / "README.md"
    (root / "README.md").write_text(
        f"# {zname}\n\nFree app by PINTAZ. Download: the [latest release](https://github.com/{OWNER}/{zid}/releases/latest)"
        f"{' (one download gets all the Z apps)' if zid == 'appz' else ''}.\n\n"
        f"{credit_line(up_id)} See NOTICE, LICENSE-MIT and LICENSE-APACHE.\n\n"
        f"This repository follows upstream (`storytold/{up_repo}`) through `.github/workflows/upstream-sync-z.yml`, "
        f"which re-applies `.pintaz/rebrand.py` and opens a pull request. Builds: `.github/workflows/release-z.yml` "
        f"(unsigned Windows x64 MSI + portable zip, macOS universal DMG).\n", encoding="utf-8")


def write_workflows(root: Path, up_id: str):
    up_repo, up_display, zid, zname = APPS[up_id]
    wf = root / ".github" / "workflows"
    if wf.exists():
        for p in wf.iterdir():
            if p.is_file() and not p.name.endswith("-z.yml"):
                run("git", "rm", "-q", "-f", str(p.relative_to(root)), cwd=root)
    wf.mkdir(parents=True, exist_ok=True)
    fonts_ref = upstream_fonts_ref(root)
    for name in ("release-z.yml", "upstream-sync-z.yml"):
        t = (HERE / "templates" / name).read_text(encoding="utf-8")
        t = (t.replace("@ZID@", zid).replace("@ZNAME@", zname).replace("@UPREPO@", up_repo).replace("@UPID@", up_id)
              .replace("@FONTSREF@", fonts_ref).replace("@ZUPPER@", zid.upper()))
        (wf / name).write_text(t, encoding="utf-8")


_FONTS_REF = {}


def upstream_fonts_ref(root: Path) -> str:
    return _FONTS_REF.get("ref", "")


def capture_fonts_ref(root: Path):
    p = root / ".github" / "workflows" / "release.yml"
    if p.exists():
        m = re.search(r"craft-fonts-ref:\s*([0-9a-f]{7,40})", p.read_text(encoding="utf-8"))
        if m:
            _FONTS_REF["ref"] = m.group(1)


# ---------------------------------------------------------------------------------------------
def launcher_patches(root: Path) -> list[str]:
    """Release feed (ArtCraft's server) and the screenshot downloads (ArtCraft-branded pictures) off;
    no ArtCraft social links. Each patch must apply exactly once."""
    done = []
    def patch(rel, old_rx, new, flags=0):
        p = root / rel
        t = p.read_text(encoding="utf-8")
        t2, n = re.subn(old_rx, new, t, count=1, flags=flags)
        if n != 1:
            raise SystemExit(f"launcher patch did not apply: {rel}: {old_rx}")
        p.write_text(t2, encoding="utf-8")
        done.append(rel)
    patch("crates/core/src/feed.rs", r'pub const FEED_URL: &str = "[^"]*";', 'pub const FEED_URL: &str = ""; // PINTAZ: ArtCraft release feed off (GitHub only)')
    patch("crates/native/src/backend.rs", r"(fn fetch_feed\([^)]*\) -> FeedFetch \{\n)",
          r"\1    if url.is_empty() {\n        return FeedFetch::Failed; // PINTAZ: feed off\n    }\n")
    # our tags are v<upstream>-z<N>: read the -zN as build metadata, not as a pre-release
    zcode = ("    // PINTAZ: v1.2.3-z1 is our build mark on upstream 1.2.3, not a pre-release.\n"
             "    let z = t.rfind(\"-z\").filter(|&i| i + 2 < t.len() && t[i + 2..].bytes().all(|b| b.is_ascii_digit()));\n"
             "    let zfree = z.map(|i| format!(\"{}+{}\", &t[..i], &t[i + 1..]));\n"
             "    let t = zfree.as_deref().unwrap_or(t);\n")
    patch("crates/core/src/version.rs", r"    let t = t\.strip_prefix\(\['v', 'V'\]\)\.unwrap_or\(t\);\n",
          lambda m: m.group(0) + zcode)
    patch("crates/core/src/details.rs", r'\.map\(\|s\| format!\("\{SCREENSHOTS_BASE\}/\{SCREENSHOTS_REV\}/\{\}/\{\}\.jpg", self\.id, s\.key\)\)',
          '.and(None::<String>) // PINTAZ: upstream screenshots show the upstream names; off')
    patch("crates/core/src/catalog.rs", r"pub const SOCIAL: \[\(&str, &str\); 5\] = \[[^\]]*\];",
          "pub const SOCIAL: [(&str, &str); 0] = []; // PINTAZ: no upstream social accounts", flags=re.S)
    # the launcher has no About window: the credit goes under the Settings title (name + version)
    credit = (lambda m: m.group(0) + f"\n{m.group(1)}// {ABOUT_MARK}: required credit (Apache-2.0 change notice; ArtCraft brand licence)"
              f"\n{m.group(1)}ui.label(egui::RichText::new(\"by PINTAZ\").strong());"
              f"\n{m.group(1)}ui.weak(\"{credit_line('artcraft-launcher')}\");")
    patch("crates/ui-egui/src/dialogs.rs", r'^([ \t]*)Self::title\(ui, Some\(crate::icons::artcraft_mark\(\)\), tl!\("Settings"\)[^\n]*;$', credit, flags=re.M)
    return done


def leftovers(root: Path) -> list[str]:
    out = []
    for p in walk(root):
        if protected(p, root) or not is_text(p):
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(("docs/", "book/", ".pintaz/")) or rel.endswith(".md"):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            if "ArtCraft" in line or "getartcraft" in line or "discord.gg" in line:
                out.append(f"{rel}:{i}: {line.strip()[:160]}")
    return out


def main():
    root = Path(sys.argv[1]).resolve()
    up_id = sys.argv[2]
    launcher = up_id == "artcraft-launcher"
    up_repo, up_display, zid, zname = APPS[up_id]
    capture_fonts_ref(root)

    write_workflows(root, up_id)
    replace_brand_assets(root, zname, zid)
    rename_paths(root, up_id, launcher)
    for p in walk(root):
        if protected(p, root) or not is_text(p):
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(".github/workflows/") and rel.endswith("-z.yml"):
            continue
        t = p.read_text(encoding="utf-8")
        t2 = transform_text(t, up_id, launcher, p)
        if t2 != t:
            p.write_bytes(t2.encode("utf-8"))
    replace_icons(root, zid, launcher)
    about = add_about(root, up_id, launcher)
    lp = launcher_patches(root) if launcher else []
    append_notice(root, up_id)
    write_readme(root, up_id)
    # ship the tool inside the fork for the weekly sync
    dst = root / ".pintaz"
    dst.mkdir(exist_ok=True)
    shutil.copy2(HERE / "rebrand.py", dst / "rebrand.py")
    for sub in ("templates", "icons"):
        if (dst / sub).exists():
            shutil.rmtree(dst / sub)
        shutil.copytree(HERE / sub, dst / sub)
    left = leftovers(root)
    rep = [f"rebrand {up_id} -> {zname}", f"about credit inserted in: {about or 'NOT FOUND'}", f"launcher patches: {lp}",
           f"lines still naming ArtCraft/getartcraft/discord (non-doc): {len(left)}"] + left
    (dst / "rebrand-report.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep[:4]))
    print("\n".join(left[:80]))


if __name__ == "__main__":
    main()

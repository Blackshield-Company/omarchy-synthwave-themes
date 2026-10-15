#!/usr/bin/env python3
"""Layout, palette, contrast, config-syntax and secret checks. Stdlib only."""
from __future__ import annotations

import re
import struct
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import palette as P  # noqa: E402

THEME_FILES = ["colors.toml", "icons.theme", "neovim.lua", "shell.lock.toml", "preview.png"]
EXTRA_FILES = ["alacritty.toml", "kitty.conf", "ghostty.conf", "hyprland.conf",
               "waybar.css", "mako.ini", "walker.css", "btop.theme"]
# Files Omarchy strips from git-installed themes or renders itself; don't ship them in themes/.
BANNED = ["hyprland.lua", "alacritty.toml", "kitty.conf", "ghostty.conf", "foot.ini", "vscode.json"]
YARU = {"Yaru-blue", "Yaru-magenta", "Yaru-red", "Yaru-purple", "Yaru-yellow", "Yaru-sage",
        "Yaru-olive", "Yaru-wartybrown", "Yaru-gray", "Yaru-grey"}
RGBA = re.compile(r"^rgba?\([0-9a-fA-F]{6,8}\)$")
errors: list[str] = []


def err(msg):
    errors.append(msg)


def image_size(p: Path):
    b = p.read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    i = 2
    while i < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


def check_palette(pal, path):
    c, meta = pal.get("colors", {}), pal.get("meta", {})
    for k in ("name", "slug", "icons", "nvim_base", "art"):
        if k not in meta:
            err(f"{path.name}: meta.{k} missing")
    if meta.get("slug") != path.stem:
        err(f"{path.name}: slug must match filename")
    if meta.get("icons") not in YARU:
        err(f"{path.name}: icons must be a shipped Yaru variant")
    if c.get("mode") != "dark":
        err(f"{path.name}: mode must be dark")
    for k in P.COLOR_KEYS:
        if not P.HEX.match(str(c.get(k, ""))):
            err(f"{path.name}: {k} missing or not #rrggbb")
    for k in ("hyprland_active_border", "hyprland_inactive_border"):
        parts = str(c.get(k, "")).split()
        if not parts or not all(RGBA.match(p) or re.match(r"^\d+deg$", p) for p in parts):
            err(f"{path.name}: {k} is not a Hyprland color/gradient")
    if errors:
        return
    for fg, bg, r, need, good in P.contrast_report(c):
        if not good:
            err(f"{path.name}: contrast {fg} on {bg} = {r:.2f} < {need}")


def check_theme(slug):
    d = P.ROOT / "themes" / slug
    for f in THEME_FILES:
        if not (d / f).is_file() or (d / f).stat().st_size == 0:
            err(f"themes/{slug}: missing {f}")
    for f in BANNED:
        if (d / f).exists():
            err(f"themes/{slug}: ships {f} (stripped or rendered by Omarchy)")
    try:
        colors = tomllib.loads((d / "colors.toml").read_text())
        pal = P.load(P.PALETTES / f"{slug}.toml")["colors"]
        for k, v in colors.items():
            if pal.get(k) != v:
                err(f"themes/{slug}/colors.toml: {k} out of sync with palette (run generate.py)")
        tomllib.loads((d / "shell.lock.toml").read_text())
    except (tomllib.TOMLDecodeError, OSError) as e:
        err(f"themes/{slug}: toml {e}")
    icons = (d / "icons.theme").read_text().strip() if (d / "icons.theme").exists() else ""
    if icons not in YARU:
        err(f"themes/{slug}/icons.theme: {icons!r} is not a shipped Yaru variant")
    bgs = sorted((d / "backgrounds").glob("*.jpg"))
    if not bgs:
        err(f"themes/{slug}: no backgrounds")
    for b in bgs:
        if image_size(b) != P.DEFAULT_RES:
            err(f"{b.relative_to(P.ROOT)}: not {P.DEFAULT_RES}")
    for w, h in P.RESOLUTIONS:
        rd = P.ROOT / "wallpapers" / slug / f"{w}x{h}"
        imgs = sorted(rd.glob("*.jpg"))
        if len(imgs) != len(bgs):
            err(f"wallpapers/{slug}/{w}x{h}: expected {len(bgs)} images, found {len(imgs)}")
        for i in imgs:
            if image_size(i) != (w, h):
                err(f"{i.relative_to(P.ROOT)}: wrong size {image_size(i)}")
    lua = (d / "neovim.lua").read_text() if (d / "neovim.lua").exists() else ""
    if lua.count("{") != lua.count("}") or lua.count("(") != lua.count(")"):
        err(f"themes/{slug}/neovim.lua: unbalanced brackets")


def check_extras(slug):
    d = P.ROOT / "extras" / slug
    for f in EXTRA_FILES:
        if not (d / f).is_file():
            err(f"extras/{slug}: missing {f}")
            return
    try:
        a = tomllib.loads((d / "alacritty.toml").read_text())
        if len(a["colors"]["normal"]) != 8 or len(a["colors"]["bright"]) != 8:
            err(f"extras/{slug}/alacritty.toml: need 8 normal + 8 bright")
    except (tomllib.TOMLDecodeError, KeyError) as e:
        err(f"extras/{slug}/alacritty.toml: {e}")
    kv = {
        "kitty.conf": re.compile(r"^[a-z_0-9]+ #[0-9a-fA-F]{6}$"),
        "ghostty.conf": re.compile(r"^[a-z-]+ = (#[0-9a-fA-F]{6}|\d{1,2}=#[0-9a-fA-F]{6})$"),
        "mako.ini": re.compile(r"^([a-z-]+=.+|\[[a-z=]+\])$"),
        "btop.theme": re.compile(r'^theme\[[a-z_]+\]="#[0-9a-fA-F]{6}"$'),
        "hyprland.conf": re.compile(r"^(\$\w+ = .+|[a-z_]+ \{|\}|\s+[a-z_.]+ = .+)$"),
    }
    for f, rx in kv.items():
        for n, line in enumerate((d / f).read_text().splitlines(), 1):
            if line.strip() and not line.lstrip().startswith("#") and not rx.match(line):
                err(f"extras/{slug}/{f}:{n}: bad line {line!r}")
    kitty = (d / "kitty.conf").read_text()
    if any(f"color{i} " not in kitty for i in range(16)):
        err(f"extras/{slug}/kitty.conf: missing color0-15")
    for f in ("waybar.css", "walker.css"):
        css = re.sub(r"/\*.*?\*/", "", (d / f).read_text(), flags=re.S)
        if css.count("{") != css.count("}"):
            err(f"extras/{slug}/{f}: unbalanced braces")
        defined = set(re.findall(r"@define-color ([\w-]+)", css))
        for ref in re.findall(r"@([\w-]+)", css):
            if ref != "define-color" and ref not in defined:
                err(f"extras/{slug}/{f}: undefined color @{ref}")
        for line in css.splitlines():
            if line.startswith("@define-color") and not re.match(r"^@define-color [\w-]+ #[0-9a-fA-F]{6};$", line):
                err(f"extras/{slug}/{f}: bad {line!r}")


def check_repo():
    pat = re.compile(r"gh[opsu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY")
    for p in P.ROOT.rglob("*"):
        if not p.is_file() or {".git", ".venv"} & set(p.parts) or p.suffix in (".jpg", ".png"):
            continue
        try:
            text = p.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if pat.search(text):
            err(f"{p.relative_to(P.ROOT)}: looks like a secret")


def main():
    pal_paths = sorted(P.PALETTES.glob("*.toml"))
    if len(pal_paths) < 3:
        err("need at least 3 palettes")
    slugs = []
    for path in pal_paths:
        pal = P.load(path)
        check_palette(pal, path)
        slugs.append(path.stem)
    shipped = sorted(x.name for x in (P.ROOT / "themes").iterdir() if x.is_dir())
    if shipped != slugs:
        err(f"themes/ {shipped} != palettes {slugs}")
    for s in slugs:
        check_theme(s)
        check_extras(s)
    check_repo()
    if errors:
        print("\n".join("FAIL: " + e for e in errors))
        return 1
    print(f"ok: {len(slugs)} themes, layout/contrast/syntax clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

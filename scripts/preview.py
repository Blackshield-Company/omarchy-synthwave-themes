"""Headless mock-desktop preview: graded wallpaper, bar, terminal window, swatches."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import palette as P

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
]


def font(size):
    for f in FONT_CANDIDATES + [str(p) for p in Path("/usr/share/fonts").rglob("*Mono*Regular*.ttf")]:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def first_color(spec: str) -> str:
    s = spec.split()[0]
    return "#" + s[s.index("(") + 1:s.index("(") + 7] if "(" in s else s


def render(pal: dict, size=(1920, 1080)) -> Path:
    c, meta = pal["colors"], pal["meta"]
    slug = meta["slug"]
    w, h = size
    bgs = sorted((P.ROOT / "themes" / slug / "backgrounds").glob("*.jpg"))
    img = (Image.open(bgs[0]).convert("RGB").resize(size) if bgs
           else Image.new("RGB", size, c["background"]))
    d = ImageDraw.Draw(img)
    f, fs = font(22), font(18)
    # bar
    d.rectangle([0, 0, w, 34], fill=c["background"])
    d.line([0, 34, w, 34], fill=c["accent"], width=2)
    x = 16
    for i in range(1, 6):
        col = c["accent"] if i == 1 else c["muted"]
        d.text((x, 6), str(i), fill=col, font=f)
        x += 34
    d.text((w // 2 - 40, 6), "01:13", fill=c["cyan"], font=f)
    d.text((w - 330, 6), "cpu 12%  mem 38%  ♪ 70%", fill=c["foreground"], font=fs)
    # terminal window with gradient-ish border (two accent stops)
    tx0, ty0, tx1, ty1 = 140, 110, 1080, 720
    stops = [first_color(s) for s in c["hyprland_active_border"].split() if s.startswith("rgba")]
    for k in range(3):
        d.rectangle([tx0 - k, ty0 - k, tx1 + k, ty1 + k], outline=stops[k % len(stops)])
    d.rectangle([tx0 + 1, ty0 + 1, tx1 - 1, ty1 - 1], fill=c["background"])
    lines = [
        [(c["green"], "synth@box"), (c["foreground"], ":"), (c["blue"], "~/themes"), (c["accent"], " ❯ "), (c["foreground"], "ls")],
        [(c["blue"], "backgrounds/  "), (c["foreground"], "colors.toml  "), (c["magenta"], "neovim.lua  "), (c["yellow"], "preview.png")],
        [(c["accent"], " ❯ "), (c["foreground"], "git status")],
        [(c["green"], "  modified: "), (c["foreground"], "palettes/"), (c["cyan"], slug + ".toml")],
        [(c["red"], "  deleted:  "), (c["muted"], "old-theme.conf")],
        [(c["muted"], "  # comments stay readable (AA)")],
        [(c["orange"], "  warning: "), (c["foreground"], "neon levels critical")],
        [(c["accent"], " ❯ "), (c["bright_foreground"], "▌")],
    ]
    y = ty0 + 24
    for line in lines:
        x = tx0 + 24
        for col, txt in line:
            d.text((x, y), txt, fill=col, font=f)
            x += d.textlength(txt, font=f)
        y += 36
    # swatches
    y = ty1 - 120
    for row, names in enumerate((P.ANSI_NAMES, ["bright_" + n for n in P.ANSI_NAMES])):
        for i, n in enumerate(names):
            x = tx0 + 24 + i * 108
            d.rectangle([x, y + row * 48, x + 96, y + row * 48 + 40], fill=c[n])
    # side card: notification
    nx0, ny0 = w - 520, 70
    d.rectangle([nx0, ny0, w - 30, ny0 + 110], fill=c["background"], outline=c["accent"], width=2)
    d.text((nx0 + 20, ny0 + 18), meta["name"], fill=c["accent"], font=font(28))
    d.text((nx0 + 20, ny0 + 64), "Omarchy synthwave theme", fill=c["foreground"], font=fs)
    out = P.ROOT / "themes" / slug / "preview.png"
    img.save(out, optimize=True)
    return out

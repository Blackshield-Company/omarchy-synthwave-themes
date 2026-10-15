"""Synthwave grade for brand art: duotone, sky glow, grid horizon, scanlines."""
from __future__ import annotations

import gc
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

import palette as P


def cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.4))


def vgradient(size, top, bottom, top_a=255, bottom_a=255) -> Image.Image:
    w, h = size
    col = Image.new("RGBA", (1, h))
    t, b = P.rgb(top), P.rgb(bottom)
    for y in range(h):
        k = y / max(h - 1, 1)
        col.putpixel((0, y), tuple(int(t[i] + (b[i] - t[i]) * k) for i in range(3))
                     + (int(top_a + (bottom_a - top_a) * k),))
    return col.resize(size)


def grid(size, color, horizon_y) -> Image.Image:
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rgb = P.rgb(color)
    lw = max(1, h // 540)
    depth = h - horizon_y
    for i in range(1, 15):  # horizontal lines, denser near the horizon
        y = horizon_y + int(depth * (i / 14) ** 2.2)
        d.line([(0, y), (w, y)], fill=rgb + (230,), width=lw)
    vp = w / 2
    for i in range(-24, 25):  # verticals converge to a vanishing point
        x = vp + i * (w / 16)
        d.line([(vp + i * (w / 160), horizon_y), (x, h)], fill=rgb + (210,), width=lw)
    fade = vgradient(size, "#000000", "#000000", 60, 255).getchannel("A")
    mask = Image.new("L", size, 0)
    mask.paste(fade.crop((0, 0, w, depth)).resize((w, depth)), (0, horizon_y))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    glow = layer.filter(ImageFilter.GaussianBlur(max(2, h // 300)))
    return Image.alpha_composite(glow, layer)


def scanlines(size, step=3, alpha=38) -> Image.Image:
    tile = Image.new("RGBA", (1, step), (0, 0, 0, 0))
    tile.putpixel((0, 0), (0, 0, 0, alpha))
    return _tile(tile, size)


def _tile(tile, size):
    w, h = size
    out = Image.new("RGBA", size)
    strip = tile.resize((w, tile.height), Image.NEAREST)
    for y in range(0, h, tile.height):
        out.paste(strip, (0, y))
    return out


def grade(src: Image.Image, pal: dict, size: tuple[int, int]) -> Image.Image:
    g = pal["grade"]
    w, h = size
    base = cover(src.convert("RGB"), size)
    duo = ImageOps.colorize(ImageOps.autocontrast(base.convert("L"), cutoff=1),
                            black=g["shadow"], white=g["highlight"], mid=g["sky"])
    img = Image.blend(base, duo, g["mix"]).convert("RGBA")
    del base, duo
    horizon_y = int(h * 0.68)
    sky = vgradient((w, horizon_y), g["sky"], g["horizon"], 120, 40)
    img.alpha_composite(sky, (0, 0))
    band = vgradient((w, h // 6), g["horizon"], g["horizon"], 0, 0)
    band.putalpha(Image.linear_gradient("L").resize((w, h // 6)).point(
        lambda v: int(90 * (1 - abs(v - 127.5) / 127.5))))
    img.alpha_composite(band, (0, horizon_y - h // 12))
    floor = vgradient((w, h - horizon_y), pal["colors"]["darker_background"],
                      pal["colors"]["darker_background"], 0, 170)
    img.alpha_composite(floor, (0, horizon_y))
    img.alpha_composite(grid(size, g["grid"], horizon_y))
    img.alpha_composite(scanlines(size))
    return img.convert("RGB")


def render_wallpapers(pal: dict, art_dir: Path) -> list[Path]:
    slug = pal["meta"]["slug"]
    out = []
    for idx, name in enumerate(pal["meta"]["art"], 1):
        src = Image.open(art_dir / name)
        src.load()
        stem = f"{idx:02d}-{Path(name).stem.replace('-1920x1080', '')}"
        for size in P.RESOLUTIONS:
            img = grade(src, pal, size)
            res = f"{size[0]}x{size[1]}"
            dest = P.ROOT / "wallpapers" / slug / res / f"{stem}.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, quality=86, optimize=True, progressive=True)
            out.append(dest)
            if size == P.DEFAULT_RES:
                bg = P.ROOT / "themes" / slug / "backgrounds" / f"{stem}.jpg"
                bg.parent.mkdir(parents=True, exist_ok=True)
                img.save(bg, quality=86, optimize=True, progressive=True)
            del img
            gc.collect()
        src.close()
    return out

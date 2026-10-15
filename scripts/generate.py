#!/usr/bin/env python3
"""Render themes from palettes/*.toml.

  generate.py                 configs only (theme/ + extras/), needs jinja2
  generate.py --wallpapers    also render the procedural synthwave wallpapers (needs Pillow + numpy)
  generate.py --previews      also render previews from the generated wallpapers

Wallpapers are drawn from scratch with the [scene] colors in each palette. Scene geometry
lives in height units (u = horizontal offset from the center, v = 0 top .. 1 bottom), so
every size renders crisp natively and ultrawides reveal more scene to the sides instead of
stretching. All randomness is seeded and generated independently of the output size.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

sys.path.insert(0, str(Path(__file__).resolve().parent))
import palette as P  # noqa: E402

TPL = P.ROOT / "templates"


def render_configs(pal: dict) -> list[Path]:
    env = Environment(loader=FileSystemLoader(str(TPL)), undefined=StrictUndefined,
                      keep_trailing_newline=True)
    c, meta = pal["colors"], pal["meta"]
    ctx = {"c": c, "meta": meta, "ansi": P.ansi16(c), "ansi_names": P.ANSI_NAMES}
    written = []
    for sub, dest in (("theme", P.ROOT / "themes" / meta["slug"]),
                      ("extras", P.ROOT / "extras" / meta["slug"])):
        dest.mkdir(parents=True, exist_ok=True)
        for t in sorted((TPL / sub).glob("*.j2")):
            out = dest / t.name[:-3]
            out.write_text(env.get_template(f"{sub}/{t.name}").render(**ctx))
            written.append(out)
    return written


# ---------------------------------------------------------------- procedural wallpapers

SS = 2          # supersampling for line/shape masks; downsampled with a box filter
U_MAX = 2.0     # scene is laid out over u in [-U_MAX, U_MAX]; 32:9 needs about 1.78


def _c(hexstr):
    import numpy as np
    return np.array(P.rgb(hexstr), np.float32) / 255.0


class Canvas:
    """Float RGB canvas in scene units. One per render; drop it when done."""

    def __init__(self, w, h):
        import numpy as np
        self.np = np
        self.w, self.h = w, h
        self.img = np.zeros((h, w, 3), np.float32)
        self.vs = (np.arange(h, dtype=np.float32) + 0.5) / h  # v of each row

    def pt(self, u, v, k=1):
        return ((self.w / 2 + u * self.h) * k, v * self.h * k)

    def px(self, length):
        return length * self.h

    def mask(self, draw_fn):
        """draw_fn(draw, pt, width) draws in 255 on a supersampled L mask."""
        from PIL import Image, ImageDraw
        m = Image.new("L", (self.w * SS, self.h * SS), 0)
        d = ImageDraw.Draw(m)
        draw_fn(d, lambda u, v: self.pt(u, v, SS), lambda wd: max(1, round(wd * self.h * SS)))
        out = m.resize((self.w, self.h), Image.BOX)
        m.close()
        return out

    def arr(self, m, alpha=1.0):
        return self.np.asarray(m, dtype=self.np.float32) * (alpha / 255.0)

    def paint(self, m, color, alpha=1.0):
        a = (m if isinstance(m, self.np.ndarray) else self.arr(m)) * alpha
        col = color if isinstance(color, self.np.ndarray) and color.ndim > 1 else _c(color) if isinstance(color, str) else color
        self.img += (col - self.img) * a[..., None]

    def add(self, m, color, k=1.0):
        a = m if isinstance(m, self.np.ndarray) else self.arr(m)
        self.img += a[..., None] * (_c(color) * k)

    def glow(self, m, color, radii=((0.003, 0.9), (0.012, 0.6), (0.04, 0.35))):
        from PIL import Image, ImageFilter
        if isinstance(m, self.np.ndarray):
            m = Image.fromarray(self.np.clip(m * 255, 0, 255).astype("uint8"))
        for r, k in radii:
            self.add(m.filter(ImageFilter.GaussianBlur(self.px(r))), color, k)

    def vgradient(self, stops, y0=0.0, y1=1.0):
        """Fill rows between v=y0..y1 with color stops [(v, '#hex'), ...]."""
        np = self.np
        vs = np.array([s[0] for s in stops], np.float32)
        cols = np.stack([_c(s[1]) for s in stops])
        r0, r1 = int(round(y0 * self.h)), int(round(y1 * self.h))
        v = self.vs[r0:r1]
        g = np.stack([np.interp(v, vs, cols[:, i]) for i in range(3)], -1)
        self.img[r0:r1] = g[:, None, :]

    def column_gradient(self, stops):
        np = self.np
        vs = np.array([s[0] for s in stops], np.float32)
        cols = np.stack([_c(s[1]) for s in stops])
        return np.stack([np.interp(self.vs, vs, cols[:, i]) for i in range(3)], -1)[:, None, :]

    def row_fade(self, m, v0, v1, power=1.0):
        """Multiply a mask by a 0..1 ramp from v0 to v1 (for grid fade-in at the horizon)."""
        np = self.np
        a = self.arr(m) if not isinstance(m, np.ndarray) else m
        ramp = np.clip((self.vs - v0) / (v1 - v0), 0, 1) ** power
        return a * ramp[:, None]

    def finish(self, seed):
        from PIL import Image
        np = self.np
        rng = np.random.default_rng(seed)
        noise = rng.random((self.h, self.w), dtype=np.float32) - 0.5  # dither against banding
        self.img *= 255.0
        self.img += noise[..., None] * 1.2
        del noise
        np.clip(self.img, 0, 255, out=self.img)
        out = Image.fromarray(self.img.astype(np.uint8))
        self.img = None
        return out


def perspective_grid(cv, hz, color, spacing=0.12, rows=36, width=0.0016, base=0.9):
    """Glowing floor grid: horizontals bunch toward the horizon, verticals meet at (0, hz)."""
    depth = 1.0 - hz
    n_vert = int(U_MAX / spacing * 6)

    def draw(d, pt, wd):
        lw = wd(width)
        for n in range(rows):
            v = hz + depth / (1 + n * 0.42) - depth * 0.04
            if v <= hz:
                break
            d.line([pt(-U_MAX * 1.2, v), pt(U_MAX * 1.2, v)], fill=255, width=lw)
        for i in range(-n_vert, n_vert + 1):
            d.line([pt(0, hz), pt(i * spacing * 2.2, hz + depth * 2.2)], fill=255, width=lw)

    m = cv.row_fade(cv.mask(draw), hz, hz + depth * 0.7, 1.6)
    cv.paint(m, color, base)
    cv.glow(m, color, ((0.002, 0.7), (0.008, 0.4), (0.03, 0.15)))
    # bright horizon seam
    seam = cv.mask(lambda d, pt, wd: d.line([pt(-U_MAX, hz), pt(U_MAX, hz)], fill=255, width=wd(0.0022)))
    cv.add(seam, color, 0.9)
    cv.glow(seam, color, ((0.004, 0.6), (0.02, 0.3), (0.07, 0.15)))


def stars(cv, rng, count, v_max, color, avoid=None):
    us = rng.uniform(-U_MAX, U_MAX, count)
    vs = v_max * rng.random(count) ** 1.5
    rs = rng.uniform(0.0006, 0.0017, count)
    bs = rng.uniform(0.25, 1.0, count)

    def draw(d, pt, wd):
        for u, v, r, b in zip(us, vs, rs, bs):
            if avoid and avoid(u, v):
                continue
            x, y = pt(u, v)
            rr = max(r * cv.h * SS, 0.8)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=int(255 * b))

    m = cv.mask(draw)
    cv.add(m, color, 1.0)
    cv.glow(m, color, ((0.002, 0.8),))


def scene_neon_horizon(cv, s, seed):
    np = cv.np
    rng = np.random.default_rng(seed)
    hz = 0.64
    cv.vgradient([(0, s["sky_top"]), (0.42, s["sky_mid"]), (hz, s["sky_low"])], 0, hz)
    cv.vgradient([(hz, s["floor"]), (1, s["floor"])], hz, 1)
    sx, sy, sr = 0.0, hz - 0.13, 0.205
    stars(cv, rng, 700, hz - 0.08, s["star"], avoid=lambda u, v: (u - sx) ** 2 + (v - sy) ** 2 < (sr * 1.25) ** 2)
    # haze band along the horizon
    band = cv.mask(lambda d, pt, wd: d.rectangle([pt(-U_MAX, hz - 0.03), pt(U_MAX, hz)], fill=255))
    cv.glow(band, s["sun_mid"], ((0.05, 0.2),))

    # striped sun
    def sun(d, pt, wd):
        x, y = pt(sx, sy)
        r = sr * cv.h * SS
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        gy = sy - sr * 0.15
        k = 0
        while gy < hz:
            t = 0.004 + 0.0022 * k
            d.rectangle([pt(sx - sr - 0.01, gy), pt(sx + sr + 0.01, gy + t)], fill=0)
            gy += t + 0.024 - 0.0012 * k
            k += 1
        d.rectangle([pt(-U_MAX, hz), pt(U_MAX, 1.0)], fill=0)

    m = cv.mask(sun)
    col = cv.column_gradient([(sy - sr, s["sun_top"]), (sy, s["sun_mid"]), (hz, s["sun_bottom"])])
    cv.glow(m, s["sun_mid"], ((0.02, 0.45), (0.08, 0.35)))
    cv.paint(m, col)
    del col

    # wireframe mountains on both flanks, nothing within |u| < 0.33
    cols, rows = 46, 6
    for side in (-1, 1):
        us = 0.30 + np.linspace(0, 1, cols) ** 1.15 * (U_MAX - 0.25)
        env = np.clip((us - 0.30) / 0.30, 0, 1) ** 1.3
        raw = rng.random((rows, cols))
        for _ in range(2):
            raw[:, 1:-1] = (raw[:, :-2] + 2 * raw[:, 1:-1] + raw[:, 2:]) / 4
        peaks = 0.05 + 0.19 * raw * (0.6 + 0.4 * np.sin(us * 4.1 + side * 1.7) ** 2)
        hts = -np.sort(-peaks, axis=0) * env * np.linspace(1, 0.35, rows)[:, None]
        jit = rng.uniform(-0.012, 0.012, (rows, cols))
        P_ = [[(side * (us[j] + jit[k, j]), hz - hts[k, j]) for j in range(cols)] for k in range(rows)]
        P_.append([(side * us[j], hz) for j in range(cols)])
        top = [max(range(rows + 1), key=lambda k: -P_[k][j][1]) for j in range(cols)]
        sil = [P_[top[j]][j] for j in range(cols)]
        fill = cv.mask(lambda d, pt, wd: d.polygon([pt(*q) for q in sil] + [pt(side * U_MAX * 1.1, hz), pt(side * 0.3, hz)], fill=255))
        cv.paint(fill, s["mountain_fill"], 0.94)

        def wire(d, pt, wd):
            lw = wd(0.0011)
            for k in range(rows + 1):
                d.line([pt(*q) for q in P_[k]], fill=255, width=lw, joint="curve")
            for k in range(rows):
                for j in range(cols):
                    d.line([pt(*P_[k][j]), pt(*P_[k + 1][j])], fill=200, width=lw)
                    if j + 1 < cols:
                        d.line([pt(*P_[k][j]), pt(*P_[k + 1][j + 1])], fill=170, width=lw)

        w = cv.mask(wire)
        cv.paint(w, s["mountain"], 0.95)
        cv.glow(w, s["mountain"], ((0.002, 0.5), (0.01, 0.3)))
    perspective_grid(cv, hz, s["grid"])


def scene_ocean_drive(cv, s, seed):
    np = cv.np
    rng = np.random.default_rng(seed)
    hz = 0.67
    cv.vgradient([(0, s["sky_top"]), (0.3, s["sky_mid"]), (0.56, s["sky_low"]), (hz, s["horizon"])], 0, hz)
    cv.vgradient([(hz, s["sea_top"]), (1, s["sea_bottom"])], hz, 1)
    sx, sy, sr = 0.62, hz - 0.075, 0.15

    # soft cloud bands
    bands = []
    for _ in range(26):
        u, v = rng.uniform(-U_MAX, U_MAX), rng.uniform(0.07, 0.55)
        if abs(u) < 0.35 and 0.28 < v:
            continue
        bands.append((u, v, rng.uniform(0.25, 0.7), rng.uniform(0.012, 0.03), rng.integers(3, 7), rng.random(8)))

    def clouds(d, pt, wd):
        for u, v, L, t, n, jj in bands:
            for i in range(n):
                cu = u - L / 2 + L * (i + jj[i]) / n
                ch = t * (0.6 + jj[i])
                d.ellipse([pt(cu - L / n * 0.9, v - ch), pt(cu + L / n * 0.9, v + ch * 0.45)], fill=255)
            d.ellipse([pt(u - L * 0.6, v - t * 0.25), pt(u + L * 0.6, v + t * 0.4)], fill=255)

    from PIL import ImageFilter
    m = cv.mask(clouds).filter(ImageFilter.GaussianBlur(cv.px(0.004)))
    cv.paint(m, s["cloud"], 0.72)

    # sun, glow and striped reflection
    def sun(d, pt, wd):
        x, y = pt(sx, sy)
        r = sr * cv.h * SS
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
        d.rectangle([pt(-U_MAX, hz), pt(U_MAX, 1)], fill=0)

    m = cv.mask(sun)
    cv.glow(m, s["sun"], ((0.03, 0.35), (0.12, 0.3)))
    cv.paint(m, cv.column_gradient([(sy - sr, s["sun_core"]), (hz, s["sun"])]))
    refl = []
    for n in range(30):
        f = n / 30
        v = hz + 0.004 + (1 - hz) * f ** 1.5 * 0.9
        half = sr * (0.95 - 0.55 * f) * rng.uniform(0.6, 1.1)
        refl.append((sx + rng.uniform(-0.02, 0.02), v, half, 0.002 + 0.006 * f, 1 - f * 0.85))

    def reflection(d, pt, wd):
        for u, v, half, t, b in refl:
            d.rounded_rectangle([pt(u - half, v), pt(u + half, v + t)], radius=t * cv.h * SS / 2, fill=int(255 * b))

    m = cv.mask(reflection)
    cv.add(m, s["sun"], 0.8)
    cv.glow(m, s["sun"], ((0.004, 0.5), (0.02, 0.25)))
    shimmer = [(rng.uniform(-U_MAX, U_MAX), hz + (1 - hz) * rng.random() ** 1.7, rng.uniform(0.03, 0.2)) for _ in range(160)]
    m = cv.mask(lambda d, pt, wd: [d.line([pt(u - L, v), pt(u + L, v)], fill=60, width=wd(0.0012)) for u, v, L in shimmer])
    cv.add(m, s["horizon"], 0.5)

    # distant headlands receding to the horizon, left of center
    def ridge(u0, u1, base, amp, n, freq):
        us = np.linspace(u0, u1, n)
        k = (us - u1) / (u0 - u1)
        vs = base - amp * k ** 0.8 * (0.75 + 0.25 * np.sin(us * freq + rng.uniform(0, 6)))
        return list(zip(us, vs))

    for u0, amp, col, a in ((-U_MAX, 0.075, s["distant"], 0.7), (-U_MAX, 0.045, s["rail"], 0.85)):
        pts = ridge(u0, -0.02 if amp > 0.05 else -0.25, hz, amp, 120, 9 + amp * 40)
        m = cv.mask(lambda d, pt, wd: d.polygon([pt(*q) for q in pts] + [pt(-0.02, hz + 0.002), pt(u0, hz + 0.002)], fill=255))
        cv.paint(m, col, a)

    # hillside: high on the left edge, dropping toward the road bend
    hill_u = np.linspace(-U_MAX, -0.38, 160)
    t = (hill_u + U_MAX) / (U_MAX - 0.38)
    hill_v = 0.30 + 0.44 * t ** 2.2 + 0.012 * np.sin(hill_u * 31) + 0.008 * np.sin(hill_u * 73)
    hill = list(zip(hill_u, hill_v))

    def hill_v_at(u):
        return float(np.interp(u, hill_u, hill_v))

    # coastal road: bezier centerline from the lower left, bending away into the hills
    tt = np.linspace(0, 1, 200)
    B = [(-0.72, 1.12), (0.02, 0.95), (-0.12, 0.77), (-0.44, 0.72)]
    cu = sum(c[0] * w for c, w in zip(B, [(1 - tt) ** 3, 3 * tt * (1 - tt) ** 2, 3 * tt ** 2 * (1 - tt), tt ** 3]))
    cvv = sum(c[1] * w for c, w in zip(B, [(1 - tt) ** 3, 3 * tt * (1 - tt) ** 2, 3 * tt ** 2 * (1 - tt), tt ** 3]))
    du, dv = np.gradient(cu), np.gradient(cvv)
    nl = np.hypot(du, dv)
    nu, nv = -dv / nl, du / nl
    half = 0.2 * (1 - tt) ** 1.5 + 0.004
    left = list(zip(cu - nu * half, cvv - nv * half))
    right = list(zip(cu + nu * half, cvv + nv * half))
    rail = list(zip(cu + nu * half * 1.08, cvv + nv * half * 1.08 - 0.025 * (1 - tt) ** 1.4 - 0.003))
    cliff = right + [(0.12, 1.05), (-1.2, 1.05)]

    m = cv.mask(lambda d, pt, wd: d.polygon([pt(*q) for q in hill] + [pt(-0.38, 0.78), pt(-0.2, 1.05), pt(-U_MAX, 1.05)], fill=255))
    cv.paint(m, s["hill"])
    m = cv.mask(lambda d, pt, wd: d.polygon([pt(*q) for q in cliff], fill=255))
    cv.paint(m, s["hill"])
    m = cv.mask(lambda d, pt, wd: d.polygon([pt(*q) for q in left + right[::-1]], fill=255))
    cv.paint(m, cv.column_gradient([(0.7, s["rail"]), (1.0, s["road"])]))

    def lines(d, pt, wd):
        for edge in (left, right):
            for i in range(len(tt) - 1):
                d.line([pt(*edge[i]), pt(*edge[i + 1])], fill=200, width=wd(0.0005 + 0.004 * (1 - tt[i]) ** 2))
        for off in (-0.012, 0.012):
            for i in range(len(tt) - 1):
                d.line([pt(cu[i] + nu[i] * off * (1 - tt[i]) ** 1.6, cvv[i] + nv[i] * off * (1 - tt[i]) ** 1.6),
                        pt(cu[i + 1] + nu[i + 1] * off * (1 - tt[i + 1]) ** 1.6, cvv[i + 1] + nv[i + 1] * off * (1 - tt[i + 1]) ** 1.6)],
                       fill=230, width=wd(0.0004 + 0.0035 * (1 - tt[i]) ** 2))

    m = cv.mask(lines)
    cv.paint(m, s["road_line"], 0.75)
    cv.glow(m, s["sun"], ((0.003, 0.25),))

    def guard(d, pt, wd):
        for i in range(len(tt) - 1):
            d.line([pt(*rail[i]), pt(*rail[i + 1])], fill=255, width=wd(0.001 + 0.007 * (1 - tt[i]) ** 2))
        for i in range(0, len(tt) - 20, 9):
            d.line([pt(*rail[i]), pt(rail[i][0], rail[i][1] + 0.035 * (1 - tt[i]) ** 1.5 + 0.002)], fill=255, width=wd(0.001 + 0.006 * (1 - tt[i]) ** 2))

    m = cv.mask(guard)
    cv.paint(m, s["rail"])

    # palms on the hillside, more of them revealed on wide screens
    palms = []
    for i in range(13):
        u = -0.5 - i * 0.12 - rng.uniform(0, 0.05)
        hgt = rng.uniform(0.17, 0.32) * (0.65 + 0.35 * min(1, (-u - 0.5) / 0.6))
        palms.append((u, hill_v_at(u) + 0.01, hgt, rng.uniform(-0.03, 0.05), rng.uniform(0, 1, 12)))

    def palm(d, pt, wd):
        for u, base, hgt, lean, jj in palms:
            n = 24
            pts = [(u + lean * (k / n) ** 1.6, base - hgt * k / n) for k in range(n + 1)]
            for k in range(n):
                d.line([pt(*pts[k]), pt(*pts[k + 1])], fill=255, width=wd(hgt * (0.035 - 0.02 * k / n)))
            tx, ty = pts[-1]
            for f in range(10):
                a = np.pi * (f / 9) * 1.15 - 0.08 + (jj[f] - 0.5) * 0.25
                L = hgt * (0.32 + 0.12 * jj[f + 1])
                seg = [(tx + np.cos(a) * L * q, ty - np.sin(a) * L * q * 0.7 + L * 0.55 * q * q) for q in np.linspace(0, 1, 12)]
                for k in range(11):
                    d.line([pt(*seg[k]), pt(*seg[k + 1])], fill=255, width=wd(hgt * 0.022 * (1 - k / 11) + 0.0006))
                    if k > 1:
                        lx, ly = seg[k]
                        d.line([pt(lx, ly), pt(lx + (np.cos(a) * 0.3) * L * 0.12, ly + L * 0.14 * (1 - k / 11))], fill=255, width=wd(0.0009))
            d.ellipse([pt(tx - hgt * 0.025, ty - hgt * 0.01), pt(tx + hgt * 0.025, ty + hgt * 0.035)], fill=255)

    m = cv.mask(palm)
    cv.paint(m, s["hill"])


def scene_chrome_city(cv, s, seed):
    np = cv.np
    rng = np.random.default_rng(seed)
    hz = 0.63
    cv.vgradient([(0, s["sky_top"]), (0.42, s["sky_mid"]), (hz, s["haze"])], 0, hz)
    cv.vgradient([(hz, s["floor"]), (1, s["sky_top"])], hz, 1)
    haze = [(rng.uniform(-U_MAX, U_MAX), rng.uniform(0.15, 0.5), rng.uniform(0.2, 0.6), rng.uniform(0.02, 0.05)) for _ in range(14)]
    from PIL import ImageFilter
    m = cv.mask(lambda d, pt, wd: [d.ellipse([pt(u - L, v - t), pt(u + L, v + t)], fill=255) for u, v, L, t in haze])
    cv.add(m.filter(ImageFilter.GaussianBlur(cv.px(0.03))), s["haze"], 0.22)
    mx, my, mr = -0.6, 0.2, 0.13
    stars(cv, rng, 260, hz - 0.15, s["moon"], avoid=lambda u, v: (u - mx) ** 2 + (v - my) ** 2 < (mr * 1.1) ** 2)

    # faint wireframe moon
    def moon(d, pt, wd):
        lw = wd(0.0012)
        x0, y0 = pt(mx - mr, my - mr)
        x1, y1 = pt(mx + mr, my + mr)
        d.ellipse([x0, y0, x1, y1], outline=255, width=lw)
        for k in range(1, 9):
            phi = -np.pi / 2 + np.pi * k / 9
            yy, half = my + mr * np.sin(phi), mr * np.cos(phi)
            d.line([pt(mx - half, yy), pt(mx + half, yy)], fill=200, width=lw)
        for k in range(1, 9):
            half = mr * abs(np.cos(np.pi * k / 9))
            if half * cv.h * SS > 2:
                d.ellipse([pt(mx - half, my - mr)[0], y0, pt(mx + half, my + mr)[0], y1], outline=200, width=lw)

    disc = cv.mask(lambda d, pt, wd: d.ellipse([pt(mx - mr, my - mr), pt(mx + mr, my + mr)], fill=255))
    cv.paint(disc, s["moon"], 0.08)
    m = cv.mask(moon)
    cv.paint(m, s["moon"], 0.5)
    cv.glow(m, s["moon"], ((0.004, 0.35), (0.03, 0.2)))

    dark, light = _c(s["tower_dark"]), _c(s["tower_light"])
    edge_glow = np.zeros((cv.h, cv.w), np.float32)
    win = _c(s["window"])

    def tower(u0, wdt, top, layer, idx, edge_col):
        h, W = cv.h, cv.w
        x0, x1 = int(round(cv.pt(u0, 0)[0])), int(round(cv.pt(u0 + wdt, 0)[0]))
        y0, y1 = int(round(top * h)), int(round(hz * h))
        xa, xb = max(x0, 0), min(x1, W)
        if xb <= xa or y1 <= y0:
            return
        t = (np.arange(xa, xb, dtype=np.float32) - x0) / max(x1 - x0, 1)
        sheen = 0.12 + 0.55 * np.exp(-((t - 0.28) / 0.09) ** 2) + 0.18 * np.exp(-((t - 0.8) / 0.05) ** 2)
        vy = (np.arange(y0, y1, dtype=np.float32) - y0) / max(y1 - y0, 1)
        shade = (1 - 0.65 * vy)[:, None] * sheen[None, :] * (0.55 if layer == 0 else 1.0)
        block = dark + (light - dark) * shade[..., None]
        trng = np.random.default_rng(seed * 1000 + idx)  # windows: per-tower grid, size independent
        nr, nc = max(2, int((hz - top) / 0.012)), max(2, int(wdt / 0.012))
        lit = trng.random((nr, nc)) < (0.18 if layer else 0.1)
        ri = np.minimum((vy * nr).astype(int), nr - 1)
        ci = np.minimum((t * nc).astype(int), nc - 1)
        fy = (vy * nr) % 1 < 0.45
        fx = (t * nc) % 1 < 0.5
        wmask = lit[ri][:, ci] & fy[:, None] & fx[None, :] & (vy[:, None] > 0.03)
        block[wmask] = block[wmask] * 0.4 + win * (0.6 if layer else 0.35)
        cv.img[y0:y1, xa:xb] = block
        ew = max(1, round(0.0013 * h))
        ec = _c(edge_col) * (0.55 if layer == 0 else 1.0)
        for ex in (x0, x1 - ew):
            if 0 <= ex and ex + ew <= W:
                cv.img[y0:y1, ex:ex + ew] = ec
                edge_glow[y0:y1, ex:ex + ew] += 0.6 if layer else 0.25
        cv.img[y0:y0 + ew, xa:xb] = ec
        edge_glow[y0:y0 + ew, xa:xb] += 0.5 if layer else 0.2

    idx = 0
    for layer, (count, wr, hr) in enumerate(((90, (0.025, 0.06), (0.05, 0.22)), (46, (0.04, 0.09), (0.1, 0.42)))):
        us = np.sort(rng.uniform(-U_MAX, U_MAX, count))
        for u in us:
            wdt = rng.uniform(*wr)
            ht = rng.uniform(*hr) * (0.6 + 0.4 * min(1, abs(u) / 0.45)) if layer else rng.uniform(*hr)
            col = s["edge_a"] if rng.random() < 0.6 else s["edge_b"]
            top = hz - ht
            tower(u - wdt / 2, wdt, top, layer, idx, col)
            idx += 1
            if layer and rng.random() < 0.75:  # setback crown and spire
                cw = wdt * rng.uniform(0.45, 0.7)
                ch = ht * rng.uniform(0.08, 0.2)
                tower(u - cw / 2, cw, top - ch, layer, idx, col)
                idx += 1
                if rng.random() < 0.7:
                    sh = ht * rng.uniform(0.08, 0.25)
                    x = int(round(cv.pt(u, 0)[0]))
                    y0, y1 = int(round((top - ch - sh) * cv.h)), int(round((top - ch) * cv.h))
                    ew = max(1, round(0.0012 * cv.h))
                    if 0 <= x and x + ew <= cv.w:
                        cv.img[y0:y1, x:x + ew] = _c(col)
                        edge_glow[y0:y1, x:x + ew] += 0.8

    cv.glow(np.clip(edge_glow, 0, 1), s["edge_a"], ((0.002, 0.7), (0.008, 0.45), (0.03, 0.25)))
    del edge_glow
    # mirrored skyline on the glossy floor
    r = int(round(hz * cv.h))
    depth = cv.h - r
    src = cv.img[max(0, r - depth):r][::-1]
    fade = np.linspace(0.16, 0.0, src.shape[0], dtype=np.float32)[:, None, None]
    cv.img[r:r + src.shape[0]] += src * fade
    del src
    perspective_grid(cv, hz, s["grid"], spacing=0.13, base=0.85)


SCENES = {"neon-horizon": scene_neon_horizon, "ocean-drive": scene_ocean_drive,
          "chrome-city": scene_chrome_city}


def render_wallpaper(pal: dict, size: tuple[int, int]):
    slug = pal["meta"]["slug"]
    seed = sum(map(ord, slug)) * 7919  # stable across runs, sizes and Python versions
    cv = Canvas(*size)
    SCENES[slug](cv, pal["scene"], seed)
    return cv.finish(seed)


def render_wallpapers(pal: dict) -> list[Path]:
    """One image at a time, freed before the next, so 5120x1440 fits in a small box."""
    import gc
    slug = pal["meta"]["slug"]
    name = f"01-{slug}.jpg"
    out = []
    for size in P.RESOLUTIONS:
        img = render_wallpaper(pal, size)
        dest = P.ROOT / "wallpapers" / slug / f"{size[0]}x{size[1]}" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, quality=92, optimize=True, progressive=True, subsampling=0)
        out.append(dest)
        if size == P.DEFAULT_RES:
            bg = P.ROOT / "themes" / slug / "backgrounds" / name
            bg.parent.mkdir(parents=True, exist_ok=True)
            img.save(bg, quality=92, optimize=True, progressive=True, subsampling=0)
        img.close()
        del img
        gc.collect()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wallpapers", action="store_true")
    ap.add_argument("--previews", action="store_true")
    ap.add_argument("--only", help="palette slug")
    a = ap.parse_args()
    pals = [p for p in P.all_palettes() if not a.only or p["meta"]["slug"] == a.only]
    for pal in pals:
        n = len(render_configs(pal))
        print(f"{pal['meta']['slug']}: {n} configs")
        if a.wallpapers:
            for f in render_wallpapers(pal):
                print("  ", f.relative_to(P.ROOT))
        if a.previews:
            import preview
            print("  ", preview.render(pal).relative_to(P.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

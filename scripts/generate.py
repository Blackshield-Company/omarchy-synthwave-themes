#!/usr/bin/env python3
"""Render themes from palettes/*.toml.

  generate.py                 configs only (theme/ + extras/), needs jinja2
  generate.py --wallpapers    also grade brand art into wallpapers (needs Pillow + art dir)
  generate.py --previews      also render previews from the generated wallpapers
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wallpapers", action="store_true")
    ap.add_argument("--previews", action="store_true")
    ap.add_argument("--art-dir", default="/workspace/brand")
    ap.add_argument("--only", help="palette slug")
    a = ap.parse_args()
    pals = [p for p in P.all_palettes() if not a.only or p["meta"]["slug"] == a.only]
    for pal in pals:
        n = len(render_configs(pal))
        print(f"{pal['meta']['slug']}: {n} configs")
        if a.wallpapers:
            import art
            for f in art.render_wallpapers(pal, Path(a.art_dir)):
                print("  ", f.relative_to(P.ROOT))
        if a.previews:
            import preview
            print("  ", preview.render(pal).relative_to(P.ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

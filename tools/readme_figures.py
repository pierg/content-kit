#!/usr/bin/env python3
"""The README's figures, derived from the pages that own them.

A figure's one home is the page that embeds it inline, where the shell's tokens give it its
colours and its dark mode. GitHub renders the README without the shell, so this writes each
figure marked `data-figure="<name>"` in the docs pages as a standalone SVG under
assets/figures/, with the tokens resolved to the shell's light values and, in `<name>-dark.svg`,
its dark ones; the README shows them through a <picture>. Regenerate after editing a figure:

    python3 tools/readme_figures.py            # writes assets/figures/*.svg
    python3 tools/readme_figures.py --check    # exit 1 when a written file is stale
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [ROOT / "content" / "hubs" / "content-kit.html",
         ROOT / "content" / "books" / "running-a-library" / "01-install.html"]
OUT = ROOT / "assets" / "figures"

LIGHT = {"surface-1": "#ffffff", "page": "#faf9f6", "surface-2": "#f3f1ec", "ink-1": "#1d1b17", "ink-2": "#57524a",
         "ink-3": "#8b857a", "grid": "#e8e5de", "baseline": "#d2cdc3", "azure": "#2a78d6", "violet": "#4a3aa7",
         "orange": "#eb6834", "teal": "#0f766e", "indigo": "#4f46e5", "blue": "#2563eb", "amber": "#d97706", "red": "#dc2626"}
DARK = {"surface-1": "#1c1c1a", "page": "#131312", "surface-2": "#1f1f1d", "ink-1": "#ecebe6", "ink-2": "#b9b4aa",
        "ink-3": "#8b867c", "grid": "#2b2a27", "baseline": "#3d3c38", "azure": "#3987e5", "violet": "#9085e9",
        "orange": "#d95926", "teal": "#5eead4", "indigo": "#7c8cff", "blue": "#60a5fa", "amber": "#fbbf24", "red": "#f87171"}
FIGURE = re.compile(r'<figure data-figure="([^"]+)"[^>]*>\s*(<svg.*?</svg>)', re.S)
VIEWBOX = re.compile(r'viewBox="0 0 (\d+) (\d+)"')


def render(svg: str, tokens: dict[str, str]) -> str:
    out = re.sub(r"var\(--([a-z0-9-]+)\)", lambda m: tokens[m.group(1)], svg)
    w, h = VIEWBOX.search(out).groups()
    style = (f'<style>text{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;fill:{tokens["ink-1"]}}}'
             f'.t2{{fill:{tokens["ink-2"]}}}.t3{{fill:{tokens["ink-3"]}}}</style>\n'
             f'<rect width="{w}" height="{h}" rx="14" fill="{tokens["page"]}"/>\n')
    out = out.replace("<defs>", style + "<defs>", 1)
    return out.replace('<svg ', f'<svg width="{w}" height="{h}" ', 1) + "\n"


def files() -> dict[Path, str]:
    want: dict[Path, str] = {}
    for page in PAGES:
        for name, svg in FIGURE.findall(page.read_text(encoding="utf-8")):
            want[OUT / f"{name}.svg"] = render(svg, LIGHT)
            want[OUT / f"{name}-dark.svg"] = render(svg, DARK)
    return want


def main(argv: list[str]) -> int:
    want = files()
    if "--check" in argv:
        stale = [p for p, text in want.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)} — run python3 tools/readme_figures.py")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for p, text in want.items():
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

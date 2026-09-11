"""The genre taxonomy: which shapes exist, where each lives, and what is checked on each.

Core genres ship with the engine (`genres.json`); a repo extends or overrides them under
`genres` in `lab.json`. Classification is by path — the content tree *is* the taxonomy —
and a page that matches no genre is an error, not a default.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

from .paths import PACKAGE_DIR, Repo

LAYOUTS = ("flat", "folder", "book-index", "book-page")


@dataclass
class Genre:
    name: str
    dir: str
    layout: str
    skeleton: str | None
    register: str
    reader: str
    forbidden: str
    checks: dict


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def core_spec() -> dict:
    return json.loads((PACKAGE_DIR / "genres.json").read_text(encoding="utf-8"))["genres"]


def load_genres(repo: Repo | None = None) -> dict[str, Genre]:
    spec = core_spec()
    ext = (repo.cfg.get("genres") if repo else None) or {}
    if not isinstance(ext, dict):
        raise SystemExit("lab.json: `genres` must be an object keyed by genre name")
    for name, over in ext.items():
        if not isinstance(over, dict):
            raise SystemExit(f"lab.json: genres.{name} must be an object")
        spec[name] = _deep_merge(spec.get(name, {}), over)

    out: dict[str, Genre] = {}
    for name, g in spec.items():
        for req in ("dir", "layout"):
            if req not in g:
                raise SystemExit(f"genre {name!r}: missing required field {req!r}")
        if g["layout"] not in LAYOUTS:
            raise SystemExit(f"genre {name!r}: layout must be one of {LAYOUTS}")
        out[name] = Genre(
            name=name,
            dir=str(g["dir"]).strip("/"),
            layout=g["layout"],
            skeleton=g.get("skeleton"),
            register=g.get("register", ""),
            reader=g.get("reader", ""),
            forbidden=g.get("forbidden", ""),
            checks=dict(g.get("checks") or {}),
        )
    return out


EXEMPT_PARTS = {"archive"}  # an archived page is kept for the record, not held to the contract


def classify(repo: Repo, page: Path, genres: dict[str, Genre]) -> Genre | None:
    """The genre a page belongs to by its position in the content tree, or None."""
    try:
        rel = page.resolve().relative_to(repo.content.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2 or page.suffix != ".html":
        return None
    top = parts[0]
    candidates = [g for g in genres.values() if g.dir == top]
    if not candidates:
        return None
    depth = len(parts)
    for g in candidates:
        if g.layout == "book-index" and depth == 3 and parts[2] == "index.html":
            return g
        if g.layout == "book-page" and depth == 3 and parts[2] != "index.html":
            return g
        if g.layout == "flat" and depth == 2:
            return g
        if g.layout == "folder" and depth >= 3:
            return g
    return None


def is_exempt(repo: Repo, page: Path) -> bool:
    try:
        rel = page.resolve().relative_to(repo.content.resolve())
    except ValueError:
        return True
    return any(p in EXEMPT_PARTS for p in rel.parts)


def target_path(repo: Repo, genre: Genre, slug: str) -> Path:
    """Where a new page of this genre goes. Chapters take `<book>/<NN-slug>`."""
    base = repo.content / genre.dir
    if genre.layout == "flat":
        return base / f"{slug}.html"
    if genre.layout == "folder":
        return base / slug / "index.html"
    if genre.layout == "book-index":
        return base / slug / "index.html"
    if genre.layout == "book-page":
        if "/" not in slug:
            raise SystemExit(f"a {genre.name} slug is <book>/<NN-name>, got {slug!r}")
        book, name = slug.split("/", 1)
        return base / book / f"{name}.html"
    raise AssertionError(genre.layout)

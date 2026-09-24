"""The genre taxonomy: which shapes exist, where each lives, and what is checked on each.

Core genres ship with the engine (`genres.json`); a repo extends or overrides them under
`genres` in `kit.json`. Classification is by path — the content tree *is* the taxonomy —
and a page that matches no genre is an error, not a default.

`genres` is either one object keyed by genre name, or a list whose items are such objects or
repo-relative paths to a JSON file holding one (`{"genres": {...}}` or the bare object) — how a
layer ships its genres in a vendored, pinned file while the repo keeps its own overrides after
it. Every item deep-merges into the spec in order. A skeleton path is looked up in the shell's
skeletons first, then from the repo root, so a layer's skeleton lives beside its genre file.

The genre table is also the catalog: every genre that owns a directory is a group in the
sidebar, on the landing page and among the search filters, in declaration order — core first,
then extensions — unless a genre says `"after": "<genre>"`. `"label"` names the group.
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
    label: str = ""
    after: str | None = None


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


def _extension_items(repo: Repo) -> list[tuple[str, dict]]:
    """(where, {name: spec}) for each item under kit.json `genres`, in order."""
    ext = repo.cfg.get("genres") or {}
    items = ext if isinstance(ext, list) else [ext]
    out: list[tuple[str, dict]] = []
    for i, item in enumerate(items):
        where = f"kit.json genres[{i}]" if isinstance(ext, list) else "kit.json genres"
        if isinstance(item, str):
            p = repo.root / item
            if not p.is_file():
                raise SystemExit(f"{where}: {item!r} not found")
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{item}: invalid JSON — {exc}") from exc
            where = item
            item = data.get("genres", data) if isinstance(data, dict) else data
        if not isinstance(item, dict):
            raise SystemExit(f"{where}: `genres` must be an object keyed by genre name, "
                             "or a list of such objects and paths to JSON files holding one")
        out.append((where, {k: v for k, v in item.items() if not k.startswith("_")}))
    return out


def load_genres(repo: Repo | None = None) -> dict[str, Genre]:
    spec = core_spec()
    for where, ext in (_extension_items(repo) if repo else []):
        for name, over in ext.items():
            if not isinstance(over, dict):
                raise SystemExit(f"{where}: genres.{name} must be an object")
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
            label=str(g.get("label") or ""),
            after=g.get("after"),
        )
    for g in out.values():
        if g.after is not None and g.after not in out:
            raise SystemExit(f"genre {g.name!r}: after {g.after!r} names no genre")
    return out


def ordered(genres: dict[str, Genre]) -> list[Genre]:
    """Declaration order, except that a genre with `after` follows the genre it names (and
    anything already placed after that one)."""
    placed: list[Genre] = [g for g in genres.values() if g.after is None]
    pending = [g for g in genres.values() if g.after is not None]
    while pending:
        progressed = False
        for g in list(pending):
            anchor = next((i for i, x in enumerate(placed) if x.name == g.after), None)
            if anchor is None:
                continue
            i = anchor + 1
            while i < len(placed) and placed[i].after == g.after:
                i += 1
            placed.insert(i, g)
            pending.remove(g)
            progressed = True
        if not progressed:
            raise SystemExit("genres: `after` forms a cycle among " + ", ".join(g.name for g in pending))
    return placed


RESERVED_GROUP_KEYS = {"site", "topics", "groups", "record", "links", "refs", "indices", "threads"}


def catalog_groups(genres: dict[str, Genre]) -> list[dict]:
    """One group per content directory, from the genre that indexes it (a chapter lives inside
    its book and is never a group of its own)."""
    out: list[dict] = []
    seen: set[str] = set()
    for g in ordered(genres):
        if g.layout == "book-page" or g.dir in seen:
            continue
        if g.dir in RESERVED_GROUP_KEYS:
            raise SystemExit(f"genre {g.name!r}: dir {g.dir!r} collides with a catalog key")
        seen.add(g.dir)
        out.append({"key": g.dir, "label": g.label or g.dir.capitalize(), "kind": g.name,
                    "layout": "flat" if g.layout == "flat" else "folder"})
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

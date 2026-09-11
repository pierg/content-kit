"""Scaffold a page of a genre from its skeleton: `ckit new <genre> <slug> [--title …]`.

    ckit new note   proofs-are-hypotheses
    ckit new concept k-induction
    ckit new chapter proofs-forever/04-floor      # <book>/<NN-name>
    ckit new book    proofs-forever

The page lands where its genre says it lives, with the skeleton's status line already in
place, and the voice card for that genre is printed so the author starts in the right register.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from .genres import load_genres, target_path
from .paths import Repo, load_repo

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*(?:/[0-9]{2}-[a-z0-9][a-z0-9-]*)?$")


def _skeleton(repo: Repo, skeleton: str) -> Path:
    for base in (repo.shell / "skeletons", repo.root):
        p = base / skeleton
        if p.exists():
            return p
    raise SystemExit(f"skeleton {skeleton!r} not found under {repo.rel(repo.shell / 'skeletons')}")


def _retitle(html: str, title: str) -> str:
    html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", html, count=1, flags=re.S)
    return re.sub(r"<h1>.*?</h1>", f"<h1>{title}</h1>", html, count=1, flags=re.S)


def create(repo: Repo, genre_name: str, slug: str, *, title: str | None = None) -> Path:
    genres = load_genres(repo)
    if genre_name not in genres:
        raise SystemExit(f"unknown genre {genre_name!r} — one of {', '.join(sorted(genres))}")
    g = genres[genre_name]
    if not SLUG.match(slug):
        raise SystemExit(f"slug {slug!r}: lowercase, digits and dashes (chapters: <book>/<NN-name>)")
    if not g.skeleton:
        raise SystemExit(f"genre {g.name!r} declares no skeleton — write the page by hand")
    dest = target_path(repo, g, slug)
    if dest.exists():
        raise SystemExit(f"{repo.rel(dest)} already exists")
    if g.layout == "book-page" and not dest.parent.is_dir():
        raise SystemExit(f"no book at {repo.rel(dest.parent)} — `ckit new book {dest.parent.name}` first")
    src = _skeleton(repo, g.skeleton)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A folder skeleton brings its siblings (source.json for an entry, …); a flat one is a file.
    if g.layout in ("folder", "book-index") and Path(g.skeleton).parent.name not in ("", "."):
        for sib in src.parent.iterdir():
            if sib.is_file() and sib != src:
                shutil.copy2(sib, dest.parent / sib.name)
    html = src.read_text(encoding="utf-8")
    if title:
        html = _retitle(html, title)
    dest.write_text(html, encoding="utf-8")
    return dest


def voice_card(repo: Repo, genre_name: str) -> str:
    g = load_genres(repo)[genre_name]
    lines = [f"{g.name} — {g.register}", f"  reader:    {g.reader}", f"  forbidden: {g.forbidden}"]
    if g.checks:
        lines.append("  checked:   " + ", ".join(f"{k}={v}" for k, v in g.checks.items()))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit new", description=__doc__.split("\n")[0])
    ap.add_argument("genre")
    ap.add_argument("slug")
    ap.add_argument("--title")
    args = ap.parse_args(argv)
    repo = load_repo()
    dest = create(repo, args.genre, args.slug, title=args.title)
    print(f"created {repo.rel(dest)}")
    print(voice_card(repo, args.genre))
    print(f"see kit/genres/GENRES.md for the full voice; `ckit check` before it lands")
    return 0

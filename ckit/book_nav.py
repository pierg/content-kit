"""Discover navigation and indices from the content tree.

Convention for content/books/<slug>/:
  1. index.html first (book hub)
  2. NN-*.html sorted by chapter number
  3. other *.html alphabetically (doubts, drills, …)

Optional thin override: content/books/<slug>/book.json
  {
    "homeLabel": "Proofs forever",          # default: index <title> / slug
    "homeHref": "index.html",
    "order": ["doubts.html", "drills.html"], # reorder non-numbered pages only
    "chapters": ["index.html", "01-a.html"], # full order override (rare)
    "labels": { "07-pe.html": "07 PE" },
    "planned": [ { "file": "11-x.html", "label": "11 X", "title": "Coming soon" } ]
  }

Writes (committed artifacts; regenerate via `ckit nav` — lint does it too):
  content/books/<slug>/nav.json
  content/catalog.json · content/search-index.json · content/backlinks.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import chronicle, config, ladder, plugins
from .genres import EXEMPT_PARTS, catalog_groups, load_genres
from .paths import Repo
from .text import (
    DEFN_RE, H1_RE, H2_RE, H3_RE, SUB_RE, TAGS_META_RE, TITLE_RE, strip_tags, title_of,
)

NUMBERED = re.compile(r"^(\d+)-.+\.html$", re.I)
HREF_RE = re.compile(r'href="(/content/[^"#?]*)(?:[#?][^"]*)?"', re.I)



def groups(repo: Repo) -> list[dict]:
    """Sidebar / landing / search-filter order, derived from the genre table (genres.catalog_groups):
    a folder group lists <dir>/<slug>/index.html, a flat one <dir>/<slug>.html. Deriving it is
    what keeps an extension genre from linting and searching fine while never reaching the sidebar."""
    return catalog_groups(load_genres(repo))


def kind_by_folder(repo: Repo) -> dict[str, str]:
    return {g["key"]: g["kind"] for g in groups(repo)}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _title(p: Path) -> str:
    try:
        return title_of(_read(p), p.stem)
    except OSError:
        return p.stem


def _label_from_file(name: str) -> str:
    if name == "index.html":
        return "Hub"
    stem = name[: -len(".html")] if name.endswith(".html") else name
    m = NUMBERED.match(name)
    if m:
        rest = stem.split("-", 1)[1] if "-" in stem else stem
        return f"{int(m.group(1)):02d} {rest.replace('-', ' ').title()}"
    return stem.replace("-", " ").title()


def _load_book_json(repo: Repo, book_dir: Path) -> dict:
    path = book_dir / "book.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"{repo.rel(path)}: {e}") from e
    if not isinstance(data, dict):
        raise SystemExit(f"{repo.rel(path)}: must be a JSON object")
    return data


def _default_order(files: list[str], extras_order: list[str] | None) -> list[str]:
    index = [f for f in files if f == "index.html"]
    numbered: list[tuple[int, str]] = []
    other: list[str] = []
    for f in files:
        if f == "index.html":
            continue
        m = NUMBERED.match(f)
        if m:
            numbered.append((int(m.group(1)), f))
        else:
            other.append(f)
    numbered_files = [f for _, f in sorted(numbered)]
    if extras_order:
        seen = set(extras_order)
        ordered_other = [f for f in extras_order if f in other]
        ordered_other += sorted(f for f in other if f not in seen)
    else:
        ordered_other = sorted(other)
    return index + numbered_files + ordered_other


def build_book_nav(repo: Repo, book_dir: Path) -> dict:
    cfg = _load_book_json(repo, book_dir)
    files = sorted(p.name for p in book_dir.glob("*.html"))
    if not files:
        raise SystemExit(f"{repo.rel(book_dir)}: no HTML pages")

    labels = cfg.get("labels") or {}
    if not isinstance(labels, dict):
        raise SystemExit(f"{repo.rel(book_dir / 'book.json')}: labels must be an object")

    if cfg.get("chapters"):
        order = cfg["chapters"]
        if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
            raise SystemExit(f"{repo.rel(book_dir / 'book.json')}: chapters must be a string list")
        for f in order:
            if f not in files:
                raise SystemExit(f"{repo.rel(book_dir)}: chapters lists missing file {f}")
        for f in files:
            if f not in order:
                raise SystemExit(f"{repo.rel(book_dir)}: {f} exists but not in book.json chapters")
    else:
        extras = cfg.get("order")
        if extras is not None and (
            not isinstance(extras, list) or not all(isinstance(x, str) for x in extras)
        ):
            raise SystemExit(f"{repo.rel(book_dir / 'book.json')}: order must be a string list")
        order = _default_order(files, extras)

    chapters = [
        {"file": f, "label": labels.get(f) or _label_from_file(f),
         "title": _title(book_dir / f), "status": "landed"}
        for f in order
    ]
    for item in cfg.get("planned") or []:
        if not isinstance(item, dict) or "file" not in item:
            raise SystemExit(f"{repo.rel(book_dir / 'book.json')}: planned entries need at least file")
        f = item["file"]
        chapters.append({
            "file": f,
            "label": item.get("label") or labels.get(f) or _label_from_file(f),
            "title": item.get("title") or item.get("label") or _label_from_file(f),
            "status": "planned",
        })

    home_label = cfg.get("homeLabel")
    if not home_label:
        idx = book_dir / "index.html"
        home_label = _title(idx) if idx.is_file() else book_dir.name
    return {"homeLabel": home_label, "homeHref": cfg.get("homeHref") or "index.html",
            "chapters": chapters}


def _books(repo: Repo) -> list[Path]:
    books = repo.content / "books"
    if not books.is_dir():
        return []
    return [d for d in sorted(books.iterdir()) if d.is_dir() and (d / "index.html").is_file()]


def build_catalog(repo: Repo) -> dict:
    c = repo.content_name
    grps = groups(repo)
    out: dict = {"groups": grps}
    for g in grps:
        folder, layout = g["key"], g["layout"]
        d = repo.content / folder
        items: list[dict] = []
        if d.is_dir():
            if layout == "folder":
                for p in sorted(child / "index.html" for child in d.iterdir() if child.is_dir()):
                    if p.is_file():
                        items.append({"slug": p.parent.name, "title": _title(p),
                                      "href": f"/{c}/{folder}/{p.parent.name}/"})
            else:
                for p in sorted(d.glob("*.html")):
                    items.append({"slug": p.stem, "title": _title(p),
                                  "href": f"/{c}/{folder}/{p.stem}.html"})
        out[folder] = items
    out["record"] = chronicle.record_catalog(repo) if chronicle.enabled(repo) else []
    for key, items in (("links", config.links(repo)), ("refs", config.refs(repo)),
                       ("indices", config.indices(repo))):
        if items:  # only when declared, so a repo that uses none carries none
            out[key] = items
    if ladder.enabled(repo):
        out["dashboard"] = True  # opt-in only — omitted otherwise, so a non-adopting repo's catalog.json is unchanged
    return out


def _kind_of(repo: Repo, rel: Path, kinds: dict[str, str] | None = None) -> str:
    parts = rel.parts
    if len(parts) >= 2 and parts[0] == repo.content_name:
        return (kinds if kinds is not None else kind_by_folder(repo)).get(parts[1], "page")
    return "page"


def _snippet(html: str, pattern: re.Pattern, limit: int = 200) -> str:
    m = pattern.search(html)
    return strip_tags(m.group(1))[:limit] if m else ""


def _all(html: str, pattern: re.Pattern, limit: int = 8) -> list[str]:
    out: list[str] = []
    for m in pattern.finditer(html):
        text = strip_tags(m.group(1))
        if text:
            out.append(text[:120])
        if len(out) >= limit:
            break
    return out


def _indexable(repo: Repo) -> list[Path]:
    if not repo.content.is_dir():
        return []
    out = []
    for p in sorted(repo.content.rglob("*.html")):
        rel = p.relative_to(repo.root)
        if any(part in EXEMPT_PARTS for part in rel.parts):
            continue
        out.append(p)
    return out


def _href_of(repo: Repo, p: Path) -> str:
    href = "/" + p.relative_to(repo.root).as_posix()
    return href[: -len("index.html")] if href.endswith("/index.html") else href


def _record(repo: Repo, p: Path, kinds: dict[str, str]) -> dict:
    text = _read(p)
    tags_match = TAGS_META_RE.search(text)
    return {
        "title": _snippet(text, TITLE_RE) or _snippet(text, H1_RE) or p.stem,
        "sub": _snippet(text, SUB_RE, 240),
        "defn": _snippet(text, DEFN_RE, 400),
        "headings": _all(text, H2_RE) + _all(text, H3_RE, 4),
        "tags": [t.strip() for t in tags_match.group(1).split(",")] if tags_match else [],
        "kind": _kind_of(repo, p.relative_to(repo.root), kinds),
        "href": _href_of(repo, p),
    }


def build_search_index(repo: Repo) -> list[dict]:
    kinds = kind_by_folder(repo)
    return [_record(repo, p, kinds) for p in _indexable(repo)]


def _normalize_href(href: str) -> str:
    return href[: -len("index.html")] if href.endswith("/index.html") else href


def build_backlinks(repo: Repo) -> dict[str, list[dict]]:
    """Reverse index: for each internal href, the pages that link to it."""
    pages = []
    kinds = kind_by_folder(repo)
    for p in _indexable(repo):
        text = _read(p)
        title = _snippet(text, TITLE_RE) or _snippet(text, H1_RE) or p.stem
        pages.append((text, _href_of(repo, p), title, _kind_of(repo, p.relative_to(repo.root), kinds)))
    reverse: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for text, self_href, title, kind in pages:
        for m in HREF_RE.finditer(text):
            target = _normalize_href(m.group(1))
            if target == self_href or (self_href, target) in seen:
                continue
            seen.add((self_href, target))
            reverse.setdefault(target, []).append({"title": title, "href": self_href, "kind": kind})
    for target in reverse:
        reverse[target].sort(key=lambda x: (x["kind"], x["title"].lower()))
    return dict(sorted(reverse.items()))


def _dump(data: object) -> str:
    if isinstance(data, str):
        return data
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def expected_files(repo: Repo) -> dict[Path, object]:
    expected: dict[Path, object] = {}
    for d in _books(repo):
        expected[d / "nav.json"] = build_book_nav(repo, d)
    expected[repo.content / "catalog.json"] = build_catalog(repo)
    expected[repo.content / "search-index.json"] = build_search_index(repo)
    expected[repo.content / "backlinks.json"] = build_backlinks(repo)
    if chronicle.enabled(repo):
        chron = chronicle.build(repo)
        expected[repo.content / "chronicle.json"] = chron
        if ladder.enabled(repo):
            expected[repo.content / "ladder.json"] = ladder.build(repo, chron)
    core = {p.resolve() for p in expected}
    for path, data in plugins.generated_files(repo).items():
        if path in core:
            raise SystemExit(f"a generator claims {repo.rel(path)}, which the engine generates itself")
        expected[path] = data
    return expected


def regenerate(repo: Repo) -> list[str]:
    written: list[str] = []
    for path, data in expected_files(repo).items():
        text = _dump(data)
        old = path.read_text(encoding="utf-8") if path.is_file() else None
        if old != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written.append(repo.rel(path))
    return written


def check(repo: Repo) -> list[str]:
    """Committed indices that differ from discovery."""
    dirty: list[str] = []
    for path, data in expected_files(repo).items():
        cur = path.read_text(encoding="utf-8") if path.is_file() else None
        if cur != _dump(data):
            dirty.append(repo.rel(path))
    return dirty

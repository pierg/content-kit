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

Every catalog entry carries `created` and `updated` (YYYY-MM-DD) and the `sha` of what it covers
(a page, or a whole book): a page whose text changes gets today's date, an unchanged one keeps its
dates (whitespace does not count: a re-flowed page is unchanged), and one the catalog has never seen is dated from git history when there is any — so the
dates are as stable as the pages, and `ckit check` fails on a page edited without `ckit lint`.

Writes (committed artifacts; regenerate via `ckit nav` — lint does it too):
  content/books/<slug>/nav.json
  content/catalog.json · content/search-index.json · content/backlinks.json · content/threads.json
  content/chronicle.json (when the repo declares a record) · every kit.json generator's files
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import annotations, chronicle, config, plugins
from .genres import EXEMPT_PARTS, catalog_groups, load_genres
from .paths import Repo
from .text import DEFN_RE, H1_RE, H2_RE, H3_RE, SUB_RE, TITLE_RE, meta_content, strip_tags, title_of

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


def topic_of(html: str) -> str | None:
    """A page's `<meta name="topic">` — a mechanism any content tree may use; a layer decides
    whether it is required (folio does)."""
    return (meta_content(html, "topic") or "").strip() or None


def tags_of(html: str) -> list[str]:
    return [t.strip() for t in (meta_content(html, "tags") or "").split(",") if t.strip()]


def _topic(p: Path) -> str | None:
    try:
        return topic_of(_read(p))
    except OSError:
        return None


def _tags(p: Path) -> list[str]:
    try:
        return tags_of(_read(p))
    except OSError:
        return []


def today() -> str:
    """The date a changed page is stamped with: UTC, or $CKIT_TODAY (fixtures pin it)."""
    return os.environ.get("CKIT_TODAY") or datetime.now(timezone.utc).date().isoformat()


_WS_BYTES = re.compile(rb"\s+")


def _sha(files: list[Path], *, legacy: bool = False) -> str:
    """What an entry covers, hashed with its whitespace collapsed: a page re-flowed, re-indented
    or checked out with CRLF line endings says the same thing, so it keeps its dates (and is not
    stale). `legacy` is the 0.5.0.dev0 hash (line endings only), read once so a catalog written
    by it keeps its dates across the upgrade."""
    h = hashlib.sha1()
    for f in files:
        h.update(f.name.encode("utf-8"))
        h.update(b"\0")
        data = f.read_bytes().replace(b"\r\n", b"\n")
        h.update(data if legacy else _WS_BYTES.sub(b" ", data).strip())
    return h.hexdigest()[:12]


def _git_history(repo: Repo) -> dict[str, tuple[str, str]]:
    """{repo-relative path: (first commit date, last commit date)} for the content tree, from one
    `git log` — empty when the repo is not a git work tree (a scratch repo, an export)."""
    try:
        r = subprocess.run(["git", "-C", str(repo.root), "log", "--relative", "--format=%x00%cs", "--name-only",
                            "--", repo.content_name], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return {}
    if r.returncode != 0:
        return {}
    hist: dict[str, tuple[str, str]] = {}
    date = None
    for line in r.stdout.splitlines():
        if line.startswith("\0"):
            date = line[1:].strip() or None
            continue
        path = line.strip()
        if not path or date is None:
            continue
        # newest commits come first: the first sighting is the last change, later ones move the first back
        hist[path] = (date, hist[path][1]) if path in hist else (date, date)
    return hist


def _catalog_entries(cat: object) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not isinstance(cat, dict):
        return out
    for g in cat.get("groups") or []:
        items = cat.get(g.get("key")) if isinstance(g, dict) else None
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("href"), str):
                out[item["href"]] = item
    return out


def _previous_catalogs(repo: Repo) -> list[dict[str, dict]]:
    """The dates the catalog already carries: the file on disk — or, when it does not parse (a
    merge conflict in it, the moment `ckit lint` is run to resolve one), both sides of the
    conflict and then HEAD, so resolving a conflict never re-dates the library: a page kept from
    either side keeps that side's dates."""
    p = repo.content / "catalog.json"
    try:
        text = p.read_text(encoding="utf-8")
        got = _catalog_entries(json.loads(text))
        if got or text.strip().startswith("{"):
            return [got]
    except (OSError, ValueError):
        pass
    out: list[dict[str, dict]] = []
    for rev in (":2:", ":3:", "HEAD:"):  # ours and theirs while a merge is unresolved, else HEAD
        try:
            r = subprocess.run(["git", "-C", str(repo.root), "show", f"{rev}./{repo.rel(p)}"],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                out.append(_catalog_entries(json.loads(r.stdout)))
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    return out


def date_items(repo: Repo, entries: list[tuple[dict, list[Path]]]) -> None:
    """Stamp each catalog item with created / updated / sha (see the module docstring)."""
    prevs = _previous_catalogs(repo)
    hist: dict[str, tuple[str, str]] | None = None
    now = today()
    for item, files in entries:
        files = [f for f in files if f.is_file()]
        sha = _sha(files)
        olds = [c[item["href"]] for c in prevs if item["href"] in c]
        legacy = _sha(files, legacy=True) if olds else None
        same = next((o for o in olds if o.get("sha") in (sha, legacy) and o.get("created") and o.get("updated")),
                    None)
        born = sorted(str(o["created"]) for o in olds if o.get("created"))
        if same:
            created, updated = same["created"], same["updated"]
        elif born:
            created, updated = born[0], now
        else:
            if hist is None:
                hist = _git_history(repo)
            seen = [hist[repo.rel(f)] for f in files if repo.rel(f) in hist]
            if seen:
                created, updated = min(c for c, _ in seen), max(u for _, u in seen)
            else:
                created = updated = now
        item["created"], item["updated"], item["sha"] = created, updated, sha


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


def topic_labels(repo: Repo) -> dict[str, str]:
    """kit.json `topics` — {slug: label} — when the repo declares any: the shell names topics by
    them. Whether a topic is required is a layer's convention (folio's); naming one is not."""
    got = repo.cfg.get("topics")
    if isinstance(got, list):  # a list of slugs names each topic by its slug
        return {str(s): str(s) for s in got}
    return {str(k): str(v) for k, v in got.items()} if isinstance(got, dict) else {}


def build_catalog(repo: Repo) -> dict:
    c = repo.content_name
    grps = groups(repo)
    site = {"name": str(repo.cfg.get("name") or "library")}
    if repo.cfg.get("question"):
        site["question"] = str(repo.cfg["question"])
    out: dict = {"site": site}
    labels = topic_labels(repo)
    if labels:
        out["topics"] = labels
    out["groups"] = grps
    dated: list[tuple[dict, list[Path]]] = []
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
            for item, p in zip(items, [d / i["slug"] / "index.html" if layout == "folder" else d / f"{i['slug']}.html"
                                       for i in items]):
                topic = _topic(p)
                if topic:  # only when declared, so a repo without topics carries none
                    item["topic"] = topic
                tags = _tags(p)
                if tags:
                    item["tags"] = tags
                # a book is dated by every page in it; any other entry by its own page
                dated.append((item, sorted(p.parent.glob("*.html")) if g["kind"] == "book" else [p]))
        out[folder] = items
    date_items(repo, dated)
    out["record"] = chronicle.record_catalog(repo) if chronicle.enabled(repo) else []
    for key, items in (("links", config.links(repo)), ("refs", config.refs(repo)),
                       ("indices", config.indices(repo))):
        if items:  # only when declared, so a repo that uses none carries none
            out[key] = items
    counts = thread_counts(repo)
    if counts["total"]:  # only a repo that has been annotated carries them
        out["threads"] = counts
    return out


def thread_counts(repo: Repo) -> dict[str, int]:
    """How many threads wait (open), how many are noted (an agent's flags) and how many there are
    at all: what the rail's Review item shows without reading every sidecar."""
    counts = annotations.build_index(repo)["counts"]
    return {"open": counts["open"], "noted": counts["noted"], "total": sum(counts.values())}


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
    topic = topic_of(text)
    rec = {
        "title": _snippet(text, TITLE_RE) or _snippet(text, H1_RE) or p.stem,
        "sub": _snippet(text, SUB_RE, 240),
        "defn": _snippet(text, DEFN_RE, 400),
        "headings": _all(text, H2_RE) + _all(text, H3_RE, 4),
        "tags": tags_of(text),
        "kind": _kind_of(repo, p.relative_to(repo.root), kinds),
        "href": _href_of(repo, p),
    }
    if topic:
        rec["topic"] = topic
    return rec


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
    expected[repo.content / "threads.json"] = annotations.build_index(repo)
    if chronicle.enabled(repo):
        expected[repo.content / "chronicle.json"] = chronicle.build(repo)
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


def regenerate_threads(repo: Repo) -> list[str]:
    """After a write through the engine (the browser, or `ckit annotations …`): the two indices
    that read the sidecars, so the gate stays green without a `ckit lint` in between."""
    written: list[str] = []
    if not repo.content.is_dir():
        return written
    for path, data in ((repo.content / "threads.json", annotations.build_index(repo)),
                       (repo.content / "catalog.json", build_catalog(repo))):
        text = _dump(data)
        old = path.read_text(encoding="utf-8") if path.is_file() else None
        if old != text:
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

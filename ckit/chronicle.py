"""The chronicle: a generated timeline of the record — never authored.

`content/` shows the current direction. How it got there lives in the record — logbooks,
decision logs, pre-registrations — which is append-only and stays markdown. The chronicle is an
index over that record, regenerated like the catalog and the search index (`ckit lint` /
`ckit nav`), checked current by `ckit check`, and rendered by `/shell/chronicle.html`. Nobody
writes it, so it cannot drift from the files it points at.

Generic extraction (any repo): every dated heading in a declared record file is an event.

    ### 2026-09-11T08:41Z — [pivot] the substrate changes
    ## 2026-08-26 — [decision] the library narrows its scope

The tag names the kind — pivot · kill · decision · lesson · instrument · result — and an
untagged heading is a plain `entry`. A repo declares its record in kit.json:

    "record": ["HISTORY.md", "journal/log.md", "decisions/"],
    "chronicle": {
      "sources":    ["HISTORY.md", "journal/", "decisions/"],
      "extractors": ["kit/tools/chronicle_x.py"]
    }

`record` names the files a reader browses in the sidebar (files only; a directory or a
glob there is ignored for the sidebar — the scanner sweeps `chronicle.sources` instead).
When `chronicle.sources` is absent the scanner falls back to `record`, so a small repo
gets away with declaring one thing.

Extractors are plugins for a vocabulary the engine does not know. Each is a Python file exposing

    def extract(root: pathlib.Path, cfg: dict) -> dict:   # {"events": [...], "cards": [...]}

and optionally

    KINDS = [{"name": "release", "hue": "teal"}, ...]      # event kinds it emits (hue: a shell
                                                           #   hue; "story": false keeps a kind
                                                           #   out of the Story view)
    CARDS = {"view": "releases", "label": "Releases", "kind": "release", "empty": "…"}

Its events are merged, validated and sorted with the generic ones; an event whose kind neither
the core nor an extractor declares fails loud. Cards are one per long-lived thing the record
tracks (a release, a pre-registered experiment), rendered as a third view named by `CARDS`.

Schema (content/chronicle.json):
    kinds[]:  name · hue · story                 — the core kinds, then each extractor's
    events[]: date · kind · title · summary · href · source · links[{label, href}] · (extra keys pass through)
    cards?:   {view, label, kind, empty, items[]} — items[]: title · href · date? · status? ·
              fields[{label, text? | link?{label, href} | items?[{chip?, label, href, text?}], empty?}]
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from .paths import Repo
from .text import normalize

# The core kinds, in legend order, with the shell hue each is drawn in. `entry` is an untagged
# heading: it stays out of the Story view and is listed last.
CORE_KINDS = (
    {"name": "pivot", "hue": "orange", "story": True},
    {"name": "kill", "hue": "red", "story": True},
    {"name": "decision", "hue": "violet", "story": True},
    {"name": "lesson", "hue": "amber", "story": True},
    {"name": "instrument", "hue": "azure", "story": True},
    {"name": "result", "hue": "kept", "story": True},
)
ENTRY = {"name": "entry", "hue": "ink", "story": False}
TAGS = tuple(k["name"] for k in CORE_KINDS)

DATED = re.compile(
    r"^(#{2,4})\s+(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}Z)?)\s*[—–-]\s*(?:\[([a-z][a-z-]*)\]\s*)?(.+?)\s*$"
)
H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)
_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Heading → anchor id. The viewer (shell/record.html) computes the same, so links land."""
    return _SLUG_BAD.sub("-", text.lower()).strip("-")


def viewer_href(rel: str, anchor: str | None = None) -> str:
    return f"/shell/record.html?p={rel}" + (f"#{anchor}" if anchor else "")


def _expand(repo: Repo, items: list, key: str) -> list[Path]:
    """Files, directories (all .md beneath), and globs → a de-duped list of .md files."""
    out: list[Path] = []
    for item in items:
        if "*" in item:
            out.extend(p for p in sorted(repo.root.glob(item)) if p.is_file() and p.suffix == ".md")
            continue
        p = repo.root / item
        if p.is_dir():
            out.extend(sorted(q for q in p.rglob("*.md") if q.is_file()))
        elif p.is_file():
            out.append(p)
        else:
            raise SystemExit(f"kit.json {key}: {item!r} does not exist")
    seen: set[Path] = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def record_files(repo: Repo) -> list[Path]:
    """What the generic scanner sweeps: chronicle.sources, else record."""
    sources = (repo.cfg.get("chronicle") or {}).get("sources")
    if sources is not None:
        return _expand(repo, sources, "chronicle.sources")
    return _expand(repo, repo.cfg.get("record") or [], "record")


def md_title(text: str, fallback: str) -> str:
    m = H1.search(text)
    return normalize(m.group(1)) if m else fallback


def _summary(lines: list[str], start: int, limit: int = 240) -> str:
    """The first paragraph after a heading, flattened."""
    buf: list[str] = []
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("#"):
            break
        if not s:
            if buf:
                break
            continue
        buf.append(s)
    return normalize(" ".join(buf))[:limit]


def extractor_kinds(mods: list) -> list[dict]:
    """The kinds every extractor declares (KINDS), validated, in declaration order."""
    out: list[dict] = []
    seen = set(TAGS) | {"entry"}
    for mod in mods:
        for k in getattr(mod, "KINDS", None) or []:
            k = {"name": k} if isinstance(k, str) else k
            if not isinstance(k, dict) or not isinstance(k.get("name"), str) \
                    or not re.fullmatch(r"[a-z][a-z-]*", k["name"]):
                raise SystemExit(f"{mod.__name__}: KINDS entries are names or {{name, hue, story}}: {k!r}")
            if k["name"] in seen:
                continue
            seen.add(k["name"])
            out.append({"name": k["name"], "hue": str(k.get("hue") or "ink"),
                        "story": bool(k.get("story", True))})
    return out


def kinds(repo: Repo, mods: list | None = None) -> list[dict]:
    """Every kind this repo's chronicle may hold: the core tags, the extractors', then entry."""
    mods = load_extractors(repo) if mods is None else mods
    return [dict(k) for k in CORE_KINDS] + extractor_kinds(mods) + [dict(ENTRY)]


def extract_headings(repo: Repo, path: Path, known: set[str] | None = None) -> list[dict]:
    rel = path.relative_to(repo.root).as_posix()
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    events: list[dict] = []
    for i, ln in enumerate(lines):
        m = DATED.match(ln)
        if not m:
            continue
        _, date, tag, title = m.groups()
        kind = tag or "entry"
        if kind not in (known if known is not None else set(TAGS) | {"entry"}):
            raise SystemExit(
                f"{rel}:{i + 1}: unknown chronicle tag [{tag}] — one of " + " · ".join(TAGS)
                + " (or a kind an extractor declares)"
            )
        events.append({
            "date": date,
            "kind": kind,
            "title": normalize(title),
            "summary": _summary(lines, i + 1),
            "href": viewer_href(rel, slugify(f"{date} {title}")),
            "source": rel,
            "links": [],
        })
    return events


def load_extractors(repo: Repo) -> list:
    cfg = repo.cfg.get("chronicle") or {}
    mods = []
    for item in cfg.get("extractors") or []:
        p = repo.root / item
        if not p.is_file():
            raise SystemExit(f"kit.json chronicle.extractors: {item!r} not found")
        spec = importlib.util.spec_from_file_location(f"chronicle_ext_{p.stem}", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        if not hasattr(mod, "extract"):
            raise SystemExit(f"{item}: an extractor must define extract(root, cfg)")
        mods.append(mod)
    return mods


def _validate(ev: dict, where: str, known: set[str]) -> None:
    for k in ("date", "kind", "title", "href"):
        if not isinstance(ev.get(k), str) or not ev[k]:
            raise SystemExit(f"{where}: event missing {k!r}: {ev!r}"[:300])
    if ev["kind"] not in known:
        raise SystemExit(f"{where}: event kind {ev['kind']!r} is not declared — the core kinds are "
                         f"{', '.join(TAGS)}; an extractor declares its own in KINDS")
    ev.setdefault("summary", "")
    ev.setdefault("links", [])
    ev.setdefault("source", "")


def _cards(mod, items: list, where: str) -> dict:
    spec = getattr(mod, "CARDS", None)
    if not isinstance(spec, dict) or not spec.get("view") or not spec.get("label"):
        raise SystemExit(f"{where}: an extractor that returns cards declares CARDS = "
                         "{'view': …, 'label': …, 'kind': …, 'empty': …}")
    for c in items:
        if not isinstance(c, dict) or not c.get("title") or not c.get("href"):
            raise SystemExit(f"{where}: a card needs a title and an href: {c!r}"[:300])
        c.setdefault("fields", [])
    return {"view": str(spec["view"]), "label": str(spec["label"]),
            "kind": str(spec.get("kind") or ""), "empty": str(spec.get("empty") or ""),
            "items": sorted(items, key=lambda c: (c.get("date") or "", c["title"]), reverse=True)}


def build(repo: Repo) -> dict:
    mods = load_extractors(repo)
    all_kinds = kinds(repo, mods)
    known = {k["name"] for k in all_kinds}
    events: list[dict] = []
    cards: dict | None = None
    for p in record_files(repo):
        events.extend(extract_headings(repo, p, known))
    for mod in mods:
        out = mod.extract(repo.root, repo.cfg) or {}
        for ev in out.get("events") or []:
            _validate(ev, mod.__name__, known)
            events.append(ev)
        if out.get("cards"):
            if cards is not None:
                raise SystemExit(f"{mod.__name__}: only one extractor may supply cards")
            cards = _cards(mod, list(out["cards"]), mod.__name__)
    events.sort(key=lambda e: (e["date"], e["kind"], e["title"]), reverse=True)
    out = {"version": 2, "kinds": all_kinds, "events": events}
    if cards is not None:
        out["cards"] = cards
    return out


def enabled(repo: Repo) -> bool:
    cfg = repo.cfg.get("chronicle") or {}
    return bool(repo.cfg.get("record")) or bool(cfg.get("sources")) or bool(cfg.get("extractors"))


def record_catalog(repo: Repo) -> list[dict]:
    """Sidebar entries — files declared in `record` only (a dir/glob there is scanner-only).

    The sidebar is a curated front door: a repo lists the ledger and the standing surfaces
    a reader wants to browse, not the whole tree the scanner sweeps for dated headings.
    """
    out = []
    for item in repo.cfg.get("record") or []:
        if "*" in item:
            continue  # a glob is a scanner sweep, not a sidebar item
        p = repo.root / item
        if p.is_dir() or p.suffix != ".md":
            continue
        if not p.is_file():
            raise SystemExit(f"kit.json record: {item!r} does not exist")
        rel = p.relative_to(repo.root).as_posix()
        out.append({"title": md_title(p.read_text(encoding="utf-8", errors="replace"), p.stem),
                    "path": rel, "href": viewer_href(rel)})
    return out

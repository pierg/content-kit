"""The chronicle: a generated timeline of the record — never authored.

`content/` shows the current direction. How it got there lives in the record — logbooks,
missions, locked pre-registrations, findings — which is append-only and stays markdown. The
chronicle is an index over that record, regenerated like the catalog and the search index
(`ckit lint` / `ckit nav`), checked current by `ckit check`, and rendered by
`/shell/chronicle.html`. Nobody writes it, so it cannot drift from the files it points at.

Generic extraction (any repo): every dated heading in a declared record file is an event.

    ### 2026-09-11T08:41Z — [pivot] the substrate changes
    ## 2026-08-26 — [decision] folio becomes a library

The tag names the kind — pivot · kill · decision · lesson · instrument · result — and an
untagged heading is a plain `entry`. A repo declares its record in lab.json:

    "record": ["HISTORY.md", "QUESTIONS.md", "ops/", "record/", "experiments/*/PROBE.md"],
    "chronicle": {
      "sources":    ["HISTORY.md", "ops/", "record/", "experiments/*/PROBE.md"],
      "extractors": ["kit/tools/chronicle_lab.py"]
    }

`record` names the files a reader browses in the sidebar (files only; a directory or a
glob there is ignored for the sidebar — the scanner sweeps `chronicle.sources` instead).
When `chronicle.sources` is absent the scanner falls back to `record`, so a small repo
gets away with declaring one thing.

Extractors are plugins for a vocabulary the engine does not know (a lab's PROBEs, F-<n>
findings, missions). Each is a Python file exposing

    def extract(root: pathlib.Path, cfg: dict) -> dict:   # {"events": [...], "experiments": [...]}

and its output is merged, validated and sorted with the generic events.

Schema (content/chronicle.json):
    events[]:      date · kind · title · summary · href · source · links[{label, href}] · experiment?
    experiments[]: slug · title · question · locked · status · kill_rule · href ·
                   findings[{id, title, status, href}] · supersedes? · superseded_by?
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from .paths import Repo
from .text import normalize

KINDS = ("entry", "pivot", "kill", "decision", "lesson", "instrument", "result",
         "experiment", "finding", "claim", "mission")

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
            raise SystemExit(f"lab.json {key}: {item!r} does not exist")
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


def extract_headings(repo: Repo, path: Path) -> list[dict]:
    rel = path.relative_to(repo.root).as_posix()
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    events: list[dict] = []
    for i, ln in enumerate(lines):
        m = DATED.match(ln)
        if not m:
            continue
        _, date, tag, title = m.groups()
        kind = tag or "entry"
        if kind not in KINDS:
            raise SystemExit(
                f"{rel}:{i + 1}: unknown chronicle tag [{tag}] — one of "
                + " · ".join(k for k in KINDS if k not in ("experiment", "finding", "claim", "mission"))
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
            raise SystemExit(f"lab.json chronicle.extractors: {item!r} not found")
        spec = importlib.util.spec_from_file_location(f"chronicle_ext_{p.stem}", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        if not hasattr(mod, "extract"):
            raise SystemExit(f"{item}: an extractor must define extract(root, cfg)")
        mods.append(mod)
    return mods


def _validate(ev: dict, where: str) -> None:
    for k in ("date", "kind", "title", "href"):
        if not isinstance(ev.get(k), str) or not ev[k]:
            raise SystemExit(f"{where}: event missing {k!r}: {ev!r}"[:300])
    if ev["kind"] not in KINDS:
        raise SystemExit(f"{where}: event kind {ev['kind']!r} not in {KINDS}")
    ev.setdefault("summary", "")
    ev.setdefault("links", [])
    ev.setdefault("source", "")


def build(repo: Repo) -> dict:
    events: list[dict] = []
    experiments: list[dict] = []
    for p in record_files(repo):
        events.extend(extract_headings(repo, p))
    for mod in load_extractors(repo):
        out = mod.extract(repo.root, repo.cfg) or {}
        for ev in out.get("events") or []:
            _validate(ev, mod.__name__)
            events.append(ev)
        for ex in out.get("experiments") or []:
            for k in ("slug", "title", "href"):
                if not ex.get(k):
                    raise SystemExit(f"{mod.__name__}: experiment missing {k!r}: {ex!r}"[:300])
            experiments.append(ex)
    events.sort(key=lambda e: (e["date"], e["kind"], e["title"]), reverse=True)
    experiments.sort(key=lambda x: (x.get("locked") or "", x["slug"]), reverse=True)
    return {"version": 1, "events": events, "experiments": experiments}


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
            raise SystemExit(f"lab.json record: {item!r} does not exist")
        rel = p.relative_to(repo.root).as_posix()
        out.append({"title": md_title(p.read_text(encoding="utf-8", errors="replace"), p.stem),
                    "path": rel, "href": viewer_href(rel)})
    return out

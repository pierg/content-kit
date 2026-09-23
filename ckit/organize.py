"""Organise a library without breaking it: topics, tags, and pages that move.

    ckit topics                                  every topic: label · hub · pages; what is off the list
    ckit topics add <slug> [--label L]           declare a topic (then its hub: `ckit new hub <slug>`)
    ckit topics rename <old> <new> [--label L]   one slug for another, on every page and in kit.json
    ckit topics merge <a> [<b>…] --into <c> [--label L]
                                                 their pages move onto <c>; the old slugs become tags
    ckit topics assign <slug> <page>…            put pages on a topic — how a topic is split
    ckit tags                                    every tag and its pages; spellings that look alike
    ckit tags rename <old> <new>                 one tag for another, on every page
    ckit mv <page> <to>                          move a page (a folder page with all it holds)
    ckit rm <page> --to <page>                   retire a page into another

A page's address is part of the library: other pages link to it, its annotation sidecar sits
beside it, the catalog dates it by it, and readers bookmark it. `ckit mv` and `ckit rm` rewrite
every link to it (and a moved page's own relative links), carry its sidecar and its created
date (its updated date becomes the day it moved), and record the old address in kit.json
`moved`, which `ckit serve` and the exported site redirect. `ckit rm` deletes only what git can
bring back, and never a page with an open annotation thread.
A topic is metadata, not a folder, so re-topicking a page never changes its address.

Every verb edits pages in place and regenerates the indices; the gate then names what is left
for an author, such as a merged topic's two hubs to fold into one.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import posixpath
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote

from . import annotations as ann
from . import book_nav, links
from .genres import classify, load_genres
from .lint import TAG_SLUG, iter_pages
from .paths import Repo, load_repo
from .text import set_meta

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CARD = re.compile(r'<details\b[^>]*class=["\'][^"\']*\b(?:fcard|check)\b', re.I)


# ----------------------------------------------------------------------------- kit.json

def _cfg_path(repo: Repo) -> Path:
    return repo.marker or repo.root / "kit.json"


def _load_cfg(repo: Repo) -> dict:
    return json.loads(_cfg_path(repo).read_text(encoding="utf-8"))


def _save_cfg(repo: Repo, cfg: dict) -> Repo:
    _cfg_path(repo).write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return load_repo(repo.root)


def declared(repo: Repo) -> dict[str, str]:
    """kit.json `topics` as {slug: label} — an object, or a list of slugs."""
    t = repo.cfg.get("topics")
    if isinstance(t, dict):
        return {str(k): str(v or k) for k, v in t.items()}
    if isinstance(t, list):
        return {str(s): str(s) for s in t}
    return {}


def _label(slug: str) -> str:
    return slug.replace("-", " ").capitalize()


# ----------------------------------------------------------------------------- pages

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _write(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")


def _page(repo: Repo, ref: str) -> Path:
    try:
        return ann.resolve_page(repo, ref)
    except ann.AnnotationError as exc:
        raise SystemExit(str(exc)) from exc


def _address(repo: Repo, p: Path) -> str:
    return ann.href_of(repo, p)


def _hub_dir(repo: Repo) -> Path | None:
    g = load_genres(repo).get("hub")
    return repo.content / g.dir if g else None


def _regenerate(repo: Repo) -> None:
    written = book_nav.regenerate(repo)
    if written:
        print("  indices: " + ", ".join(written))


# ----------------------------------------------------------------------------- topics

def topics_report(repo: Repo) -> str:
    topics = declared(repo)
    hub_dir = _hub_dir(repo)
    on: dict[str, list[Path]] = {}
    hubs: dict[str, list[Path]] = {}
    none: list[Path] = []
    for p in iter_pages(repo):
        t = book_nav.topic_of(_read(p))
        if not t:
            none.append(p)
            continue
        on.setdefault(t, []).append(p)
        if hub_dir is not None and p.parent == hub_dir:
            hubs.setdefault(t, []).append(p)
    if not topics and not on:
        return "no topics — declare one: ckit topics add <slug> [--label \"…\"]"
    w = max((len(s) for s in topics), default=0)
    lines = []
    for slug, label in topics.items():
        hub = ", ".join(repo.rel(h) for h in hubs.get(slug, [])) or "NO HUB"
        lines.append(f"{slug:<{w}}  {label} · {hub} · {len(on.get(slug, []))} page(s)")
    off = sorted(set(on) - set(topics))
    if off:
        lines.append("not declared: " + ", ".join(f"{t} ({len(on[t])})" for t in off))
    if topics and none:
        more = " …" if len(none) > 6 else ""
        lines.append(f"no topic: {len(none)} page(s) — " + ", ".join(repo.rel(p) for p in none[:6]) + more)
    return "\n".join(lines)


def topics_add(repo: Repo, slug: str, label: str | None = None) -> Repo:
    if not SLUG.match(slug):
        raise SystemExit(f"topic {slug!r}: a lowercase slug (a-z 0-9 -)")
    if slug in declared(repo):
        raise SystemExit(f"topic {slug!r} is already declared")
    cfg = _load_cfg(repo)
    t = cfg.setdefault("topics", {})
    if isinstance(t, list) and label:  # a label needs the object form; the others keep their slugs
        cfg["topics"] = t = {str(x): str(x) for x in t}
        print("  kit.json topics: a list of slugs, now an object of slug → label")
    label = label or _label(slug)
    if isinstance(t, list):
        t.append(slug)
    elif isinstance(t, dict):
        t[slug] = label
    else:
        raise SystemExit("kit.json topics: must be an object {slug: label} or a list of slugs")
    repo = _save_cfg(repo, cfg)
    _regenerate(repo)
    print(f"declared topic {slug!r} ({label}) — its front door next: "
          f'ckit new hub {slug} --title "{label}"')
    return repo


def _retopic(pages: dict[Path, str], *, keep_old_as_tag: bool) -> int:
    changed = 0
    for p, new in pages.items():
        text = _read(p)
        old = book_nav.topic_of(text)
        out = set_meta(text, "topic", new)
        if keep_old_as_tag and old and old != new:
            tags = book_nav.tags_of(out)
            if old not in tags:
                out = set_meta(out, "tags", ", ".join([*tags, old]))
        if out != text:
            _write(p, out)
            changed += 1
    return changed


def _on(repo: Repo, topics: set[str]) -> list[Path]:
    return [p for p in iter_pages(repo) if book_nav.topic_of(_read(p)) in topics]


def topics_rename(repo: Repo, old: str, new: str, label: str | None = None) -> Repo:
    topics = declared(repo)
    if old not in topics:
        raise SystemExit(f"topic {old!r} is not declared — one of: {', '.join(topics) or '(none)'}")
    if new in topics:
        raise SystemExit(f"topic {new!r} is already declared — to fold {old!r} into it: "
                         f"ckit topics merge {old} --into {new}")
    if not SLUG.match(new):
        raise SystemExit(f"topic {new!r}: a lowercase slug (a-z 0-9 -)")
    cfg = _load_cfg(repo)
    t = cfg["topics"]
    if isinstance(t, list) and label:  # a label needs the object form
        t = {str(x): str(x) for x in t}
    if isinstance(t, dict):
        cfg["topics"] = {(new if k == old else k): ((label or v) if k == old else v) for k, v in t.items()}
    else:
        cfg["topics"] = [new if k == old else k for k in t]
    repo = _save_cfg(repo, cfg)
    n = _retopic({p: new for p in _on(repo, {old})}, keep_old_as_tag=False)
    print(f"renamed topic {old!r} → {new!r}: {n} page(s)")
    hub_dir = _hub_dir(repo)
    if hub_dir is not None and (hub_dir / f"{old}.html").is_file() and not (hub_dir / f"{new}.html").exists():
        repo = move(repo, hub_dir / f"{old}.html", hub_dir / f"{new}.html")
    else:
        _regenerate(repo)
    return repo


def topics_merge(repo: Repo, olds: list[str], into: str, label: str | None = None) -> Repo:
    topics = declared(repo)
    missing = [o for o in olds if o not in topics]
    if missing:
        raise SystemExit(f"not declared: {', '.join(missing)} — one of: {', '.join(topics) or '(none)'}")
    if into in olds:
        raise SystemExit("--into names the topic the others are folded into; it cannot be one of them")
    if not SLUG.match(into):
        raise SystemExit(f"topic {into!r}: a lowercase slug (a-z 0-9 -)")
    cfg = _load_cfg(repo)
    t = cfg["topics"]
    if isinstance(t, dict):
        out: dict[str, str] = {}
        for k, v in t.items():
            if k in olds:
                if into not in t and into not in out:
                    out[into] = label or _label(into)
                continue
            out[k] = label if (k == into and label) else v
        cfg["topics"] = out
    else:
        seq = []
        for k in t:
            if k in olds:
                if into not in t and into not in seq:
                    seq.append(into)
                continue
            seq.append(k)
        cfg["topics"] = seq
    repo = _save_cfg(repo, cfg)
    n = _retopic({p: into for p in _on(repo, set(olds))}, keep_old_as_tag=True)
    _regenerate(repo)
    print(f"merged {', '.join(olds)} into {into!r}: {n} page(s) re-topicked, each keeping its old "
          "topic as a tag")
    hub_dir = _hub_dir(repo)
    hubs = [p for p in _on(repo, {into}) if hub_dir is not None and p.parent == hub_dir]
    if len(hubs) > 1:
        keep = next((h for h in hubs if h.name == f"{into}.html"), hubs[0])
        rest = [h for h in hubs if h != keep]
        print(f"  {into!r} now has {len(hubs)} hubs: fold their maps into {repo.rel(keep)}, then retire "
              "the others into it — " + "; ".join(f"ckit rm {repo.rel(h)} --to {repo.rel(keep)}" for h in rest))
    return repo


def topics_assign(repo: Repo, slug: str, refs: list[str]) -> Repo:
    topics = declared(repo)
    if topics and slug not in topics:
        raise SystemExit(f"topic {slug!r} is not declared — ckit topics add {slug}")
    pages = [_page(repo, r) for r in refs]
    n = _retopic({p: slug for p in pages}, keep_old_as_tag=False)
    _regenerate(repo)
    print(f"{n} page(s) now on {slug!r}")
    return repo


# ----------------------------------------------------------------------------- tags

def _alike(tag: str) -> str:
    k = re.sub(r"[^a-z0-9]", "", tag.lower())
    return k[:-1] if len(k) > 3 and k.endswith("s") else k


def tags_report(repo: Repo) -> str:
    count: dict[str, int] = {}
    for p in iter_pages(repo):
        for t in book_nav.tags_of(_read(p)):
            count[t] = count.get(t, 0) + 1
    if not count:
        return 'no tags yet — <meta name="tags" content="a-tag, another">, or ckit new … --tags a,b'
    lines = [f"{n:4d}  {t}" for t, n in sorted(count.items(), key=lambda x: (-x[1], x[0]))]
    groups: dict[str, list[str]] = {}
    for t in count:
        groups.setdefault(_alike(t), []).append(t)
    for same in (sorted(g) for g in groups.values() if len(g) > 1):
        ok = [t for t in same if TAG_SLUG.match(t)]
        keep = ok[0] if ok else (re.sub(r"[^a-z0-9._-]+", "-", same[0].lower()).strip("-") or "tag")
        lines.append(f"alike: {' · '.join(same)} — one spelling: "
                     + "; ".join(f"ckit tags rename {t} {keep}" for t in same if t != keep))
    return "\n".join(lines)


def tags_rename(repo: Repo, old: str, new: str) -> Repo:
    if not TAG_SLUG.match(new):
        raise SystemExit(f"tag {new!r}: a lowercase slug (a-z 0-9 - . _)")
    n = 0
    for p in iter_pages(repo):
        text = _read(p)
        tags = book_nav.tags_of(text)
        if old not in tags:
            continue
        _write(p, set_meta(text, "tags", ", ".join(dict.fromkeys(new if t == old else t for t in tags))))
        n += 1
    _regenerate(repo)
    print(f"tag {old!r} → {new!r} on {n} page(s)")
    return repo


# ----------------------------------------------------------------------------- moves

def _suffix(url: str) -> str:
    cut = min((i for i in (url.find("?"), url.find("#")) if i >= 0), default=len(url))
    return url[cut:]


def _file_of(res: links.Resolver, rel: str) -> str | None:
    """The repo-relative file an address serves (a folder's index.html), when one does."""
    if rel.startswith("shell/") or rel == "shell" or not rel:
        return None
    found = res.exact(res.root, rel)
    if found is None:
        return None
    if found.is_dir():
        return rel.rstrip("/") + "/index.html" if (found / "index.html").is_file() else None
    return rel


def _rewrite(res: links.Resolver, page: Path, text: str, mapping: dict[str, str],
             new_page: str | None = None) -> tuple[str, int]:
    """`text` (the page at `page`, read before anything moves) with every link into `mapping`
    pointed at its new address. When the page itself moves to `new_page` (repo-relative), each of
    its relative links is kept only if it still names the same target from the new place, and is
    otherwise made root-absolute — shell and generated addresses included."""
    n = 0
    for start, end, _attr, url, quoted in reversed(links.links_in(text)):
        got = res.address(url, page)
        if got is None:
            continue
        rel0, as_dir = got
        if rel0 == ".." or rel0.startswith("../"):
            continue  # leaves the repository: the gate reports it
        rel = _file_of(res, rel0)
        relative = not url.startswith("/")
        if rel is not None and rel in mapping:
            target = mapping[rel]
        elif new_page is not None and relative:
            target = links.canon(rel) if rel is not None else "/" + rel0 + ("/" if as_dir and rel0 else "")
        else:
            continue
        if new_page is not None and relative:
            path = unquote(url.split("#", 1)[0].split("?", 1)[0])
            there = posixpath.normpath(posixpath.join(posixpath.dirname(new_page), path))
            if links.canon(there).rstrip("/") == target.rstrip("/"):
                continue  # still names the same target from the new place
        new = html_mod.escape(target + _suffix(url), quote=True)
        text = text[:start] + (new if quoted else f'"{new}"') + text[end:]
        n += 1
    return text, n


def _record_moves(repo: Repo, addresses: dict[str, str]) -> Repo:
    """kit.json: each old address redirects to its new one (chains collapse; a page moved back
    where it was drops its entry), and `home` and `links` follow the page."""
    cfg = _load_cfg(repo)
    moved = {str(k): str(v) for k, v in (cfg.get("moved") or {}).items()}
    for old, new in addresses.items():
        for k, v in list(moved.items()):
            if links.canon(v).rstrip("/") == links.canon(old).rstrip("/"):
                moved[k] = new
        moved[old] = new
    live = {links.canon(v).rstrip("/") for v in addresses.values()}
    moved = {k: v for k, v in moved.items()
             if links.canon(k).rstrip("/") != links.canon(v).rstrip("/")  # moved back where it was
             and links.canon(k).rstrip("/") not in live}                   # a page lives there again
    cfg["moved"] = dict(sorted(moved.items()))
    if not cfg["moved"]:
        cfg.pop("moved")
    canon_map = {links.canon(o).rstrip("/"): n for o, n in addresses.items()}
    home = cfg.get("home")
    if isinstance(home, str) and links.canon(home).rstrip("/") in canon_map:
        cfg["home"] = canon_map[links.canon(home).rstrip("/")].lstrip("/")
    for item in cfg.get("links") or []:
        if isinstance(item, dict) and isinstance(item.get("href"), str) \
                and links.canon(item["href"]).rstrip("/") in canon_map:
            item["href"] = canon_map[links.canon(item["href"]).rstrip("/")]
    return _save_cfg(repo, cfg)


def reclaim(repo: Repo, page: Path) -> str | None:
    """A new page at an address kit.json `moved` redirects takes the address back: the entry is
    dropped. Returns where it redirected, or None."""
    here = links.canon(ann.href_of(repo, page)).rstrip("/")
    cfg = _load_cfg(repo)
    moved = cfg.get("moved") or {}
    if not isinstance(moved, dict):
        return None
    was = next((v for k, v in moved.items() if links.canon(str(k)).rstrip("/") == here), None)
    if was is None:
        return None
    cfg["moved"] = {k: v for k, v in moved.items() if links.canon(str(k)).rstrip("/") != here}
    if not cfg["moved"]:
        cfg.pop("moved")
    _save_cfg(repo, cfg)
    if cfg.get("moved"):  # the caller's view of kit.json follows the file
        repo.cfg["moved"] = cfg["moved"]
    else:
        repo.cfg.pop("moved", None)
    return str(was)


def _carry_dates(repo: Repo, hrefs: dict[str, str]) -> None:
    """Rename entries in the committed catalog so the regenerated one finds a moved page's dates."""
    p = repo.content / "catalog.json"
    try:
        cat = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    changed = False
    for g in cat.get("groups") or []:
        for item in cat.get(g.get("key")) or [] if isinstance(g, dict) else []:
            if isinstance(item, dict) and item.get("href") in hrefs:
                item["href"] = hrefs[item["href"]]
                changed = True
    if changed:
        p.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _all_pages(repo: Repo) -> list[Path]:
    return sorted(repo.content.rglob("*.html")) if repo.content.is_dir() else []


def _owns_folder(repo: Repo, page: Path) -> bool:
    g = classify(repo, page, load_genres(repo))
    return page.name == "index.html" and g is not None and g.layout in ("folder", "book-index")


def _dest(repo: Repo, ref: str) -> Path:
    s = ref.strip().lstrip("/")
    p = repo.root / s
    return p / "index.html" if s.endswith("/") or not s.endswith(".html") else p


def move(repo: Repo, src: Path, dst: Path) -> Repo:
    """Move the page at `src` to `dst` (a page path; a folder page moves with all it holds)."""
    genres = load_genres(repo)
    src, dst = src.resolve(), dst.resolve()
    if dst.exists() and not _same(src, dst):
        raise SystemExit(f"{repo.rel(dst)} already exists")
    try:
        dst.relative_to(repo.content.resolve())
    except ValueError as exc:
        raise SystemExit(f"{repo.rel(dst)} is not under {repo.content_name}/") from exc
    if classify(repo, dst, genres) is None:
        raise SystemExit(f"{repo.rel(dst)} is outside any genre — pages live under "
                         f"{repo.content_name}/{{{', '.join(sorted({g.dir for g in genres.values()}))}}}")
    root = repo.root.resolve()
    whole = _owns_folder(repo, src) and dst.name == "index.html"
    files: dict[Path, Path] = {}
    if whole:
        if dst.parent.exists() and not _same(src.parent, dst.parent):
            raise SystemExit(f"{repo.rel(dst.parent)} already exists")
        if src.parent in dst.parents:
            raise SystemExit(f"cannot move {repo.rel(src.parent)} into itself")
        for f in sorted(src.parent.rglob("*")):
            if f.is_file():
                files[f] = dst.parent / f.relative_to(src.parent)
    else:
        if _owns_folder(repo, src):
            extra = [f for f in src.parent.rglob("*") if f.is_file() and f not in (src, ann.sidecar_for(src))]
            if extra:
                raise SystemExit(f"{repo.rel(src.parent)} holds more than its page ("
                                 + ", ".join(repo.rel(f) for f in extra[:4])
                                 + ") — move it as a folder: ckit mv "
                                 + f"{repo.rel(src)} {repo.rel(dst)[:-len('.html')]}/")
        files[src] = dst
        if ann.sidecar_for(dst).exists() and not _same(ann.sidecar_for(src), ann.sidecar_for(dst)):
            raise SystemExit(f"an annotation sidecar already sits at {repo.rel(ann.sidecar_for(dst))} — "
                             "an orphan from an earlier page: resolve it before moving a page there")
        if ann.sidecar_for(src).is_file():
            files[ann.sidecar_for(src)] = ann.sidecar_for(dst)
    rel = {f: f.relative_to(root).as_posix() for f in files}
    mapping = {rel[f]: (links.canon(t.relative_to(root).as_posix()) if f.suffix == ".html"
                        else "/" + t.relative_to(root).as_posix()) for f, t in files.items()}
    res = links.Resolver(repo)
    texts: dict[Path, str] = {}
    touched = rewritten = 0
    for p in _all_pages(repo):
        p = p.resolve()
        text = _read(p)
        out, n = _rewrite(res, p, text, mapping, files[p].relative_to(root).as_posix() if p in files else None)
        if n or p in files:
            texts[files.get(p, p)] = out
        if n and p not in files:
            touched += 1
        rewritten += n
    cards = sum(len(CARD.findall(_read(f))) for f in files if f.suffix == ".html")
    # every read is done: now move, then write
    if whole:
        dst.parent.parent.mkdir(parents=True, exist_ok=True)
        os.rename(src.parent, dst.parent) if _same(src.parent, dst.parent) else shutil.move(str(src.parent), str(dst.parent))
    else:
        for f, t in files.items():
            t.parent.mkdir(parents=True, exist_ok=True)
            os.rename(f, t) if _same(f, t) else shutil.move(str(f), str(t))
        if _owns_folder(repo, src) and src.parent.is_dir() and not any(src.parent.iterdir()):
            src.parent.rmdir()
    for p, text in texts.items():
        _write(p, text)
    for f, t in files.items():
        if t.name.endswith(".annotations.json"):
            data = ann.load(t)
            data["page"] = ann.href_of(repo, ann.page_for_sidecar(t))
            ann.save(t, data)
    pages = {links.canon(rel[f]): mapping[rel[f]] for f in files if f.suffix == ".html"}
    repo = _record_moves(repo, pages)
    _carry_dates(repo, pages)
    print(f"moved {repo.rel(src)} → {repo.rel(dst)}"
          + (f" (with {len(files) - 1} more file(s) in its folder)" if whole and len(files) > 1 else ""))
    print(f"  {rewritten} link(s) rewritten ({touched} other page(s)); redirect "
          f"{links.canon(rel[src])} → {mapping[rel[src]]} recorded in kit.json `moved`")
    if cards:
        print(f"  {cards} flashcard(s) on it: a schedule kept by page address (a folio's revise page) "
              "starts them afresh")
    _regenerate(repo)
    return repo


def _same(a: Path, b: Path) -> bool:
    """One file under two spellings — a case-only rename on a case-insensitive filesystem."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _uncommitted(repo: Repo, paths: list[Path]) -> list[str] | None:
    """What among `paths` git could not bring back (untracked, ignored, or changed since the last
    commit), or None when the repo is not a git work tree."""
    try:
        r = subprocess.run(["git", "-C", str(repo.root), "status", "--porcelain=v1", "-z", "--ignored",
                            "--untracked-files=all", "--", *[str(p) for p in paths]],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out, items, i = [], r.stdout.split(b"\0"), 0
    while i < len(items):
        entry = items[i]
        if len(entry) > 3:
            out.append(entry[3:].decode("utf-8", "replace"))
            if entry[:1] in (b"R", b"C"):  # a rename or copy: the next item is where it came from
                i += 1
        i += 1
    return out


def _open_threads(sidecars: list[Path]) -> list[Path]:
    return [sc for sc in sidecars if sc.is_file()
            and any(t.get("state") == "open" for t in ann.load(sc).get("threads", []))]


def remove(repo: Repo, page: Path, into: Path, *, folder: bool = False) -> Repo:
    """Retire `page` into `into`: links to it point there, and so does its old address. Only what
    git can bring back is deleted, and never a page with an open annotation thread."""
    page, into = page.resolve(), into.resolve()
    if page == into:
        raise SystemExit("a page cannot be retired into itself")
    root = repo.root.resolve()
    owns = _owns_folder(repo, page)
    sidecar = ann.sidecar_for(page)
    if owns:
        if into.parent == page.parent or page.parent in into.parents:
            raise SystemExit(f"--to names a page inside {repo.rel(page.parent)}, which is being retired")
        extra = [f for f in page.parent.rglob("*") if f.is_file() and f not in (page, sidecar)]
        if extra and not folder:
            raise SystemExit(f"{repo.rel(page.parent)} holds more than its page ("
                             + ", ".join(repo.rel(f) for f in extra[:4])
                             + ") — pass --folder to retire all of it")
        doomed = [page.parent]
        live = _open_threads(sorted(page.parent.rglob("*.annotations.json")))
        gone = sorted(page.parent.rglob("*.html"))
    else:
        doomed = [page, sidecar] if sidecar.exists() else [page]
        live = _open_threads([sidecar])
        gone = [page]
    if live:
        raise SystemExit(f"open annotation threads on {', '.join(repo.rel(x) for x in live)} — settle them "
                         "first (/address), or keep the page and move it")
    loose = _uncommitted(repo, doomed)
    if loose is None:
        raise SystemExit("not a git work tree — `ckit rm` deletes only what git can bring back; retire "
                         "the page by hand")
    if loose:
        raise SystemExit("not committed, so nothing could bring it back: " + ", ".join(loose[:6])
                         + (" …" if len(loose) > 6 else "") + " — commit it, or move it out, first")
    target = links.canon(into.relative_to(root).as_posix())
    mapping = {f.resolve().relative_to(root).as_posix(): target for f in gone}
    res = links.Resolver(repo)
    touched = rewritten = 0
    writes: dict[Path, str] = {}
    for p in _all_pages(repo):
        p = p.resolve()
        if p in gone or (owns and page.parent in p.parents):
            continue
        text = _read(p)
        out, n = _rewrite(res, p, text, mapping)
        if n:
            writes[p] = out
            touched += 1
            rewritten += n
    if owns:
        shutil.rmtree(page.parent)
    else:
        for f in doomed:
            f.unlink()
    for p, text in writes.items():
        _write(p, text)
    repo = _record_moves(repo, {links.canon(k): v for k, v in mapping.items()})
    print(f"retired {repo.rel(page)} into {repo.rel(into)}: {rewritten} link(s) rewritten "
          f"({touched} page(s)); its address redirects there (kit.json `moved`)")
    _regenerate(repo)
    return repo


# ----------------------------------------------------------------------------- CLI

def topics_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit topics", description="the library's topics")
    sub = ap.add_subparsers(dest="verb")
    p = sub.add_parser("add", help="declare a topic")
    p.add_argument("slug")
    p.add_argument("--label")
    p = sub.add_parser("rename", help="one slug for another, everywhere")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--label")
    p = sub.add_parser("merge", help="fold topics into one; the old slugs become tags")
    p.add_argument("olds", nargs="+")
    p.add_argument("--into", required=True)
    p.add_argument("--label")
    p = sub.add_parser("assign", help="put pages on a topic")
    p.add_argument("slug")
    p.add_argument("pages", nargs="+")
    args = ap.parse_args(argv)
    repo = load_repo()
    if args.verb is None:
        print(topics_report(repo))
    elif args.verb == "add":
        topics_add(repo, args.slug, args.label)
    elif args.verb == "rename":
        topics_rename(repo, args.old, args.new, args.label)
    elif args.verb == "merge":
        topics_merge(repo, args.olds, args.into, args.label)
    elif args.verb == "assign":
        topics_assign(repo, args.slug, args.pages)
    return 0


def tags_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit tags", description="the library's tags")
    sub = ap.add_subparsers(dest="verb")
    p = sub.add_parser("rename", help="one tag for another, on every page")
    p.add_argument("old")
    p.add_argument("new")
    args = ap.parse_args(argv)
    repo = load_repo()
    if args.verb is None:
        print(tags_report(repo))
    else:
        tags_rename(repo, args.old, args.new)
    return 0


def mv_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit mv", description="move a page without breaking a link to it")
    ap.add_argument("page", help="the page: content/notes/x.html, /content/entries/y/")
    ap.add_argument("to", help="where it goes: content/entries/x/ (a folder page) or content/notes/y.html")
    args = ap.parse_args(argv)
    repo = load_repo()
    move(repo, _page(repo, args.page), _dest(repo, args.to))
    return 0


def rm_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit rm", description="retire a page into another")
    ap.add_argument("page")
    ap.add_argument("--to", required=True, help="the page that takes over its links and its address")
    ap.add_argument("--folder", action="store_true", help="a folder page: retire everything it holds")
    args = ap.parse_args(argv)
    repo = load_repo()
    remove(repo, _page(repo, args.page), _page(repo, args.to), folder=args.folder)
    return 0

"""Every internal link resolves: `ckit lint` checks it, and `ckit mv` rewrites by it.

A link to an address nothing answers is a 404 a reader finds before the author does: a page
moved, a hub folded into another, a skeleton's placeholder never replaced. The resolver answers
what the server would, without a server:

  /                      the landing page (generated)
  /shell/<file>          the vendored shell, or a kit.json `shell_pages` entry
  /shell/theme.css · /shell/pagefind.json · /pagefind/… · /__annotations/…     generated
  /<path>                a file under the repo root, or a directory holding an index.html
  <relative>             the same, from the page's own directory

It is as strict as the exported site, where that is stricter than `ckit serve`: a directory
without an index.html (the server lists it, a static host 404s), a bare slug (the server
redirects it, a static host does not), a letter-case mismatch (a Mac forgives it, a Linux host
does not), and a file git ignores (it is here and in no clone, so CI and every other checkout
404). A link to an address kit.json `moved` redirects is reported too: the redirect keeps the
world's bookmarks working, while the library's own links name the page where it is now.

`data-unchecked` on the element exempts one link the gate cannot see: a build product, or an
address another process serves.
"""

from __future__ import annotations

import html as html_mod
import json
import os
import posixpath
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from . import config
from .paths import Repo

SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
TAG = re.compile(r"<([A-Za-z][\w:-]*)\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.S)
URL_ATTR = re.compile(r"""(?<![\w:-])(href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""", re.I)
UNCHECKED = re.compile(r"(?<![\w:-])data-unchecked(?![\w-])", re.I)
COMMENT = re.compile(r"<!--.*?-->", re.S)
BODY = re.compile(r"(<(script|style|noscript|template)\b[^>]*>)(.*?)(</\2\s*>)", re.S | re.I)
GENERATED = {"shell/theme.css", "shell/pagefind.json"}
GENERATED_PREFIX = ("pagefind/", "__annotations/")
PLACEHOLDER = re.compile(r"(?:^|/)OTHER(?:[./#]|$)")


def _blank(s: str) -> str:
    return re.sub(r"[^\n]", " ", s)


def served_markup(text: str) -> str:
    """The page as a reader is served it, at the same offsets: comments blanked, and the bodies
    of script, style, noscript and template blanked (their opening tags, and a script's src, stay)."""
    text = COMMENT.sub(lambda m: _blank(m.group(0)), text)
    return BODY.sub(lambda m: m.group(1) + _blank(m.group(3)) + m.group(4), text)


def links_in(text: str) -> list[tuple[int, int, str, str, bool]]:
    """(start, end, attribute, url, quoted) of every href and src on the served page — the
    offsets are those of the value in `text` (inside its quotes, when it has them), so a rewrite
    can replace exactly it."""
    masked = served_markup(text)
    out: list[tuple[int, int, str, str, bool]] = []
    for t in TAG.finditer(masked):
        attrs = t.group(2)
        if UNCHECKED.search(attrs):
            continue
        for a in URL_ATTR.finditer(attrs):
            g = next(i for i in (2, 3, 4) if a.group(i) is not None)
            start = t.start(2) + a.start(g)
            end = t.start(2) + a.end(g)
            out.append((start, end, a.group(1).lower(), html_mod.unescape(a.group(g)), g != 4))
    return out


def canon(address: str) -> str:
    """An address as the library names a page: /content/x/index.html and /content/x both name
    /content/x/; a file keeps its name."""
    a = "/" + address.lstrip("/")
    if a.endswith("/index.html"):
        a = a[: -len("index.html")]
    return a


def moved_map(repo: Repo) -> dict[str, str]:
    """kit.json `moved` — {old address: new address} — keyed canonically."""
    got = repo.cfg.get("moved") or {}
    if not isinstance(got, dict):
        return {}
    return {canon(str(k)).rstrip("/"): canon(str(v)) for k, v in got.items()}


def moved_now(repo: Repo) -> dict[str, str]:
    """kit.json `moved` as the file says it now — a running server sees a `ckit mv` made after
    it started without a restart."""
    try:
        cfg = json.loads((repo.marker or repo.root / "kit.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = repo.cfg
    return moved_map(Repo(root=repo.root, cfg={"moved": cfg.get("moved") if isinstance(cfg, dict) else None}))


def follow(moved: dict[str, str], address: str, limit: int = 32) -> str | None:
    """Where `address` has moved to (following a chain), or None when it has not moved."""
    cur, seen = canon(address).rstrip("/"), 0
    target = None
    while cur in moved and seen < limit:
        target = moved[cur]
        cur = target.rstrip("/")
        seen += 1
    return target


def _git_ignored(root: Path) -> tuple[set[str], tuple[str, ...]]:
    """(ignored files, ignored directories as 'dir/' prefixes), repo-relative — empty outside git."""
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--others", "--ignored",
                            "--exclude-standard", "--directory"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return set(), ()
    if r.returncode != 0:
        return set(), ()
    files: set[str] = set()
    dirs: list[str] = []
    for raw in r.stdout.split(b"\0"):
        entry = raw.decode("utf-8", "replace")
        if not entry:
            continue
        (dirs.append(entry) if entry.endswith("/") else files.add(entry))
    return files, tuple(dirs)


class Resolver:
    """One per lint run: directory listings and git's ignore list are read once and cached."""

    def __init__(self, repo: Repo):
        self.repo = repo
        self.root = repo.root.resolve()
        self.shell = repo.shell
        self.pages = config.shell_pages(repo)
        self.moved = moved_map(repo)
        self._ls: dict[str, set[str] | None] = {}
        self._ignored: tuple[set[str], tuple[str, ...]] | None = None

    def _names(self, d: Path) -> set[str] | None:
        key = str(d)
        if key not in self._ls:
            try:
                self._ls[key] = set(os.listdir(d))
            except OSError:
                self._ls[key] = None
        return self._ls[key]

    def exact(self, base: Path, rel: str) -> Path | None:
        """base/rel when every part of it exists with exactly this letter case."""
        cur = base
        for part in (p for p in rel.split("/") if p):
            names = self._names(cur)
            if names is None or part not in names:
                return None
            cur = cur / part
        return cur

    def folded(self, base: Path, rel: str) -> str | None:
        """The path that matches rel ignoring letter case, when exactly one does."""
        cur, got = base, []
        for part in (p for p in rel.split("/") if p):
            names = self._names(cur) or set()
            hits = [n for n in names if n.lower() == part.lower()]
            if len(hits) != 1:
                return None
            got.append(hits[0])
            cur = cur / hits[0]
        return "/".join(got)

    def ignored(self, target: Path) -> bool:
        if self._ignored is None:
            self._ignored = _git_ignored(self.root)
        files, dirs = self._ignored
        try:
            rel = target.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return False
        return rel in files or any(rel.startswith(d) for d in dirs)

    def address(self, url: str, page: Path) -> tuple[str, bool] | None:
        """(repo-relative path, written as a directory) that `url` on `page` names, or None when
        it is not the library's to resolve (another site, a fragment, a query alone)."""
        if not url or url.startswith(("#", "//")) or SCHEME.match(url):
            return None
        path = url.split("#", 1)[0].split("?", 1)[0]
        if not path:
            return None
        path = unquote(path)
        as_dir = path.endswith("/")
        if path.startswith("/"):
            rel = path.strip("/")
        else:
            try:
                here = page.parent.resolve().relative_to(self.root).as_posix()
            except ValueError:
                here = ""
            rel = posixpath.join(here, path) if here not in ("", ".") else path
        rel = posixpath.normpath(rel) if rel else ""
        return ("" if rel == "." else rel), as_dir

    def target(self, rel: str) -> Path | None:
        """The file a repo-relative address serves, when one does (an index.html for a folder)."""
        if rel.startswith("shell/") or rel == "shell":
            tail = rel[len("shell/"):] if rel != "shell" else ""
            if tail in self.pages:
                return self.pages[tail] if self.pages[tail].is_file() else None
            found = self.exact(self.shell, tail)
        else:
            found = self.exact(self.root, rel)
        if found is not None and found.is_dir():
            found = found / "index.html" if (found / "index.html").is_file() else None
        return found

    def problem(self, url: str, page: Path) -> str | None:
        """None when `url`, written on `page`, resolves; else why it does not."""
        got = self.address(url, page)
        if got is None:
            return None
        rel, as_dir = got
        if rel == ".." or rel.startswith("../"):
            return "leaves the repository"
        if rel == "" or rel in GENERATED or rel.startswith(GENERATED_PREFIX):
            return None
        shell = rel.startswith("shell/") or rel == "shell"
        tail = rel[len("shell/"):] if shell and rel != "shell" else ("" if shell else rel)
        if shell and tail in self.pages:
            return None if self.pages[tail].is_file() else "a kit.json shell page whose file is missing"
        base = self.shell if shell else self.root
        found = self.exact(base, tail)
        if found is None:
            new = None if shell else follow(self.moved, "/" + rel)  # only a missing address has moved
            if new:
                return f"moved to {new} (kit.json `moved`) — link the new address"
            if PLACEHOLDER.search(rel):
                return "a skeleton's placeholder — link a real page, or drop the link"
            slug = self._slug(rel) if not shell and "/" not in rel else None
            if slug:
                return f"a bare slug — `ckit serve` redirects it, a static host 404s: link {slug}"
            folded = self.folded(base, tail)
            if folded:
                prefix = "/shell/" if shell else "/"
                return (f"differs in letter case from {prefix}{folded} — a Mac forgives it, the "
                        "exported site on a Linux host 404s")
            return "nothing lives there"
        if found.is_dir():
            if not (found / "index.html").is_file():
                return ("a directory without an index.html — `ckit serve` lists it, the exported "
                        "site 404s")
            found = found / "index.html"
        elif as_dir:
            return "names a file as a directory (a trailing /)"
        if self.ignored(found):
            return "git ignores it — it exists here and in no clone"
        return None

    def _slug(self, slug: str) -> str | None:
        from .book_nav import _href_of
        from .serve import _slug_file
        p = _slug_file(self.repo, slug)
        return _href_of(self.repo, p) if p is not None else None


def address_problem(address: object) -> str | None:
    """Why `address` cannot be a kit.json `moved` address, or None: a site path from the root —
    one leading slash, no `.` or `..` segment, no backslash, no scheme."""
    if not isinstance(address, str) or not address.startswith("/") or address.startswith("//"):
        return "is not a site address (one leading /)"
    if "\\" in address or SCHEME.match(address.lstrip("/")) or any(c in address for c in "?#\0"):
        return "is not a plain path"
    if any(part in (".", "..") for part in address.split("/")):
        return "has a . or .. segment"
    return None


def moved_problems(repo: Repo) -> list[str]:
    """kit.json `moved`, read against the tree: an old address where a page lives again, a chain
    that ends where no page lives, a cycle. Reported with the lint, so the rest of the gate runs."""
    got = repo.cfg.get("moved") or {}
    if not isinstance(got, dict):
        return []
    res = Resolver(repo)
    moved = moved_map(repo)
    out: list[str] = []
    for old in got:
        if address_problem(old) or address_problem(got[old]):
            continue  # a malformed entry is config's to report
        seen, cur = set(), canon(old).rstrip("/")
        while cur in moved and cur not in seen:
            seen.add(cur)
            cur = moved[cur].rstrip("/")
        if cur in moved:
            out.append(f"kit.json moved: {old} is part of a cycle of redirects")
            continue
        if res.target(canon(old).strip("/")) is not None:
            out.append(f"kit.json moved: a page lives at {old} again — drop the entry (the page keeps "
                       "the address), or move the page")
        final = follow(moved, old) or got[old]
        if res.target(final.strip("/")) is None:
            out.append(f"kit.json moved: {old} ends at {final}, where no page lives")
    return out


def check_page(resolver: Resolver, rel: str, page: Path, text: str) -> list[str]:
    out: list[str] = []
    for start, _end, attr, url, _quoted in links_in(text):
        why = resolver.problem(url, page)
        if why:
            line = text.count("\n", 0, start) + 1
            out.append(f"{rel}:{line}: {attr} {url} — {why}")
    return out

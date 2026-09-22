"""Lint a content tree against the shell contract and the genre contract.

    ckit lint                 # every page; regenerates nav / catalog / search / backlinks
    ckit lint content/notes   # a subtree
    ckit lint --no-nav

Form (every page):
  1. no raw hex colors — use the shell's .hb tokens
  2. classes that look like shell vocabulary are actually in the allowlist
  3. every page loads /shell/lib.css
  4. no reference to the retired book.js / book.css

Genre (by position in the tree — see genres.json and genres/GENRES.md):
  5. every page belongs to a genre; a page outside any genre is an error, not a default
  6. status — the first <p class="sub"> declares LIVE · HISTORICAL · PARKED · RETIRED · FROZEN · DRAFT
  7. per-genre proxies for voice: word bounds, no <h2> in a note, a defn in a concept that cites
     no finding, no undeclared forward reference in a chapter, a lifecycle meta on a project,
     the fixed sections of a story in order and the rows its status line is sealed to

Annotations:
  8. every *.annotations.json validates and every quote it anchors is still on its page

This is the *content* gate. A lab's *record* gate — every number traces to a finding — is
lab-kit's ladder lint, and the two are deliberately separate: form is whether a page renders
like the rest of the library, the ladder is whether it is allowed to say what it says.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import annotations, book_nav, config, plugins
from .genres import Genre, classify, is_exempt, load_genres
from .paths import DOC_STATUS, Repo
from .text import DEFN_RE, STATUS_META_RE, SUB_RE, strip_tags, word_count

HEX = re.compile(r"(?<![\w-])#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
CLASS_ATTR = re.compile(r'\bclass="([^"]*)"')
SHELL_LINK = re.compile(r'href="/shell/lib\.css"')
BOOK_JS = re.compile(r'src=["\']book\.js["\']')
BOOK_CSS = re.compile(r"book\.css")
H2 = re.compile(r"<h2\b", re.I)
H2_ID = re.compile(r'<h2\b[^>]*\sid="([^"]+)"', re.I)
FINDING = re.compile(r"\bF-\d+(?:\.\d+)*\b")
# A row id as a page cites it: `F-12`, `F-22.1`, or another lab's pinned row, `dsl:F-3`.
BOUND_ID = re.compile(r"<code\b[^>]*>\s*(?:[a-z][a-z0-9_-]*:)?F-\d+(?:\.\d+)*\s*</code>", re.I)
COMMENT = re.compile(r"<!--.*?-->", re.S)
BURIED = re.compile(r"<(script|style|noscript|template)\b[^>]*>.*?</\1>", re.S | re.I)
ANCHOR = re.compile(r"<a\b([^>]*)>", re.I)
HREF = re.compile(r'href="([^"#?]+)', re.I)
NUMBERED = re.compile(r"^(\d+)-.+\.html$", re.I)
DEFN_NAME = re.compile(r'class="[^"]*\bdefn-name\b', re.I)

# Classes that claim to be shell vocabulary — must be known.
SHELLISH = re.compile(r"^(?:ev-|v-|st-|sw-|hb-|hb$|own$)")

ALLOWED = {
    # root / chrome
    "hb", "sub", "muted", "mono", "q", "anchors", "idx", "cols", "card",
    "check", "fcard", "ans", "back", "own", "law", "defn", "defn-name",
    "defn-link", "defn-pop", "defn-pop-name", "formula",
    "active", "here", "sep", "dhead", "did",
    # chips
    "ev", "ev-m", "ev-b", "ev-d", "ev-o",
    "v", "v-kept", "v-disc", "v-rej", "v-unt", "v-gen",
    "st", "st-done", "st-plan", "st-open",
    "sw-reach", "sw-cert", "sw-target", "sw-slack", "sw-leak",
    "sw-gen", "sw-judge", "sw-world",
    # lanes / motifs
    "lane", "lane-reach", "lane-cert", "lane-judge", "lane-gen",
    "lane-world", "lane-kept", "lane-baseline",
    "twin", "twin-tag", "twin-row", "twin-k",
    "split", "split-tag", "note", "note-warn",
    # widget primitives
    "tbtn", "on", "cyc", "prow", "cur", "skip", "nrow", "drawer", "hyp",
    "cell", "cellrow", "vline", "reach", "inS", "cap", "bad", "cti", "dead",
    "tag", "lbl", "gate", "gline", "g", "pass", "fail", "flat", "stop",
    "lchip", "new", "cbar", "ho", "mtable",
    "wcap", "wcap-sm", "wcap-md", "wcap-lg",
    "k", "d", "r", "c", "sel", "run", "viol",
    # injected by lib.js rather than authored in HTML
    "hb-nav", "hb-home", "hb-foot",
    "hb-has-shell", "hb-no-side", "hb-stage", "hb-side", "hb-side-open",
    "hb-side-toggle", "hb-side-backdrop", "hb-side-section", "hb-side-lib",
    "hb-side-search",
    "hb-side-label", "hb-side-list", "hb-toc", "hb-toc-label",
    "hb-kind", "hb-kind-book", "hb-kind-entry", "hb-kind-concept",
    "hb-kind-hub", "hb-kind-note", "hb-kind-project", "hb-kind-page",
    "hb-kind-paper", "hb-kind-related", "hb-kind-story",
}


def allowed_classes(repo: Repo, genres: dict[str, Genre]) -> set[str]:
    """The shell's vocabulary, a badge per loaded genre, and whatever kit.json `classes` adds."""
    return ALLOWED | {f"hb-kind-{name}" for name in genres} | config.classes(repo)


def _form(rel: str, text: str, allowed: set[str] = ALLOWED) -> list[str]:
    probs: list[str] = []
    for m in HEX.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        probs.append(f"{rel}:{line}: hex color {m.group(0)} — use shell tokens")
    if BOOK_CSS.search(text):
        probs.append(f"{rel}: references book.css (retired)")
    if BOOK_JS.search(text):
        probs.append(f"{rel}: references book.js (retired — use book.json + nav.json)")
    if not SHELL_LINK.search(text):
        probs.append(f'{rel}: missing href="/shell/lib.css"')
    for m in CLASS_ATTR.finditer(text):
        for cls in m.group(1).split():
            if SHELLISH.match(cls) and cls not in allowed:
                probs.append(f"{rel}: unknown shell class '{cls}'")
    return probs


def _served(text: str) -> str:
    """The markup a reader is actually served. A structural check that reads raw text can be
    satisfied by a page that renders without the thing it promised — a section commented out."""
    return BURIED.sub(" ", COMMENT.sub(" ", text))


def _status_word(text: str) -> str | None:
    m = SUB_RE.search(text)
    if not m:
        return None
    sub = strip_tags(m.group(1))
    for w in DOC_STATUS:
        if re.search(rf"\b{w}\b", sub):
            return w
    return None


def _forward_refs(page: Path, text: str) -> list[str]:
    """Links from chapter NN to a later-numbered chapter of the same book, not marked data-fwd."""
    m = NUMBERED.match(page.name)
    if not m:
        return []
    mine = int(m.group(1))
    out: list[str] = []
    for a in ANCHOR.finditer(text):
        attrs = a.group(1)
        h = HREF.search(attrs)
        if not h:
            continue
        target = h.group(1).rsplit("/", 1)[-1]
        t = NUMBERED.match(target)
        if not t or not (page.parent / target).is_file():
            continue
        if int(t.group(1)) > mine and "data-fwd" not in attrs:
            out.append(target)
    return sorted(set(out))


# The checks the engine implements. A genre may name any other check a module under kit.json
# `checks` provides; a name nobody provides fails the gate (see `plugin_checks`).
CORE_CHECKS = ("status", "max_words", "no_h2", "require_defn", "defn_no_findings",
               "no_forward_refs", "require_meta_status", "require_sections", "bound_ids",
               "no_findings")


def plugin_checks(repo: Repo, genres: dict[str, Genre]) -> tuple[dict, dict]:
    """(page checks, repo checks) from kit.json `checks`, after proving every check a genre names
    is provided by the core or a plugin — an unprovided name is a configuration error."""
    page, whole = plugins.checks(repo)
    for g in genres.values():
        for name, arg in g.checks.items():
            if arg and name not in CORE_CHECKS and name not in page:
                raise SystemExit(
                    f"genre {g.name!r} names check {name!r}, which is not a core check and no module "
                    "in kit.json `checks` provides — register the module that implements it, or drop "
                    "the check from the genre")
    return page, whole


def _plugin(repo: Repo, rel: str, page: Path, text: str, g: Genre, provided: dict) -> list[str]:
    probs: list[str] = []
    served = _served(text)
    for name, arg in g.checks.items():
        if not arg or name in CORE_CHECKS:
            continue
        ctx = plugins.CheckContext(repo=repo, page=page, rel=rel, text=text, served=served,
                                   genre=g, arg=arg, cfg=repo.cfg)
        got = provided[name](ctx) or []
        if not isinstance(got, list):
            raise SystemExit(f"check {name!r} must return a list of problems, got {type(got).__name__}")
        probs.extend(str(x) for x in got)
    return probs


def _genre(rel: str, page: Path, text: str, g: Genre) -> list[str]:
    probs: list[str] = []
    c = g.checks
    if c.get("status"):
        if _status_word(text) is None:
            probs.append(
                f'{rel}: no status in the opening line — the first <p class="sub"> must say one of '
                + " · ".join(DOC_STATUS)
            )
    if c.get("max_words"):
        n = word_count(text)
        if n > int(c["max_words"]):
            probs.append(
                f"{rel}: {g.name} runs {n} words, over the {c['max_words']} bound — "
                "promote it to the next genre up or cut"
            )
    if c.get("no_h2") and H2.search(text):
        probs.append(f"{rel}: {g.name} has <h2> sections — a {g.name} is one claim; promote it")
    if c.get("require_defn"):
        d = DEFN_RE.search(text)
        if not d or not DEFN_NAME.search(d.group(0)):
            probs.append(
                f"{rel}: no <blockquote class=\"defn\"> with a .defn-name — a {g.name} is a "
                "definition of record and the popover needs its payload"
            )
    if c.get("defn_no_findings"):
        d = DEFN_RE.search(text)
        if d:
            ids = sorted(set(FINDING.findall(d.group(1))))
            if ids:
                probs.append(
                    f"{rel}: cites {', '.join(ids)} inside its defn — a definition must survive "
                    "findings changing; cite below the defn, not in it"
                )
    if c.get("no_forward_refs"):
        fwd = _forward_refs(page, text)
        if fwd:
            probs.append(
                f"{rel}: forward reference to {', '.join(fwd)} — a chapter assumes only prior "
                "chapters; if the link is deliberate mark it <a data-fwd …>"
            )
    if c.get("require_meta_status"):
        m = STATUS_META_RE.search(text)
        if not m:
            probs.append(f'{rel}: {g.name} needs <meta name="status" content="active|shipped|paused">')
        elif m.group(1) not in ("active", "shipped", "paused"):
            probs.append(f"{rel}: meta status {m.group(1)!r} is not active|shipped|paused")
    if c.get("require_sections"):
        # Extra sections are a page's business; the declared ones must all be there, in this
        # relative order — a genre whose shape is fixed reads the same page to page.
        want = c["require_sections"]
        if not isinstance(want, list) or not all(isinstance(s, str) for s in want):
            raise SystemExit(f"genre {g.name!r}: require_sections is a list of <h2> ids, got {want!r}")
        seen: dict[str, int] = {}
        for i, sec in enumerate(H2_ID.findall(_served(text))):
            seen.setdefault(sec, i)
        at = -1
        for sec in want:
            here = seen.get(sec)
            if here is None:
                probs.append(f'{rel}: no <h2 id="{sec}"> section — a {g.name} carries '
                             + " → ".join(want))
                break
            if here < at:
                probs.append(f'{rel}: <h2 id="{sec}"> is out of order — a {g.name} carries '
                             + " → ".join(want))
                break
            at = here
    if c.get("bound_ids"):
        sub = SUB_RE.search(_served(text))
        if not BOUND_ID.search(sub.group(1) if sub else ""):
            probs.append(
                f'{rel}: the opening line names no finding — a {g.name} is sealed to the rows it '
                'tells, so its first <p class="sub"> carries at least one <code>F-<n></code>'
            )
    if c.get("no_findings"):
        ids = sorted(set(FINDING.findall(text)))
        if ids:
            probs.append(f"{rel}: {g.name} cites {', '.join(ids)} — this genre carries no results")
    return probs


def lint_file(repo: Repo, path: Path, genres: dict[str, Genre],
              provided: dict | None = None, allowed: set[str] | None = None) -> list[str]:
    rel = repo.rel(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    probs = _form(rel, text, allowed if allowed is not None else allowed_classes(repo, genres))
    g = classify(repo, path, genres)
    if g is None:
        known = ", ".join(sorted({x.dir for x in genres.values()}))
        probs.append(f"{rel}: outside any genre — pages live under {repo.content_name}/{{{known}}}")
    else:
        probs.extend(_genre(rel, path, text, g))
        probs.extend(_plugin(repo, rel, path, text, g, provided or {}))
    return probs


def iter_pages(repo: Repo, paths: list[Path] | None = None) -> list[Path]:
    if not paths:
        found = sorted(repo.content.rglob("*.html")) if repo.content.is_dir() else []
    else:
        found = []
        for p in paths:
            p = p.resolve() if p.is_absolute() else (repo.root / p).resolve()
            found.extend(sorted(p.rglob("*.html")) if p.is_dir() else [p])
    return [p for p in found
            if p.resolve().is_relative_to(repo.content.resolve()) and not is_exempt(repo, p)]


def run(repo: Repo, paths: list[Path] | None = None, *, nav: bool = True) -> tuple[list[str], int]:
    """(problems, files linted). Regenerates the indices unless nav=False."""
    genres = load_genres(repo)
    page_checks, repo_checks = plugin_checks(repo, genres)
    allowed = allowed_classes(repo, genres)
    files = iter_pages(repo, paths)
    probs: list[str] = []
    for f in files:
        probs.extend(lint_file(repo, f, genres, page_checks, allowed))
    for name, fn in repo_checks.items():
        got = fn(repo) or []
        if not isinstance(got, list):
            raise SystemExit(f"repo check {name!r} must return a list of problems, got {type(got).__name__}")
        probs.extend(str(x) for x in got)
    books = repo.content / "books"
    if books.is_dir():
        for d in sorted(books.iterdir()):
            if d.is_dir() and (d / "book.js").is_file():
                probs.append(f"{repo.rel(d)}/book.js: retired — use book.json and `ckit nav`")
    probs.extend(annotations.check_all(repo))
    if nav and repo.content.is_dir():
        written = book_nav.regenerate(repo)
        if written:
            print("nav refreshed: " + ", ".join(written))
    return probs, len(files)


def main(argv: list[str]) -> int:
    import argparse

    from .paths import load_repo

    ap = argparse.ArgumentParser(prog="ckit lint", description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--no-nav", action="store_true", help="skip regenerating the indices")
    args = ap.parse_args(argv)
    repo = load_repo()
    if not repo.content.is_dir():
        print(f"no content directory at {repo.rel(repo.content)} — nothing to lint")
        return 0
    probs, n = run(repo, args.paths, nav=not args.no_nav)
    if probs:
        print("\n".join(probs))
        print(f"\n{len(probs)} problem(s) in {n} file(s)")
        return 1
    print(f"content lint clean — {n} file(s)")
    return 0

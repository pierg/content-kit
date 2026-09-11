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
     no finding, no undeclared forward reference in a chapter, a lifecycle meta on a project

Annotations:
  8. every *.annotations.json validates and every quote it anchors is still on its page

This is the *content* gate. A lab's *record* gate — every number traces to a finding — is
lab-kit's ladder lint, and the two are deliberately separate: form is whether a page renders
like the rest of the library, the ladder is whether it is allowed to say what it says.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import annotations, book_nav
from .genres import Genre, classify, is_exempt, load_genres
from .paths import DOC_STATUS, Repo
from .text import DEFN_RE, STATUS_META_RE, SUB_RE, strip_tags, word_count

HEX = re.compile(r"(?<![\w-])#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
CLASS_ATTR = re.compile(r'\bclass="([^"]*)"')
SHELL_LINK = re.compile(r'href="/shell/lib\.css"')
BOOK_JS = re.compile(r'src=["\']book\.js["\']')
BOOK_CSS = re.compile(r"book\.css")
H2 = re.compile(r"<h2\b", re.I)
FINDING = re.compile(r"\bF-\d+(?:\.\d+)*\b")
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
    "hb-kind-paper", "hb-kind-related",
}


def _form(rel: str, text: str) -> list[str]:
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
            if SHELLISH.match(cls) and cls not in ALLOWED:
                probs.append(f"{rel}: unknown shell class '{cls}'")
    return probs


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
    if c.get("no_findings"):
        ids = sorted(set(FINDING.findall(text)))
        if ids:
            probs.append(f"{rel}: {g.name} cites {', '.join(ids)} — this genre carries no results")
    return probs


def lint_file(repo: Repo, path: Path, genres: dict[str, Genre]) -> list[str]:
    rel = repo.rel(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    probs = _form(rel, text)
    g = classify(repo, path, genres)
    if g is None:
        known = ", ".join(sorted({x.dir for x in genres.values()}))
        probs.append(f"{rel}: outside any genre — pages live under {repo.content_name}/{{{known}}}")
    else:
        probs.extend(_genre(rel, path, text, g))
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
    files = iter_pages(repo, paths)
    probs: list[str] = []
    for f in files:
        probs.extend(lint_file(repo, f, genres))
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

"""One paragraph per line: find hard-wrapped prose, and join it (`ckit unwrap`).

Prose is written one paragraph to a line and soft-wrapped by the editor. A paragraph broken
across lines at a column is noise in every diff that re-flows it, and a page written that way
teaches the next author, human or agent, to write the same.

A leaf prose element (a p, li, dd, dt, figcaption, summary, caption, td, th, h1–h6 or
blockquote holding no block-level element) is hard-wrapped when its text, trimmed, still breaks
a line in its text. A break straight after a <br> is deliberate (an address, a verse) and stays;
a break inside a tag (between attributes, inside a value) is markup, not prose, and stays too.
Lists, tables and headings keep their natural breaks between elements; only the breaks inside
one are joined. Math keeps its lines, as code does — display math, and inline math holding a
TeX `%` comment, which would swallow the rest of a joined line. The reader's text does not
change (HTML collapses the whitespace either way — unless the page's CSS makes whitespace
significant with `white-space: pre`), so joining is mechanical: `ckit unwrap`.
"""

from __future__ import annotations

import re

WRAP = ("p", "li", "dd", "dt", "figcaption", "summary", "caption", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote")
START = re.compile(r"<(" + "|".join(WRAP) + r")\b[^>]*>", re.I)
BLOCKY = re.compile(
    r"<(?:" + "|".join(WRAP) + r"|div|ul|ol|dl|table|thead|tbody|tfoot|tr|pre|figure|details|"
    r"section|article|aside|header|footer|nav|hr|form|fieldset|svg|math|iframe|video|audio|"
    r"canvas|object|script|style|template|textarea|select|main)\b", re.I)
COMMENT = re.compile(r"<!--.*?-->", re.S)
BODY = re.compile(r"(<(script|style|noscript|template)\b[^>]*>)(.*?)(</\2\s*>)", re.S | re.I)
TAG = re.compile(r"<(?:[^>\"']|\"[^\"]*\"|'[^']*')*>")
BR = re.compile(r"<br\b", re.I)
DISPLAY_MATH = re.compile(r"\$\$|\\\[|\\begin\{", re.S)
INLINE_MATH = re.compile(r"\\\((.*?)\\\)|(?<!\\)\$(.+?)(?<!\\)\$", re.S)


def _masked(text: str) -> str:
    """Comments and script/style/noscript/template bodies blanked to spaces, offsets kept."""
    text = COMMENT.sub(lambda m: " " * len(m.group(0)), text)
    return BODY.sub(lambda m: m.group(1) + " " * len(m.group(3)) + m.group(4), text)


def _segments(inner: str) -> list[tuple[bool, str]]:
    """(is_tag, text) pieces of an element's inner markup, in order."""
    out, pos = [], 0
    for m in TAG.finditer(inner):
        out.append((False, inner[pos:m.start()]))
        out.append((True, m.group(0)))
        pos = m.end()
    out.append((False, inner[pos:]))
    return out


def _breaks(inner: str) -> bool:
    """A line break in the element's text — not inside a tag, not straight after a <br>."""
    after_br = False
    for is_tag, piece in _segments(inner.strip()):
        if is_tag:
            after_br = bool(BR.match(piece))
            continue
        body = re.sub(r"^[ \t]*\n", "", piece, count=1) if after_br else piece
        if "\n" in body:
            return True
        after_br = False
    return False


def _keeps_lines(inner: str) -> bool:
    """Math keeps its lines, as code does: display math, and inline math holding a TeX `%`
    comment (joining a line after it would comment the rest out)."""
    return bool(DISPLAY_MATH.search(inner)) or any(
        "%" in (m.group(1) or m.group(2) or "") for m in INLINE_MATH.finditer(inner))


def wrapped(text: str) -> list[tuple[int, int]]:
    """(start, end) of the inner markup of every hard-wrapped leaf prose element."""
    masked = _masked(text)
    out: list[tuple[int, int]] = []
    for m in START.finditer(masked):
        name = m.group(1).lower()
        close = re.compile(rf"</{name}\s*>", re.I).search(masked, m.end())
        if not close:
            continue
        inner = masked[m.end():close.start()]
        if BLOCKY.search(inner) or _keeps_lines(inner):
            continue
        if _breaks(inner):
            out.append((m.end(), close.start()))
    return out


def _join(inner: str) -> str:
    """The element's text joined onto one line; tags, and a break straight after a <br>, kept."""
    core = inner.strip()
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    out, after_br = [], False
    for is_tag, piece in _segments(core):
        if is_tag:
            out.append(piece)
            after_br = bool(BR.match(piece))
            continue
        head = ""
        if after_br:
            m = re.match(r"[ \t]*\n", piece)
            if m:
                head, piece = m.group(0), piece[m.end():]
        out.append(head + re.sub(r"[ \t]*\n[ \t]*", " ", piece))
        after_br = False
    return lead + "".join(out) + trail


def unwrap(text: str) -> tuple[str, int]:
    """(text with every hard-wrapped element joined, how many were joined)."""
    spans = wrapped(text)
    for start, end in reversed(spans):
        text = text[:start] + _join(text[start:end]) + text[end:]
    return text, len(spans)


def problems(rel: str, text: str) -> list[str]:
    spans = wrapped(text)
    if not spans:
        return []
    line = text.count("\n", 0, spans[0][0]) + 1
    many = f"{len(spans)} hard-wrapped elements" if len(spans) > 1 else "a hard-wrapped element"
    return [f"{rel}:{line}: {many} — one paragraph per line (soft-wrap in the editor); "
            f"`ckit unwrap {rel}` joins them"]


def unwrap_repo(repo, paths=None) -> tuple[int, list[tuple[str, int]]]:
    """Join the hard-wrapped prose of a repo's pages (or of `paths`): (joined, [(page, n)]). The
    catalog is regenerated first, so a page it joins keeps its dates, and again after."""
    from . import book_nav
    from .lint import iter_pages
    book_nav.regenerate(repo)
    done: list[tuple[str, int]] = []
    for page in iter_pages(repo, paths):
        out, n = unwrap(page.read_text(encoding="utf-8"))
        if n:
            page.write_text(out, encoding="utf-8")
            done.append((repo.rel(page), n))
    book_nav.regenerate(repo)
    return sum(n for _p, n in done), done


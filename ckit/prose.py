"""One paragraph per line: find hard-wrapped prose, and join it (`ckit unwrap`).

Prose is written one paragraph to a line and soft-wrapped by the editor. A paragraph broken
across lines at a column is noise in every diff that re-flows it, and a page written that way
teaches the next author, human or agent, to write the same.

A leaf prose element (a p, li, dd, dt, figcaption, summary, caption, td, th, h1–h6 or
blockquote holding no block-level element) is hard-wrapped when its text, trimmed, still breaks
a line. A break straight after a <br> is deliberate (an address, a verse) and stays. Lists,
tables and headings keep their natural breaks between elements; only the breaks inside one are
joined. An element holding display math keeps its lines, as code does: a TeX `%` comment
would swallow the rest of a joined line. The reader's text does not change (HTML collapses the
whitespace either way), so joining is mechanical: `ckit unwrap`.
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
BREAK_AFTER_BR = re.compile(r"<br\s*/?>[ \t]*\n", re.I)
DISPLAY_MATH = re.compile(r"\$\$|\\\[|\\begin\{", re.S)


def _masked(text: str) -> str:
    """Comments and script/style/noscript/template bodies blanked to spaces, offsets kept."""
    text = COMMENT.sub(lambda m: " " * len(m.group(0)), text)
    return BODY.sub(lambda m: m.group(1) + " " * len(m.group(3)) + m.group(4), text)


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
        if BLOCKY.search(inner) or DISPLAY_MATH.search(inner):
            continue
        if "\n" in BREAK_AFTER_BR.sub("<br>", inner.strip()):
            out.append((m.end(), close.start()))
    return out


def _join(inner: str) -> str:
    core = inner.strip()
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    core = BREAK_AFTER_BR.sub(lambda m: m.group(0).replace("\n", "\0"), core)
    core = re.sub(r"[ \t]*\n[ \t]*", " ", core).replace("\0", "\n")
    return lead + core + trail


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

"""One text model for a page, shared by every consumer.

Lint counts words on it; the annotation layer anchors quotes in it; the search index snippets
come from the same helpers. Keeping a single extraction is what lets a quote the browser saved
(from `innerText`) be found again here: both sides collapse whitespace, both drop script and
style, and both put whitespace at block boundaries.
"""

from __future__ import annotations

import html as html_mod
import re

_MAIN = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)
_DROP = re.compile(r"<(script|style|noscript|template)\b[^>]*>.*?</\1>", re.S | re.I)
_SVG = re.compile(r"<svg\b[^>]*>.*?</svg>", re.S | re.I)
_BLOCK = re.compile(
    r"</?(?:p|div|li|ul|ol|h[1-6]|tr|td|th|blockquote|section|article|figure|figcaption|pre|"
    r"table|thead|tbody|dl|dt|dd|details|summary|nav|aside|header|footer|main|br|hr)\b[^>]*>",
    re.I,
)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.I | re.S)
H3_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.I | re.S)
SUB_RE = re.compile(r'<p\b[^>]*class="[^"]*\bsub\b[^"]*"[^>]*>(.*?)</p>', re.I | re.S)
DEFN_RE = re.compile(
    r'<blockquote\b[^>]*class="[^"]*\bdefn\b[^"]*"[^>]*>(.*?)</blockquote>', re.I | re.S
)
TAGS_META_RE = re.compile(r'<meta[^>]*name=["\']tags["\'][^>]*content=["\']([^"\']*)["\']', re.I)
TOPIC_META_RE = re.compile(r'<meta[^>]*name=["\']topic["\'][^>]*content=["\']([^"\']*)["\']', re.I)
STATUS_META_RE = re.compile(
    r'<meta[^>]*name=["\']status["\'][^>]*content=["\']([^"\']*)["\']', re.I
)


def normalize(text: str) -> str:
    return _WS.sub(" ", text).strip()


def main_html(html: str) -> str:
    m = _MAIN.search(html)
    return m.group(1) if m else html


def strip_tags(fragment: str) -> str:
    """Inline strip for titles/headings: tags removed, entities decoded, whitespace collapsed."""
    return normalize(html_mod.unescape(_TAG.sub("", fragment)))


def page_text(html: str, *, keep_svg: bool = True) -> str:
    """The prose of a page as the browser's `innerText` would see it (normalized)."""
    s = _DROP.sub(" ", main_html(html))
    if not keep_svg:
        s = _SVG.sub(" ", s)
    s = _BLOCK.sub(" ", s)
    s = _TAG.sub("", s)
    return normalize(html_mod.unescape(s))


def word_count(html: str) -> int:
    return len(page_text(html, keep_svg=False).split())


def title_of(html: str, fallback: str) -> str:
    m = TITLE_RE.search(html) or H1_RE.search(html)
    return strip_tags(m.group(1)) if m else fallback


# --- metadata: <meta name=… content=…> read and written in either attribute order, outside
#     comments and inert bodies (a commented-out meta is not the page's)

_META = re.compile(r"<meta\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>", re.I | re.S)
_ATTR = re.compile(r"""([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")
_INERT = re.compile(r"<!--.*?-->|(<(script|style|noscript|template)\b[^>]*>).*?</\2\s*>", re.S | re.I)
_HEAD_END = re.compile(r"</head\s*>", re.I)


def _mask_inert(html: str) -> str:
    return _INERT.sub(lambda m: " " * len(m.group(0)), html)


def meta_tags(html: str) -> list[tuple[int, int, dict[str, str]]]:
    """(start, end, attributes) of every <meta> a browser would read, in document order."""
    out: list[tuple[int, int, dict[str, str]]] = []
    for m in _META.finditer(_mask_inert(html)):
        attrs = {}
        for a in _ATTR.finditer(html[m.start() + 5:m.end() - 1]):
            val = next(g for g in (a.group(2), a.group(3), a.group(4)) if g is not None)
            attrs[a.group(1).lower()] = html_mod.unescape(val)
        out.append((m.start(), m.end(), attrs))
    return out


def meta_content(html: str, name: str) -> str | None:
    """The content of the page's <meta name="…">, or None when it has none."""
    for _s, _e, attrs in meta_tags(html):
        if attrs.get("name", "").lower() == name:
            return attrs.get("content", "")
    return None


_CONTENT_ATTR = re.compile(r"""(?<![\w:.-])(content\s*=\s*)("[^"]*"|'[^']*'|[^\s"'>]+)""", re.I)


def set_meta(html: str, name: str, value: str | None) -> str:
    """The page with <meta name="…">'s content set to `value` — its other attributes kept — or
    added after the head's last <meta> when it has none; with `value` None, the tag removed (its
    line too, when it stood alone on one)."""
    found = [(s, e) for s, e, attrs in meta_tags(html) if attrs.get("name", "").lower() == name]
    quoted = f'"{html_mod.escape(value, quote=True)}"' if value is not None else ""
    if found:
        s, e = found[0]
        tag = html[s:e]
        if value is None:
            line = html.rfind("\n", 0, s) + 1
            if not html[line:s].strip() and html[e:e + 1] in ("\n", ""):
                s, e = line, e + 1  # alone on its line: the line goes
            elif html[e:e + 1] == "\n":
                e += 1
            return html[:s] + html[e:]
        m = _CONTENT_ATTR.search(tag)
        if m:
            tag = tag[:m.start(2)] + quoted + tag[m.end(2):]
        else:
            close = "/>" if tag.endswith("/>") else ">"
            tag = tag[: -len(close)].rstrip() + f" content={quoted}" + (" />" if close == "/>" else ">")
        return html[:s] + tag + html[e:]
    if value is None:
        return html
    new = f'<meta name="{name}" content={quoted}>'
    masked = _mask_inert(html)
    head = _HEAD_END.search(masked)
    limit = head.start() if head else len(html)
    ends = [e for s, e, _a in meta_tags(html) if s < limit]
    if ends:
        return html[:ends[-1]] + "\n" + new + html[ends[-1]:]
    if head:
        return html[:head.start()] + new + "\n" + html[head.start():]
    return new + "\n" + html

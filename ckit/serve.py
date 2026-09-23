"""Serve a repo's reader pages — stdlib only, zero deps, no build step.

    ckit serve                       # foreground, port from kit.json
    ckit up / ckit down              # background (ctl.py)

Two roots are mounted:

  /shell/...        the vendored shell (CSS / JS / KaTeX / skeletons / search page), plus
                    /shell/theme.css (the repo's kit.json `theme`, or an empty stylesheet) and
                    each kit.json `shell_pages` entry at /shell/<name>
  /...              the repo root, so /content/... resolves to the repo's own pages

That split is why a repo vendors only the shell, and why every page's absolute
`/shell/lib.css` href works unchanged when the same page is served from any repo.

One write endpoint exists, for the annotation layer:

An address kit.json `moved` names answers 301 to where the page lives now (`ckit mv`).

  GET  /__annotations/ping          → {"ok": true, "engine": "<version>"}  (lib.js probes this;
                                       static hosting answers 404 and the affordance never appears)
  POST /__annotations               → {"op": "add" | "reply" | "state", ...}  writes the sidecar

Reads of a sidecar are plain static GETs of `<page>.annotations.json`.

Files are served `Cache-Control: no-cache` with an `ETag` built from the file's mtime (to the
nanosecond) and size: the browser keeps its copy and asks each time, so an edited page shows on
reload — even one written twice in a second — and an unchanged one costs a 304. Where pagefind
is installed (see pagefind.py), a full-text index of the content is built in the background at
start and served at /pagefind/ — the palette and the search page use it when it answers.
"""

from __future__ import annotations

import argparse
import email.utils
import html as html_mod
import json
import mimetypes
import re
import signal
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from . import __version__, annotations
from . import chronicle, config, links, pagefind
from .book_nav import _books, _href_of, _title, build_catalog, build_search_index, groups
from .paths import Repo, home_page, home_shell_page, load_repo


def _esc(text: str) -> str:
    return html_mod.escape(text, quote=False)


def _attr(text: str) -> str:
    """For an attribute value: quotes escaped too, so a title with a quote in it stays one attribute."""
    return html_mod.escape(text, quote=True)


def _href(repo: Repo, p: Path) -> str:
    return "/" + p.relative_to(repo.root).as_posix()


def _based(href: str, base: str) -> str:
    """A root-absolute href under a base path ("/" leaves it alone) — for `ckit export --base`."""
    if base == "/" or not href.startswith("/") or href.startswith("//"):
        return href
    return base.rstrip("/") + href


def _group_items(repo: Repo, folder: str, layout: str) -> list[tuple[str, Path]]:
    d = repo.content / folder
    if not d.is_dir():
        return []
    if folder == "books":
        return [(_title(b / "index.html"), b / "index.html") for b in _books(repo)]
    if layout == "folder":
        pages = sorted(c / "index.html" for c in d.iterdir() if c.is_dir())
        return [(_title(p), p) for p in pages if p.is_file()]
    return [(_title(p), p) for p in sorted(d.glob("*.html"))]


def _list_group(repo: Repo, title: str, items: list[tuple[str, Path]], empty: str,
                base: str = "/") -> str:
    if not items:
        return f'<h2>{_esc(title)}</h2><p class="muted">{_esc(empty)}</p>'
    lis = "\n".join(
        f'<li><a href="{_esc(_based(_href(repo, p), base))}">{_esc(name)}</a>'
        f'<div class="path">{_esc(_href(repo, p))}</div></li>'
        for name, p in items
    )
    return f'<h2>{_esc(title)}</h2>\n<ul class="catalog">\n{lis}\n</ul>'


SEARCH_ICON = ('<svg class="hb-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
               '<path d="m20 20-3.5-3.5"/></svg>')


def _fmt_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{d.day} {d.strftime('%b %Y')}"


def _clean_sub(sub: str) -> str:
    """A page's opening line without its status word — the summary a reader wants on a card."""
    return re.sub(r"^\s*Status:\s*[A-Z]+\s*[—–-]\s*", "", sub or "").strip()


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _landing(repo: Repo, base: str = "/", *, threads: bool = False) -> bytes:
    """The generated home page, for a repo whose kit.json names no `home`: what the library holds,
    by topic when its pages declare topics, what changed lately, and a shelf per genre. Built from
    the committed indices (the catalog and the search index) — the same data the chrome reads.
    Served (`threads`), it opens with the annotation threads still open — what a reader, or an
    agent flagging what it added beyond its source, is waiting on; the exported site omits them."""
    b = lambda href: _attr(_based(href, base))  # noqa: E731
    name = _esc(str(repo.cfg.get("name", "library")))
    question = _esc(str(repo.cfg.get("question", "")))
    cat = _read_json(repo.content / "catalog.json") or build_catalog(repo)
    idx = _read_json(repo.content / "search-index.json")
    if not isinstance(idx, list):
        idx = build_search_index(repo)
    subs = {r.get("href"): _clean_sub(r.get("sub", "")) for r in idx if isinstance(r, dict)}
    grps = [g for g in cat.get("groups") or [] if isinstance(g, dict)]
    pages = [dict(it, _g=g) for g in grps for it in cat.get(g["key"], []) if isinstance(it, dict)]
    labels = cat.get("topics") or {}

    parts: list[str] = []
    parts.append(
        '<section class="hb-hero">\n'
        f"<h1>{name}</h1>\n" + (f'<p class="hb-hero-q">{question}</p>\n' if question else "") +
        f'<a class="hb-hero-search" href="{b("/shell/search.html")}" data-hb-palette>{SEARCH_ICON}'
        '<span class="hb-find-label">Search everything…</span><span class="hb-kbd">/</span></a>\n</section>')

    waiting = annotations.list_threads(repo, state="open") if threads else []
    if waiting:
        titles = {p["href"]: p.get("title", "") for p in pages}
        rows = []
        for t in waiting[:8]:
            href = str(t.get("page") or "")
            quoted = t["target"].get("exact") if isinstance(t.get("target"), dict) else ""
            rows.append(f'<li><a href="{b(href)}"><span class="hb-date">{_esc(_clip(str(t.get("author", "")), 18))}</span>'
                        f'<span>{_esc(titles.get(href) or href)}</span>'
                        f'<span class="hb-where">{_esc(_clip(str(t.get("body") or quoted or ""), 72))}</span></a></li>')
        more = len(waiting) - len(rows)
        parts.append(f'<h2>Waiting for you · {len(waiting)} open thread{"" if len(waiting) == 1 else "s"}</h2>\n'
                     '<ul class="hb-list">\n' + "\n".join(rows) + "\n</ul>"
                     + (f'\n<p class="muted">{more} more — <code>ckit annotations list</code></p>' if more else ""))

    order = list(labels) + sorted({p["topic"] for p in pages if p.get("topic")} - set(labels))
    cards = []
    for slug in order:
        mine = [p for p in pages if p.get("topic") == slug]
        if not mine:
            continue
        hub = next((p for p in mine if p["_g"]["kind"] == "hub"), None)
        counts = []
        for g in grps:
            n = sum(1 for p in mine if p["_g"] is g)
            if n and g["kind"] != "hub":
                counts.append(f"{n} {_esc(g['kind'] if n == 1 else g['label'].lower())}")
        latest = max((p.get("updated") or "" for p in mine), default="")
        href = hub["href"] if hub else f"/shell/search.html?topic={quote(slug)}"
        stance = subs.get(hub["href"], "") if hub else ""
        cards.append(
            f'<a class="hb-card" href="{b(href)}"><span class="hb-card-title">{_esc(str(labels.get(slug) or slug.replace("-", " ").title()))}</span>'
            + (f'<span class="hb-card-sub">{_esc(stance)}</span>' if stance else "")
            + f'<span class="hb-card-meta"><span>{len(mine)} pages</span><span>{" · ".join(counts)}</span>'
            + (f"<span>updated {_esc(_fmt_date(latest))}</span>" if latest else "") + "</span></a>")
    if cards:
        parts.append('<h2>Topics</h2>\n<div class="hb-grid">\n' + "\n".join(cards) + "\n</div>")

    recent = sorted((p for p in pages if p.get("updated")), key=lambda p: (p["updated"], p.get("title", "")), reverse=True)[:8]
    if recent:
        rows = []
        for p in recent:
            kind = p["_g"]["kind"]
            topic = p.get("topic")
            where = _esc(str(labels.get(topic) or topic.replace("-", " ").title())) if topic else ""
            rows.append(f'<li><a href="{b(p["href"])}"><span class="hb-date">{_esc(_fmt_date(p["updated"]))}</span>'
                        f'<span><span class="hb-kind hb-kind-{_attr(kind)}">{_esc(kind)}</span>{_esc(p.get("title", ""))}</span>'
                        f'<span class="hb-where">{where}</span></a></li>')
        parts.append('<h2>Recently updated</h2>\n<ul class="hb-list">\n' + "\n".join(rows) + "\n</ul>")

    shelves = []
    for g in grps:
        items = [p for p in pages if p["_g"] is g]
        if not items:
            continue
        lis = "".join(f'<li><a href="{b(p["href"])}" title="{_attr(p.get("title", ""))}">{_esc(p.get("title", ""))}</a></li>' for p in items[:6])
        more = (f'<li class="hb-more"><a href="{b("/shell/search.html?kind=" + quote(g["kind"]))}">All {len(items)} &rarr;</a></li>'
                if len(items) > 6 else "")
        shelves.append(f'<div class="hb-shelf"><h3><span>{_esc(g["label"])}</span><span class="hb-count">{len(items)}</span></h3>'
                       f"<ul>{lis}{more}</ul></div>")
    if shelves:
        parts.append('<h2>Library</h2>\n<div class="hb-shelves">\n' + "\n".join(shelves) + "\n</div>")

    links = []
    if chronicle.enabled(repo):
        links.append(f'<a href="{b("/shell/chronicle.html")}">Chronicle &rarr;</a>')
        for r in chronicle.record_catalog(repo):
            title = re.sub(r"\s+[—–-]\s+(LIVE|HISTORICAL|PARKED|RETIRED|FROZEN|DRAFT)\s*$", "", r["title"])
            links.append(f'<a href="{b(r["href"])}" title="{_attr(r["path"])}">{_esc(title)} &rarr;</a>')
    for x in config.links(repo):
        links.append(f'<a href="{b(x["href"])}"' + (f' title="{_attr(x["title"])}"' if x.get("title") else "")
                     + f'>{_esc(x["label"])} &rarr;</a>')
    if links:
        parts.append('<h2>Elsewhere</h2>\n<div class="hb-links-row">' + " ".join(links) + "</div>")

    if len(parts) == 1:
        parts.append('<p class="muted">Nothing here yet — <code>ckit new note &lt;slug&gt;</code> writes the first page.</p>')

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title>
<link rel="stylesheet" href="{b("/shell/lib.css")}">
<script src="{b("/shell/lib.js")}" defer></script>
</head>
<body class="hb" data-hb-app>
<main class="hb-home">
""" + "\n\n".join(parts) + """
</main>
</body>
</html>
"""
    return body.encode("utf-8")


def _slug_file(repo: Repo, slug: str) -> Path | None:
    """Resolve a bare slug to a page, so /foo redirects to whichever genre owns it."""
    if not slug or "/" in slug or slug in (".", ".."):
        return None
    for g in groups(repo):
        p = repo.content / g["key"] / slug / "index.html" if g["layout"] == "folder" \
            else repo.content / g["key"] / f"{slug}.html"
        if p.is_file():
            return p
    return None


def _dir_listing(repo: Repo, directory: Path) -> bytes | None:
    items: list[tuple[str, Path]] = []
    for child in sorted(directory.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "index.html").is_file():
            items.append((_title(child / "index.html"), child / "index.html"))
        elif child.suffix == ".html":
            items.append((_title(child), child))
    if not items:
        return None
    heading = directory.relative_to(repo.root).as_posix()
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{_esc(heading)}</title>"
        '<link rel="stylesheet" href="/shell/lib.css">'
        '<script src="/shell/lib.js" defer></script></head>'
        f'<body class="hb" data-hb-app><main>{_list_group(repo, heading, items, "")}</main></body></html>'
    ).encode("utf-8")


def make_handler(repo: Repo, index: "pagefind.Index | None" = None):
    shell = repo.shell.resolve()
    root = repo.root.resolve()
    index = index or pagefind.Index(None)

    def resolve(rel_path: str) -> Path | None:
        if rel_path.startswith("shell/") and rel_path[len("shell/"):] in config.shell_pages(repo):
            return config.shell_pages(repo)[rel_path[len("shell/"):]].resolve()
        if rel_path == "shell" or rel_path.startswith("shell/"):
            base, tail = shell, rel_path[len("shell"):].lstrip("/")
        else:
            base, tail = root, rel_path
        target = (base / tail).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return None
        return target

    class Handler(BaseHTTPRequestHandler):
        server_version = f"ckit/{__version__}"

        def log_message(self, fmt: str, *args) -> None:  # quiet by design
            pass

        def _send(self, status: int, data: bytes, ctype: str, body: bool = True,
                  etag: str | None = None, modified: float | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if etag is None:
                self.send_header("Cache-Control", "no-store")
            else:  # a file: keep it, but ask every time — an edit shows on the next reload
                self.send_header("Cache-Control", "no-cache")
                self.send_header("ETag", etag)
                if modified is not None:
                    self.send_header("Last-Modified", email.utils.formatdate(modified, usegmt=True))
            self.end_headers()
            if body:
                self.wfile.write(data)

        def _fresh(self, etag: str) -> bool:
            """The browser's copy is this file's current bytes (If-None-Match names its ETag)."""
            got = self.headers.get("If-None-Match") or ""
            return any(t.strip() in (etag, "*") for t in got.split(","))

        def _json(self, status: int, obj: object, body: bool = True) -> None:
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8", body)

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve(body=False)

        def do_GET(self) -> None:  # noqa: N802
            self._serve(body=True)

        def do_POST(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path != "/__annotations":
                self.send_error(404, "Not found")
                return
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                req = json.loads(raw.decode("utf-8") or "{}")
                result = annotations.apply(repo, req)
            except (json.JSONDecodeError, annotations.AnnotationError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return
            self._json(200, result)

        def _serve(self, *, body: bool) -> None:
            path = unquote(urlparse(self.path).path)
            if path in ("", "/"):
                home = repo.cfg.get("home")
                shell_home = home_shell_page(repo)
                if shell_home:
                    # a layer's shell page is the front door — served in place, not redirected,
                    # so the page's absolute /shell/ and /content/ links hold from /
                    page_file = config.shell_pages(repo)[shell_home]
                    if not page_file.is_file():
                        self.send_error(404, f'kit.json "home" ({home!r}): {repo.rel(page_file)} is missing')
                        return
                    self._send(200, page_file.read_bytes(), "text/html; charset=utf-8", body)
                    return
                if home:
                    # a content page is the front door — redirect to its canonical URL so its
                    # own relative links and the backlinks index (keyed on canonical hrefs) hold
                    page = home_page(repo)
                    if page is None:
                        self.send_error(404, f'kit.json "home" ({home!r}) does not resolve to a page')
                        return
                    self.send_response(302)
                    self.send_header("Location", _href_of(repo, page))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self._send(200, _landing(repo, threads=True), "text/html; charset=utf-8", body)
                return
            if path == "/shell/theme.css":
                self._send(200, config.theme_css(repo), "text/css; charset=utf-8", body)
                return
            if path == "/shell/pagefind.json":  # whether /pagefind/ answers — asked once per session
                self._json(200, {"available": index.dir is not None}, body)
                return
            if path == "/__annotations/ping":
                self._json(200, {"ok": True, "engine": __version__}, body)
                return
            rel_path = path.lstrip("/")
            if rel_path.startswith("pagefind/") and not (repo.root / "pagefind").exists():
                target = index.file(rel_path[len("pagefind/"):])
                if target is None:
                    self.send_error(404, "Not found")
                    return
            else:
                target = resolve(rel_path)
            if target is None:
                self.send_error(403, "Forbidden")
                return
            if target.is_dir():
                idx = target / "index.html"
                if idx.is_file():
                    target = idx
                else:
                    listing = _dir_listing(repo, target)
                    if listing is None:
                        self.send_error(404, "Not found")
                        return
                    self._send(200, listing, "text/html; charset=utf-8", body)
                    return
            if not target.is_file():
                new = links.follow(links.moved_now(repo), path)
                if new:  # kit.json `moved`: the page lives on at its new address
                    query = urlparse(self.path).query
                    self.send_response(301)
                    self.send_header("Location", quote(new) + (f"?{query}" if query else ""))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                found = _slug_file(repo, Path(rel_path).name)
                if found is not None:
                    self.send_response(302)
                    self.send_header("Location", _href(repo, found))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_error(404, "Not found")
                return
            try:  # a file can go between finding it and reading it (a full-text rebuild swapping in)
                st = target.stat()
                data = target.read_bytes()  # HEAD too: its Content-Length is the file's
            except OSError:
                self.send_error(404, "Not found")
                return
            etag = f'W/"{st.st_mtime_ns:x}-{st.st_size:x}"'
            ctype, _ = mimetypes.guess_type(str(target))
            ctype = ctype or "application/octet-stream"
            if (ctype.startswith("text/") or ctype in
                    ("application/javascript", "application/json", "image/svg+xml")) \
                    and "charset" not in ctype:
                ctype = f"{ctype}; charset=utf-8"
            if self._fresh(etag):
                self.send_response(304)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("ETag", etag)
                self.end_headers()
                return
            self._send(200, data, ctype, body, etag=etag, modified=st.st_mtime)

    return Handler


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit serve", description="Serve a repo's reader pages.")
    ap.add_argument("--root", help="the repo to serve (default: found from the working directory)")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    args = ap.parse_args(argv)
    repo = load_repo(args.root)
    if not (repo.shell / "lib.css").is_file():
        raise SystemExit(f"no vendored shell at {repo.rel(repo.shell)} — run `ckit init` here first")
    host = args.host or repo.cfg["host"]
    port = args.port or int(repo.cfg["port"])
    index = pagefind.Index(pagefind.command())
    httpd = ThreadingHTTPServer((host, port), make_handler(repo, index))
    print(f"{repo.cfg.get('name', 'library')} at http://{host}:{port}/  (root={repo.root})", flush=True)
    if index.cmd:  # full text, when pagefind is installed: built beside the server, never committed
        threading.Thread(target=index.build, args=(repo,), daemon=True).start()

    def _stop(*_):  # `ckit down` sends SIGTERM: stop the same way ^C does, so the cleanup below runs
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _stop)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
        index.close()
    return 0

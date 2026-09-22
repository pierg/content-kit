"""Serve a repo's reader pages — stdlib only, zero deps, no build step.

    ckit serve                       # foreground, port from kit.json
    ckit up / ckit down              # background (ctl.py)

Two roots are mounted:

  /shell/...        the vendored shell (CSS / JS / KaTeX / skeletons / search page)
  /...              the repo root, so /content/... resolves to the repo's own pages

That split is why a repo vendors only the shell, and why every page's absolute
`/shell/lib.css` href works unchanged when the same page is served from any repo.

One write endpoint exists, for the annotation layer:

  GET  /__annotations/ping          → {"ok": true, "engine": "<version>"}  (lib.js probes this;
                                       static hosting answers 404 and the affordance never appears)
  POST /__annotations               → {"op": "add" | "reply" | "state", ...}  writes the sidecar

Reads of a sidecar are plain static GETs of `<page>.annotations.json`.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import __version__, annotations
from . import chronicle, ladder
from .book_nav import CATALOG_GROUPS, _books, _href_of, _title
from .paths import Repo, home_page, load_repo


def _esc(text: str) -> str:
    return html_mod.escape(text, quote=False)


def _href(repo: Repo, p: Path) -> str:
    return "/" + p.relative_to(repo.root).as_posix()


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


def _list_group(repo: Repo, title: str, items: list[tuple[str, Path]], empty: str) -> str:
    if not items:
        return f'<h2>{_esc(title)}</h2><p class="muted">{_esc(empty)}</p>'
    lis = "\n".join(
        f'<li><a href="{_esc(_href(repo, p))}">{_esc(name)}</a>'
        f'<div class="path">{_esc(_href(repo, p))}</div></li>'
        for name, p in items
    )
    return f'<h2>{_esc(title)}</h2>\n<ul class="catalog">\n{lis}\n</ul>'


def _landing(repo: Repo) -> bytes:
    name = _esc(str(repo.cfg.get("name", "library")))
    question = _esc(str(repo.cfg.get("question", "")))
    lede = f'<p class="sub">{question}</p>' if question else ""
    c = repo.content_name
    chron = ' <a class="search-cta" href="/shell/chronicle.html">Chronicle &rarr;</a>' if chronicle.enabled(repo) else ""
    rec = chronicle.record_catalog(repo) if chronicle.enabled(repo) else []
    record = ("<h2>Record</h2>\n<ul class=\"catalog\">\n" + "\n".join(
        f'<li><a href="{_esc(r["href"])}">{_esc(r["title"])}</a><div class="path">{_esc(r["path"])}</div></li>' for r in rec)
        + "\n</ul>") if rec else ""
    groups = "\n".join(
        _list_group(repo, folder.capitalize(), _group_items(repo, folder, layout),
                    f"No {folder} yet — `ckit new {kind} <slug>`")
        for folder, kind, layout in CATALOG_GROUPS
    )
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title>
<link rel="stylesheet" href="/shell/lib.css">
<script src="/shell/lib.js" defer></script>
<style>
  .catalog {{ list-style: none; padding: 0; }}
  .catalog li {{ margin: 0 0 10px; }}
  .catalog .path {{ color: var(--ink-3); font-size: 12px; }}
  .home-lede {{ background: var(--surface-1); border: 1px solid var(--ring);
                border-radius: 12px; padding: 14px 18px; margin: 18px 0; }}
  .home-lede a.search-cta {{ display: inline-block; margin-top: 6px;
                border: 1.5px solid var(--judge); color: var(--judge);
                border-radius: 999px; padding: 4px 14px; font-weight: 700;
                font-size: 13px; text-decoration: none; }}
  .home-lede a.search-cta:hover {{ background: color-mix(in srgb, var(--judge) 10%, transparent); }}
</style>
</head>
<body class="hb">
<main>
<h1>{name}</h1>
{lede}

<div class="home-lede">
Looking for something? <a class="search-cta" href="/shell/search.html">Search everything &rarr;</a>{chron}
</div>

{groups}
{record}
</main>
</body>
</html>
"""
    return body.encode("utf-8")


def _slug_file(repo: Repo, slug: str) -> Path | None:
    """Resolve a bare slug to a page, so /foo redirects to whichever genre owns it."""
    if not slug or "/" in slug or slug in (".", ".."):
        return None
    for folder, _kind, layout in CATALOG_GROUPS:
        p = repo.content / folder / slug / "index.html" if layout == "folder" \
            else repo.content / folder / f"{slug}.html"
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
        f'<body class="hb"><main>{_list_group(repo, heading, items, "")}</main></body></html>'
    ).encode("utf-8")


def make_handler(repo: Repo):
    shell = repo.shell.resolve()
    root = repo.root.resolve()

    def resolve(rel_path: str) -> Path | None:
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

        def _send(self, status: int, data: bytes, ctype: str, body: bool = True) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(data)

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
                if home and home != "dashboard":
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
                dash = repo.shell / "dashboard.html"
                if home == "dashboard" and ladder.enabled(repo) and dash.is_file():
                    self._send(200, dash.read_bytes(), "text/html; charset=utf-8", body)
                    return
                self._send(200, _landing(repo), "text/html; charset=utf-8", body)
                return
            if path == "/__annotations/ping":
                self._json(200, {"ok": True, "engine": __version__}, body)
                return
            rel_path = path.lstrip("/")
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
                found = _slug_file(repo, Path(rel_path).name)
                if found is not None:
                    self.send_response(302)
                    self.send_header("Location", _href(repo, found))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_error(404, "Not found")
                return
            data = target.read_bytes()
            ctype, _ = mimetypes.guess_type(str(target))
            ctype = ctype or "application/octet-stream"
            if (ctype.startswith("text/") or ctype in
                    ("application/javascript", "application/json", "image/svg+xml")) \
                    and "charset" not in ctype:
                ctype = f"{ctype}; charset=utf-8"
            self._send(200, data, ctype, body)

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
    httpd = ThreadingHTTPServer((host, port), make_handler(repo))
    print(f"{repo.cfg.get('name', 'library')} at http://{host}:{port}/  (root={repo.root})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
    return 0

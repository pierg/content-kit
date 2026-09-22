"""Write the reader's site as static files: `ckit export [--out dist] [--base /]`.

    dist/index.html       the landing page — or a redirect to a content-page `home`, or the
                          shell page a `home` names
    dist/shell/…          the vendored shell, /shell/theme.css, and every kit.json shell page
    dist/content/…        the content tree and its generated indices (annotation sidecars stay
                          home: review traffic is for the served repo, not the published site)
    dist/<record files>   the markdown the record viewer and the chronicle link to
    dist/.nojekyll        so GitHub Pages serves every path as-is

The export rewrites nothing at the default base. `--base /<repo>/` is for a site served under a
path (a GitHub project site): root-absolute `href`/`src`/`action` attributes and CSS `url()`s in
the exported HTML and CSS gain the prefix; JSON indices and scripts are left alone, because the
shell reads its own base from the URL it was loaded from. The source tree is never touched.

Serve it with anything static: `python3 -m http.server -d dist`.
"""

from __future__ import annotations

import argparse
import html as html_mod
import re
import shutil
from pathlib import Path

from . import chronicle, config
from .book_nav import _href_of
from .paths import Repo, home_page, home_shell_page, load_repo
from .serve import _landing

MARKER = ".ckit-export"
ATTR = re.compile(r'(\s(?:href|src|action|poster)=)(["\'])/(?!/)')
CSS_URL = re.compile(r'url\(\s*(["\']?)/(?!/)')


def rebase(text: str, base: str) -> str:
    """Prefix root-absolute URLs in markup and CSS with `base` ("/" leaves the text unchanged)."""
    if base == "/":
        return text
    b = base.strip("/")
    text = ATTR.sub(lambda m: f"{m.group(1)}{m.group(2)}/{b}/", text)
    return CSS_URL.sub(lambda m: f"url({m.group(1)}/{b}/", text)


def _write(dest: Path, data: bytes | str, base: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.suffix in (".html", ".htm", ".css"):
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        dest.write_text(rebase(text, base), encoding="utf-8")
    else:
        dest.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def _copy_tree(src: Path, dest: Path, base: str, skip=lambda p: False) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if not p.is_file() or any(part.startswith(".") or part == "__pycache__" for part in rel.parts) or skip(p):
            continue
        _write(dest / rel, p.read_bytes(), base)
        n += 1
    return n


def _index(repo: Repo, base: str) -> str:
    shell_home = home_shell_page(repo)
    if shell_home:
        return config.shell_pages(repo)[shell_home].read_text(encoding="utf-8")
    page = home_page(repo)
    if page is not None:
        # attributes stay root-absolute (rebase() prefixes them); the refresh URL is prefixed here
        href = html_mod.escape(_href_of(repo, page))
        target = html_mod.escape(base.rstrip("/") + _href_of(repo, page))
        return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
                f'<meta http-equiv="refresh" content="0; url={target}">'
                f'<link rel="canonical" href="{href}"><title>{html_mod.escape(str(repo.cfg.get("name", "")))}</title>'
                f'</head><body><p><a href="{href}">Continue</a></p></body></html>\n')
    return _landing(repo).decode("utf-8")


def run(repo: Repo, out: Path, base: str = "/") -> int:
    if not base.startswith("/") or not base.endswith("/"):
        raise SystemExit(f"--base must start and end with '/' (e.g. /my-repo/), got {base!r}")
    out = out if out.is_absolute() else repo.root / out
    out = out.resolve()
    for inner in (repo.content.resolve(), repo.shell.resolve(), repo.kit.resolve()):
        if out == inner or inner in out.parents:
            raise SystemExit(f"--out {out} lies inside {repo.rel(inner)} — export next to the tree, not into it")
    if out.exists():
        if any(out.iterdir()) and not (out / MARKER).is_file():
            raise SystemExit(f"{out} exists and was not written by `ckit export` — pick another --out")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_text("written by ckit export; the whole directory is replaced on the next export\n")
    (out / ".nojekyll").write_text("")

    _write(out / "index.html", _index(repo, base), base)
    n_shell = _copy_tree(repo.shell, out / "shell", base, skip=lambda p: "skeletons" in p.parts)
    _write(out / "shell" / "theme.css", config.theme_css(repo), base)
    for name, src in config.shell_pages(repo).items():
        _write(out / "shell" / name, src.read_bytes(), base)
    n_content = _copy_tree(repo.content, out / repo.content_name, base,
                           skip=lambda p: p.name.endswith(".annotations.json"))
    n_record = 0
    if chronicle.enabled(repo):
        for p in chronicle.record_files(repo) + [repo.root / r["path"] for r in chronicle.record_catalog(repo)]:
            dest = out / p.relative_to(repo.root)
            if not dest.exists():
                _write(dest, p.read_bytes(), base)
                n_record += 1
    print(f"exported {repo.rel(out) if out.is_relative_to(repo.root) else out}: "
          f"{n_content} content · {n_shell + 1 + len(config.shell_pages(repo))} shell · {n_record} record files"
          + (f" · base {base}" if base != "/" else ""))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit export", description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="dist", help="output directory (default: dist, beside the content)")
    ap.add_argument("--base", default="/", help="the path the site is served under, e.g. /my-repo/")
    args = ap.parse_args(argv)
    return run(load_repo(), Path(args.out), args.base)

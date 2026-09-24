"""The declarative extension points in kit.json, read and validated in one place.

    "shell_pages": {"board.html": "ext/board.html"}       served as /shell/<name>
    "theme":       "assets/theme.css"  (or a list)                        served as /shell/theme.css
    "classes":     ["sw-brand", "lane-brand"]                             the form lint accepts them
    "links":       [{"label": "Revise", "href": "/shell/revise.html", "title": "…"}]
    "refs":        [{"pattern": "Q-\\d+", "href": "/shell/record.html?p=QUESTIONS.md#{id}"}]
    "indices":     ["content/federated.json"]                             merged by the search page

`links`, `refs` and `indices` reach the browser through `catalog.json`; the shell pages and the
theme are served by `ckit serve` and written by `ckit export`. Anything malformed is reported by
name and fails `ckit check` — a declaration the shell silently ignores is worse than none.
"""

from __future__ import annotations

import re
from pathlib import Path

from .paths import Repo

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def theme_files(repo: Repo) -> list[Path]:
    theme = repo.cfg.get("theme")
    if not theme:
        return []
    items = theme if isinstance(theme, list) else [theme]
    return [repo.root / str(x) for x in items]


def theme_css(repo: Repo) -> bytes:
    """The repo's theme, as served at /shell/theme.css: its stylesheets concatenated in order,
    or an empty stylesheet — lib.css imports it unconditionally."""
    parts = [b"/* theme.css: the repo's own names for the shell's hues (kit.json \"theme\") */\n"]
    for p in theme_files(repo):
        if p.is_file():
            parts.append(f"/* --- {repo.rel(p)} --- */\n".encode())
            parts.append(p.read_bytes())
            parts.append(b"\n")
    return b"".join(parts)


def shell_pages(repo: Repo) -> dict[str, Path]:
    pages = repo.cfg.get("shell_pages") or {}
    return {str(k): repo.root / str(v) for k, v in pages.items()} if isinstance(pages, dict) else {}


def classes(repo: Repo) -> set[str]:
    got = repo.cfg.get("classes") or []
    return {c for c in got if isinstance(c, str)} if isinstance(got, list) else set()


def links(repo: Repo) -> list[dict]:
    return [dict(x) for x in repo.cfg.get("links") or [] if isinstance(x, dict)]


def refs(repo: Repo) -> list[dict]:
    return [{"pattern": x["pattern"], "href": x["href"]}
            for x in repo.cfg.get("refs") or [] if isinstance(x, dict) and "pattern" in x and "href" in x]


def indices(repo: Repo) -> list[str]:
    """Each extra index as the URL the search page fetches (root-absolute)."""
    return ["/" + str(x).lstrip("/") for x in repo.cfg.get("indices") or [] if isinstance(x, str)]


def problems(repo: Repo) -> list[str]:
    """Every malformed declaration, by key — `ckit check` fails on any."""
    out: list[str] = []
    cfg = repo.cfg

    pages = cfg.get("shell_pages") or {}
    if not isinstance(pages, dict):
        out.append('kit.json shell_pages: must be an object {"<name>": "<repo-relative file>"}')
    else:
        for name, src in pages.items():
            if not NAME.match(str(name)) or name == "theme.css":
                out.append(f"kit.json shell_pages: {name!r} must be a plain file name (not theme.css)")
            elif (repo.shell / str(name)).exists():
                out.append(f"kit.json shell_pages: {name!r} would shadow the shell's own /shell/{name}")
            if not isinstance(src, str) or not (repo.root / src).is_file():
                out.append(f"kit.json shell_pages: {name!r} → {src!r} does not exist")

    theme = cfg.get("theme")
    if theme:
        items = theme if isinstance(theme, list) else [theme]
        for x in items:
            if not isinstance(x, str) or not x.endswith(".css"):
                out.append(f"kit.json theme: {x!r} must be a repo-relative .css path")
            elif not (repo.root / x).is_file():
                out.append(f"kit.json theme: {x!r} does not exist")

    got = cfg.get("classes") or []
    if not isinstance(got, list) or not all(isinstance(c, str) and c and " " not in c for c in got):
        out.append("kit.json classes: must be a list of class names")

    got = cfg.get("links") or []
    if not isinstance(got, list):
        out.append("kit.json links: must be a list of {label, href}")
    else:
        for x in got:
            if not isinstance(x, dict) or not isinstance(x.get("label"), str) \
                    or not isinstance(x.get("href"), str) or not x["label"] or not x["href"]:
                out.append(f"kit.json links: {x!r} needs a label and an href")

    got = cfg.get("refs") or []
    if not isinstance(got, list):
        out.append("kit.json refs: must be a list of {pattern, href}")
    else:
        for x in got:
            if not isinstance(x, dict) or not isinstance(x.get("pattern"), str) \
                    or not isinstance(x.get("href"), str):
                out.append(f"kit.json refs: {x!r} needs a pattern and an href")
                continue
            try:
                rx = re.compile(x["pattern"])
            except re.error as exc:
                out.append(f"kit.json refs: pattern {x['pattern']!r} is not a regular expression — {exc}")
                continue
            if rx.groups:
                out.append(f"kit.json refs: pattern {x['pattern']!r} must use only (?:…) groups — "
                           "the whole match is the id")
            if "{id}" not in x["href"]:
                out.append(f"kit.json refs: href {x['href']!r} must contain {{id}}")

    got = cfg.get("moved") or {}
    if not isinstance(got, dict):
        out.append('kit.json moved: must be an object {"<old address>": "<new address>"} (ckit mv writes it)')
    else:
        from .links import address_problem
        for old, new in got.items():
            why = address_problem(old) or address_problem(new)
            if why:
                out.append(f"kit.json moved: {old!r} → {new!r} — {why}")

    got = cfg.get("indices") or []
    if not isinstance(got, list):
        out.append("kit.json indices: must be a list of repo-relative JSON paths")
    else:
        for x in got:
            p = repo.root / str(x)
            if not isinstance(x, str) or not x.endswith(".json"):
                out.append(f"kit.json indices: {x!r} must be a repo-relative .json path")
            elif not p.is_file():
                out.append(f"kit.json indices: {x!r} does not exist — generate it (ckit lint) or drop it")
            else:
                try:
                    p.resolve().relative_to(repo.content.resolve())
                except ValueError:
                    out.append(f"kit.json indices: {x!r} must live under {repo.content_name}/, "
                               "where it is served and exported")
    return out

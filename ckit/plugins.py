"""The extension points a layer reaches the engine through — declared in kit.json, implemented
as repo-relative (usually vendored) Python files, loaded here and nowhere else.

    "checks":     ["ext/checks.py"]  CHECKS = {name: fn(ctx) -> [problem]}
                                                  REPO_CHECKS = {name: fn(repo) -> [problem]}
    "generators": ["ext/cards.py"]    generate(repo) -> {path: data}

A page-level check runs where a genre names it (`"checks": {"require_topic": true}`), exactly like a
core check: the genre's value arrives as `ctx.arg`. A name no core check and no plugin provides is
a configuration error that fails the gate — a check that silently never runs is worse than none.
Every repo-level check a registered module exposes runs once per lint.

A generator's files join the committed indices: `ckit lint` / `ckit nav` write them, `ckit check`
fails when one is stale. Paths are repo-relative (or absolute under the repo); a str is written
verbatim, anything else as indented JSON.

Plugins run inside the engine, so they may import `ckit.*`; the context they are handed carries
what a check usually needs so most need not.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Callable

from .paths import Repo

_CACHE: dict[tuple[str, int, int], ModuleType] = {}


@dataclass
class CheckContext:
    """What a page-level check is handed."""
    repo: Repo
    page: Path          # the file
    rel: str            # its repo-relative path, for messages: "<rel>: <problem>"
    text: str           # the raw file
    served: str         # the markup a reader is served: comments, scripts and styles removed
    genre: object       # the ckit.genres.Genre it belongs to
    arg: object         # the value the genre gives this check
    cfg: dict = field(default_factory=dict)  # the repo's kit.json


def load_module(repo: Repo, item: object, key: str) -> ModuleType:
    """Import one repo-relative Python file named under `key` in kit.json."""
    if not isinstance(item, str) or not item.endswith(".py"):
        raise SystemExit(f"kit.json {key}: {item!r} must be a repo-relative path to a .py file")
    p = (repo.root / item).resolve()
    if not p.is_file():
        raise SystemExit(f"kit.json {key}: {item!r} not found")
    st = p.stat()
    stamp = (str(p), st.st_mtime_ns, st.st_size)
    if stamp in _CACHE:
        return _CACHE[stamp]
    spec = importlib.util.spec_from_file_location(f"ckit_plugin_{key}_{p.stem}", p)
    if spec is None or spec.loader is None:
        raise SystemExit(f"kit.json {key}: {item!r} cannot be imported")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _CACHE[stamp] = mod
    return mod


def _items(repo: Repo, key: str) -> list:
    items = repo.cfg.get(key) or []
    if not isinstance(items, list):
        raise SystemExit(f"kit.json {key}: must be a list of repo-relative .py paths")
    return items


def checks(repo: Repo) -> tuple[dict[str, Callable], dict[str, Callable]]:
    """(page checks, repo checks) from every module under `checks`, first declaration wins a name."""
    page: dict[str, Callable] = {}
    whole: dict[str, Callable] = {}
    for item in _items(repo, "checks"):
        mod = load_module(repo, item, "checks")
        found = False
        for attr, into in (("CHECKS", page), ("REPO_CHECKS", whole)):
            table = getattr(mod, attr, None)
            if table is None:
                continue
            if not isinstance(table, dict) or not all(callable(f) for f in table.values()):
                raise SystemExit(f"{item}: {attr} must map check names to functions")
            found = True
            for name, fn in table.items():
                into.setdefault(name, fn)
        if not found:
            raise SystemExit(f"{item}: a check module exposes CHECKS and/or REPO_CHECKS")
    return page, whole


def generators(repo: Repo) -> list[tuple[str, ModuleType]]:
    out = []
    for item in _items(repo, "generators"):
        mod = load_module(repo, item, "generators")
        if not callable(getattr(mod, "generate", None)):
            raise SystemExit(f"{item}: a generator defines generate(repo) -> {{path: data}}")
        out.append((item, mod))
    return out


def generated_files(repo: Repo) -> dict[Path, object]:
    """Every generator's files, keyed by absolute path; a path two generators claim is an error."""
    out: dict[Path, object] = {}
    owner: dict[Path, str] = {}
    root = repo.root.resolve()
    for item, mod in generators(repo):
        got = mod.generate(repo) or {}
        if not isinstance(got, dict):
            raise SystemExit(f"{item}: generate() must return a dict of path -> data")
        for path, data in got.items():
            p = Path(path)
            p = (p if p.is_absolute() else repo.root / p).resolve()
            try:
                p.relative_to(root)
            except ValueError:
                raise SystemExit(f"{item}: generated {path} lies outside the repo") from None
            if p in out:
                raise SystemExit(f"{item}: {repo.rel(p)} is already generated by {owner[p]}")
            out[p] = data
            owner[p] = item
    return out

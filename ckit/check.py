"""The content gate: `ckit check`.

  1. the repo declares the engine version it was checked against, and it is this one
  2. the vendored shell is present
  3. `home`, if set, is either `"dashboard"` or an existing page under the content directory
  4. the committed indices equal discovery — a stale catalog / search index / backlinks / nav
     fails, it is not silently rewritten (`ckit lint` or `ckit nav` regenerates; commit the result)
  5. lint — form, genre, annotations
  6. every book verifies (node), when node is available

Fail-loud, seconds-fast, no network. Identical locally and in CI — that is the point.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from . import __version__, book_nav, lint
from .paths import PACKAGE_DIR, Repo, home_page, load_repo


def run(repo: Repo) -> int:
    declared = repo.cfg.get("ckit")
    if declared is None:
        print(
            f'{repo.rel(repo.marker or repo.root / "kit.json")}: no "ckit" version declared — add '
            f'"ckit": "{__version__}" so the repo records what it was checked against',
            file=sys.stderr,
        )
        return 1
    if str(declared) != __version__:
        print(
            f"engine mismatch: kit.json declares ckit {declared}, this engine is {__version__}. "
            "Re-run `ckit init` with the engine you mean to use, or bump the pin deliberately.",
            file=sys.stderr,
        )
        return 1
    if not (repo.shell / "lib.css").is_file():
        print(f"no vendored shell at {repo.rel(repo.shell)} — run `ckit init` here",
              file=sys.stderr)
        return 1

    home = repo.cfg.get("home")
    if home and home != "dashboard" and home_page(repo) is None:
        print(
            f'kit.json "home" ({home!r}) does not resolve to a page under {repo.rel(repo.content)} — '
            'point it at an existing file, or a directory with an index.html, or set "home": "dashboard".',
            file=sys.stderr,
        )
        return 1

    stale = book_nav.check(repo) if repo.content.is_dir() else []
    if stale:
        print("indices out of date — run `ckit nav` (or `ckit lint`) and commit the result:", file=sys.stderr)
        print("\n".join("  " + s for s in stale), file=sys.stderr)
        return 1
    probs, n = lint.run(repo, nav=False)
    if probs:
        print("\n".join(probs))
        print(f"\n{len(probs)} problem(s) in {n} file(s)")
        return 1
    print(f"content lint clean — {n} file(s)")

    books = repo.content / "books"
    node = shutil.which("node")
    if books.is_dir() and node:
        env = {**os.environ, "CKIT_ROOT": str(repo.root)}
        for book in sorted(books.iterdir()):
            if not (book / "index.html").is_file():
                continue
            r = subprocess.run([node, str(PACKAGE_DIR / "verify_book.mjs"), repo.rel(book)],
                               cwd=repo.root, env=env)
            if r.returncode != 0:
                print(f"book verify failed: {repo.rel(book)}", file=sys.stderr)
                return r.returncode
    elif books.is_dir():
        print("books present but node not found — book verify skipped", file=sys.stderr)
        return 1
    print("content check ok")
    return 0


def main(argv: list[str]) -> int:
    return run(load_repo())

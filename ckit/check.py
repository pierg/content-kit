"""The content gate: `ckit check`.

  1. the repo declares the engine version it was checked against, and it is this one
  2. the vendored shell is present
  3. every extension point kit.json declares holds (config.problems), and `home`, if set, is an
     existing page under the content directory or a declared shell page
  4. the committed indices equal discovery — a stale catalog / search index / backlinks / nav
     fails, it is not silently rewritten (`ckit lint` or `ckit nav` regenerates; commit the result)
  5. lint — form (links, prose, tags included), genre, annotations
  6. every book verifies (node), when node is available

1–3 are preconditions and stop the gate; 3's home and 4–6 all run and report, and the gate
fails at the end on any of them — one run names every problem. Fail-loud, seconds-fast, no
network. Identical locally and in CI — that is the point.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from . import __version__, book_nav, config, lint
from .paths import PACKAGE_DIR, Repo, home_page, home_shell_page, load_repo


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

    bad = config.problems(repo)
    if bad:
        print("kit.json declares extension points that do not hold:", file=sys.stderr)
        print("\n".join("  " + s for s in bad), file=sys.stderr)
        return 1

    # From here on every stage runs and reports, and the gate fails at the end on any of them:
    # one run names every problem, so an author (or an agent) fixes them in one pass instead of
    # meeting them one stage at a time.
    failed: list[str] = []
    home = repo.cfg.get("home")
    if home and home_page(repo) is None and home_shell_page(repo) is None:
        print(
            f'kit.json "home" ({home!r}) does not resolve to a page under {repo.rel(repo.content)} — '
            'point it at an existing file, a directory with an index.html, or a declared shell page.',
            file=sys.stderr,
        )
        failed.append("home")

    stale = book_nav.check(repo) if repo.content.is_dir() else []
    if stale:
        print("indices out of date — run `ckit nav` (or `ckit lint`) and commit the result:", file=sys.stderr)
        print("\n".join("  " + s for s in stale), file=sys.stderr)
        failed.append("indices")
    probs, n = lint.run(repo, nav=False)
    if probs:
        print("\n".join(probs))
        print(f"\n{len(probs)} problem(s) in {n} file(s)")
        failed.append("lint")
    else:
        print(f"content lint clean — {n} file(s)")

    books = repo.content / "books"
    to_verify = [b for b in sorted(books.iterdir()) if (b / "index.html").is_file()] if books.is_dir() else []
    node = shutil.which("node")
    if to_verify and not node:
        print(f"{len(to_verify)} book(s) to verify but node is not on PATH — install node to run the gate",
              file=sys.stderr)
        failed.append("books")
        to_verify = []
    env = {**os.environ, "CKIT_ROOT": str(repo.root)}
    for book in to_verify:
        r = subprocess.run([node, str(PACKAGE_DIR / "verify_book.mjs"), repo.rel(book)],
                           cwd=repo.root, env=env, capture_output=True, text=True)
        sys.stdout.write(r.stdout)  # through Python's streams, so a caller capturing them gets it
        sys.stderr.write(r.stderr)
        if r.returncode != 0:
            print(f"book verify failed: {repo.rel(book)}", file=sys.stderr)
            if "books" not in failed:
                failed.append("books")
    if failed:
        print(f"content check failed: {' · '.join(failed)}", file=sys.stderr)
        return 1
    print("content check ok")
    return 0


def main(argv: list[str]) -> int:
    return run(load_repo())

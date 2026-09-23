"""Full-text search through Pagefind, when it is installed — an accelerator, never a requirement.

    pip install 'pagefind[bin]'        # or: npm i -g pagefind — anything that puts it on PATH

Pagefind indexes the pages as their authors wrote them (the text of each <main>, never the
chrome) into a static, chunked index: a query loads only the fragments it needs. `ckit serve`
builds one in the background into a temporary directory and serves it at /pagefind/, rebuilding
after the indices change (`ckit lint`); `ckit export` writes one into the site. Nothing is
committed and nothing is required: without pagefind the palette and the search page search the
generated search index, as before. `$CKIT_PAGEFIND` names a binary, or `off` turns it off.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


def command() -> list[str] | None:
    """How to run pagefind here, or None."""
    env = os.environ.get("CKIT_PAGEFIND", "").strip()
    if env.lower() in ("0", "off", "no", "false"):
        return None
    if env:
        return [env]
    for name in ("pagefind_extended", "pagefind"):
        exe = shutil.which(name)
        if exe:
            return [exe]
    py = shutil.which("python3") or shutil.which("python")
    if py:
        try:
            ok = subprocess.run([py, "-c", "import pagefind_bin"], capture_output=True, timeout=20).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
        if ok:
            return [py, "-m", "pagefind"]
    return None


def build(cmd: list[str], site: Path, glob: str, out: Path) -> bool:
    """Index `site`'s pages matching `glob` into `out`. True on success; a failure is reported,
    not raised — full text is an accelerator, and the search index still answers."""
    try:
        r = subprocess.run([*cmd, "--site", str(site), "--glob", glob, "--root-selector", "main",
                            "--output-path", str(out), "--quiet"],
                           capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"pagefind: not run — {exc}", flush=True)
        return False
    if r.returncode != 0:
        print(f"pagefind: failed — {(r.stderr or r.stdout).strip()[:400]}", flush=True)
        return False
    return (out / "pagefind.js").is_file()


class Index:
    """The index `ckit serve` keeps: built in a private temporary directory (mkdtemp — this
    process's, unguessable, 0700), swapped in whole, rebuilt when the committed catalog changes
    (a `ckit lint` ran), removed when the server stops. The build before the current one is kept
    too, so a page opened before a rebuild can still fetch the fragments its pagefind.js names."""

    def __init__(self, cmd: list[str] | None):
        self.cmd = cmd
        self.dir: Path | None = None
        self.prev: Path | None = None
        self._stamp: float | None = None
        self._repo = None
        self._lock = threading.Lock()
        self._building = False

    def _catalog_mtime(self) -> float | None:
        try:
            return (self._repo.content / "catalog.json").stat().st_mtime if self._repo else None
        except OSError:
            return None

    def build(self, repo) -> None:
        if not self.cmd:
            return
        with self._lock:
            if self._building:
                return
            self._building = True
        try:
            self._repo = repo
            stamp = self._catalog_mtime()
            out = Path(tempfile.mkdtemp(prefix="ckit-pagefind-"))
            if build(self.cmd, repo.root, f"{repo.content_name}/**/*.html", out):
                gone, self.prev, self.dir = self.prev, self.dir, out
                if gone:
                    shutil.rmtree(gone, ignore_errors=True)
            else:
                shutil.rmtree(out, ignore_errors=True)
            self._stamp = stamp  # a failed build is not retried until the catalog changes again
        finally:
            self._building = False

    def file(self, rel: str) -> Path | None:
        """A file of the current index, or None; a stale index starts its own rebuild."""
        if self._repo is not None and self._catalog_mtime() != self._stamp and not self._building:
            threading.Thread(target=self.build, args=(self._repo,), daemon=True).start()
        if not rel or ".." in Path(rel).parts:
            return None
        for d in (self.dir, self.prev):
            if not d:
                continue
            p = (d / rel).resolve()
            try:
                p.relative_to(d.resolve())
            except ValueError:
                continue
            if p.is_file():
                return p
        return None

    def close(self) -> None:
        for d in (self.dir, self.prev):
            if d:
                shutil.rmtree(d, ignore_errors=True)
        self.dir = self.prev = None

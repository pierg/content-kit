"""Where the repo is, and what it declares.

The engine is installed once and run from inside a repo, so the repo root is found from the
working directory (or `$CKIT_ROOT`), never from where this file lives. The marker is `kit.json`;
`lab.json`, the name every repo carried before 0.4, is still read for one minor version and
says so once per run.

    {
      "name": "My library",
      "content": "content",          # the content tree, relative to the root
      "host": "127.0.0.1", "port": 5180,
      "ckit": "0.4.0",               # the engine version this repo was checked against
      "home": "content/hubs/start.html",
      "genres": { ... }              # optional genre extensions / overrides
      ... and the extension points: see EXTENSION_KEYS below and genres/GENRES.md
    }
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

MARKER = "kit.json"
LEGACY_MARKER = "lab.json"
MARKERS = (MARKER, LEGACY_MARKER)  # search order: the first one present in a directory wins
ROOT_ENV = "CKIT_ROOT"
LEGACY_ROOT_ENV = "LAB_ROOT"

# Every key content-kit owns, with its default. A layer (lab-kit, folio) owns its own keys
# beside these; the engine passes them through untouched.
DEFAULTS: dict = {
    "name": "library",
    "content": "content",
    "host": "127.0.0.1",
    "port": 5180,
    "shell": "kit/shell",   # the vendored shell, repo-relative (content-kit's own docs: "shell")
    "theme": None,          # a stylesheet (or a list) served as /shell/theme.css
    "classes": [],          # extra class names the form lint accepts
    "checks": [],           # modules exposing CHECKS / REPO_CHECKS
    "generators": [],       # modules exposing generate(repo) -> {path: data}
    "shell_pages": {},      # {name: repo-relative file} served as /shell/<name>
    "links": [],            # [{label, href, title?}] in the sidebar and on the landing page
    "refs": [],             # [{pattern, href}] id patterns the shell turns into links
    "indices": [],          # extra search indices the search page merges
}
EXTENSION_KEYS = ("genres", "checks", "generators", "chronicle", "shell_pages", "links", "refs",
                  "theme", "classes", "indices")

# Every document declares whether it is still true, in its opening lines.
DOC_STATUS = ("LIVE", "HISTORICAL", "PARKED", "RETIRED", "FROZEN", "DRAFT")

PACKAGE_DIR = Path(__file__).resolve().parent


def kit_source() -> Path:
    """The directory holding the kit's vendorable parts (shell/, genres/, craft/, skills/,
    templates/, tools/, verify.sh): the package data of an installed wheel, else the checkout
    this engine runs from. `ckit where` prints it; layer installers read it."""
    data = PACKAGE_DIR / "_data"
    return data if (data / "shell").is_dir() else PACKAGE_DIR.parent


KIT_SRC = kit_source()

_warned_legacy = False


def _warn_legacy(path: Path) -> None:
    """One deprecation line per process, however many times a lab.json repo is loaded."""
    global _warned_legacy
    if _warned_legacy:
        return
    _warned_legacy = True
    print(f"ckit: {path} is deprecated — rename it to kit.json (git mv lab.json kit.json); "
          "lab.json is read until 0.5", file=sys.stderr)


@dataclass
class Repo:
    root: Path
    cfg: dict
    marker: Path | None = None

    @property
    def content(self) -> Path:
        return self.root / self.cfg["content"]

    @property
    def kit(self) -> Path:
        return self.root / "kit"

    @property
    def shell(self) -> Path:
        return self.root / str(self.cfg.get("shell") or DEFAULTS["shell"])

    @property
    def content_name(self) -> str:
        return str(self.cfg["content"]).strip("/")

    @property
    def config_name(self) -> str:
        """The config file's name, for messages — kit.json unless a legacy repo still has lab.json."""
        return self.marker.name if self.marker else MARKER

    def rel(self, path: Path) -> str:
        """Path relative to the root when possible, else absolute — for messages."""
        try:
            return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(path)


def home_page(repo: Repo) -> Path | None:
    """The content page `home` names, when it names one.

    A file resolves to itself; a directory resolves to its `index.html`. None when `home` is
    not a string, is unset/empty, names a shell page (see `home_shell_page`), or the resolved
    target is not an existing file under the content directory — callers already hold `home`
    itself to tell "nothing asked for" apart from "asked for and dangling" (`ckit check` fails
    the gate on the latter; `ckit serve` 404s). A non-string `home` (e.g. `true`) is dangling,
    not a crash — `Path / home` is never reached.
    """
    home = repo.cfg.get("home")
    if not isinstance(home, str) or not home or home_shell_page(repo):
        return None
    target = (repo.root / home).resolve()
    if target.is_dir():
        target = target / "index.html"
    try:
        target.relative_to(repo.content.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


def home_shell_page(repo: Repo) -> str | None:
    """The `shell_pages` name `home` names (`"revise"` or `"revise.html"`), if it names one:
    a layer's page served at `/` as the front door."""
    home = repo.cfg.get("home")
    pages = repo.cfg.get("shell_pages") or {}
    if not isinstance(home, str) or not isinstance(pages, dict):
        return None
    for name in (home, f"{home}.html"):
        if name in pages:
            return name
    return None


def _marker_in(d: Path) -> Path | None:
    for name in MARKERS:
        if (d / name).is_file():
            return d / name
    return None


def find_root(start: Path | str | None = None) -> Path:
    for var in (ROOT_ENV, LEGACY_ROOT_ENV):
        env = os.environ.get(var)
        if env:
            root = Path(env).resolve()
            if _marker_in(root) is None:
                raise SystemExit(f"{var}={root}: no {MARKER} there")
            return root
    here = Path(start or os.getcwd()).resolve()
    for cand in [here, *here.parents]:
        if _marker_in(cand) is not None:
            return cand
    raise SystemExit(
        f"no {MARKER} in {here} or any parent — run inside a repo the kit was installed "
        f"into (`ckit init <repo>`), or set {ROOT_ENV}"
    )


def load_repo(start: Path | str | None = None) -> Repo:
    root = find_root(start)
    marker = _marker_in(root)
    assert marker is not None
    if marker.name == LEGACY_MARKER:
        _warn_legacy(marker)
    cfg = json.loads(json.dumps(DEFAULTS))  # a deep copy: list/dict defaults are never shared
    try:
        loaded = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{marker}: invalid JSON — {exc}") from exc
    if not isinstance(loaded, dict):
        raise SystemExit(f"{marker}: must be a JSON object")
    cfg.update(loaded)
    return Repo(root=root, cfg=cfg, marker=marker)

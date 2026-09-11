"""Where the repo is, and what it declares.

The engine is installed once and run from inside a repo, so the repo root is found from the
working directory (or `$LAB_ROOT`), never from where this file lives. The marker is `lab.json`
— the historical name, kept because every existing repo already has one; a repo need not be a
lab to carry it.

    {
      "name": "folio",
      "content": "content",          # the content tree, relative to the root
      "host": "127.0.0.1", "port": 5180,
      "ckit": "0.1.0",               # the engine version this repo was checked against
      "genres": { ... }              # optional per-repo genre extensions / overrides
    }
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

MARKER = "lab.json"
DEFAULTS = {"content": "content", "port": 5180, "host": "127.0.0.1", "name": "library"}

# DISCIPLINE §8 — every document declares whether it is still true, in its opening lines.
DOC_STATUS = ("LIVE", "HISTORICAL", "PARKED", "RETIRED", "FROZEN", "DRAFT")

PACKAGE_DIR = Path(__file__).resolve().parent
KIT_SRC = PACKAGE_DIR.parent  # the content-kit checkout this engine runs from


@dataclass
class Repo:
    root: Path
    cfg: dict

    @property
    def content(self) -> Path:
        return self.root / self.cfg["content"]

    @property
    def kit(self) -> Path:
        return self.root / "kit"

    @property
    def shell(self) -> Path:
        return self.kit / "shell"

    @property
    def content_name(self) -> str:
        return str(self.cfg["content"]).strip("/")

    def rel(self, path: Path) -> str:
        """Path relative to the root when possible, else absolute — for messages."""
        try:
            return Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)


def find_root(start: Path | str | None = None) -> Path:
    env = os.environ.get("LAB_ROOT")
    if env:
        root = Path(env).resolve()
        if not (root / MARKER).is_file():
            raise SystemExit(f"LAB_ROOT={root}: no {MARKER} there")
        return root
    here = Path(start or os.getcwd()).resolve()
    for cand in [here, *here.parents]:
        if (cand / MARKER).is_file():
            return cand
    raise SystemExit(
        f"no {MARKER} in {here} or any parent — run inside a repo the kit was installed "
        "into (bash /path/to/content-kit/install.sh <repo>), or set LAB_ROOT"
    )


def load_repo(start: Path | str | None = None) -> Repo:
    root = find_root(start)
    cfg = dict(DEFAULTS)
    marker = root / MARKER
    try:
        cfg.update(json.loads(marker.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{marker}: invalid JSON — {exc}") from exc
    return Repo(root=root, cfg=cfg)

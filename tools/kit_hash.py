#!/usr/bin/env python3
"""Content hash of a kit tree — the thing a lab pins so drift is detectable.

A vendored kit that can be edited in place silently is not a shared kit; it is four
divergent copies with the same name. The lab's gate recomputes this hash and fails
loud on a mismatch, so the only way to change the kit is to change it upstream and
re-sync deliberately.

    python3 tools/kit_hash.py [<kit-dir>]
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

EXCLUDE_NAMES = {"PIN", ".git", "__pycache__", ".DS_Store", ".serve.pid", ".serve.log"}


def kit_files(kit: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(kit.rglob("*")):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_NAMES for part in p.relative_to(kit).parts):
            continue
        out.append(p)
    return out


def kit_hash(kit: Path) -> str:
    h = hashlib.sha256()
    for p in kit_files(kit):
        rel = p.relative_to(kit).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    print(kit_hash(root.resolve()))

"""One instruction file and one skill body, with the other paths as links.

`ckit check` reports when a repo drifts from that layout. It changes nothing.
`ckit init` creates the layout and, re-run, repairs the links it owns.
"""

from __future__ import annotations

import os
from pathlib import Path

from .paths import Repo

AGENTS_LIMIT = 24 * 1024
CLAUDE_TEXT = b"@AGENTS.md\n"
CLAUDE_LINK = "../.agents/skills"


def skill_bodies(root: Path) -> dict[str, list[Path]]:
    """Skill name → directories that hold its `SKILL.md`.

    A library vendors those directories under `kit/skills/` and `kit/<layer>/skills/`.
    The content-kit checkout itself has no `kit/skills/`; its bodies are `skills/<name>/`.
    """
    found: dict[str, list[Path]] = {}

    def take(directory: Path) -> None:
        if not directory.is_dir():
            return
        for child in sorted(directory.iterdir()):
            if child.name.startswith(".") or not (child / "SKILL.md").is_file():
                continue
            found.setdefault(child.name, []).append(child)

    kit = root / "kit"
    take(kit / "skills")
    if kit.is_dir():
        for layer in sorted(p for p in kit.iterdir() if p.is_dir()):
            if layer.name in ("skills",) or layer.name.startswith("."):
                continue
            take(layer / "skills")
    if not (kit / "skills").exists():
        take(root / "skills")
    return found


def problems(repo: Repo) -> list[str]:
    """Every way the instruction files or the skill links are wrong. Empty means they hold."""
    root = repo.root
    out: list[str] = []

    agents = root / "AGENTS.md"
    if agents.is_symlink():
        out.append("AGENTS.md is a symlink — it must be a regular file, the only copy of the operating rules")
    elif not agents.is_file():
        out.append("AGENTS.md is missing")
    else:
        size = agents.stat().st_size
        if size == 0:
            out.append("AGENTS.md is empty")
        elif size > AGENTS_LIMIT:
            out.append(f"AGENTS.md is {size} bytes; the limit is {AGENTS_LIMIT} (24 KiB)")

    claude = root / "CLAUDE.md"
    if claude.is_symlink() or not claude.is_file() or claude.read_bytes() != CLAUDE_TEXT:
        out.append("CLAUDE.md must be exactly @AGENTS.md and a trailing newline")

    claude_skills = root / ".claude" / "skills"
    if not _is_rel_link(claude_skills, CLAUDE_LINK):
        out.append(".claude/skills must be a relative symlink to ../.agents/skills")

    cursor = root / ".cursor" / "skills"
    if cursor.is_symlink() or cursor.exists():
        out.append(".cursor/skills must not exist")

    bodies = skill_bodies(root)
    agents_dir = root / ".agents" / "skills"
    for name, dirs in bodies.items():
        link = agents_dir / name
        raw = os.readlink(link) if link.is_symlink() else None
        resolved = (link.parent / raw).resolve() if raw and not Path(raw).is_absolute() else (
            Path(raw).resolve() if raw else None
        )
        for body in dirs:
            rel_body = repo.rel(body)
            if raw is None:
                out.append(f".agents/skills/{name} must be a relative symlink to {rel_body}")
            elif Path(raw).is_absolute():
                out.append(f".agents/skills/{name} must be a relative symlink to {rel_body}")
            elif resolved != body.resolve():
                out.append(f".agents/skills/{name} resolves outside {rel_body}")

    if agents_dir.is_dir():
        for entry in sorted(agents_dir.iterdir()):
            if entry.name in bodies:
                if not entry.is_symlink() and entry.is_dir():
                    out.append(f".agents/skills/{entry.name} reuses a kit skill name")
                continue
            if entry.is_symlink() or not entry.is_dir() or not (entry / "SKILL.md").is_file():
                out.append(
                    f".agents/skills/{entry.name} must be a directory containing SKILL.md"
                )

    seen: dict[str, set[Path]] = {}
    for name, dirs in bodies.items():
        for body in dirs:
            seen.setdefault(name, set()).add((body / "SKILL.md").resolve())
    for base in (agents_dir, claude_skills):
        if not (base.is_symlink() or base.is_dir()):
            continue
        try:
            children = list(base.iterdir())
        except OSError:
            continue
        for child in children:
            skill = child / "SKILL.md"
            if skill.is_file():
                seen.setdefault(child.name, set()).add(skill.resolve())
    for name, paths in seen.items():
        if len(paths) > 1:
            out.append(f"{name}: SKILL.md resolves to more than one file")
    return out


def _is_rel_link(path: Path, expected: str) -> bool:
    return path.is_symlink() and os.readlink(path) == expected

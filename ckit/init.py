"""Vendor the kit's rules into a repo, and scaffold anything the repo is missing: `ckit init`.

    ckit init [<repo>] [--name "Name"] [--port 5180]

Vendored into <repo>/kit/ — the parts an agent must find in-repo, readable, pinned:
    shell/  genres/  craft/  skills/{present,address,curate}  tools/kit_hash.py  verify.sh
from `ckit where`: the package data of an installed engine, or the checkout it runs from.
The engine itself is not vendored; the repo records the version it was checked against in
kit.json (`"ckit"`), and `ckit check` fails on a mismatch.

Idempotent: re-running re-vendors and re-pins, and scaffolds only what is missing. It touches
only its own paths under kit/, so a layer vendored beside them (lab-kit, say) survives.
Layer installers call it first, then add their own files and `source` line.

kit/PIN records `source content-kit <where> <ref>`: the checkout's git remote and commit when
there is one, else the project URL and the release tag when running from an installed wheel,
else the local path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import __version__
from .paths import KIT_SRC, LEGACY_MARKER, MARKER

PROJECT_URL = "https://github.com/pierg/content-kit"
VENDORED_DIRS = ("shell", "genres", "craft")
SKILLS = ("present", "address", "curate")
CONTENT_DIRS = ("notes", "entries", "concepts", "hubs", "projects", "papers", "related", "books")


def _git(src: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(src), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def public_url(remote: str) -> str:
    """A git remote as a credential-free https URL: git@github.com:o/r.git → https://github.com/o/r."""
    r = remote.strip()
    m = re.match(r"^(?:ssh://)?git@([^:/]+)[:/](.+?)(?:\.git)?/?$", r)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    r = re.sub(r"^(https?://)[^@/]+@", r"\1", r)  # drop any user:token@
    return re.sub(r"\.git/?$", "", r).rstrip("/")


def source_of(src: Path) -> tuple[str, str]:
    """(where, ref) for the kit/PIN line of a kit source directory."""
    if _git(src, "rev-parse", "--show-toplevel") and (src / ".git").exists():
        sha = _git(src, "rev-parse", "HEAD") or "unknown"
        remote = _git(src, "remote", "get-url", "origin")
        return (public_url(remote) if remote else str(src)), sha
    if src.name == "_data":  # an installed wheel: the release it was built from
        return PROJECT_URL, f"v{__version__}"
    return str(src), "unknown"


def _copytree(src: Path, dest: Path) -> None:
    if dest.exists() or dest.is_symlink():
        shutil.rmtree(dest) if dest.is_dir() and not dest.is_symlink() else dest.unlink()
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc"))


def vendor(repo: Path, src: Path = KIT_SRC) -> None:
    kit = repo / "kit"
    (kit / "skills").mkdir(parents=True, exist_ok=True)
    (kit / "tools").mkdir(parents=True, exist_ok=True)
    for d in VENDORED_DIRS:
        _copytree(src / d, kit / d)
    genres_json = Path(__file__).resolve().parent / "genres.json"
    shutil.copy2(genres_json, kit / "genres" / "genres.json")  # a readable copy; the engine's is authoritative
    for s in SKILLS:
        _copytree(src / "skills" / s, kit / "skills" / s)
    shutil.copy2(src / "tools" / "kit_hash.py", kit / "tools" / "kit_hash.py")
    shutil.copy2(src / "verify.sh", kit / "verify.sh")
    os.chmod(kit / "verify.sh", 0o755)


def _scaffold(repo: Path, rel: str, template: Path, say) -> None:
    dest = repo / rel
    if dest.exists():
        say(f"  keep    {rel}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, dest)
    say(f"  create  {rel}")


def _config(repo: Path, name: str, port: int | None, say) -> Path:
    """kit.json: name and port on first creation; the engine pin every time — installing IS the
    deliberate act of accepting this engine version. A repo still carrying only lab.json keeps it."""
    legacy = repo / LEGACY_MARKER
    p = legacy if legacy.is_file() and not (repo / MARKER).is_file() else repo / MARKER
    if p == legacy:
        say(f"  note    {LEGACY_MARKER} is deprecated — `git mv {LEGACY_MARKER} {MARKER}` when convenient")
    cfg = json.loads(p.read_text(encoding="utf-8"))
    if str(cfg.get("name", "")).startswith("<"):
        cfg["name"] = name
        if port:
            cfg["port"] = int(port)
        say(f"  set     {p.name} name={name}" + (f" port={port}" if port else ""))
    if cfg.get("ckit") != __version__:
        say(f"  pin     {p.name} ckit={__version__}" + (f" (was {cfg['ckit']})" if cfg.get("ckit") else ""))
        cfg["ckit"] = __version__
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def _link_skills(repo: Path, say) -> None:
    """One body per kit skill, linked from `.agents/skills/<name>`. `.claude/skills` is a single
    relative symlink to that directory. A real directory already occupying a kit skill's name is
    replaced: a repo-owned skill may not shadow a kit skill. A real directory under `.claude/skills`
    whose name is not a kit skill is left — it belongs to the repo and moves to `.agents/skills/`."""
    from .agents import skill_bodies

    bodies = skill_bodies(repo)
    agents = repo / ".agents" / "skills"
    agents.mkdir(parents=True, exist_ok=True)
    for name, dirs in bodies.items():
        if len(dirs) != 1:
            say(f"  note    {name} has {len(dirs)} bodies — not linked")
            continue
        dest = agents / name
        rel = os.path.relpath(dirs[0], agents)
        if dest.is_symlink() and os.readlink(dest) == rel:
            continue
        if dest.is_dir() and not dest.is_symlink():
            say(f"  replace .agents/skills/{name}  (it shadowed the kit skill)")
            shutil.rmtree(dest)
        elif dest.is_symlink() or dest.is_file():
            dest.unlink()
        dest.symlink_to(rel)
        say(f"  link    .agents/skills/{name}")

    claude = repo / ".claude" / "skills"
    if claude.is_symlink():
        if os.readlink(claude) != "../.agents/skills":
            claude.unlink()
            claude.symlink_to("../.agents/skills")
            say("  link    .claude/skills")
        return
    if claude.is_dir():
        for child in list(claude.iterdir()):
            if child.is_symlink() or child.is_file():
                child.unlink()
        leftover = list(claude.iterdir())
        if leftover:
            for child in leftover:
                say(f"  keep    .claude/skills/{child.name}  (repo's own — move it to .agents/skills/{child.name})")
            return
        claude.rmdir()
    elif claude.exists():
        claude.unlink()
    claude.parent.mkdir(parents=True, exist_ok=True)
    claude.symlink_to("../.agents/skills")
    say("  link    .claude/skills")


def pin(repo: Path, name: str, where: str, ref: str) -> None:
    """Put this kit's `source` line into kit/PIN (keeping every other kit's), then re-hash the tree."""
    pin_file = repo / "kit" / "PIN"
    others = []
    if pin_file.is_file():
        others = [ln for ln in pin_file.read_text(encoding="utf-8").splitlines()
                  if ln.startswith("source ") and not ln.startswith(f"source {name} ")]
    lines = [f"source {name} {where} {ref}", *others] if name == "content-kit" else [*others, f"source {name} {where} {ref}"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("kit_hash", repo / "kit" / "tools" / "kit_hash.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    digest = mod.kit_hash(repo / "kit")  # the hash excludes PIN itself
    pin_file.write_text("\n".join([*lines, f"hash {digest}"]) + "\n", encoding="utf-8")


def run(repo: Path, *, name: str | None = None, port: int | None = None, quiet: bool = False,
        src: Path = KIT_SRC) -> int:
    say = (lambda *_: None) if quiet else print
    repo.mkdir(parents=True, exist_ok=True)
    repo = repo.resolve()
    say(f"vendoring content-kit {__version__} -> {repo / 'kit'}")
    vendor(repo, src)
    say("scaffolding")
    tpl = src / "templates"
    if not ((repo / LEGACY_MARKER).is_file() and not (repo / MARKER).is_file()):
        _scaffold(repo, MARKER, tpl / "kit.json", say)
    _scaffold(repo, "Makefile", tpl / "Makefile", say)
    _scaffold(repo, ".gitignore", tpl / "gitignore", say)
    _scaffold(repo, "AGENTS.md", tpl / "AGENTS.md", say)
    claude = repo / "CLAUDE.md"
    if not claude.exists() and not claude.is_symlink():
        claude.write_text("@AGENTS.md\n", encoding="utf-8")
        say("  create  CLAUDE.md")
    for d in CONTENT_DIRS:
        (repo / "content" / d).mkdir(parents=True, exist_ok=True)
    _config(repo, name or repo.name, port, say)
    _link_skills(repo, say)
    where, ref = source_of(src)
    pin(repo, "content-kit", where, ref)
    say(f"pinned  content-kit@{ref[:8]}")
    from . import book_nav
    from .paths import load_repo
    try:
        written = book_nav.regenerate(load_repo(repo))
    except SystemExit as exc:  # a layer named in kit.json that is not vendored yet, say
        written = []
        say(f"  note    indices not generated yet ({exc}) — run `ckit nav` once every layer is installed")
    if written:
        say("indices generated: " + ", ".join(written))
    say("\ndone. next:")
    say(f"  cd {repo} && make check     # the content gate")
    say(f"  cd {repo} && make docs      # read the pages; ✎ Annotate appears bottom-right")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ckit init", description=__doc__.split("\n")[0])
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--name")
    ap.add_argument("--port", type=int)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    return run(Path(args.repo), name=args.name, port=args.port, quiet=args.quiet)

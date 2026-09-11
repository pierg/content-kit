#!/usr/bin/env bash
# Vendor the kit's rules into a repo, and scaffold anything the repo is missing.
#
#   bash install.sh /path/to/repo [--name "Name"] [--port 5180]
#
# Vendored into <repo>/kit/ — the parts an agent must find in-repo, readable, pinned:
#   shell/   genres/   craft/   skills/present   skills/address   tools/kit_hash.py   verify.sh
# Not vendored — the engine. `ckit` is installed once (install-engine.sh) and the repo
# records the version it was checked against in lab.json; `ckit check` fails on a mismatch.
#
# Idempotent: re-running re-vendors and re-pins, and scaffolds only what is missing.
# It touches only its own paths under kit/, so a lab-kit overlay beside them survives.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
REPO=""; NAME=""; PORT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) REPO="$1"; shift ;;
  esac
done
[ -n "$REPO" ] || { echo "usage: bash install.sh /path/to/repo [--name N] [--port P]" >&2; exit 2; }
mkdir -p "$REPO"
REPO="$(cd "$REPO" && pwd)"
NAME="${NAME:-$(basename "$REPO")}"
KIT="$REPO/kit"
VERSION="$(python3 -c "import re,pathlib; print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('$SRC/ckit/__init__.py').read_text()).group(1))")"

echo "vendoring content-kit $VERSION -> $KIT"
mkdir -p "$KIT/skills" "$KIT/tools"
for d in shell genres craft; do
  rm -rf "$KIT/$d"
  cp -r "$SRC/$d" "$KIT/$d"
done
cp "$SRC/ckit/genres.json" "$KIT/genres/genres.json"   # a readable copy; the engine's is authoritative
for s in present address; do
  rm -rf "$KIT/skills/$s"
  cp -r "$SRC/skills/$s" "$KIT/skills/$s"
done
cp "$SRC/tools/kit_hash.py" "$KIT/tools/kit_hash.py"
cp "$SRC/verify.sh" "$KIT/verify.sh"
find "$KIT" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

scaffold() {  # scaffold <relative-target> <template>
  if [ -e "$REPO/$1" ]; then echo "  keep    $1"; else
    mkdir -p "$(dirname "$REPO/$1")"
    cp "$SRC/templates/$2" "$REPO/$1"
    echo "  create  $1"
  fi
}
echo "scaffolding"
scaffold lab.json   lab.json
scaffold Makefile   Makefile
scaffold .gitignore gitignore
mkdir -p "$REPO"/content/{notes,entries,concepts,hubs,projects,papers,related,books}

# lab.json: name and port on first creation; the engine pin every time — installing IS the
# deliberate act of accepting this engine version.
python3 - "$REPO" "$NAME" "${PORT:-}" "$VERSION" <<'PY'
import json, sys
from pathlib import Path
repo, name, port, version = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
p = repo / "lab.json"
cfg = json.loads(p.read_text())
if str(cfg.get("name", "")).startswith("<"):
    cfg["name"] = name
    if port:
        cfg["port"] = int(port)
    print(f"  set     lab.json name={name}" + (f" port={port}" if port else ""))
if cfg.get("ckit") != version:
    print(f"  pin     lab.json ckit={version}" + (f" (was {cfg['ckit']})" if cfg.get("ckit") else ""))
    cfg["ckit"] = version
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
PY

# Skills are symlinked so a re-sync updates them and drift is visible. A pre-existing real
# directory is the repo's own skill: leave it and say so.
mkdir -p "$REPO/.claude/skills"
for s in present address; do
  dest="$REPO/.claude/skills/$s"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "  keep    .claude/skills/$s  (repo's own — kit's copy NOT linked)"
  else
    ln -sfn "../../kit/skills/$s" "$dest"
  fi
done

# PIN: one `source` line per kit that vendored into kit/, then the hash of the whole tree.
PIN="$KIT/PIN"
SHA="$(git -C "$SRC" rev-parse HEAD 2>/dev/null || echo unknown)"
{
  echo "source content-kit $SRC $SHA"
  [ -f "$PIN" ] && grep -E '^source ' "$PIN" | grep -v '^source content-kit ' || true
} > "$PIN.tmp"
mv "$PIN.tmp" "$PIN"
bash "$KIT/verify.sh" --repin >/dev/null
echo "pinned  content-kit@${SHA:0:8}"
if command -v ckit >/dev/null 2>&1; then
  (cd "$REPO" && ckit nav >/dev/null) && echo "indices generated (ckit nav)"
fi

echo
echo "done. next:"
echo "  cd $REPO && make check     # the content gate"
echo "  cd $REPO && make docs      # read the pages; ✎ Annotate appears bottom-right"
command -v ckit >/dev/null 2>&1 || echo "  (ckit is not on PATH — run: bash $SRC/install-engine.sh)"

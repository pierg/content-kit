#!/usr/bin/env bash
# Put `ckit` on PATH, once. Re-running is harmless; `git pull` in this checkout is the upgrade,
# and each repo's lab.json pin decides whether that upgrade is accepted.
#
#   bash install-engine.sh [bin-dir]      # default: ~/.local/bin
#
# No packaging step: bin/ckit runs the package straight from this checkout (stdlib only,
# Python ≥ 3.10; node for book verification). `pip install -e .` also works where pip exists.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
BIN="${1:-$HOME/.local/bin}"
mkdir -p "$BIN"
ln -sfn "$SRC/bin/ckit" "$BIN/ckit"
echo "linked $BIN/ckit -> $SRC/bin/ckit"
if command -v ckit >/dev/null 2>&1; then
  echo "ckit $(ckit version) on PATH"
else
  echo "add $BIN to PATH (e.g. export PATH=\"$BIN:\$PATH\") — then \`ckit version\`"
fi

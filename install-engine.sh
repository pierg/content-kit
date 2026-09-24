#!/usr/bin/env bash
# Put this checkout's `ckit` on PATH — for working on the kit itself. Users install a release:
#
#   uv tool install git+https://github.com/pierg/content-kit@v0.5.0
#
# Here, `git pull` in this checkout is the upgrade, and each repo's kit.json pin decides whether
# that upgrade is accepted (`ckit check` fails loud on a mismatch).
#
#   bash install-engine.sh [bin-dir]      # default: ~/.local/bin
#
# No packaging step: bin/ckit runs the package straight from this checkout (stdlib only,
# Python ≥ 3.10; node for book verification).
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

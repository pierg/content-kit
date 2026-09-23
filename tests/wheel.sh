#!/usr/bin/env bash
# The engine as a user gets it: `uv tool install` this checkout into a throwaway tool directory,
# then prove the installed `ckit` — which has no checkout to lean on — vendors from its own
# package data, pins the release rather than a path, and inits a repo whose gate is green.
# Skipped (not failed) where uv is absent; CI always has it.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
command -v uv >/dev/null 2>&1 || { echo "wheel: uv not found — skipped"; exit 0; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail() { echo "wheel: $*" >&2; exit 1; }
export UV_TOOL_DIR="$TMP/tools" UV_TOOL_BIN_DIR="$TMP/bin" UV_NO_CONFIG=1
uv tool install --quiet --no-cache "$KIT" >/dev/null 2>&1 || uv tool install --no-cache "$KIT" || fail "uv tool install failed"
CKIT="$TMP/bin/ckit"
[ -x "$CKIT" ] || fail "no ckit in the tool bin dir"
export PATH="$TMP/bin:$PATH"   # and nothing of the checkout's
[ "$(ckit version)" = "$(PYTHONPATH="$KIT" python3 -c 'import ckit; print(ckit.__version__)')" ] || fail "installed version differs from the checkout's"
WHERE="$(ckit where)"
case "$WHERE" in "$KIT"*) fail "the installed engine vendors from the checkout ($WHERE), not its package data" ;; esac
[ -f "$WHERE/shell/lib.css" ] && [ -f "$WHERE/templates/kit.json" ] && [ -f "$WHERE/verify.sh" ] || fail "package data incomplete at $WHERE"
ckit init "$TMP/repo" --name "Wheel" --quiet
grep -q "^source content-kit https://github.com/pierg/content-kit v$(ckit version)$" "$TMP/repo/kit/PIN" \
  || fail "an installed engine must pin the release, got: $(grep '^source' "$TMP/repo/kit/PIN")"
( cd "$TMP/repo" && make check >/dev/null ) || fail "make check failed on a repo the installed engine initialised"
( cd "$TMP/repo" && ckit new note first >/dev/null ) || fail "ckit new failed"
# its skeleton's placeholder links, pointed somewhere real as an author would
sed -i.bak 's#href="/content/[^"]*OTHER[^"]*"#href="/content/notes/first.html"#g' "$TMP/repo/content/notes/first.html" \
  && rm -f "$TMP/repo/content/notes/first.html.bak"
( cd "$TMP/repo" && ckit lint >/dev/null && make check >/dev/null ) || fail "gate red after a first page"
( cd "$TMP/repo" && make kit-sync >/dev/null && make kit-verify >/dev/null ) || fail "kit-sync through the installed engine failed"
echo "wheel ok"

#!/usr/bin/env bash
# Confirm the vendored kit/ still matches its pin — or re-sync it deliberately.
#
#   bash kit/verify.sh            verify (what `make kit-verify` runs)
#   bash kit/verify.sh --sync     re-vendor from every pinned source, in PIN order
#   bash kit/verify.sh --repin    recompute the hash line (installers call this; you don't)
#
# kit/PIN:  source <kit-name> <url-or-path> <ref>   one per kit that vendored into kit/
#           hash <sha256>                            of the whole tree, PIN excluded
#
# --sync finds each source locally, in this order: $<NAME> (content-kit → $CONTENT_KIT,
# lab-kit → $LAB_KIT, folio → $FOLIO), the recorded path if it is a directory here, the
# installed engine for content-kit (`ckit where`), then a sibling checkout ../<kit-name>.
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$KIT/.." && pwd)"
PIN="$KIT/PIN"
[ -f "$PIN" ] || { echo "kit: no PIN file — this kit was not installed by ckit init or a layer installer" >&2; exit 1; }

case "${1:-}" in
  --sync)
    SOURCES="$(mktemp)"  # outside kit/: the tree is re-hashed while this loop runs
    trap 'rm -f "$SOURCES"' EXIT
    grep -E '^source ' "$PIN" > "$SOURCES"
    while read -r _ name src ref; do
      var="$(printf '%s' "$name" | tr 'a-z-' 'A-Z_')"
      dir="${!var:-}"
      [ -z "$dir" ] && [ -d "$src" ] && dir="$src"
      if [ -z "$dir" ] && [ "$name" = content-kit ] && command -v ckit >/dev/null 2>&1; then dir="$(ckit where)"; fi
      [ -z "$dir" ] && [ -d "$REPO/../$name" ] && dir="$(cd "$REPO/../$name" && pwd)"
      if [ -z "$dir" ] || [ ! -d "$dir" ]; then
        echo "kit: $name ($src @ $ref) is not present here — clone it and set $var=/path/to/it" >&2; exit 1
      fi
      echo "re-vendoring $name from $dir"
      if [ "$name" = content-kit ]; then
        if [ -x "$dir/bin/ckit" ]; then "$dir/bin/ckit" init "$REPO" --quiet; else ckit init "$REPO" --quiet; fi
      else
        bash "$dir/install.sh" "$REPO"
      fi
    done < "$SOURCES"
    exit 0 ;;
  --repin)
    H="$(python3 "$KIT/tools/kit_hash.py" "$KIT")"
    { grep -E '^source ' "$PIN"; echo "hash $H"; } > "$PIN.tmp"
    mv "$PIN.tmp" "$PIN"
    echo "kit repinned $H"
    exit 0 ;;
  "") ;;
  *) sed -n '2,12p' "$0" >&2; exit 2 ;;
esac

PINNED="$(awk '/^hash/ {print $2}' "$PIN")"
ACTUAL="$(python3 "$KIT/tools/kit_hash.py" "$KIT")"
if [ "$ACTUAL" != "$PINNED" ]; then
  cat >&2 <<EOF
kit: VENDORED COPY HAS DRIFTED FROM ITS PIN
  pinned  $PINNED
  actual  $ACTUAL

kit/ is a frozen surface. Change it upstream —
$(grep -E '^source ' "$PIN" | awk '{print "  " $2 ": " $3}')
— then re-sync here with \`make kit-sync\`. Editing kit/ in place makes this repo's copy
silently different from every other repo's, which is the failure this pin exists to prevent.
EOF
  exit 1
fi
echo "kit ok ($(grep -E '^source ' "$PIN" | awk '{printf "%s@%s ", $2, substr($4,1,8)}'))"

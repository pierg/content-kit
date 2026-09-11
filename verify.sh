#!/usr/bin/env bash
# Confirm the vendored kit/ still matches its pin — or re-sync it deliberately.
#
#   bash kit/verify.sh            verify (what `make kit-verify` runs)
#   bash kit/verify.sh --sync     re-vendor from every pinned source, in PIN order
#   bash kit/verify.sh --repin    recompute the hash line (installers call this; you don't)
#
# kit/PIN:  source <kit-name> <path> <commit>   one per kit that vendored into kit/
#           hash <sha256>                        of the whole tree, PIN excluded
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$KIT/.." && pwd)"
PIN="$KIT/PIN"
[ -f "$PIN" ] || { echo "kit: no PIN file — this kit was not installed by an install.sh" >&2; exit 1; }

case "${1:-}" in
  --sync)
    mapfile -t SOURCES < <(grep -E '^source ' "$PIN")
    for line in "${SOURCES[@]}"; do
      read -r _ name src _ <<<"$line"
      [ -d "$src" ] || { echo "kit: source $name at $src is not present — cannot sync" >&2; exit 1; }
      echo "re-vendoring $name from $src"
      bash "$src/install.sh" "$REPO"
    done
    exit 0 ;;
  --repin)
    H="$(python3 "$KIT/tools/kit_hash.py" "$KIT")"
    { grep -E '^source ' "$PIN"; echo "hash $H"; } > "$PIN.tmp"
    mv "$PIN.tmp" "$PIN"
    echo "kit repinned $H"
    exit 0 ;;
  "") ;;
  *) sed -n '2,10p' "$0" >&2; exit 2 ;;
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

#!/usr/bin/env bash
# End-to-end: install into a scratch repo, run its gate, scaffold pages, serve, annotate through
# the HTTP endpoint, act on the thread through the CLI, and prove the gate catches drift, a bad
# engine pin, and an open thread whose passage was rewritten. This is the check unit tests cannot
# give: the kit runs from a directory it was copied into, with the engine found on PATH.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$KIT/bin:$PATH"
TMP="$(mktemp -d)"
REPO="$TMP/repo"
PORT=5398
trap 'cd /; [ -f "$REPO/.serve.pid" ] && kill "$(cat "$REPO/.serve.pid")" 2>/dev/null; rm -rf "$TMP"' EXIT
fail() { echo "e2e: $*" >&2; exit 1; }

echo "--- install ---"
bash "$KIT/install.sh" "$REPO" --name "Scratch Repo" --port $PORT >/dev/null
for f in lab.json Makefile .gitignore kit/PIN kit/shell/lib.css kit/shell/search.html kit/shell/annotate.js \
         kit/genres/GENRES.md kit/genres/genres.json kit/craft/CRAFT.md kit/skills/present/SKILL.md \
         kit/skills/address/SKILL.md kit/verify.sh kit/tools/kit_hash.py; do
  [ -e "$REPO/$f" ] || fail "install did not create $f"
done
[ -L "$REPO/.claude/skills/present" ] || fail "present skill not symlinked"
[ -L "$REPO/.claude/skills/address" ] || fail "address skill not symlinked"
grep -q "\"ckit\": \"$(ckit version)\"" "$REPO/lab.json" || fail "lab.json did not get the engine pin"
grep -q '^source content-kit ' "$REPO/kit/PIN" || fail "PIN has no content-kit source line"
( cd "$REPO" && git init -q && git add -A && git status --porcelain kit/PIN | grep -q . ) \
  || fail "kit/PIN is not stageable — it must be tracked, not ignored"
rm -rf "$REPO/.git"
echo "install ok"

echo "--- gate on a fresh repo, then on scaffolded pages ---"
( cd "$REPO" && make check >/dev/null ) || fail "make check failed on a fresh repo"
( cd "$REPO" && ckit new note hello --title "Hello" >/dev/null && ckit new concept thing >/dev/null \
  && ckit new book primer >/dev/null && ckit new chapter primer/01-start >/dev/null \
  && ckit new related cluster >/dev/null && ckit new paper draft >/dev/null ) || fail "ckit new failed"
( cd "$REPO" && make check >/dev/null 2>&1 ) && fail "stale indices after scaffolding passed the gate"
( cd "$REPO" && ckit lint >/dev/null && make check >/dev/null ) || fail "make check failed on scaffolded pages after ckit lint"
[ -f "$REPO/content/catalog.json" ] || fail "indices were not generated"
grep -q '"related"' "$REPO/content/catalog.json" || fail "catalog lacks the related genre"
echo "gate ok"

echo "--- the record and its chronicle ---"
mkdir -p "$REPO/record"
printf '# Log — LIVE\n\n### 2026-09-01 — [pivot] direction changed\n\nBecause.\n' > "$REPO/record/log.md"
python3 - "$REPO/lab.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); c = json.loads(p.read_text())
c["record"] = ["record/log.md"]
c["chronicle"] = {"sources": ["record/"]}
p.write_text(json.dumps(c, indent=2) + "\n")
PY
( cd "$REPO" && ckit lint >/dev/null && make check >/dev/null ) || fail "gate red with a record declared"
grep -q '"pivot"' "$REPO/content/chronicle.json" || fail "chronicle.json lacks the pivot"
grep -q 'record/log.md' "$REPO/content/catalog.json" || fail "catalog lacks the record"
printf '### 2026-09-02 — [bogus] x\n' >> "$REPO/record/log.md"
( cd "$REPO" && ckit lint >/dev/null 2>&1 ) && fail "an unknown chronicle tag passed"
sed -i.bak '$ d' "$REPO/record/log.md" && rm -f "$REPO/record/log.md.bak"
( cd "$REPO" && ckit lint >/dev/null )
echo "chronicle ok"

echo "--- kit drift is detected, and re-sync repairs it ---"
echo "# tampered" >> "$REPO/kit/shell/COMPONENTS.md"
( cd "$REPO" && make kit-verify >/dev/null 2>&1 ) && fail "tampering with kit/ was NOT detected"
( cd "$REPO" && make kit-sync >/dev/null && make kit-verify >/dev/null ) || fail "re-sync did not repair"
echo "drift ok"

echo "--- the engine pin bites ---"
python3 - "$REPO/lab.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); c = json.loads(p.read_text()); c["ckit"] = "0.0.0"; p.write_text(json.dumps(c, indent=2) + "\n")
PY
( cd "$REPO" && ckit check >/dev/null 2>&1 ) && fail "a mismatched pin passed the gate"
python3 - "$REPO/lab.json" "$(ckit version)" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); c = json.loads(p.read_text()); c["ckit"] = sys.argv[2]; p.write_text(json.dumps(c, indent=2) + "\n")
PY
echo "pin ok"

echo "--- serve, and the annotation round-trip ---"
( cd "$REPO" && make docs >/dev/null )
sleep 0.7
B="http://127.0.0.1:$PORT"
curl -fsS "$B/" | grep -q "Scratch Repo" || fail "landing page did not render"
curl -fsS "$B/shell/lib.css" >/dev/null || fail "/shell/ mount not served"
curl -fsS "$B/shell/search.html" | grep -q "search-index" || fail "search page not served from the shell"
curl -fsS "$B/shell/record.html?p=record/log.md" | grep -q "marked.umd.js" || fail "record viewer not served"
curl -fsS "$B/shell/vendor/marked/marked.umd.js" >/dev/null || fail "marked not served"
curl -fsS "$B/shell/chronicle.html" >/dev/null || fail "chronicle page not served"
curl -fsS "$B/content/chronicle.json" | grep -q "direction changed" || fail "chronicle.json not served"
curl -fsS "$B/" | grep -q "Chronicle" || fail "landing lacks the chronicle link"
curl -fsS "$B/content/notes/hello.html" | grep -q "Status: LIVE" || fail "scaffolded page lacks its status line"

echo "--- a home written to lab.json on disk reaches the handler through load_repo ---"
python3 - "$REPO/lab.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); c = json.loads(p.read_text())
c["home"] = "content/concepts/thing"
c["dashboard"] = True
p.write_text(json.dumps(c, indent=2) + "\n")
PY
( cd "$REPO" && ckit down >/dev/null && ckit up >/dev/null )
sleep 0.5
curl -sI "$B/" | grep -q '302' || fail "a content-page home on disk did not redirect through load_repo"
curl -sI "$B/" | grep -q '^Location: /content/concepts/thing/' || fail "content-page home redirected to the wrong canonical URL"
python3 - "$REPO/lab.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); c = json.loads(p.read_text())
del c["home"]; del c["dashboard"]  # later steps' `make check` needs the pre-existing (ladder-off) state back
p.write_text(json.dumps(c, indent=2) + "\n")
PY
( cd "$REPO" && ckit down >/dev/null && ckit up >/dev/null )
sleep 0.5
echo "home ok"

curl -fsS "$B/__annotations/ping" | grep -q '"ok": true' || fail "annotation ping failed"
curl -fsS -X POST -H 'Content-Type: application/json' "$B/__annotations" \
  -d '{"op":"add","page":"/content/notes/hello.html","author":"e2e","body":"tighten this","target":{"type":"TextQuoteSelector","exact":"Atomic-thought unit"}}' \
  | grep -q '"ok": true' || fail "annotation add via HTTP failed"
[ -f "$REPO/content/notes/hello.annotations.json" ] || fail "sidecar not written"
curl -fsS "$B/content/notes/hello.annotations.json" | grep -q "tighten this" || fail "sidecar not readable as a static file"
CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' "$B/__annotations" \
  -d '{"op":"add","page":"/content/notes/hello.html","author":"e2e","body":"x","target":{"type":"TextQuoteSelector","exact":"text that is nowhere"}}')"
[ "$CODE" = "400" ] || fail "a quote not on the page was accepted (HTTP $CODE)"
( cd "$REPO" && ckit annotations list | grep -q "tighten this" ) || fail "CLI list does not show the thread"
ID="$(cd "$REPO" && ckit annotations list --json | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')"
( cd "$REPO" && ckit annotations reply /content/notes/hello.html "$ID" --author "agent:e2e" --body "done" --state addressed >/dev/null ) \
  || fail "CLI reply failed"
( cd "$REPO" && ckit annotations list | grep -q "no open threads" ) || fail "addressed thread still listed as open"
( cd "$REPO" && make check >/dev/null ) || fail "gate red after addressing"
# an OPEN thread whose passage is rewritten must turn the gate red
( cd "$REPO" && ckit annotations add /content/notes/hello.html --author e2e --body "again" --quote "Atomic-thought unit" >/dev/null )
( cd "$REPO" && ckit lint >/dev/null )
sed -i.bak 's/Atomic-thought unit/Rewritten/' "$REPO/content/notes/hello.html" && rm -f "$REPO/content/notes/hello.html.bak"
( cd "$REPO" && make check >/dev/null 2>&1 ) && fail "an open thread with a stale anchor passed the gate"
( cd "$REPO" && make down >/dev/null )
echo "annotate ok"

echo "e2e ok"

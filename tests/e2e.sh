#!/usr/bin/env bash
# End-to-end: init a scratch repo, run its gate, scaffold pages, serve, annotate through the HTTP
# endpoint, act on the thread through the CLI, extend it through kit.json (a check module, a
# generator, a shell page, a theme), export it as a static site — at the root and under a base
# path — and prove the gate catches drift, a bad engine pin, and an open thread whose passage was
# rewritten. This is the check unit tests cannot give: the kit runs from a directory it was copied
# into, with the engine found on PATH.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$KIT/bin:$PATH"
TMP="$(mktemp -d)"
REPO="$TMP/repo"
PORT=5398
SPORT=5397
trap 'cd /; [ -f "$REPO/.serve.pid" ] && kill "$(cat "$REPO/.serve.pid")" 2>/dev/null; [ -n "${HTTPD:-}" ] && kill "$HTTPD" 2>/dev/null; rm -rf "$TMP"' EXIT
fail() { echo "e2e: $*" >&2; exit 1; }
edit() { sed -i.bak "$1" "$2" && rm -f "$2.bak"; }   # in place, on GNU and BSD sed alike
serves() {  # serves <url> <grep args…>: the body is read whole first — `curl | grep -q` races
  local body   # (grep exits at its first match, curl meets a closed pipe, and pipefail fails the line)
  body="$(curl -fsS "$1")" || return 1
  shift
  grep -q "$@" <<<"$body"
}
fill() {  # point every skeleton placeholder link at a real page, as an author would
  grep -rl 'OTHER' "$REPO/content" --include='*.html' | while read -r f; do
    edit 's#href="/content/[^"]*OTHER[^"]*"#href="/content/concepts/thing/"#g' "$f"
  done
}
json_set() {  # json_set <file> <python expression over c>
  python3 - "$1" "$2" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); c = json.loads(p.read_text()); exec(sys.argv[2]); p.write_text(json.dumps(c, indent=2) + "\n")
PY
}

echo "--- init ---"
ckit init "$REPO" --name "Scratch Repo" --port $PORT >/dev/null
for f in kit.json Makefile .gitignore kit/PIN kit/shell/lib.css kit/shell/search.html kit/shell/annotate.js \
         kit/genres/GENRES.md kit/genres/genres.json kit/craft/CRAFT.md kit/skills/present/SKILL.md \
         kit/skills/address/SKILL.md kit/skills/curate/SKILL.md kit/verify.sh kit/tools/kit_hash.py; do
  [ -e "$REPO/$f" ] || fail "init did not create $f"
done
[ -L "$REPO/.claude/skills/present" ] || fail "present skill not symlinked"
[ -L "$REPO/.claude/skills/address" ] || fail "address skill not symlinked"
[ -L "$REPO/.claude/skills/curate" ] || fail "curate skill not symlinked"
grep -q "\"ckit\": \"$(ckit version)\"" "$REPO/kit.json" || fail "kit.json did not get the engine pin"
grep -q '^source content-kit ' "$REPO/kit/PIN" || fail "PIN has no content-kit source line"
[ "$(awk '/^source content-kit/ {print NF}' "$REPO/kit/PIN")" = 4 ] || fail "the PIN source line must keep four fields (CI reads the fourth)"
if git -C "$KIT" remote get-url origin >/dev/null 2>&1; then
  grep -q '^source content-kit https://' "$REPO/kit/PIN" || fail "a checkout with a remote must pin its URL, not a path"
fi
( cd "$REPO" && git init -q && git add -A && git status --porcelain kit/PIN | grep -q . ) \
  || fail "kit/PIN is not stageable — it must be tracked, not ignored"
rm -rf "$REPO/.git"
# install.sh is a one-line wrapper around `ckit init` for one minor version
bash "$KIT/install.sh" "$REPO" >/dev/null || fail "install.sh (the ckit init wrapper) failed on an initialised repo"
[ "$(ckit where)" = "$KIT" ] || fail "ckit where must name the checkout the engine runs from"
echo "init ok"

echo "--- gate on a fresh repo, then on scaffolded pages ---"
( cd "$REPO" && make check >/dev/null ) || fail "make check failed on a fresh repo"
( cd "$REPO" && ckit new note hello --title "Hello" >/dev/null && ckit new concept thing >/dev/null \
  && ckit new book primer >/dev/null && ckit new chapter primer/01-start >/dev/null \
  && ckit new related cluster >/dev/null && ckit new paper draft >/dev/null ) || fail "ckit new failed"
( cd "$REPO" && make check >/dev/null 2>&1 ) && fail "stale indices after scaffolding passed the gate"
OUT="$(cd "$REPO" && ckit lint 2>&1 || true)"
echo "$OUT" | grep -q "skeleton's placeholder" || fail "the lint must name a fresh scaffold's placeholder links"
fill
( cd "$REPO" && ckit lint >/dev/null && make check >/dev/null ) || fail "make check failed on scaffolded pages after ckit lint"
[ -f "$REPO/content/catalog.json" ] || fail "indices were not generated"
grep -q '"related"' "$REPO/content/catalog.json" || fail "catalog lacks the related genre"
grep -q '"groups"' "$REPO/content/catalog.json" || fail "catalog lacks its groups"
echo "gate ok"

echo "--- the record and its chronicle ---"
mkdir -p "$REPO/record"
printf '# Log — LIVE\n\n### 2026-09-01 — [pivot] direction changed\n\nBecause.\n' > "$REPO/record/log.md"
json_set "$REPO/kit.json" 'c["record"] = ["record/log.md"]; c["chronicle"] = {"sources": ["record/"]}'
( cd "$REPO" && ckit lint >/dev/null && make check >/dev/null ) || fail "gate red with a record declared"
grep -q '"pivot"' "$REPO/content/chronicle.json" || fail "chronicle.json lacks the pivot"
grep -q '"kinds"' "$REPO/content/chronicle.json" || fail "chronicle.json lacks its kinds"
grep -q 'record/log.md' "$REPO/content/catalog.json" || fail "catalog lacks the record"
printf '### 2026-09-02 — [bogus] x\n' >> "$REPO/record/log.md"
( cd "$REPO" && ckit lint >/dev/null 2>&1 ) && fail "an unknown chronicle tag passed"
edit '$ d' "$REPO/record/log.md"
( cd "$REPO" && ckit lint >/dev/null )
echo "chronicle ok"

echo "--- extension points: a check module, a generator, a shell page, a theme, a link ---"
mkdir -p "$REPO/ext"
cat > "$REPO/ext/checks_x.py" <<'PY'
def no_todo(ctx):
    return [f"{ctx.rel}: leaves a TODO in the served page"] if "TODO" in ctx.served else []
CHECKS = {"no_todo": no_todo}
PY
cat > "$REPO/ext/gen_x.py" <<'PY'
def generate(repo):
    return {"content/x-count.json": {"notes": len(list((repo.content / "notes").glob("*.html")))}}
PY
printf '<!DOCTYPE html><html><head><link rel="stylesheet" href="/shell/lib.css"><title>X board</title></head><body class="hb"><main><h1>X board</h1></main></body></html>\n' > "$REPO/ext/board.html"
printf '.hb { --glacier: var(--teal); }\n.hb .sw-glacier { color: var(--glacier); }\n' > "$REPO/ext/theme.css"
json_set "$REPO/kit.json" '
c["checks"] = ["ext/checks_x.py"]; c["generators"] = ["ext/gen_x.py"]
c["shell_pages"] = {"board.html": "ext/board.html"}; c["theme"] = "ext/theme.css"; c["classes"] = ["sw-glacier"]
c["links"] = [{"label": "Board", "href": "/shell/board.html"}]
c["genres"] = {"note": {"checks": {"no_todo": True}}}'
( cd "$REPO" && ckit lint >/dev/null && make check >/dev/null ) || fail "gate red with every extension point declared"
[ -f "$REPO/content/x-count.json" ] || fail "the generator's file was not written"
printf '<!DOCTYPE html><html><head><title>Glacier</title><link rel="stylesheet" href="/shell/lib.css"></head><body class="hb"><main><h1>Glacier</h1><p class="sub"><b>Status: LIVE</b> — x.</p><p><span class="sw-glacier" style="color: var(--glacier)">ice</span></p></main></body></html>\n' > "$REPO/content/notes/glacier.html"
( cd "$REPO" && ckit lint >/dev/null ) || fail "a page in the theme's vocabulary did not lint clean"
printf '<!DOCTYPE html><html><head><title>Todo</title><link rel="stylesheet" href="/shell/lib.css"></head><body class="hb"><main><h1>Todo</h1><p class="sub"><b>Status: LIVE</b> — x.</p><p>TODO later</p></main></body></html>\n' > "$REPO/content/notes/todo.html"
OUT="$(cd "$REPO" && ckit lint 2>&1 || true)"
echo "$OUT" | grep -q "notes/todo.html: leaves a TODO" || fail "the check module did not fire on a planted page"
rm "$REPO/content/notes/todo.html"
echo '{"notes": 999}' > "$REPO/content/x-count.json"
( cd "$REPO" && make check >/dev/null 2>&1 ) && fail "a stale generated file passed the gate"
( cd "$REPO" && ckit lint >/dev/null && make check >/dev/null ) || fail "gate red after regenerating"
echo "extension points ok"

echo "--- kit drift is detected, and re-sync repairs it ---"
echo "# tampered" >> "$REPO/kit/shell/COMPONENTS.md"
( cd "$REPO" && make kit-verify >/dev/null 2>&1 ) && fail "tampering with kit/ was NOT detected"
( cd "$REPO" && make kit-sync >/dev/null && make kit-verify >/dev/null ) || fail "re-sync did not repair"
echo "drift ok"

echo "--- the engine pin bites ---"
json_set "$REPO/kit.json" 'c["ckit"] = "0.0.0"'
( cd "$REPO" && ckit check >/dev/null 2>&1 ) && fail "a mismatched pin passed the gate"
json_set "$REPO/kit.json" "c['ckit'] = '$(ckit version)'"
echo "pin ok"

echo "--- serve, and the annotation round-trip ---"
( cd "$REPO" && make docs >/dev/null )
sleep 0.7
B="http://127.0.0.1:$PORT"
serves "$B/" "Scratch Repo" || fail "landing page did not render"
serves "$B/" ">Board &rarr;<" || fail "landing lacks the declared link"
serves "$B/shell/lib.css" '@import url("theme.css")' || fail "/shell/lib.css does not import the theme"
serves "$B/shell/theme.css" -- "--glacier" || fail "/shell/theme.css does not serve the declared theme"
serves "$B/shell/board.html" "X board" || fail "the declared shell page is not served"
serves "$B/shell/search.html" "search-index" || fail "search page not served from the shell"
serves "$B/shell/record.html?p=record/log.md" "marked.umd.js" || fail "record viewer not served"
curl -fsS "$B/shell/vendor/marked/marked.umd.js" >/dev/null || fail "marked not served"
curl -fsS "$B/shell/chronicle.html" >/dev/null || fail "chronicle page not served"
serves "$B/content/chronicle.json" "direction changed" || fail "chronicle.json not served"
serves "$B/" "Chronicle" || fail "landing lacks the chronicle link"
serves "$B/content/notes/hello.html" "Status: LIVE" || fail "scaffolded page lacks its status line"

echo "--- a home written to kit.json on disk reaches the handler through load_repo ---"
json_set "$REPO/kit.json" 'c["home"] = "content/concepts/thing"'
( cd "$REPO" && ckit down >/dev/null && ckit up >/dev/null )
sleep 0.5
curl -sI "$B/" | grep -q '302' || fail "a content-page home on disk did not redirect through load_repo"
curl -sI "$B/" | grep -q '^Location: /content/concepts/thing/' || fail "content-page home redirected to the wrong canonical URL"
json_set "$REPO/kit.json" 'c["home"] = "board"'
( cd "$REPO" && ckit down >/dev/null && ckit up >/dev/null )
sleep 0.5
serves "$B/" "X board" || fail "a home naming a shell page did not serve it at /"
json_set "$REPO/kit.json" 'del c["home"]'
( cd "$REPO" && ckit down >/dev/null && ckit up >/dev/null )
sleep 0.5
echo "home ok"

serves "$B/__annotations/ping" '"ok": true' || fail "annotation ping failed"
curl -fsS -X POST -H 'Content-Type: application/json' "$B/__annotations" \
  -d '{"op":"add","page":"/content/notes/hello.html","author":"e2e","body":"tighten this","target":{"type":"TextQuoteSelector","exact":"Atomic-thought unit"}}' \
  | grep -q '"ok": true' || fail "annotation add via HTTP failed"
[ -f "$REPO/content/notes/hello.annotations.json" ] || fail "sidecar not written"
serves "$B/content/notes/hello.annotations.json" "tighten this" || fail "sidecar not readable as a static file"
CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' "$B/__annotations" \
  -d '{"op":"add","page":"/content/notes/hello.html","author":"e2e","body":"x","target":{"type":"TextQuoteSelector","exact":"text that is nowhere"}}')"
[ "$CODE" = "400" ] || fail "a quote not on the page was accepted (HTTP $CODE)"
( cd "$REPO" && ckit annotations list | grep -q "tighten this" ) || fail "CLI list does not show the thread"
ID="$(cd "$REPO" && ckit annotations list --json | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')"
( cd "$REPO" && ckit annotations reply /content/notes/hello.html "$ID" --author "agent:e2e" --body "done" --state addressed >/dev/null ) \
  || fail "CLI reply failed"
( cd "$REPO" && ckit annotations list | grep -q "no open threads" ) || fail "addressed thread still listed as open"
( cd "$REPO" && make check >/dev/null ) || fail "gate red after addressing"
( cd "$REPO" && make down >/dev/null )
echo "annotate ok"

echo "--- export: a static site that serves under python3 -m http.server, at the root and under a base ---"
( cd "$REPO" && ckit export --out "$TMP/site" >/dev/null ) || fail "ckit export failed"
for f in index.html 404.html .nojekyll shell/lib.css shell/lib.js shell/theme.css shell/board.html shell/search.html \
         content/catalog.json content/notes/hello.html record/log.md; do
  [ -e "$TMP/site/$f" ] || fail "export lacks $f"
done
[ -e "$TMP/site/content/notes/hello.annotations.json" ] && fail "export must leave annotation sidecars at home"
cmp -s "$REPO/content/notes/hello.html" "$TMP/site/content/notes/hello.html" || fail "export at base / must not rewrite a page"
python3 -m http.server "$SPORT" -d "$TMP/site" -b 127.0.0.1 >/dev/null 2>&1 & HTTPD=$!
sleep 0.7
S="http://127.0.0.1:$SPORT"
serves "$S/" "Scratch Repo" || fail "exported landing did not serve"
serves "$S/shell/theme.css" -- "--glacier" || fail "exported theme did not serve"
serves "$S/content/concepts/thing/" 'href="/shell/lib.css"' || fail "exported page did not serve"
serves "$S/content/catalog.json" '"groups"' || fail "exported catalog did not serve"
kill "$HTTPD"; HTTPD=""
mkdir -p "$TMP/pages"
( cd "$REPO" && ckit export --out "$TMP/pages/proj" --base /proj/ >/dev/null ) || fail "ckit export --base failed"
grep -q 'href="/proj/shell/lib.css"' "$TMP/pages/proj/content/notes/hello.html" || fail "--base did not prefix the page's shell link"
grep -q 'href="/proj/shell/search.html"' "$TMP/pages/proj/404.html" || fail "the 404 page must link search under the base"
grep -q 'href="/shell/' "$TMP/pages/proj/content/notes/hello.html" && fail "--base left a root-absolute shell link"
grep -q '"href": "/content/' "$TMP/pages/proj/content/catalog.json" || fail "--base must leave the JSON indices alone"
python3 -m http.server "$SPORT" -d "$TMP/pages" -b 127.0.0.1 >/dev/null 2>&1 & HTTPD=$!
sleep 0.7
serves "$S/proj/" 'href="/proj/shell/lib.css"' || fail "the based landing did not serve under /proj/"
curl -fsS "$S/proj/shell/lib.css" >/dev/null || fail "the based shell did not serve under /proj/"
serves "$S/proj/content/notes/hello.html" "Status: LIVE" || fail "a based page did not serve under /proj/"
kill "$HTTPD"; HTTPD=""
echo "export ok"

echo "--- organise: a topic and its hub, tags, prose joined, a move that keeps every link ---"
( cd "$REPO" && ckit topics add kitchen --label "Kitchen" >/dev/null && ckit new hub kitchen --title "Kitchen" >/dev/null \
  && ckit new note pepper --title "Pepper" --topic kitchen --tags salt,heat >/dev/null ) || fail "topics add / new --topic failed"
grep -q '<meta name="topic" content="kitchen">' "$REPO/content/hubs/kitchen.html" || fail "a hub named for a declared topic must take it"
grep -q '<meta name="tags" content="salt, heat">' "$REPO/content/notes/pepper.html" || fail "new --tags did not set the tags"
fill
edit 's#</main>#<p><a href="/content/notes/pepper.html">pepper</a></p></main>#' "$REPO/content/hubs/kitchen.html"
python3 -c 'import sys, pathlib; p = pathlib.Path(sys.argv[1]); p.write_text(p.read_text().replace("</main>", "<p>hard\nwrapped</p>\n</main>"))' \
  "$REPO/content/notes/pepper.html"
OUT="$(cd "$REPO" && ckit lint 2>&1 || true)"
echo "$OUT" | grep -q "ckit unwrap" || fail "hard-wrapped prose must be reported with its fix"
( cd "$REPO" && ckit unwrap >/dev/null && ckit lint >/dev/null ) || fail "ckit unwrap did not leave the lint clean"
( cd "$REPO" && ckit topics | grep -q "^kitchen  Kitchen · content/hubs/kitchen.html" ) || fail "ckit topics must list the topic with its hub"
( cd "$REPO" && ckit tags | grep -q "salt" ) || fail "ckit tags must list the tags"
( cd "$REPO" && ckit mv content/notes/pepper.html content/entries/pepper/ >/dev/null ) || fail "ckit mv failed"
[ -f "$REPO/content/entries/pepper/index.html" ] || fail "ckit mv did not move the page"
grep -q 'href="/content/entries/pepper/"' "$REPO/content/hubs/kitchen.html" || fail "ckit mv did not rewrite the hub's link"
grep -q '"/content/notes/pepper.html": "/content/entries/pepper/"' "$REPO/kit.json" || fail "ckit mv did not record the redirect"
( cd "$REPO" && make check >/dev/null ) || fail "gate red after a move"
( cd "$REPO" && make docs >/dev/null )
sleep 0.7
curl -sI "$B/content/notes/pepper.html" | grep -q '^Location: /content/entries/pepper/' || fail "the old address must redirect"
( cd "$REPO" && make down >/dev/null )
echo "organise ok"

echo "--- an open thread whose passage is rewritten turns the gate red ---"
( cd "$REPO" && ckit annotations add /content/notes/hello.html --author e2e --body "again" --quote "Atomic-thought unit" >/dev/null )
( cd "$REPO" && ckit lint >/dev/null )
edit 's/Atomic-thought unit/Rewritten/' "$REPO/content/notes/hello.html"
( cd "$REPO" && make check >/dev/null 2>&1 ) && fail "an open thread with a stale anchor passed the gate"
echo "stale anchor ok"

echo "e2e ok"

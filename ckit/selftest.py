"""The engine's own gate: planted fixtures with known answers.

Builds a scratch repo, scaffolds one clean page per core genre through `ckit new` (so the
skeletons are proven lint-clean), runs the full gate on it, then plants one violation per
check and asserts each is reported by name. A check that cannot be made to fire on a fixture
designed to break it is not a check. Also round-trips an annotation: add → anchored → reply →
tamper the page → the anchor is reported stale.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from contextlib import redirect_stdout
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import re

from . import __version__, annotations as ann, book_nav, check, config, genres, lint, new, serve
from .paths import KIT_SRC, PACKAGE_DIR, Repo, load_repo

CLEAN = {
    "note": "a-note",
    "concept": "a-concept",
    "entry": "an-entry",
    "hub": "a-hub",
    "project": "a-project",
    "paper": "a-paper",
    "related": "a-related",
    "book": "a-book",
    "chapter": "a-book/01-first",
}

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="/shell/lib.css"><script src="/shell/lib.js" defer></script>{head}</head>
<body class="hb"><main><h1>{title}</h1><p class="sub">{sub}</p>{body}</main></body></html>
"""


def _page(title: str, body: str = "<p>Body.</p>", *, sub: str = "<b>Status: LIVE</b> — fixture.",
          head: str = "") -> str:
    return PAGE.format(title=title, sub=sub, body=body, head=head)


SHAPE = ("steps", "why", "pitfalls")  # a fixed-shape extension genre's sections, in order
SHAPED = {"howto": {"dir": "howtos", "layout": "folder",
                    "checks": {"status": True, "require_sections": list(SHAPE)}}}


def _shaped(title: str, *, sections: tuple[str, ...] = SHAPE) -> str:
    """A page of a fixed-shape genre: the declared sections, in the declared order."""
    return _page(title, "".join(f'<h2 id="{s}">{s}</h2><p>x</p>' for s in sections))


def _write(repo: Repo, rel: str, text: str) -> Path:
    p = repo.content / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _scratch() -> tuple[Path, Repo]:
    tmp = Path(tempfile.mkdtemp(prefix="ckit-selftest-"))
    root = tmp / "repo"
    (root / "kit").mkdir(parents=True)
    os.symlink(KIT_SRC / "shell", root / "kit" / "shell")
    (root / "kit.json").write_text(json.dumps({
        "name": "Scratch", "content": "content", "host": "127.0.0.1", "port": 5399,
        "ckit": __version__,
    }, indent=2) + "\n")
    (root / "content").mkdir()
    return tmp, load_repo(root)


def _lint(repo: Repo) -> list[str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        probs, _ = lint.run(repo, nav=True)
    return probs


def _request(port: int, path: str) -> tuple[int, str | None, bytes]:
    """One GET against a live selftest server — status, Location (if any), and the body."""
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, resp.getheader("Location"), resp.read()
    finally:
        conn.close()


def _get(port: int, path: str, headers: dict | None = None) -> tuple[int, dict, bytes]:
    """One GET with request headers — status, the response headers (lower-cased), and the body."""
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


# What every page loads before its own content: the shell's stylesheet and script, gzipped, and the
# two reading faces. A budget nothing checks gets spent; this one is checked on the kit's own shell.
SHELL_BUDGET = 32 * 1024
FONT_BUDGET = 200 * 1024


def shell_weight_problems(shell: Path) -> list[str]:
    import gzip
    out: list[str] = []
    weight = sum(len(gzip.compress((shell / f).read_bytes(), 9)) for f in ("lib.css", "lib.js") if (shell / f).is_file())
    if weight > SHELL_BUDGET:
        out.append(f"the shell (lib.css + lib.js) is {weight} bytes gzipped, over its {SHELL_BUDGET}-byte budget")
    fonts = sum(p.stat().st_size for p in (shell / "vendor" / "fonts").glob("*.woff2"))
    if fonts > FONT_BUDGET:
        out.append(f"the shell's fonts are {fonts} bytes, over their {FONT_BUDGET}-byte budget")
    return out


def _expect(probs: list[str], rel: str, needle: str, failures: list[str]) -> None:
    if not any(rel in p and needle in p for p in probs):
        failures.append(f"planted {rel!r} — expected a problem containing {needle!r}; got: "
                        + (" | ".join(p for p in probs if rel in p) or "(nothing)"))


def main(argv: list[str]) -> int:
    tmp, repo = _scratch()
    failures: list[str] = []
    planted = 0
    try:
        # --- clean: every skeleton scaffolds through `ckit new` and passes the whole gate
        for genre, slug in CLEAN.items():
            new.create(repo, genre, slug, title=f"Fixture {genre}")
        probs = _lint(repo)
        if probs:
            failures.append("clean skeletons should lint clean:\n  " + "\n  ".join(probs))
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = check.run(repo)
        if rc != 0:
            failures.append(f"`ckit check` on a clean repo returned {rc}:\n{buf.getvalue()}")

        # --- the config file: kit.json, with lab.json read as a deprecated alias that says so
        #     exactly once per run however often a legacy repo is loaded
        legacy = tmp / "legacy"
        legacy.mkdir()
        (legacy / "lab.json").write_text(json.dumps({"name": "Legacy", "ckit": __version__}))
        from . import paths as paths_mod
        paths_mod._warned_legacy = False
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            old_a, old_b = load_repo(legacy), load_repo(legacy)
        warned = [ln for ln in err.getvalue().splitlines() if "deprecated" in ln]
        if old_a.cfg.get("name") != "Legacy" or old_b.marker.name != "lab.json":
            failures.append("a repo carrying only lab.json must still load")
        if len(warned) != 1:
            failures.append(f"lab.json must print exactly one deprecation line per run, got {len(warned)}")
        if repo.marker is None or repo.marker.name != "kit.json" or repo.cfg.get("name") != "Scratch":
            failures.append("a repo with kit.json must load from kit.json")
        both = tmp / "both"
        both.mkdir()
        (both / "kit.json").write_text(json.dumps({"name": "New"}))
        (both / "lab.json").write_text(json.dumps({"name": "Old"}))
        if load_repo(both).cfg.get("name") != "New":
            failures.append("kit.json must win over lab.json when both exist")
        planted += 3

        # --- the genre set and the catalog are one registry: the groups are derived from the
        #     genre table, so a genre dir cannot lint and search fine yet never reach the sidebar
        cat = json.loads((repo.content / "catalog.json").read_text())
        dirs = {g["dir"] for g in genres.core_spec().values()}
        keys = [g["key"] for g in cat.get("groups") or []]
        if set(keys) != dirs or len(keys) != len(dirs):
            failures.append(f"catalog groups must be exactly the genre dirs: {keys} vs {sorted(dirs)}")
        if not all(isinstance(cat.get(k), list) for k in keys):
            failures.append("every catalog group must carry its item list")
        planted += 1
        # --- a stale committed index fails the gate; regenerating repairs it
        catalog = repo.content / "catalog.json"
        good = catalog.read_text(encoding="utf-8")
        catalog.write_text(good.replace("a-note", "a-note-renamed"), encoding="utf-8")
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = check.run(repo)
        if rc == 0 or "out of date" not in err.getvalue():
            failures.append("a stale catalog.json must fail `ckit check`")
        planted += 1
        _lint(repo)  # regenerates
        if catalog.read_text(encoding="utf-8") != good:
            failures.append("regeneration did not restore the catalog")

        # --- the chronicle: dated headings + a plugin → content/chronicle.json, checked current
        (repo.root / "record").mkdir()
        (repo.root / "record" / "lab.md").write_text(
            "# Lab logbook — LIVE\n\n### 2026-09-01 — [pivot] the substrate changes\n\nWhy it changed, in one paragraph.\n\n"
            "### 2026-09-02T10:00Z — an untagged entry\n\nPlain.\n\n### 2026-09-03 — [lesson] what bit us\n", encoding="utf-8")
        (repo.root / "ext.py").write_text(
            "KINDS = [{'name': 'release', 'hue': 'teal'}, 'errata']\n"
            "CARDS = {'view': 'releases', 'label': 'Releases', 'kind': 'release', 'empty': 'no releases'}\n"
            "def extract(root, cfg):\n"
            "    return {'events': [{'date': '2026-09-04', 'kind': 'release', 'title': 'R1 shipped', 'href': '/shell/record.html?p=r1.md'}],\n"
            "            'cards': [{'title': 'R1', 'href': '/shell/record.html?p=r1.md', 'date': '2026-09-04', 'status': 'SHIPPED',\n"
            "                       'fields': [{'label': 'Notes', 'text': 'the first'}, {'label': 'Fixes', 'items': [], 'empty': 'none'}]},\n"
            "                      {'title': 'R0', 'href': '/shell/record.html?p=r0.md', 'date': '2026-09-09', 'fields': []}]}\n",
            encoding="utf-8")
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg["record"] = ["record/lab.md"]
        cfg["chronicle"] = {"sources": ["record/"], "extractors": ["ext.py"]}
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo = load_repo(repo.root)
        _lint(repo)
        chron = json.loads((repo.content / "chronicle.json").read_text())
        kinds = [e["kind"] for e in chron["events"]]
        if kinds != ["release", "lesson", "entry", "pivot"]:
            failures.append(f"chronicle events wrong or unsorted: {kinds}")
        legend = [k["name"] for k in chron.get("kinds") or []]
        if legend != ["pivot", "kill", "decision", "lesson", "instrument", "result", "release", "errata", "entry"]:
            failures.append(f"chronicle.json must list the core kinds, then the extractor's, then entry: {legend}")
        rel_kind = next((k for k in chron.get("kinds") or [] if k["name"] == "release"), {})
        if rel_kind.get("hue") != "teal" or rel_kind.get("story") is not True:
            failures.append(f"an extractor kind keeps its declared hue and joins the Story view: {rel_kind}")
        cards = chron.get("cards") or {}
        if cards.get("view") != "releases" or [c["title"] for c in cards.get("items") or []] != ["R1", "R0"]:
            failures.append(f"the extractor's cards must reach chronicle.json under its view, in its order: {cards}")
        planted += 2
        if not any(e["summary"].startswith("Why it changed") for e in chron["events"]):
            failures.append("event summary not taken from the paragraph under the heading")
        cat = json.loads((repo.content / "catalog.json").read_text())
        if not cat.get("record") or cat["record"][0]["href"] != "/shell/record.html?p=record/lab.md":
            failures.append(f"record not in the catalog: {cat.get('record')}")
        planted += 1

        # split: `record` lists files (sidebar); `chronicle.sources` sweeps dirs (scanner)
        (repo.root / "record" / "log.md").write_text(
            "# Log — LIVE\n\n### 2026-09-05 — [decision] the split lands\n\nBecause.\n", encoding="utf-8")
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg["record"] = ["record/lab.md", "record/log.md", "record/"]  # a dir here is scanner-only, not sidebar
        cfg["chronicle"] = {"sources": ["record/"], "extractors": ["ext.py"]}
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo2 = load_repo(repo.root)
        _lint(repo2)
        cat2 = json.loads((repo2.content / "catalog.json").read_text())
        paths = [r["path"] for r in cat2.get("record") or []]
        if paths != ["record/lab.md", "record/log.md"]:
            failures.append(f"sidebar must list only file entries in record: {paths}")
        chron2 = json.loads((repo2.content / "chronicle.json").read_text())
        dec = next((e for e in chron2["events"] if e["kind"] == "decision"), None)
        if not dec or dec.get("source") != "record/log.md":
            failures.append(f"chronicle.sources did not sweep record/log.md: {dec}")
        planted += 1
        (repo.root / "record" / "bad.md").write_text("### 2026-09-05 — [bogus] tag\n", encoding="utf-8")
        try:
            _lint(repo)
            failures.append("an unknown chronicle tag must fail loud")
        except SystemExit:
            pass
        (repo.root / "record" / "bad.md").unlink()
        planted += 1
        # a kind no extractor declares is refused too, naming the kind
        good_ext = (repo.root / "ext.py").read_text(encoding="utf-8")
        (repo.root / "ext.py").write_text(good_ext.replace("'kind': 'release'", "'kind': 'bogus-kind'"), encoding="utf-8")
        try:
            _lint(load_repo(repo.root))
            failures.append("an extractor event of an undeclared kind must fail loud")
        except SystemExit as exc:
            if "bogus-kind" not in str(exc):
                failures.append(f"the undeclared-kind error must name the kind, got: {exc}")
        (repo.root / "ext.py").write_text(good_ext, encoding="utf-8")
        planted += 1
        _lint(repo)

        # --- `home` as a content page: `/` 302s to its canonical URL; a dangling one fails
        #     `ckit check` and 404s at serve time — exercised through a live instance of the handler
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(repo))
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        port = httpd.server_address[1]
        try:
            status, _, landing = _request(port, "/")
            if status != 200 or b"Search everything" not in landing:
                failures.append(f"with no home, / should serve the generated landing page, got {status}")
            planted += 1

            repo.cfg["home"] = "content/projects/a-project"  # a real page from the CLEAN fixtures
            status, location, _ = _request(port, "/")
            if status != 302 or location != "/content/projects/a-project/":
                failures.append(
                    f"a content-page home should 302 / to its canonical URL; got {status} {location!r}")
            planted += 1

            repo.cfg["home"] = "content/projects/does-not-exist"
            status, _, _ = _request(port, "/")
            if status != 404:
                failures.append(f"a dangling home should 404 at serve time, not fall back silently; got {status}")
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = check.run(repo)
            if rc == 0 or "does not resolve to a page" not in err.getvalue():
                failures.append("a dangling home must fail `ckit check` with the new message")
            planted += 1

            # a non-string home (the likely slip for a boolean switch) is dangling, not a crash
            repo.cfg["home"] = True
            status, _, _ = _request(port, "/")
            if status != 404:
                failures.append(f'"home": true should 404 at serve time like any other dangling home, got {status}')
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = check.run(repo)
            if rc == 0 or "does not resolve to a page" not in err.getvalue():
                failures.append('"home": true must fail `ckit check` with the dangling-home message, not raise')
            planted += 1
        finally:
            repo.cfg.pop("home", None)  # leave the fixture consistent for what follows
            httpd.shutdown()
            httpd.server_close()
            server_thread.join(timeout=2)

        # --- annotation round-trip on a clean page
        note = repo.content / "notes" / "a-note.html"
        t = ann.add(repo, "/content/notes/a-note.html", "tighten this",
                    author="tester", target={"exact": "Atomic-thought unit"})
        if not ann.sidecar_for(note).is_file():
            failures.append("annotation add did not write a sidecar")
        if ann.check_all(repo):
            failures.append("fresh annotation should anchor: " + " | ".join(ann.check_all(repo)))
        try:
            ann.add(repo, "/content/notes/a-note.html", "x", author="tester",
                    target={"exact": "text that is not on the page at all"})
            failures.append("adding a quote that is not on the page should be refused")
        except ann.AnnotationError:
            pass
        try:
            ann.reply(repo, "/content/notes/a-note.html", t["id"], "", author="agent",
                      state="declined")
            failures.append("declining without a reason should be refused")
        except ann.AnnotationError:
            pass
        # editing the quoted passage while the thread is OPEN is the failure: loud
        note.write_text(note.read_text(encoding="utf-8").replace("Atomic-thought unit", "Rewritten"))
        _expect(_lint(repo), "a-note.annotations.json", "STALE", failures)
        planted += 1
        # addressing it retires the anchor from the gate — the passage changed because it was acted on
        ann.reply(repo, "/content/notes/a-note.html", t["id"], "done", author="agent",
                  state="addressed")
        if ann.check_all(repo):
            failures.append("an addressed thread's stale anchor must not fail the gate: "
                            + " | ".join(ann.check_all(repo)))
        if [x for x in ann.list_threads(repo, state="open")]:
            failures.append("thread should not be open after being addressed")
        if not [x for x in ann.list_threads(repo, state="addressed") if x["id"] == t["id"]]:
            failures.append("addressed thread not listed")
        planted += 1
        ann.sidecar_for(note).unlink()

        # --- planted violations, one per check
        cases: list[tuple[str, str, str]] = []

        def plant(rel: str, text: str, needle: str) -> None:
            _write(repo, rel, text)
            cases.append((rel, needle, text))

        plant("notes/hex.html", _page("Hex", '<p style="color:#ff0000">x</p>'), "hex color")
        plant("notes/noshell.html", _page("No shell").replace('<link rel="stylesheet" href="/shell/lib.css">', ""),
              'missing href="/shell/lib.css"')
        plant("notes/badclass.html", _page("Bad class", '<span class="hb-bogus">x</span>'), "unknown shell class")
        plant("notes/badtoken.html", _page("Bad token", '<p style="color: var(--nope)">x</p>'),
              "unknown token var(--nope)")
        # a token the page declares itself, or one used with a fallback, is fine
        _write(repo, "notes/owntoken.html", _page("Own token",
               '<p style="--mine: var(--teal); color: var(--mine); border-color: var(--nope2, currentColor)">x</p>'))
        plant("notes/nostatus.html", _page("No status", sub="Just a lede."), "no status")
        plant("notes/sections.html", _page("Sections", "<h2>One</h2><p>x</p>"), "<h2>")
        plant("notes/long.html", _page("Long", "<p>" + "word " * 450 + "</p>"), "over the 400")
        plant("concepts/nodefn/index.html", _page("No defn"), 'no <blockquote class="defn">')
        plant("stray/x.html", _page("Stray"), "outside any genre")
        plant("projects/nometa/index.html", _page("No meta"), 'needs <meta name="status"')
        plant("projects/badmeta/index.html",
              _page("Bad meta", head='<meta name="status" content="whatever">'), "not active|shipped|paused")
        plant("hubs/long.html", _page("Long hub", "<p>" + "word " * 1600 + "</p>"), "over the 1500")
        # a fixed-shape genre (an extension declaring require_sections): the compliant page is
        # silent, each mutation is reported by the section id it broke
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg["genres"] = SHAPED
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo = load_repo(repo.root)
        _write(repo, "howtos/fine/index.html", _shaped("Fine"))
        plant("howtos/missing/index.html", _shaped("Missing", sections=("steps", "pitfalls")),
              'no <h2 id="why"> section')
        # commented-out markup renders as nothing: without stripping comments first, a page
        # could delete a section, comment it back in where it belonged, and pass
        plant("howtos/commented/index.html",
              _shaped("Commented", sections=("steps", "pitfalls")).replace(
                  '<h2 id="pitfalls">', '<!-- <h2 id="why">why</h2> --><h2 id="pitfalls">'),
              'no <h2 id="why"> section')
        plant("howtos/misordered/index.html", _shaped("Misordered", sections=("steps", "pitfalls", "why")),
              '<h2 id="pitfalls"> is out of order')
        # a chapter that links forward without declaring it, and one that declares it
        _write(repo, "books/fwd/index.html", _page("Fwd book"))
        _write(repo, "books/fwd/02-later.html", _page("Later"))
        _write(repo, "books/fwd/04-last.html", _page("Last"))
        plant("books/fwd/01-early.html", _page("Early", '<a href="02-later.html">next</a>'), "forward reference")
        _write(repo, "books/fwd/03-fine.html", _page("Fine", '<a data-fwd href="04-last.html">later</a>'))
        # annotation sidecars: invalid schema, orphan
        _write(repo, "notes/badann.html", _page("Bad ann"))
        _write(repo, "notes/badann.annotations.json",
               json.dumps({"version": 1, "page": "/content/notes/badann.html",
                           "threads": [{"id": "t-1", "body": "x", "author": "a", "target": None}]}))
        cases.append(("badann.annotations.json", "state must be one of", ""))
        _write(repo, "notes/orphan.annotations.json",
               json.dumps({"version": 1, "page": "/content/notes/orphan.html", "threads": []}))
        cases.append(("orphan.annotations.json", "orphan", ""))

        probs = _lint(repo)
        for rel, needle, _ in cases:
            _expect(probs, rel, needle, failures)
            planted += 1
        if any("owntoken" in p for p in probs):
            failures.append("a token the page declares, or one with a fallback, must not be reported: "
                            + " | ".join(p for p in probs if "owntoken" in p))
        planted += 1
        if any("03-fine.html" in p for p in probs):
            failures.append("a declared (data-fwd) forward reference must not be reported")
        planted += 1
        if any("howtos/fine" in p for p in probs):
            failures.append("a compliant fixed-shape page was reported: "
                            + " | ".join(p for p in probs if "howtos/fine" in p))
        planted += 1

        # --- per-repo genre extension: a new genre dir is recognised and its checks apply
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg["genres"] = {"recipe": {"dir": "recipes", "layout": "flat",
                                    "checks": {"status": True, "max_words": 50}}}
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo2 = load_repo(repo.root)
        _write(repo2, "recipes/ok.html", _page("Recipe"))
        _write(repo2, "recipes/long.html", _page("Long recipe", "<p>" + "word " * 80 + "</p>"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            probs2, _ = lint.run(repo2, nav=False)
        if any("recipes/ok.html" in p for p in probs2):
            failures.append("an extension genre's clean page was reported: "
                            + " | ".join(p for p in probs2 if "recipes/ok.html" in p))
        _expect(probs2, "recipes/long.html", "over the 50", failures)
        planted += 2

        # --- check plugins: a module under kit.json `checks` provides a page check a genre names
        #     and a repo check that always runs; each fires by name on a planted page, a clean
        #     page stays silent, and a genre naming a check nobody provides fails loud
        (repo.root / "plug").mkdir(exist_ok=True)
        (repo.root / "plug" / "checks_fx.py").write_text(
            "def shouts(ctx):\n"
            "    return [f'{ctx.rel}: shouts — {ctx.arg}'] if 'SHOUTING' in ctx.served else []\n"
            "def forbidden(repo):\n"
            "    return [f'{repo.rel(p)}: forbidden page name' for p in repo.content.rglob('forbidden.html')]\n"
            "CHECKS = {'shouts': shouts}\n"
            "REPO_CHECKS = {'forbidden_names': forbidden}\n", encoding="utf-8")
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg.pop("genres", None)
        cfg["checks"] = ["plug/checks_fx.py"]
        cfg["genres"] = {"note": {"checks": {"shouts": "no shouting in a note"}}}
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo3 = load_repo(repo.root)
        _write(repo3, "notes/loud.html", _page("Loud", "<p>SHOUTING here.</p>"))
        _write(repo3, "notes/quiet-shout.html", _page("Quiet", "<!-- SHOUTING -->"))
        _write(repo3, "notes/forbidden.html", _page("Forbidden"))
        with redirect_stdout(io.StringIO()):
            probs3, _ = lint.run(repo3, nav=False)
        _expect(probs3, "notes/loud.html", "shouts — no shouting in a note", failures)
        _expect(probs3, "notes/forbidden.html", "forbidden page name", failures)
        if any("quiet-shout" in p for p in probs3):
            failures.append("a plugin check must see the served text — a commented-out word is not served")
        planted += 3
        cfg["genres"]["note"]["checks"]["no_such_check"] = True
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        try:
            with redirect_stdout(io.StringIO()):
                lint.run(load_repo(repo.root), nav=False)
            failures.append("a genre naming a check nobody provides must fail the gate")
        except SystemExit as exc:
            if "no_such_check" not in str(exc):
                failures.append(f"the unprovided-check error must name the check, got: {exc}")
        planted += 1
        for rel in ("notes/loud.html", "notes/quiet-shout.html", "notes/forbidden.html"):
            (repo3.content / rel).unlink()

        # --- generators: a module under kit.json `generators` adds a file to the indices; lint
        #     writes it, a tampered copy fails `ckit check`, and claiming an engine index is refused
        (repo.root / "plug" / "gen_fx.py").write_text(
            "def generate(repo):\n"
            "    notes = sorted(p.stem for p in (repo.content / 'notes').glob('*.html'))\n"
            "    return {'content/fixture-index.json': {'notes': notes}}\n", encoding="utf-8")
        cfg["genres"] = {}
        cfg["checks"] = []
        cfg["generators"] = ["plug/gen_fx.py"]
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo3 = load_repo(repo.root)
        _lint(repo3)
        gen_out = repo3.content / "fixture-index.json"
        if not gen_out.is_file() or "a-note" not in gen_out.read_text():
            failures.append("a generator's file was not written by `ckit lint`")
        else:
            gen_out.write_text(gen_out.read_text().replace("a-note", "tampered"))
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc = check.run(repo3)
            if rc == 0 or "content/fixture-index.json" not in err.getvalue():
                failures.append("a stale generated file must fail `ckit check` by name")
        planted += 2
        (repo.root / "plug" / "gen_bad.py").write_text(
            "def generate(repo):\n    return {'content/catalog.json': {}}\n", encoding="utf-8")
        cfg["generators"] = ["plug/gen_fx.py", "plug/gen_bad.py"]
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        try:
            with redirect_stdout(io.StringIO()):
                _lint(load_repo(repo.root))
            failures.append("a generator claiming an engine index must be refused")
        except SystemExit as exc:
            if "catalog.json" not in str(exc):
                failures.append(f"the claimed-index error must name the file, got: {exc}")
        planted += 1
        cfg["generators"] = []
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        gen_out.unlink(missing_ok=True)
        repo = load_repo(repo.root)
        _lint(repo)

        # --- the declarative extension points: each is declared in kit.json, reaches the reader
        #     (catalog.json, /shell/, the lint), and a malformed one fails `ckit check` by name
        def check_err(r: Repo) -> str:
            e = io.StringIO()
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(e):
                rc_ = check.run(r)
            return e.getvalue() if rc_ else ""

        xtmp, repo = _scratch()  # a clean repo of its own: the planted violations above stay put
        new.create(repo, "hub", "a-hub", title="Fixture hub")
        (repo.root / "plug").mkdir()
        (repo.root / "plug" / "genres_fx.json").write_text(json.dumps({"genres": {
            "recipe": {"dir": "recipes", "layout": "flat", "after": "hub", "label": "Recipes",
                       "skeleton": "plug/recipe.html", "checks": {"status": True}}}}), encoding="utf-8")
        (repo.root / "plug" / "recipe.html").write_text(_page("A recipe", '<p><span class="hb-kind hb-kind-recipe">recipe</span></p>'), encoding="utf-8")
        (repo.root / "plug" / "fx.html").write_text("<!DOCTYPE html><title>Fx page</title>", encoding="utf-8")
        (repo.root / "plug" / "theme-fx.css").write_text(".hb { --fx-hue: var(--teal); }\n", encoding="utf-8")
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg.update({
            "genres": ["plug/genres_fx.json", {"recipe": {"checks": {"max_words": 60}}}],
            "shell_pages": {"fx.html": "plug/fx.html"},
            "theme": "plug/theme-fx.css",
            "classes": ["sw-fx"],
            "links": [{"label": "Fx", "href": "/shell/fx.html", "title": "a planted link"}],
            "refs": [{"pattern": "Q-\\d+", "href": "/shell/record.html?p=record/lab.md#{id}"}],
            "indices": ["content/extra-index.json"],
        })
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        (repo.content / "extra-index.json").write_text("[]\n", encoding="utf-8")
        repo = load_repo(repo.root)
        new.create(repo, "recipe", "soup")  # a repo-relative skeleton, found from the root
        _write(repo, "notes/sw.html", _page("Sw", '<p><span class="sw-fx">x</span></p>'))
        _lint(repo)
        cat = json.loads((repo.content / "catalog.json").read_text())
        keys = [g["key"] for g in cat.get("groups") or []]
        if "recipes" not in keys or keys.index("recipes") != keys.index("hubs") + 1:
            failures.append(f"an extension genre with after=hub must follow hubs in the catalog: {keys}")
        elif next(g for g in cat["groups"] if g["key"] == "recipes")["label"] != "Recipes":
            failures.append("an extension genre's label must name its group")
        if [x["slug"] for x in cat.get("recipes") or []] != ["soup"]:
            failures.append(f"the extension genre's page is not in its catalog group: {cat.get('recipes')}")
        si = json.loads((repo.content / "search-index.json").read_text())
        if {r["kind"] for r in si if "/recipes/" in r["href"]} != {"recipe"}:
            failures.append("an extension genre's page must be badged with its genre in the search index")
        planted += 3
        for key, want in (("links", "Fx"), ("refs", "Q-"), ("indices", "/content/extra-index.json")):
            if want not in json.dumps(cat.get(key)):
                failures.append(f"catalog.json must carry the declared {key}: {cat.get(key)}")
            planted += 1
        err = check_err(repo)
        if err:
            failures.append("a repo using every extension point well must pass `ckit check`: " + err)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(repo))
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            port = httpd.server_address[1]
            st, _, body = _request(port, "/shell/theme.css")
            if st != 200 or b"--fx-hue" not in body:
                failures.append(f"/shell/theme.css must serve the declared theme, got {st}")
            st, _, body = _request(port, "/shell/fx.html")
            if st != 200 or b"Fx page" not in body:
                failures.append(f"a declared shell page must be served at /shell/<name>, got {st}")
            st, _, body = _request(port, "/")
            if b'href="/shell/fx.html"' not in body or b">Fx &rarr;<" not in body:
                failures.append("the landing page must carry the declared links")
            repo.cfg["home"] = "fx"
            st, _, body = _request(port, "/")
            if st != 200 or b"Fx page" not in body:
                failures.append(f"a home naming a shell page must serve it at /, got {st}")
            repo.cfg.pop("home")
            saved_theme = repo.cfg.pop("theme")
            st, _, body = _request(port, "/shell/theme.css")
            if st != 200 or b"{" in body:
                failures.append("/shell/theme.css must be an empty stylesheet when no theme is declared")
            repo.cfg["theme"] = saved_theme
        finally:
            httpd.shutdown()
            httpd.server_close()
            th.join(timeout=2)
        planted += 4
        # the lint accepts a declared class and rejects it once undeclared
        repo.cfg["classes"] = []
        with redirect_stdout(io.StringIO()):
            probs4, _ = lint.run(repo, nav=False)
        _expect(probs4, "notes/sw.html", "unknown shell class 'sw-fx'", failures)
        repo.cfg["classes"] = ["sw-fx"]
        planted += 1
        # malformed declarations fail the gate, each by name
        for key, bad, needle in (
            ("shell_pages", {"fx.html": "plug/missing.html"}, "plug/missing.html"),
            ("shell_pages", {"lib.css": "plug/fx.html"}, "would shadow"),
            ("theme", "plug/missing.css", "plug/missing.css"),
            ("links", [{"href": "/x"}], "needs a label"),
            ("refs", [{"pattern": "Q-(\\d+", "href": "/x#{id}"}], "not a regular expression"),
            ("refs", [{"pattern": "Q-\\d+", "href": "/x"}], "must contain {id}"),
            ("indices", ["content/missing-index.json"], "content/missing-index.json"),
            ("classes", "sw-fx", "kit.json classes"),
        ):
            saved = repo.cfg.get(key)
            repo.cfg[key] = bad
            err = check_err(repo)
            if needle not in err:
                failures.append(f"a malformed {key} ({bad!r}) must fail `ckit check` naming {needle!r}; got: {err[:200]!r}")
            repo.cfg[key] = saved
            planted += 1
        # the genre table names only real genres
        (repo.root / "plug" / "genres_bad.json").write_text(json.dumps({"x": {"dir": "xs", "layout": "flat", "after": "nope"}}))
        repo.cfg["genres"] = ["plug/genres_fx.json", "plug/genres_bad.json"]
        try:
            genres.load_genres(repo)
            failures.append("an `after` naming no genre must fail loud")
        except SystemExit as exc:
            if "nope" not in str(exc):
                failures.append(f"the bad-after error must name it: {exc}")
        planted += 1
        shutil.rmtree(xtmp, ignore_errors=True)
        repo = load_repo(tmp / "repo")

        # --- the hues are neutral; a repo's own names live in its theme. The pre-0.4 formal-
        #     verification vocabulary, served as a theme (templates/theme-fv.css) with its
        #     class names registered, makes a page written in it lint clean; without it, each
        #     old name is reported. No skeleton or craft page may use a domain token.
        old = ("reach", "cert", "target", "slack", "leak", "gen", "judge", "world")
        xtmp, xrepo = _scratch()
        fv_page = _page("Old vocabulary",
                        '<p style="color: var(--reach)"><span class="sw-reach">Reach</span></p>'
                        '<div class="lane lane-leak"><div class="cellrow"><div class="cell reach">1</div></div></div>')
        _write(xrepo, "notes/fv.html", fv_page)
        with redirect_stdout(io.StringIO()):
            probs5, _ = lint.run(xrepo, nav=False)
        for needle in ("unknown token var(--reach)", "unknown shell class 'sw-reach'",
                       "unknown shell class 'lane-leak'"):
            _expect(probs5, "notes/fv.html", needle, failures)
            planted += 1
        (xrepo.root / "assets").mkdir()
        shutil.copy(KIT_SRC / "templates" / "theme-fv.css", xrepo.root / "assets" / "theme.css")
        xcfg = json.loads((xrepo.root / "kit.json").read_text())
        xcfg["theme"] = "assets/theme.css"
        xcfg["classes"] = [f"{kind}-{o}" for kind in ("sw", "lane") for o in old]
        (xrepo.root / "kit.json").write_text(json.dumps(xcfg))
        xrepo = load_repo(xrepo.root)
        with redirect_stdout(io.StringIO()):
            probs5, _ = lint.run(xrepo, nav=False)
        if probs5:
            failures.append("theme-fv.css with its classes registered must make the old vocabulary lint clean: "
                            + " | ".join(probs5))
        served = config.theme_css(xrepo).decode()
        if "--reach: var(--teal)" not in served or ".hb .cell.reach" not in served:
            failures.append("the served theme must carry the mapped names and the moved widgets")
        planted += 2
        shutil.rmtree(xtmp, ignore_errors=True)
        domain = re.compile(r"--(?:" + "|".join(old) + r")(?![\w-])|\b(?:sw|lane)-(?:" + "|".join(old) + r")\b")
        for f in sorted([*(KIT_SRC / "shell" / "skeletons").rglob("*.html"), *(KIT_SRC / "craft").glob("*.md"),
                         KIT_SRC / "shell" / "lib.css", KIT_SRC / "shell" / "COMPONENTS.md"]):
            m = domain.search(f.read_text(encoding="utf-8"))
            if m:
                failures.append(f"{f.relative_to(KIT_SRC)} uses the domain token {m.group(0)!r} — the shell's hues are neutral")
        planted += 1

        # --- the 0.4 follow-ups: text is not markup, topics reach the indices, node only for books,
        #     and init survives a kit.json that names a layer not vendored yet
        ytmp, yrepo = _scratch()
        _write(yrepo, "notes/sample.html", _page("Sample",
               "<pre><code>&lt;span class=\"hb-bogus\" style=\"color:#ff0000; border-color: var(--nope)\"&gt;</code></pre>"
               "<p>Issue #abc123, and the token var(--nope) named in prose.</p>"
               "<!-- <span class=\"hb-bogus\">commented out</span> -->",
               head='<meta name="topic" content="kitchen">'))
        with redirect_stdout(io.StringIO()):
            probs6, _ = lint.run(yrepo, nav=True)
        if any("sample.html" in x for x in probs6):
            failures.append("text that looks like markup (a code sample, a comment) must not trip the form checks: "
                            + " | ".join(x for x in probs6 if "sample.html" in x))
        planted += 1
        si6 = json.loads((yrepo.content / "search-index.json").read_text())
        cat6 = json.loads((yrepo.content / "catalog.json").read_text())
        if [r.get("topic") for r in si6 if r["href"].endswith("sample.html")] != ["kitchen"] \
                or [n.get("topic") for n in cat6["notes"]] != ["kitchen"]:
            failures.append("a page's <meta name=topic> must reach the search index and the catalog")
        planted += 1
        real_which = check.shutil.which
        check.shutil.which = lambda name: None if name == "node" else real_which(name)
        try:
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                (yrepo.content / "books").mkdir(exist_ok=True)
                rc_empty = check.run(load_repo(yrepo.root))
            new.create(yrepo, "book", "a-book")
            with redirect_stdout(io.StringIO()):
                lint.run(yrepo, nav=True)
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                rc_book = check.run(load_repo(yrepo.root))
        finally:
            check.shutil.which = real_which
        if rc_empty != 0:
            failures.append("with no book to verify, the gate must not need node")
        if rc_book == 0 or "node is not on PATH" not in err.getvalue():
            failures.append("a book to verify without node must fail the gate, saying so")
        planted += 2
        from . import init as init_mod
        fresh = ytmp / "fresh"
        fresh.mkdir()
        (fresh / "kit.json").write_text(json.dumps({"name": "Fresh", "genres": ["kit/layer/genres.json"]}))
        out = io.StringIO()
        with redirect_stdout(out):
            rc_init = init_mod.run(fresh, quiet=False)
        if rc_init != 0 or "indices not generated yet" not in out.getvalue():
            failures.append("init must survive a kit.json naming a layer that is not vendored yet, and say so")
        pin = (fresh / "kit" / "PIN").read_text()
        if not pin.startswith("source content-kit ") or len(pin.splitlines()[0].split()) != 4:
            failures.append(f"init must pin content-kit in a four-field source line: {pin.splitlines()[0]!r}")
        planted += 2
        shutil.rmtree(ytmp, ignore_errors=True)

        # --- the theme is imported first in the cascade, so a base rule a theme extends with a
        #     modifier class must not set a colour — or it silently undoes the theme's .lane-x,
        #     .hb-kind-x, … (this is how lab-kit's story badge and a theme's lanes keep their colour)
        css = (KIT_SRC / "shell" / "lib.css").read_text(encoding="utf-8")
        for base in (".hb .lane", ".hb .v", ".hb .ev", ".hb .st", ".hb .hb-kind"):
            m = re.search(r"^" + re.escape(base) + r" \{([^}]*)\}", css, re.M)
            if not m:
                failures.append(f"lib.css has no base rule {base!r} to guard")
            elif re.search(r"(?<![\w-])(?:color|border-color|border)\s*:", m.group(1)):
                failures.append(f"lib.css {base} sets a colour (or the border shorthand, which resets it): "
                                "a theme's modifier class would lose to it")
            planted += 1

        # --- 0.5: the catalog names the site and its topics, carries each page's tags, and dates
        #     every entry by what changed — stable when nothing did, stale (a red gate) when a page
        #     was edited without `ckit lint`
        ztmp, zrepo = _scratch()
        cfgz = json.loads((zrepo.root / "kit.json").read_text())
        cfgz.update({"question": "What do we cook?", "topics": {"kitchen": "The kitchen"}})
        (zrepo.root / "kit.json").write_text(json.dumps(cfgz))
        zrepo = load_repo(zrepo.root)
        meta = '<meta name="topic" content="kitchen"><meta name="tags" content="salt, heat">'
        _write(zrepo, "notes/one.html", _page("One", "<p>First.</p>", head=meta))
        _write(zrepo, "notes/two.html", _page("Two", "<p>Second.</p>"))
        saved_today = os.environ.get("CKIT_TODAY")
        try:
            os.environ["CKIT_TODAY"] = "2026-01-01"
            _lint(zrepo)
            catz = json.loads((zrepo.content / "catalog.json").read_text())
            if catz.get("site") != {"name": "Scratch", "question": "What do we cook?"}:
                failures.append(f"the catalog must name the site and its question: {catz.get('site')}")
            if catz.get("topics") != {"kitchen": "The kitchen"}:
                failures.append(f"the catalog must carry kit.json's topic labels: {catz.get('topics')}")
            one = next((n for n in catz["notes"] if n["slug"] == "one"), {})
            if one.get("tags") != ["salt", "heat"]:
                failures.append(f"a catalog entry must carry its page's tags: {one}")
            if (one.get("created"), one.get("updated")) != ("2026-01-01", "2026-01-01") or len(one.get("sha", "")) != 12:
                failures.append(f"a page the catalog has never seen, outside git, is dated today: {one}")
            planted += 4
            os.environ["CKIT_TODAY"] = "2026-02-02"
            _write(zrepo, "notes/one.html", _page("One", "<p>First, revised.</p>", head=meta))
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc_stale = check.run(load_repo(zrepo.root))
            if rc_stale == 0:
                failures.append("a page edited without `ckit lint` must fail the gate: its catalog entry is stale")
            _lint(zrepo)
            catz = json.loads((zrepo.content / "catalog.json").read_text())
            one = next(n for n in catz["notes"] if n["slug"] == "one")
            two = next(n for n in catz["notes"] if n["slug"] == "two")
            if (one["created"], one["updated"]) != ("2026-01-01", "2026-02-02"):
                failures.append(f"a changed page keeps its created date and is updated today: {one}")
            if (two["created"], two["updated"]) != ("2026-01-01", "2026-01-01"):
                failures.append(f"an unchanged page keeps both dates: {two}")
            os.environ["CKIT_TODAY"] = "2026-03-03"
            before = (zrepo.content / "catalog.json").read_text()
            _lint(zrepo)
            if (zrepo.content / "catalog.json").read_text() != before:
                failures.append("the dates must be stable: a lint on a later day with nothing changed rewrote the catalog")
            planted += 4
            # a checkout that turns LF into CRLF changes no entry: the sha reads normalised line endings
            two_path = zrepo.content / "notes" / "two.html"
            two_path.write_bytes(two_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
            with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc_crlf = check.run(load_repo(zrepo.root))
            if rc_crlf != 0:
                failures.append("a CRLF checkout of an unchanged page must leave the catalog current")
            planted += 1
            # resolving a merge conflict in catalog.json by `ckit lint` keeps the committed dates
            if shutil.which("git"):
                gitenv = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                          "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
                import subprocess
                for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
                    subprocess.run(["git", "-C", str(zrepo.root), *args], env=gitenv, capture_output=True, check=True)
                committed = (zrepo.content / "catalog.json").read_text()
                (zrepo.content / "catalog.json").write_text("<<<<<<< HEAD\n" + committed + "=======\n{}\n>>>>>>> other\n")
                os.environ["CKIT_TODAY"] = "2026-04-04"
                _lint(zrepo)
                resolved = json.loads((zrepo.content / "catalog.json").read_text())
                one = next(n for n in resolved["notes"] if n["slug"] == "one")
                if (one.get("created"), one.get("updated")) != ("2026-01-01", "2026-02-02"):
                    failures.append(f"a lint that resolves a conflicted catalog.json must keep the committed dates: {one}")
                planted += 1
                # two branches change one page; the merge conflicts; the page is taken from theirs —
                # it keeps their dates (read from the conflict's stages), not today's
                mtmp, mrepo = _scratch()

                def g(*args, ok=True):
                    r = subprocess.run(["git", "-C", str(mrepo.root), *args], env=gitenv, capture_output=True, text=True)
                    if ok and r.returncode != 0:
                        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
                    return r

                def stamp(day: str, text: str) -> None:
                    os.environ["CKIT_TODAY"] = day
                    _write(mrepo, "notes/m.html", _page("M", f"<p>{text}</p>"))
                    _lint(mrepo)

                stamp("2026-01-01", "base")
                g("init", "-q"); g("add", "-A"); g("commit", "-q", "-m", "base")
                g("checkout", "-q", "-b", "theirs")
                stamp("2026-03-03", "their revision")
                g("commit", "-q", "-am", "theirs")
                g("checkout", "-q", "-")
                stamp("2026-02-02", "our revision")
                g("commit", "-q", "-am", "ours")
                if g("merge", "--no-edit", "theirs", ok=False).returncode == 0:
                    failures.append("the merge fixture must conflict (both sides changed one page)")
                g("checkout", "--theirs", "content/notes/m.html")
                os.environ["CKIT_TODAY"] = "2026-04-04"
                _lint(mrepo)
                m = next(n for n in json.loads((mrepo.content / "catalog.json").read_text())["notes"] if n["slug"] == "m")
                if (m.get("created"), m.get("updated")) != ("2026-01-01", "2026-03-03"):
                    failures.append(f"a page kept from the other side of a conflicted merge keeps that side's dates: {m}")
                planted += 1
                shutil.rmtree(mtmp, ignore_errors=True)

            # --- files are revalidated (Last-Modified → 304), generated pages never stored, the
            #     home page is built from the catalog, and /shell/pagefind.json says whether full
            #     text answers
            httpd3 = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(zrepo))
            th3 = threading.Thread(target=httpd3.serve_forever, daemon=True)
            th3.start()
            try:
                port3 = httpd3.server_address[1]
                st, hd, _ = _get(port3, "/content/notes/one.html")
                if st != 200 or hd.get("cache-control") != "no-cache" or not hd.get("etag"):
                    failures.append(f"a file must be served no-cache with an ETag: {st} {hd.get('cache-control')}")
                st2, _, body2 = _get(port3, "/content/notes/one.html", {"If-None-Match": hd.get("etag", "")})
                if st2 != 304 or body2:
                    failures.append(f"an unchanged file asked for by its ETag must answer 304 and no body, got {st2}")
                one_path = zrepo.content / "notes" / "one.html"
                one_path.write_text(one_path.read_text() + "\n")  # rewritten within the same second
                st3, _, _ = _get(port3, "/content/notes/one.html", {"If-None-Match": hd.get("etag", "")})
                if st3 != 200:
                    failures.append(f"a file rewritten within the same second must not answer 304, got {st3}")
                planted += 1
                st, hd, body = _get(port3, "/")
                if st != 200 or hd.get("cache-control") != "no-store" or b"The kitchen" not in body \
                        or b"Search everything" not in body:
                    failures.append("the generated home page must be served no-store, with the catalog's topics on it")
                st, _, body = _get(port3, "/shell/pagefind.json")
                if st != 200 or json.loads(body) != {"available": False}:
                    failures.append(f"/shell/pagefind.json must say full text is not available here: {st} {body!r}")
                planted += 4
            finally:
                httpd3.shutdown()
                httpd3.server_close()
        finally:
            if saved_today is None:
                os.environ.pop("CKIT_TODAY", None)
            else:
                os.environ["CKIT_TODAY"] = saved_today
            shutil.rmtree(ztmp, ignore_errors=True)

        # --- the shell's weight is a budget: the kit's own shell holds it, and a planted shell that
        #     does not is reported by name
        got = shell_weight_problems(KIT_SRC / "shell")
        if got:
            failures.extend(got)
        heavy = Path(tempfile.mkdtemp(prefix="ckit-selftest-heavy-"))
        (heavy / "lib.css").write_text("/* */", encoding="utf-8")
        (heavy / "lib.js").write_bytes(os.urandom(SHELL_BUDGET + 1024))
        if not any("over its" in x for x in shell_weight_problems(heavy)):
            failures.append("a shell over its size budget must be reported")
        shutil.rmtree(heavy, ignore_errors=True)
        planted += 2

        # --- a port held by a process with no pidfile is stopped, so `ckit up` can bind it
        from . import ctl
        holder = subprocess.Popen(
            [sys.executable, "-c",
             "import socket, time\n"
             "s = socket.socket()\n"
             "s.bind(('127.0.0.1', 0))\n"
             "s.listen(1)\n"
             "print(s.getsockname()[1], flush=True)\n"
             "time.sleep(30)\n"],
            stdout=subprocess.PIPE, text=True,
        )
        try:
            taken = int(holder.stdout.readline())
            buf = io.StringIO()
            with redirect_stdout(buf):
                ctl._free_port(taken)
            try:
                holder.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            if holder.poll() is None or ctl._listeners(taken):
                failures.append(
                    f"a taken port was not freed (pid {holder.pid}, listeners {ctl._listeners(taken)})")
            if str(holder.pid) not in buf.getvalue():
                failures.append(f"freeing a port must name the pid it stopped; got {buf.getvalue()!r}")
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.wait(timeout=2)
        planted += 1

        # --- the version pin is load-bearing
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg["ckit"] = "0.0.0"
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        buf = io.StringIO()
        with redirect_stdout(buf):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = check.run(load_repo(repo.root))
        if rc == 0 or "engine mismatch" not in err.getvalue():
            failures.append("a mismatched ckit pin must fail `ckit check`")
        planted += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print("ckit selftest FAILED:\n- " + "\n- ".join(failures))
        return 1
    print(f"ckit selftest ok ({planted} planted cases, {len(CLEAN)} clean genres)")
    return 0

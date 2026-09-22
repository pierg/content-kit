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
import tempfile
import threading
from contextlib import redirect_stdout
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from . import __version__, annotations as ann, book_nav, check, genres, lint, new, serve
from .paths import KIT_SRC, Repo, load_repo

CLEAN = {
    "note": "a-note",
    "concept": "a-concept",
    "entry": "an-entry",
    "story": "a-story",
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


STORY_SECTIONS = ("question", "why", "did", "happened", "learned", "not", "deeper", "backlinks")
SEALED = "<b>Status: LIVE</b> — a sealed story of one result against <code>F-1</code>."


def _story(title: str, *, sections: tuple[str, ...] = STORY_SECTIONS, sub: str = SEALED) -> str:
    """A story: the fixed sections in their fixed order, sealed to a row in its opening line."""
    return _page(title, "".join(f'<h2 id="{s}">{s}</h2><p>x</p>' for s in sections), sub=sub)


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

        # --- the genre set and the catalog are one registry: a genre dir missing from
        #     CATALOG_GROUPS lints and is searched, but never reaches the sidebar and is
        #     badged "page" — silent, so it is asserted rather than remembered
        dirs = {g["dir"] for g in genres.core_spec().values()}
        groups = {folder for folder, _kind, _layout in book_nav.CATALOG_GROUPS}
        if dirs != groups:
            failures.append("genres.json dirs and CATALOG_GROUPS disagree — only in genres.json: "
                            f"{sorted(dirs - groups)}; only in the catalog: {sorted(groups - dirs)}")
        planted += 1
        cat = json.loads((repo.content / "catalog.json").read_text())
        if [s["slug"] for s in cat.get("stories") or []] != ["a-story"]:
            failures.append(f"the scaffolded story is not a catalog group: {cat.get('stories')}")
        si = json.loads((repo.content / "search-index.json").read_text())
        story_kinds = {r["kind"] for r in si if "/stories/" in r["href"]}
        if story_kinds != {"story"}:
            failures.append(f"a story must be badged 'story', not 'page': {story_kinds}")
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
            "def extract(root, cfg):\n"
            "    return {'events': [{'date': '2026-09-04', 'kind': 'experiment', 'title': 'E1 locked', 'href': '/shell/record.html?p=e1.md'}],\n"
            "            'experiments': [{'slug': 'e1', 'title': 'E1', 'href': '/shell/record.html?p=e1.md', 'locked': '2026-09-04', 'findings': []}]}\n", encoding="utf-8")
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg["record"] = ["record/lab.md"]
        cfg["chronicle"] = {"sources": ["record/"], "extractors": ["ext.py"]}
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo = load_repo(repo.root)
        _lint(repo)
        chron = json.loads((repo.content / "chronicle.json").read_text())
        kinds = [e["kind"] for e in chron["events"]]
        if kinds != ["experiment", "lesson", "entry", "pivot"]:
            failures.append(f"chronicle events wrong or unsorted: {kinds}")
        if not chron["experiments"] or chron["experiments"][0]["slug"] != "e1":
            failures.append("plugin experiment not merged into the chronicle")
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
        _lint(repo)

        # --- the dashboard: opt-in ladder.json, generated + drift-checked like the chronicle,
        #     merging an extractor's ladder() vocabulary with the generic now / decisions.
        (repo.root / "record" / "state.md").write_text(
            "# State — LIVE\n\nThe planted current phase, in a sentence.\n", encoding="utf-8")
        (repo.root / "ext.py").write_text(
            "def extract(root, cfg):\n"
            "    return {'events': [{'date': '2026-09-04', 'kind': 'experiment', 'title': 'E1 locked', 'href': '/shell/record.html?p=e1.md'},\n"
            "                       {'date': '2026-09-06', 'kind': 'decision', 'title': 'the planted decision', 'summary': 'why', 'href': '/shell/record.html?p=d.md'}],\n"
            "            'experiments': [{'slug': 'e1', 'title': 'E1', 'href': '/shell/record.html?p=e1.md', 'locked': '2026-09-04', 'status': 'LOCKED', 'findings': []}]}\n"
            "def ladder(root, cfg):\n"
            "    return {'questions': [{'id': 'Q1', 'title': 'the planted question', 'status': 'OPEN', 'kill': 'k', 'href': '/x#q1'}],\n"
            "            'findings': [{'id': 'F-1', 'title': 'the planted finding', 'status': 'BANKED', 'href': '/x#f-1'}],\n"
            "            'claims': [{'id': 'C-1', 'title': 'the planted claim', 'rests_on': ['F-1'], 'href': '/x#c-1'}]}\n",
            encoding="utf-8")
        cfg = json.loads((repo.root / "kit.json").read_text())
        cfg["record"] = ["record/state.md", "record/lab.md", "record/log.md", "record/"]
        cfg["chronicle"] = {"sources": ["record/"], "extractors": ["ext.py"]}
        cfg["home"] = "dashboard"
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo = load_repo(repo.root)
        _lint(repo)
        lad_path = repo.content / "ladder.json"
        if not lad_path.is_file():
            failures.append("ladder.json not generated when home=dashboard")
        else:
            lad = json.loads(lad_path.read_text())
            if [q["id"] for q in lad.get("questions") or []] != ["Q1"]:
                failures.append(f"ladder questions not merged from the extractor: {lad.get('questions')}")
            if [f["id"] for f in lad.get("findings") or []] != ["F-1"]:
                failures.append(f"ladder findings not merged: {lad.get('findings')}")
            if not lad.get("claims") or lad["claims"][0]["rests_on"] != ["F-1"]:
                failures.append(f"ladder claims not merged: {lad.get('claims')}")
            if not lad.get("now") or "planted current phase" not in (lad["now"].get("summary") or ""):
                failures.append(f"ladder 'now' not scraped from the State file: {lad.get('now')}")
            if not any(d["kind"] == "decision" for d in lad.get("decisions") or []):
                failures.append(f"ladder decisions not taken from the chronicle: {lad.get('decisions')}")
        cat = json.loads((repo.content / "catalog.json").read_text())
        if cat.get("dashboard") is not True:
            failures.append("catalog.json missing the dashboard flag when opted in")
        if not (KIT_SRC / "shell" / "dashboard.html").is_file():
            failures.append("the dashboard shell page is missing")
        planted += 1
        # a stale ladder.json fails the gate, exactly like any other committed index
        good_lad = lad_path.read_text(encoding="utf-8")
        lad_path.write_text(good_lad.replace("planted finding", "tampered"), encoding="utf-8")
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = check.run(repo)
        if rc == 0 or "out of date" not in err.getvalue():
            failures.append("a stale ladder.json must fail `ckit check`")
        _lint(repo)  # regenerates / restores
        planted += 1
        # opting out is inert: catalog carries no dashboard flag and no ladder.json is expected
        lad_path.unlink()
        cfg = json.loads((repo.root / "kit.json").read_text())
        del cfg["home"]
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo = load_repo(repo.root)
        _lint(repo)
        if lad_path.is_file():
            failures.append("ladder.json must not be regenerated once the repo opts out")
        if "dashboard" in json.loads((repo.content / "catalog.json").read_text()):
            failures.append("catalog.json must drop the dashboard flag when opted out")
        planted += 1
        # re-enable so the remaining fixtures run against a consistent, dashboard-on repo
        cfg["home"] = "dashboard"
        (repo.root / "kit.json").write_text(json.dumps(cfg))
        repo = load_repo(repo.root)
        _lint(repo)

        # --- `home` as a content page: `/` 302s to its canonical URL; a dangling one fails
        #     `ckit check` and 404s at serve time; `"home": "dashboard"` keeps serving the
        #     dashboard exactly as before — exercised through a live instance of the handler
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(repo))
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        port = httpd.server_address[1]
        try:
            status, _, dash_body = _request(port, "/")
            if status != 200 or b"<title>Dashboard</title>" not in dash_body:
                failures.append(f'"home": "dashboard" should still serve the dashboard at /, got {status}')
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

            # a non-string home (the likely slip beside "dashboard": true) is dangling, not a crash
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
            repo.cfg["home"] = "dashboard"  # leave the fixture consistent for what follows
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
        plant("notes/nostatus.html", _page("No status", sub="Just a lede."), "no status")
        plant("notes/sections.html", _page("Sections", "<h2>One</h2><p>x</p>"), "<h2>")
        plant("notes/long.html", _page("Long", "<p>" + "word " * 450 + "</p>"), "over the 400")
        plant("concepts/nodefn/index.html", _page("No defn"), 'no <blockquote class="defn">')
        plant("concepts/cites/index.html",
              _page("Cites", '<blockquote class="defn" id="c"><span class="defn-name">C</span><br>See F-3.</blockquote>'),
              "inside its defn")
        plant("stray/x.html", _page("Stray"), "outside any genre")
        plant("projects/nometa/index.html", _page("No meta"), 'needs <meta name="status"')
        plant("projects/badmeta/index.html",
              _page("Bad meta", head='<meta name="status" content="whatever">'), "not active|shipped|paused")
        plant("hubs/long.html", _page("Long hub", "<p>" + "word " * 1600 + "</p>"), "over the 1500")
        # a story's shape is fixed and its opening line is sealed to the rows it tells: the
        # compliant ones are silent, each mutation is reported by the id it broke
        _write(repo, "stories/sealed/index.html", _story("Sealed"))
        _write(repo, "stories/cross-lab/index.html",
               _story("Cross lab", sub="<b>Status: LIVE</b> — sealed to <code>dsl:F-3</code>, "
                                       "another lab's pinned row."))
        plant("stories/missing/index.html",
              _story("Missing", sections=tuple(s for s in STORY_SECTIONS if s != "not")),
              'no <h2 id="not"> section')
        # commented-out markup renders as nothing: without stripping comments first, a story
        # could delete its bounds section, comment it back in where it belonged, and pass
        commented = _story("Commented", sections=tuple(s for s in STORY_SECTIONS if s != "not"))
        plant("stories/commented/index.html",
              commented.replace('<h2 id="deeper">',
                                '<!-- <h2 id="not">what it does not show</h2> --><h2 id="deeper">'),
              'no <h2 id="not"> section')
        plant("stories/hidden-id/index.html",
              _story("Hidden id", sub="<b>Status: LIVE</b> — a story whose row is commented "
                                      "out <!-- <code>F-1</code> -->."),
              "names no finding")
        plant("stories/misordered/index.html",
              _story("Misordered", sections=("question", "why", "did", "happened", "not",
                                             "learned", "deeper", "backlinks")),
              '<h2 id="not"> is out of order')
        plant("stories/unbound/index.html",
              _story("Unbound", sub="<b>Status: LIVE</b> — a story that names no row."),
              "names no finding")
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
        if any("03-fine.html" in p for p in probs):
            failures.append("a declared (data-fwd) forward reference must not be reported")
        planted += 1
        for quiet in ("stories/sealed", "stories/cross-lab"):
            if any(quiet in p for p in probs):
                failures.append(f"a compliant story ({quiet}) was reported: "
                                + " | ".join(p for p in probs if quiet in p))
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

        # --- the version pin is load-bearing
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

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


def _page(title: str, body: str = "<p>Body.</p>", *, sub: str = "A fixture.",
          head: str = "") -> str:
    return PAGE.format(title=title, sub=sub, body=body, head=head)


SHAPE = ("steps", "why", "pitfalls")  # a fixed-shape extension genre's sections, in order
SHAPED = {"howto": {"dir": "howtos", "layout": "folder",
                    "checks": {"status": True, "require_sections": list(SHAPE)}}}


def _shaped(title: str, *, sections: tuple[str, ...] = SHAPE) -> str:
    """A page of a fixed-shape genre: the declared sections, in the declared order."""
    return _page(title, "".join(f'<h2 id="{s}">{s}</h2><p>x</p>' for s in sections))


PLACEHOLDER_HREF = re.compile(r'href="/content/[^"]*OTHER[^"]*"')


def _settle(page: Path) -> None:
    """Point a fresh scaffold's placeholder links somewhere real (the landing page), as an author
    would point them at real pages."""
    page.write_text(PLACEHOLDER_HREF.sub('href="/"', page.read_text(encoding="utf-8")), encoding="utf-8")


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


def _organise_cases(failures: list[str]) -> int:
    """0.5: every link resolves, prose is one paragraph per line, tags are a vocabulary, the gate
    reports every stage at once, dates ignore whitespace, and topics, tags and pages reorganise
    without breaking a link — each checked on planted pages."""
    from . import export, links, organize, prose
    from .book_nav import _sha, tags_of, topic_of
    from .text import page_text
    planted = 0
    otmp, repo = _scratch()
    saved_today = os.environ.get("CKIT_TODAY")

    def quiet(fn, *args, **kw):
        with redirect_stdout(io.StringIO()) as out:
            got = fn(*args, **kw)
        return got, out.getvalue()

    def catalog_item(slug: str) -> dict:
        cat = json.loads((repo.content / "catalog.json").read_text())
        return next((i for g in cat["groups"] for i in cat.get(g["key"]) or [] if i["slug"] == slug), {})

    def kit() -> dict:
        return json.loads((repo.root / "kit.json").read_text())

    try:
        cfg = kit()
        cfg["topics"] = {"kitchen": "Kitchen", "garden": "Garden"}
        (repo.root / "kit.json").write_text(json.dumps(cfg, indent=2) + "\n")
        repo = load_repo(repo.root)
        os.environ["CKIT_TODAY"] = "2026-05-01"

        # ckit new: a hub named for a declared topic takes it; --topic and --tags become metas; an
        # undeclared topic and a malformed tag are refused before anything is written
        hub = new.create(repo, "hub", "kitchen", title="Kitchen")
        _settle(hub)
        if topic_of(hub.read_text()) != "kitchen":
            failures.append("a hub named for a declared topic must declare that topic")
        salt = new.create(repo, "note", "salt", title="Salt", topic="kitchen", tags=["salt", "heat"])
        _settle(salt)
        if topic_of(salt.read_text()) != "kitchen" or tags_of(salt.read_text()) != ["salt", "heat"]:
            failures.append("ckit new --topic/--tags must set the page's metas")
        for kwargs, needle in (({"topic": "astronomy"}, "not declared"), ({"tags": ["Bad Tag"]}, "lowercase slug")):
            try:
                new.create(repo, "note", "refused", **kwargs)
                failures.append(f"ckit new {kwargs} must be refused")
            except SystemExit as exc:
                if needle not in str(exc):
                    failures.append(f"ckit new {kwargs}: the refusal must say {needle!r}, got {exc}")
            if (repo.content / "notes" / "refused.html").exists():
                failures.append("a refused `ckit new` must write nothing")
        planted += 4

        # links: each way an address can fail to resolve is named; what resolves is silent
        b = _write(repo, "notes/b.html", _page("B", "<p>Bee.</p>", head='<meta name="topic" content="kitchen">'))
        (repo.content / "notes" / "fig").mkdir()
        (repo.content / "notes" / "fig" / "ok.svg").write_text("<svg/>")
        body = ('<p><a href="/content/notes/nope.html">a</a> <a href="/content/notes/">b</a> '
                '<a href="/content/Notes/b.html">c</a> <a href="/salt">d</a> <img src="fig/missing.png" alt=""> '
                '<a href="b.html">ok</a> <a href="/shell/search.html?q=x">ok</a> <a href="/shell/theme.css">ok</a> '
                '<a href="/pagefind/pagefind.js">ok</a> <a href="https://example.org/">ok</a> <a href="#top">ok</a> '
                '<a data-unchecked href="/built/paper.pdf">ok</a> <img src="fig/ok.svg" alt=""> '
                '<a href="/content/notes/b.html#x">ok</a> <a href="/">ok</a></p>'
                '<!-- <a href="/content/gone.html">commented out</a> -->')
        lk = _write(repo, "notes/links.html", _page("Links", body))
        mine = [p for p in _lint(repo) if "notes/links.html" in p]
        for needle in ("/content/notes/nope.html — nothing lives there",
                       "/content/notes/ — a directory without an index.html",
                       "/content/Notes/b.html — differs in letter case from /content/notes/b.html",
                       "/salt — a bare slug",
                       "src fig/missing.png — nothing lives there"):
            if not any(needle in p for p in mine):
                failures.append(f"a dead link must be reported ({needle!r}); got: {mine}")
            planted += 1
        if len(mine) != 5:
            failures.append(f"only the five dead links may be reported, got {len(mine)}: {mine}")
        planted += 1
        lk.unlink()

        # prose: one paragraph per line — the hard-wrapped p, li and td are reported once, with the
        # fix; a <br>, display math and code keep their lines; unwrapping changes no word a reader sees
        wp = _write(repo, "notes/wrapped.html", _page("Wrapped",
                    "<p>one line\ncontinues here</p>\n<p>a verse<br>\nnext line</p>\n<p>$$\na = b\n$$</p>\n"
                    "<ul>\n<li>one</li>\n<li>two\nwrapped</li>\n</ul>\n<pre>code\nkeeps\nlines</pre>\n"
                    "<table><tr><td>cell\nwrapped</td></tr></table>\n<p>$a + b % the sum\n+ c$ and so</p>\n"
                    "<p>if x < y and\nz > w then</p>\n"
                    '<p>see <a title="two\nlines" href="/">this</a> link</p>'))
        got = [p for p in _lint(repo) if "notes/wrapped.html" in p]
        if len(got) != 1 or "4 hard-wrapped elements" not in got[0] or "ckit unwrap" not in got[0]:
            failures.append(f"three hard-wrapped elements must be reported once, with the fix: {got}")
        before = page_text(wp.read_text())
        text, n = prose.unwrap(wp.read_text())
        wp.write_text(text)
        if n != 4 or page_text(text) != before or "a verse<br>\nnext line" not in text \
                or "$$\na = b\n$$" not in text or "code\nkeeps\nlines" not in text \
                or "% the sum\n+ c$" not in text or 'title="two\nlines"' not in text:
            failures.append(f"unwrap must join exactly the wrapped elements and leave <br>, math (a TeX % "
                            f"inline too), code and attribute values (joined {n})")
        if any("notes/wrapped.html" in p for p in _lint(repo)):
            failures.append("an unwrapped page must lint clean")
        planted += 3

        # tags are a vocabulary: lowercase slugs, each once
        tg = _write(repo, "notes/tagged.html", _page("Tagged", head='<meta name="tags" content="LLM Security, salt, salt, ">'))
        got = [p for p in _lint(repo) if "notes/tagged.html" in p]
        for needle in ("'llm-security'", "'salt' twice", "an empty tag"):
            if not any(needle in p for p in got):
                failures.append(f"a malformed tag must be reported ({needle!r}); got: {got}")
            planted += 1
        tg.unlink()
        _lint(repo)

        # one `ckit check` reports every stage that fails, and names them
        salt.write_text(salt.read_text().replace("</main>", '<p><a href="/content/nowhere.html">x</a></p></main>'))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = check.run(load_repo(repo.root))
        if rc == 0 or "out of date" not in err.getvalue() or "/content/nowhere.html" not in out.getvalue() \
                or "indices · lint" not in err.getvalue():
            failures.append("one `ckit check` must report stale indices and the lint together, naming both")
        planted += 1
        salt.write_text(salt.read_text().replace('<p><a href="/content/nowhere.html">x</a></p>', ""))
        _lint(repo)

        # dates follow what a page says, not how it is laid out: a re-flowed, re-indented, CRLF copy
        # keeps its dates, and a catalog written by 0.5.0.dev0 (line endings only) keeps its dates
        os.environ["CKIT_TODAY"] = "2026-05-02"
        b.write_text(b.read_text().replace("<p>Bee.</p>", "<p>Bee and wasp.</p>"))
        _lint(repo)
        os.environ["CKIT_TODAY"] = "2026-05-03"
        b.write_text(b.read_text().replace("<p>Bee and wasp.</p>", "<p>Bee and\r\n    wasp.</p>"))
        _lint(repo)
        if catalog_item("b").get("updated") != "2026-05-02":
            failures.append(f"a re-flowed page must keep its dates: {catalog_item('b')}")
        b.write_text(prose.unwrap(b.read_text())[0])
        cat = json.loads((repo.content / "catalog.json").read_text())
        for item in cat["notes"]:
            if item["slug"] == "b":
                item["sha"] = _sha([b], scheme="0.5.0.dev0")
        (repo.content / "catalog.json").write_text(json.dumps(cat, indent=2) + "\n")
        os.environ["CKIT_TODAY"] = "2026-05-04"
        _lint(repo)
        if catalog_item("b").get("updated") != "2026-05-02" or catalog_item("b").get("sha") != _sha([b]):
            failures.append(f"a 0.5.0.dev0 catalog entry must keep its dates and take the new sha: {catalog_item('b')}")
        planted += 2
        w2 = _write(repo, "notes/w2.html", _page("W2", "<p>two\nlines</p>"))
        _lint(repo)
        cat = json.loads((repo.content / "catalog.json").read_text())
        for item in cat["notes"]:
            if item["slug"] == "w2":
                item["sha"] = _sha([w2], scheme="0.5.0.dev0")
        (repo.content / "catalog.json").write_text(json.dumps(cat, indent=2) + "\n")
        os.environ["CKIT_TODAY"] = "2026-05-05"
        quiet(prose.unwrap_repo, repo, [w2])
        os.environ["CKIT_TODAY"] = "2026-05-04"
        if catalog_item("w2").get("updated") != "2026-05-04" or "two lines" not in w2.read_text():
            failures.append(f"`ckit unwrap` on a 0.5.0.dev0 catalog must keep a joined page's dates: {catalog_item('w2')}")
        w2.unlink()
        _lint(repo)
        planted += 1

        # a stated LIVE says nothing: the lint names the pages that still state it (a note, never a
        # failure); `ckit unwrap --status` drops it, the lede capitalised, the dates kept — also
        # for a catalog written by 0.5.0.dev1, whose sha kept it; a stated DRAFT stays
        os.environ["CKIT_TODAY"] = "2026-05-06"
        lv = _write(repo, "notes/lv.html", _page("Lv", "<p>Lv.</p>", sub="<b>Status: LIVE</b> — what lv says."))
        dr = _write(repo, "notes/dr.html", _page("Dr", "<p>Dr.</p>", sub="<b>Status: DRAFT</b> — half done."))
        (probs, _n), said = quiet(lint.run, repo, nav=True)
        if "state Status: LIVE" not in said or "notes/lv.html" not in said or "notes/dr.html" in said.split("state Status: LIVE")[1].split("\n")[0]:
            failures.append(f"the lint must name the pages that state LIVE, and only those: {said!r}")
        if any("notes/lv.html" in p for p in probs):
            failures.append("a stated LIVE must not fail the lint")
        cat = json.loads((repo.content / "catalog.json").read_text())
        for item in cat["notes"]:
            if item["slug"] == "lv":
                item["sha"] = _sha([lv], scheme="0.5.0.dev1")
        (repo.content / "catalog.json").write_text(json.dumps(cat, indent=2) + "\n")
        os.environ["CKIT_TODAY"] = "2026-05-07"
        (_joined, _pages, dropped), _ = quiet(prose.unwrap_repo, repo, [lv, dr], status=True)
        if dropped != ["content/notes/lv.html"] or '<p class="sub">What lv says.</p>' not in lv.read_text() \
                or "<b>Status: DRAFT</b> — half done." not in dr.read_text():
            failures.append(f"unwrap --status must drop a stated LIVE (capitalising the lede) and leave DRAFT: {dropped}")
        if catalog_item("lv").get("updated") != "2026-05-06" or catalog_item("lv").get("sha") != _sha([lv]):
            failures.append(f"dropping a stated LIVE must keep the page's dates, from a 0.5.0.dev1 sha too: {catalog_item('lv')}")
        if "state Status: LIVE" in quiet(lint.run, repo, nav=True)[1]:
            failures.append("once dropped, no page states LIVE and the lint says nothing about it")
        planted += 4
        lv.unlink()
        dr.unlink()

        # topics: add (listed with no hub yet), rename (pages, kit.json and the hub move together,
        # the hub's old address redirected), merge (old slugs kept as tags), assign
        _write(repo, "hubs/garden.html", _page("Garden", "<p>Map.</p>", head='<meta name="topic" content="garden">'))
        quiet(organize.topics_add, repo, "pantry")
        repo = load_repo(repo.root)
        pantry_line = next((ln for ln in organize.topics_report(repo).splitlines() if ln.startswith("pantry")), "")
        if kit()["topics"].get("pantry") != "Pantry" or "NO HUB" not in pantry_line:
            failures.append(f"topics add must declare the topic, listed without a hub: {pantry_line!r}")
        _write(repo, "hubs/pantry.html", _page("Pantry", "<p>Map.</p>", head='<meta name="topic" content="pantry">'))
        jar = _write(repo, "notes/jar.html", _page("Jar", '<p>A <a href="/content/hubs/pantry.html">jar</a>.</p>',
                                                   head='<meta name="topic" content="pantry">'))
        _lint(repo)
        repo, _ = quiet(organize.topics_rename, repo, "pantry", "larder")
        k = kit()
        if "pantry" in k["topics"] or k["topics"].get("larder") != "Pantry" or topic_of(jar.read_text()) != "larder":
            failures.append(f"topics rename must rename it in kit.json (label kept) and on every page: {k['topics']}")
        if not (repo.content / "hubs" / "larder.html").is_file() or (repo.content / "hubs" / "pantry.html").exists() \
                or 'href="/content/hubs/larder.html"' not in jar.read_text() \
                or k.get("moved", {}).get("/content/hubs/pantry.html") != "/content/hubs/larder.html":
            failures.append("topics rename must move the topic's hub with it, links and redirect included")
        planted += 3
        repo, said = quiet(organize.topics_merge, repo, ["kitchen", "garden"], "food", "Food")
        k = kit()
        if set(k["topics"]) != {"food", "larder"} or topic_of(salt.read_text()) != "food" \
                or "kitchen" not in tags_of(salt.read_text()):
            failures.append(f"topics merge must fold the topics into one, the old slug kept as a tag: {k['topics']}")
        if "2 hubs" not in said:
            failures.append(f"a merge that leaves a topic two hubs must say so: {said!r}")
        planted += 2
        quiet(organize.topics_add, repo, "delta")
        quiet(organize.topics_add, repo, "beta")
        repo = load_repo(repo.root)
        _write(repo, "hubs/delta.html", _page("Delta", head='<meta name="topic" content="delta">'))
        _write(repo, "hubs/beta.html", _page("Beta", head='<meta name="topic" content="beta">'))
        repo, said = quiet(organize.topics_merge, repo, ["beta"], "delta")
        if "ckit rm content/hubs/beta.html --to content/hubs/delta.html" not in said:
            failures.append(f"a merge must keep the hub named for the surviving topic: {said!r}")
        planted += 1
        quiet(organize.topics_assign, repo, "larder", ["/content/notes/salt.html"])
        if topic_of(salt.read_text()) != "larder":
            failures.append("topics assign must put the page on the topic")
        planted += 1

        # tags: spellings that look alike are named; a rename merges them on every page
        heaty = _write(repo, "notes/heaty.html", _page("Heaty", head='<meta name="tags" content="heats, salt">'))
        if "alike: heat · heats" not in organize.tags_report(repo):
            failures.append(f"tags that look alike must be named: {organize.tags_report(repo)}")
        quiet(organize.tags_rename, repo, "heats", "heat")
        if tags_of(heaty.read_text()) != ["heat", "salt"]:
            failures.append(f"tags rename must rewrite the tag on every page: {tags_of(heaty.read_text())}")
        planted += 2
        up = _write(repo, "notes/up.html", _page("Up", head='<meta name="tags" content="LLM">'))
        low = _write(repo, "notes/low.html", _page("Low", head='<meta name="tags" content="llm">'))
        if "ckit tags rename LLM llm" not in organize.tags_report(repo):
            failures.append(f"the suggested spelling must be one `ckit tags rename` accepts: {organize.tags_report(repo)}")
        up.unlink()
        low.unlink()
        planted += 1

        # mv: a note promoted to an entry — links in (absolute and relative) and its own relative
        # links rewritten, its sidecar and dates carried, the old address redirected
        os.environ["CKIT_TODAY"] = "2026-05-04"
        pepper = _write(repo, "notes/pepper.html", _page(
            "Pepper", '<p>Pepper goes with <a href="salt.html">salt</a>.</p>'
            '<details class="fcard"><summary>Q?</summary><div class="back">A.</div></details>',
            head='<meta name="topic" content="larder">'))
        linker = _write(repo, "notes/linker.html", _page(
            "Linker", '<p><a href="/content/notes/pepper.html#x">abs</a> <a href="pepper.html">rel</a></p>'))
        _lint(repo)
        ann.add(repo, "/content/notes/pepper.html", "sharper?", author="tester", target={"exact": "Pepper goes with"})
        os.environ["CKIT_TODAY"] = "2026-05-05"
        repo, said = quiet(organize.move, repo, pepper, repo.content / "entries" / "pepper" / "index.html")
        moved_to = repo.content / "entries" / "pepper" / "index.html"
        sidecar = repo.content / "entries" / "pepper" / "index.annotations.json"
        if pepper.exists() or not moved_to.is_file():
            failures.append("mv must move the page")
        if 'href="/content/entries/pepper/#x"' not in linker.read_text() \
                or 'href="/content/entries/pepper/"' not in linker.read_text():
            failures.append(f"mv must rewrite absolute and relative links to the page: {linker.read_text()}")
        if 'href="/content/notes/salt.html"' not in moved_to.read_text():
            failures.append("mv must make the moved page's relative links hold from its new place")
        if not sidecar.is_file() or json.loads(sidecar.read_text()).get("page") != "/content/entries/pepper/" \
                or ann.check_all(repo):
            failures.append("mv must carry the sidecar, naming the new address, its anchors intact")
        if kit().get("moved", {}).get("/content/notes/pepper.html") != "/content/entries/pepper/":
            failures.append(f"mv must record the redirect in kit.json moved: {kit().get('moved')}")
        if catalog_item("pepper").get("created") != "2026-05-04" \
                or catalog_item("pepper").get("href") != "/content/entries/pepper/":
            failures.append(f"mv must keep the page's created date: {catalog_item('pepper')}")
        if "1 flashcard" not in said:
            failures.append(f"mv must say the page's flashcards start afresh: {said!r}")
        if _lint(repo):
            failures.append("after mv the gate must be clean: " + " | ".join(_lint(repo)))
        planted += 8
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.make_handler(repo))
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            st, location, _ = _request(httpd.server_address[1], "/content/notes/pepper.html")
            if st != 301 or location != "/content/entries/pepper/":
                failures.append(f"serve must 301 a moved address to its page: {st} {location}")
        finally:
            httpd.shutdown()
            httpd.server_close()
            th.join(timeout=2)
        quiet(export.run, repo, otmp / "dist")
        stub = otmp / "dist" / "content" / "notes" / "pepper.html"
        if not stub.is_file() or "url=/content/entries/pepper/" not in stub.read_text():
            failures.append("export must leave a refresh at a moved address")
        planted += 2
        x1 = _write(repo, "notes/x1.html", _page("X1", "<p>X.</p>"))
        cc = _write(repo, "notes/cc.html", _page("Cc", "<p>C.</p>"))
        _lint(repo)
        repo, _ = quiet(organize.move, repo, x1, repo.content / "notes" / "x2.html")
        repo, _ = quiet(organize.move, repo, cc, repo.content / "notes" / "x1.html")
        k = kit().get("moved", {})
        if "/content/notes/x1.html" in k or k.get("/content/notes/cc.html") != "/content/notes/x1.html" or _lint(repo):
            failures.append(f"a page moved onto a redirected address takes it back, and the gate stays clean: {k}")
        repo, _ = quiet(organize.move, repo, repo.content / "notes" / "x1.html", repo.content / "notes" / "cc.html")
        planted += 1
        rs = _write(repo, "notes/rs.html", _page("Rs", '<p><a href="../../shell/search.html">browse</a> '
                                                       '<a href=b.html?x=1&amp;y=2>b</a></p>'))
        uq = _write(repo, "notes/uq.html", _page("Uq", '<p><a href=/content/notes/nowhere.html>x</a> '
                                                       '<a href=/content/notes/rs.html>rs</a></p>'))
        if not any("uq.html" in p and "/content/notes/nowhere.html — nothing lives there" in p for p in _lint(repo)):
            failures.append("a dead link in an unquoted attribute must be reported")
        uq.write_text(uq.read_text().replace("<a href=/content/notes/nowhere.html>x</a> ", ""))
        repo, _ = quiet(organize.move, repo, rs, repo.content / "entries" / "rs" / "index.html")
        moved_rs = (repo.content / "entries" / "rs" / "index.html").read_text()
        if 'href="/shell/search.html"' not in moved_rs or 'href="/content/notes/b.html?x=1&amp;y=2">' not in moved_rs \
                or 'href="/content/entries/rs/"' not in uq.read_text() or _lint(repo):
            failures.append("mv must pin a moved page's relative links (shell ones too), rewrite unquoted links "
                            "to it, and leave the gate clean: " + " | ".join(_lint(repo)))
        planted += 2
        e1 = _write(repo, "entries/e1/index.html", _page("E1", '<p><img src="fig.svg" alt=""> '
                                                               '<a href="../e1/fig.svg">the figure</a></p>'))
        (e1.parent / "fig.svg").write_text("<svg/>")
        _lint(repo)
        repo, _ = quiet(organize.move, repo, e1, repo.content / "entries" / "renamed" / "index.html")
        renamed = (repo.content / "entries" / "renamed" / "index.html").read_text()
        if 'src="fig.svg"' not in renamed or 'href="/content/entries/renamed/fig.svg"' not in renamed or _lint(repo):
            failures.append("a whole-folder move keeps relative links that still hold and rewrites those naming "
                            "the old folder: " + renamed[renamed.find("<main>"):renamed.find("</main>")])
        planted += 1
        orphan = repo.content / "notes" / "orph.annotations.json"
        orphan.write_text(json.dumps({"version": 1, "page": "/content/notes/orph.html", "threads": []}))
        try:
            quiet(organize.move, repo, repo.content / "notes" / "cc.html", repo.content / "notes" / "orph.html")
            failures.append("mv onto a page whose sidecar already exists must be refused")
        except SystemExit as exc:
            if "sidecar already sits" not in str(exc):
                failures.append(f"the refusal must name the sidecar in the way: {exc}")
        orphan.unlink()
        planted += 1
        stale = _write(repo, "notes/stale.html", _page("Stale", '<p><a href="/content/notes/pepper.html">old</a></p>'))
        if not any("moved to /content/entries/pepper/" in p for p in _lint(repo) if "notes/stale.html" in p):
            failures.append("a link to a moved address must be reported, naming the new one")
        stale.unlink()
        planted += 1
        for bad, needle in (({"/content/notes/salt.html": "/content/notes/b.html"}, "lives at /content/notes/salt.html again"),
                            ({"/content/notes/gone.html": "/content/notes/nowhere.html"}, "where no page lives"),
                            ({"/x.html": "/y.html", "/y.html": "/x.html"}, "cycle")):
            saved = repo.cfg.get("moved")
            repo.cfg["moved"] = bad
            if not any(needle in p for p in links.moved_problems(repo)):
                failures.append(f"a kit.json moved that the tree contradicts ({bad}) must be reported saying {needle!r}")
            repo.cfg["moved"] = saved
            planted += 1
        saved = repo.cfg.get("moved")
        repo.cfg["moved"] = {"/../../escaped.html": "/content/notes/b.html", "/x.html": "//evil.example/"}
        got = config.problems(repo)
        if not any(". or .. segment" in p for p in got) or not any("not a site address" in p for p in got):
            failures.append(f"a moved address with .. or a // target must fail the declarations: {got}")
        quiet(export.run, repo, otmp / "dist2")
        if (otmp.parent / "escaped.html").exists() or (otmp / "escaped.html").exists():
            failures.append("export must never write a moved address outside --out")
        repo.cfg["moved"] = saved
        planted += 2

        # rm: refused with an open thread, outside git, or on what git cannot bring back; then it
        # retires a page into another, its links and its address with it
        extra = _write(repo, "notes/extra.html", _page("Extra", "<p>Extra words.</p>"))
        points = _write(repo, "notes/points.html", _page("Points", '<p><a href="extra.html">extra</a></p>'))
        _lint(repo)
        t = ann.add(repo, "/content/notes/extra.html", "keep?", author="tester", target={"exact": "Extra words."})
        fl = ann.add(repo, "/content/notes/extra.html", "Added — mine.", author="agent:t", target={"exact": "Extra"},
                     kind="flag", label="framing")
        served, exported = serve._landing(repo, threads=True).decode(), serve._landing(repo).decode()
        if "Waiting for you · 2 questions" not in served or "keep?" not in served or "#ann=" not in served \
                or "flagged by an agent" not in served or "/shell/review.html" not in served \
                or "Waiting for you" in exported or "flagged by an agent" in exported:
            failures.append("the served home page must open with the questions waiting, link each to its thread, "
                            "and name the flags; the exported one must carry none of it")
        planted += 1

        def refused(needle: str, *args, **kw) -> None:
            try:
                quiet(organize.remove, *args, **kw)
                failures.append(f"rm must be refused ({needle})")
            except SystemExit as exc:
                if needle not in str(exc):
                    failures.append(f"rm's refusal must say {needle!r}: {exc}")

        refused("open annotation", repo, extra, salt)
        ann.reply(repo, "/content/notes/extra.html", t["id"], "folded into salt", author="tester", state="addressed")
        ann.set_state(repo, "/content/notes/extra.html", fl["id"], "withdrawn", author="agent:t")
        refused("not a git work tree", repo, extra, salt)
        planted += 2
        # prune: only closed threads, only old ones, only from a committed sidecar
        _write(repo, "notes/pruned.html", _page("Pruned"))
        old_sidecar = json.dumps({"version": 1, "page": "/content/notes/pruned.html", "threads": [
            {"id": "t-old-done", "created": "2020-01-01T00:00:00Z", "author": "a", "state": "addressed", "target": None,
             "body": "x", "replies": [{"created": "2020-01-02T00:00:00Z", "author": "agent", "body": "done", "state": "addressed"}]},
            {"id": "t-old-open", "created": "2020-01-01T00:00:00Z", "author": "a", "state": "open", "target": None,
             "body": "still waiting", "replies": []}]})
        _write(repo, "notes/pruned.annotations.json", old_sidecar)
        try:
            ann.prune(repo, older_than=30)
            failures.append("prune outside a git work tree must be refused")
        except ann.AnnotationError as exc:
            if "not a git work tree" not in str(exc):
                failures.append(f"prune's refusal must say why: {exc}")
        planted += 1
        if shutil.which("git"):
            import subprocess
            gitenv = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                      "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}

            def commit() -> None:
                for args in (["add", "-A"], ["commit", "-q", "--allow-empty", "-m", "fixture"]):
                    subprocess.run(["git", "-C", str(repo.root), *args], env=gitenv, capture_output=True, check=True)

            subprocess.run(["git", "-C", str(repo.root), "init", "-q"], env=gitenv, capture_output=True, check=True)
            commit()
            gone, _ = quiet(ann.prune, repo, older_than=30)
            left = {x["id"]: x["state"] for x in ann.load(repo.content / "notes" / "pruned.annotations.json")["threads"]}
            if [g["id"] for g in gone] != ["t-old-done"] or left != {"t-old-open": "open"}:
                failures.append("prune must drop the old closed thread and keep the open one")
            commit()
            _write(repo, "notes/pruned.annotations.json", old_sidecar)  # the old thread is back, uncommitted
            try:
                quiet(ann.prune, repo, older_than=30)
                failures.append("prune must refuse a sidecar git cannot bring back")
            except ann.AnnotationError as exc:
                if "not committed" not in str(exc):
                    failures.append(f"prune's refusal must say why: {exc}")
            if quiet(ann.prune, repo, older_than=100000)[0]:
                failures.append("prune must keep a closed thread younger than --older-than")
            commit()
            planted += 3
            extra.write_text(extra.read_text().replace("Extra words.", "Extra words, edited."))
            refused("not committed", repo, extra, salt)
            _lint(repo)
            commit()
            repo, _ = quiet(organize.remove, repo, extra, salt)
            if extra.exists() or ann.sidecar_for(extra).exists() \
                    or 'href="/content/notes/salt.html"' not in points.read_text() \
                    or kit().get("moved", {}).get("/content/notes/extra.html") != "/content/notes/salt.html":
                failures.append("rm must retire the page and its sidecar, rewrite links to it and redirect its address")
            if _lint(repo):
                failures.append("after rm the gate must be clean: " + " | ".join(_lint(repo)))
            planted += 3
            # a folder: an open thread on any page in it, an untracked file, or --to inside it refuses
            new.create(repo, "book", "bk", title="Bk")
            ch = new.create(repo, "chapter", "bk/01-one", title="One")
            for f in (repo.content / "books" / "bk").glob("*.html"):
                _settle(f)
            _lint(repo)
            quote = next(q for q in ("Chapter title", "One") if q in page_text(ch.read_text()))
            t2 = ann.add(repo, "/content/books/bk/01-one.html", "hold on", author="tester", target={"exact": quote})
            commit()
            bk = repo.content / "books" / "bk" / "index.html"
            refused("01-one.annotations.json", repo, bk, salt, folder=True)
            ann.reply(repo, "/content/books/bk/01-one.html", t2["id"], "ok", author="tester", state="addressed")
            commit()
            (bk.parent / "draft.txt").write_text("mine")
            refused("draft.txt", repo, bk, salt, folder=True)
            (bk.parent / "draft.txt").unlink()
            refused("inside content/books/bk", repo, bk, ch, folder=True)
            repo, _ = quiet(organize.remove, repo, bk, salt, folder=True)
            k = kit().get("moved", {})
            if bk.parent.exists() or k.get("/content/books/bk/01-one.html") != "/content/notes/salt.html" or _lint(repo):
                failures.append("rm --folder must retire the book and redirect every page in it: " + " | ".join(_lint(repo)))
            planted += 4
            # a new page at a redirected address takes it back
            again, _ = quiet(new.create, repo, "note", "extra", title="Extra, again")
            _settle(again)
            if "/content/notes/extra.html" in kit().get("moved", {}) or _lint(repo):
                failures.append("a new page at a redirected address must take it back: " + " | ".join(_lint(repo)))
            planted += 1
    finally:
        if saved_today is None:
            os.environ.pop("CKIT_TODAY", None)
        else:
            os.environ["CKIT_TODAY"] = saved_today
        shutil.rmtree(otmp, ignore_errors=True)
    ltmp, lrepo = _scratch()
    try:
        cfg = json.loads((lrepo.root / "kit.json").read_text())
        cfg["topics"] = ["alpha", "beta"]
        (lrepo.root / "kit.json").write_text(json.dumps(cfg, indent=2) + "\n")
        lrepo = load_repo(lrepo.root)
        try:
            new.create(lrepo, "note", "n1", topic="nonexistent")
            failures.append("with topics as a list, an undeclared topic must be refused")
        except SystemExit:
            pass
        if topic_of(new.create(lrepo, "hub", "alpha").read_text()) != "alpha":
            failures.append("with topics as a list, a hub named for one must take it")
        quiet(organize.topics_add, lrepo, "gamma", "Gamma G")
        got = json.loads((lrepo.root / "kit.json").read_text())["topics"]
        if got != {"alpha": "alpha", "beta": "beta", "gamma": "Gamma G"}:
            failures.append(f"a label on a list of topics must turn it into an object, keeping every slug: {got}")
        planted += 3
    finally:
        shutil.rmtree(ltmp, ignore_errors=True)
    # metadata: a meta's other attributes survive a new value; a meta alone on its line leaves with it
    from .text import set_meta
    h = '<head>\n  <meta charset="utf-8">\n  <meta name="tags" content="a" data-keep="y">\n  <title>T</title>\n</head>'
    if set_meta('<meta name="x" data-content="keep" content="1">', "x", "2") != \
            '<meta name="x" data-content="keep" content="2">':
        failures.append("set_meta must change the content attribute, not one whose name ends in content")
    if 'data-keep="y"' not in set_meta(h, "tags", "b") \
            or set_meta(set_meta(h, "tags", "b"), "tags", None) != h.replace('  <meta name="tags" content="a" data-keep="y">\n', ""):
        failures.append("set_meta must keep a meta's other attributes, and remove a lone meta with its line")
    planted += 1
    return planted


def _expect(probs: list[str], rel: str, needle: str, failures: list[str]) -> None:
    if not any(rel in p and needle in p for p in probs):
        failures.append(f"planted {rel!r} — expected a problem containing {needle!r}; got: "
                        + (" | ".join(p for p in probs if rel in p) or "(nothing)"))


def main(argv: list[str]) -> int:
    tmp, repo = _scratch()
    failures: list[str] = []
    planted = 0
    try:
        # --- clean: every skeleton scaffolds through `ckit new`; a fresh scaffold's only complaint
        #     is each placeholder link it carries, named as one — and once those point at real
        #     pages, it passes the whole gate
        for genre, slug in CLEAN.items():
            new.create(repo, genre, slug, title=f"Fixture {genre}")
        probs = _lint(repo)
        stray = [p for p in probs if "skeleton's placeholder" not in p]
        if stray or not probs:
            failures.append("a fresh scaffold must report its placeholder links, and nothing else:\n  "
                            + "\n  ".join(stray or ["(no placeholder link reported)"]))
        planted += 1
        for page in sorted(repo.content.rglob("*.html")):
            _settle(page)
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

        # --- kinds: a flag rests as noted and asks nothing; a question opens and waits
        flagged = _write(repo, "notes/flagged.html",
                         _page("Flagged", "<p>An example I made up. A framing I chose. A claim from memory.</p>"))
        f1 = ann.add(repo, "/content/notes/flagged.html", "Added — my example.", author="agent:t",
                     target={"exact": "An example I made up."}, kind="flag", label="worked example")
        f2 = ann.add(repo, "/content/notes/flagged.html", "Added — my framing.", author="agent:t",
                     target={"exact": "A framing I chose."}, kind="flag", label="framing")
        q1 = ann.add(repo, "/content/notes/flagged.html", "Is this claim right?", author="agent:t",
                     target={"exact": "A claim from memory."})
        if f1["state"] != "noted" or f1.get("kind") != "flag" or f1.get("label") != "worked example":
            failures.append("a flag must be born noted, carrying its kind and label")
        if q1["state"] != "open" or ann.kind_of(q1) != "question":
            failures.append("a question must be born open")
        opens = {x["id"] for x in ann.list_threads(repo, state="open")}
        live = {x["id"] for x in ann.list_threads(repo, state="live")}
        if f1["id"] in opens or q1["id"] not in opens or {f1["id"], f2["id"], q1["id"]} - live:
            failures.append("list: open must leave flags out; live must hold flags and questions alike")
        if {x["id"] for x in ann.list_threads(repo, state="live", kind="flag")} != {f1["id"], f2["id"]}:
            failures.append("list --kind flag must select the flags alone")
        try:
            ann.set_state(repo, "/content/notes/flagged.html", q1["id"], "noted", author="t")
            failures.append("a question must never be noted")
        except ann.AnnotationError:
            pass
        planted += 3
        # a flag whose passage left the page is named, never failed (an open question's is the failure)
        flagged.write_text(flagged.read_text().replace("An example I made up.", "Rewritten example."))
        if ann.check_all(repo):
            failures.append("a stale noted flag must not fail the gate: " + " | ".join(ann.check_all(repo)))
        if not any(f1["id"] in n for n in ann.stale_flags(repo)):
            failures.append("a stale noted flag must be named by stale_flags")
        planted += 1
        # relabel: a question that becomes a flag rests; a flag that becomes a question waits
        x = ann.relabel(repo, "/content/notes/flagged.html", q1["id"], author="t", kind="flag", label="claim")
        if x["state"] != "noted" or x.get("label") != "claim" \
                or not any("relabelled" in r.get("body", "") for r in x["replies"]):
            failures.append("relabel question → flag must rest it as noted, with its label and a reply saying so")
        x = ann.relabel(repo, "/content/notes/flagged.html", q1["id"], author="t", kind="question")
        if x["state"] != "open":
            failures.append("relabel flag → question must open it")
        planted += 1
        # resolve: a filter is required, declining needs its reason, and only what is selected moves
        for kw in ({"state": "addressed"}, {"state": "declined", "label": "framing"}):
            try:
                ann.resolve(repo, author="t", **kw)
                failures.append(f"resolve must be refused: {kw}")
            except ann.AnnotationError:
                pass
        done = ann.resolve(repo, state="addressed", author="pier", body="Kept.", label="framing")
        after = {x["id"]: x["state"] for x in ann.list_threads(repo, state="all")}
        if [d["id"] for d in done] != [f2["id"]] or after[f2["id"]] != "addressed" \
                or after[f1["id"]] != "noted" or after[q1["id"]] != "open":
            failures.append("resolve --label must move exactly the live threads with that label")
        done = ann.resolve(repo, state="withdrawn", author="pier", by="agent:", page="/content/notes/flagged.html")
        if {d["id"] for d in done} != {f1["id"], q1["id"]}:
            failures.append("resolve --by --page must move the live threads that author left on that page")
        planted += 3
        # the threads index: generated with the rest, counted into the catalog, stale the moment a
        # sidecar changes, and current again after the write path regenerates it
        _lint(repo)
        idx = json.loads((repo.content / "threads.json").read_text())
        cat = json.loads((repo.content / "catalog.json").read_text())
        if idx["counts"]["withdrawn"] < 2 or not any(
                r["id"] == f2["id"] and r["label"] == "framing" and r["title"] == "Flagged" for r in idx["threads"]):
            failures.append("threads.json must index every thread with its label and its page's title")
        if cat.get("threads") != {"open": idx["counts"]["open"], "noted": idx["counts"]["noted"],
                                  "total": sum(idx["counts"].values())}:
            failures.append("the catalog must carry the open and noted counts and the total")
        f3 = ann.add(repo, "/content/notes/flagged.html", "Added — again.", author="agent:t",
                     target={"exact": "A framing I chose."}, kind="flag", label="framing")
        if "content/threads.json" not in book_nav.check(repo):
            failures.append("a thread added without regenerating must leave threads.json stale for the gate")
        book_nav.regenerate_threads(repo)
        if book_nav.check(repo):
            failures.append("regenerate_threads must bring the indices back: " + " | ".join(book_nav.check(repo)))
        idx = json.loads((repo.content / "threads.json").read_text())
        if not any(r["id"] == f3["id"] and r.get("stale") is False for r in idx["threads"]):
            failures.append("a live thread's row must say whether its anchor holds")
        planted += 3

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
        # the status: none stated is LIVE; a stated one must be one the shell knows
        plant("notes/badstatus.html", _page("Bad status", sub="<b>Status: SHIPPED</b> — a project's word."),
              "status 'SHIPPED' in the opening line is not one the shell knows")
        _write(repo, "notes/drafted.html", _page("Drafted", sub="<b>Status: DRAFT</b> — half done."))
        _write(repo, "notes/stated.html", _page("Stated", sub="<b>Status: LIVE</b> — still allowed."))
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
        _write(repo, "notes/badkind.html", _page("Bad kind"))
        _write(repo, "notes/badkind.annotations.json",
               json.dumps({"version": 1, "page": "/content/notes/badkind.html",
                           "threads": [{"id": "t-1", "body": "x", "author": "a", "target": None, "state": "open", "kind": "wish"},
                                       {"id": "t-2", "body": "x", "author": "a", "target": None, "state": "noted"}]}))
        cases.append(("badkind.annotations.json", "kind must be one of", ""))
        cases.append(("badkind.annotations.json", "only a flag can be noted", ""))

        probs = _lint(repo)
        for rel, needle, _ in cases:
            _expect(probs, rel, needle, failures)
            planted += 1
        if any(("drafted" in p or "stated" in p) for p in probs):
            failures.append("a known stated status (DRAFT, or LIVE itself) must pass: "
                            + " | ".join(p for p in probs if "drafted" in p or "stated" in p))
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
        _settle(new.create(repo, "hub", "a-hub", title="Fixture hub"))
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

        # --- 0.5: links, prose, tags, one report per gate, and reorganising without breaking a link
        planted += _organise_cases(failures)

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

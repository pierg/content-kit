"""`ckit` — the content-kit engine's command line."""

from __future__ import annotations

import json
import sys

from . import __version__

USAGE = f"""ckit {__version__} — serve, lint, navigate, scaffold and annotate a content tree

  ckit init [repo] [--name --port]   vendor the kit into a repo and scaffold what it lacks
  ckit check                         the content gate (version pin · shell · indices current · lint · books)
  ckit lint [paths] [--no-nav]       form + genre + annotation lint; regenerates the indices
  ckit nav [--check]                 regenerate nav.json / catalog / search-index / backlinks / chronicle / generators
  ckit new <genre> <slug> [--title --topic --tags]   scaffold a page from its skeleton
  ckit genres                        list the genres this repo knows (core + its extensions)
  ckit topics [add|rename|merge|assign …]   the topics: label · hub · pages; declare and reorganise
  ckit tags [rename <old> <new>]     the tags and their pages; spellings that look alike
  ckit mv <page> <to>                move a page: links rewritten, sidecar and dates kept, redirected
  ckit rm <page> --to <page>         retire a page into another, its links and address with it
  ckit unwrap [paths] [--status]     join hard-wrapped prose; --status drops a stated LIVE (the default)
  ckit serve [--host --port]         foreground server
  ckit up | down | status            background server
  ckit export [--out dist] [--base /] the site as static files (--base /<repo>/ for a project site)
  ckit annotations <verb> …          list · show · add · reply · state · relabel · resolve · prune · check
  ckit selftest                      the engine's own planted-fixture gate
  ckit where                         the kit source this engine vendors from (for layer installers)
  ckit version
"""


def _annotations(argv: list[str]) -> int:
    import argparse

    from . import annotations as ann, book_nav
    from .paths import load_repo

    ap = argparse.ArgumentParser(prog="ckit annotations")
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("list", help="threads across the tree (default: open — the questions waiting)")
    p.add_argument("--state", default="open", choices=(*ann.STATES, "live", "all"),
                   help="one state; live = open or noted; all")
    p.add_argument("--kind", choices=ann.KINDS, help="only questions, or only flags")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("show", help="one page's threads")
    p.add_argument("page")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("add", help="open a question, or leave a flag (page-level unless --quote)")
    p.add_argument("page")
    p.add_argument("--body", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--quote")
    p.add_argument("--kind", choices=ann.KINDS, default="question",
                   help="question (opens, waits for an answer) or flag (noted: a disclosure, asks nothing)")
    p.add_argument("--label", help="a few words the review page groups by, e.g. 'worked example'")
    p = sub.add_parser("reply", help="reply in a thread, optionally moving its state")
    p.add_argument("page")
    p.add_argument("id")
    p.add_argument("--body", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--state", choices=ann.STATES)
    p = sub.add_parser("state", help="move a thread's state without a reply")
    p.add_argument("page")
    p.add_argument("id")
    p.add_argument("state", choices=ann.STATES)
    p.add_argument("--author", required=True)
    p = sub.add_parser("relabel", help="change a thread's kind or label (a question → flag rests as noted)")
    p.add_argument("page")
    p.add_argument("id")
    p.add_argument("--kind", choices=ann.KINDS)
    p.add_argument("--label", help="'' clears it")
    p.add_argument("--author", required=True)
    p = sub.add_parser("resolve", help="move every live thread the filters select to one state, with one reply each")
    p.add_argument("--state", required=True, choices=ann.STATES)
    p.add_argument("--author", required=True)
    p.add_argument("--body", default="", help="the reply (required to decline)")
    p.add_argument("--page")
    p.add_argument("--kind", choices=ann.KINDS)
    p.add_argument("--label")
    p.add_argument("--by", help="an author, or an author prefix such as agent:")
    p = sub.add_parser("prune", help="drop closed threads untouched for N days from committed sidecars")
    p.add_argument("--older-than", type=int, default=30, metavar="DAYS")
    p.add_argument("--page")
    sub.add_parser("check", help="validate every sidecar and its anchors; name stale flags")
    args = ap.parse_args(argv)
    repo = load_repo()

    def refreshed() -> None:
        written = book_nav.regenerate_threads(repo)
        if written:
            print("indices refreshed: " + ", ".join(written))

    try:
        if args.verb == "list":
            rows = ann.list_threads(repo, state=args.state, kind=args.kind)
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            elif not rows:
                print(f"no {args.state} threads")
            else:
                for t in rows:
                    q = t["target"]["exact"] if t.get("target") else "(page)"
                    what = ann.kind_of(t) + (f" · {t['label']}" if t.get("label") else "")
                    print(f"{t['state']:9s} {t['page']}  {t['id']}  [{t['author']}]  {what}")
                    print(f"          ▸ {q[:90]}")
                    print(f"          {t['body'][:200]}")
                    for r in t.get("replies") or []:
                        print(f"            ↳ {r.get('author')}: {r.get('body', '')[:160]}"
                              + (f"  → {r['state']}" if r.get("state") else ""))
            return 0
        if args.verb == "show":
            page = ann.resolve_page(repo, args.page)
            data = ann.load(ann.sidecar_for(page))
            print(json.dumps(data, indent=2, ensure_ascii=False) if args.json
                  else f"{len(data.get('threads', []))} thread(s) on {ann.href_of(repo, page)}")
            if not args.json:
                for t in data.get("threads", []):
                    q = t["target"]["exact"] if t.get("target") else "(page)"
                    what = ann.kind_of(t) + (f" · {t['label']}" if t.get("label") else "")
                    print(f"  {t['state']:9s} {t['id']}  [{t['author']}]  {what}  ▸ {q[:80]}")
                    print(f"            {t['body'][:200]}")
            return 0
        if args.verb == "add":
            target = {"exact": args.quote} if args.quote else None
            t = ann.add(repo, args.page, args.body, author=args.author, target=target,
                        kind=args.kind, label=args.label)
            print(f"{'noted' if t['state'] == 'noted' else 'opened'} {t['id']} on {args.page}")
            refreshed()
            return 0
        if args.verb == "reply":
            t = ann.reply(repo, args.page, args.id, args.body, author=args.author, state=args.state)
            print(f"{t['id']} → {t['state']}")
            refreshed()
            return 0
        if args.verb == "state":
            t = ann.set_state(repo, args.page, args.id, args.state, author=args.author)
            print(f"{t['id']} → {t['state']}")
            refreshed()
            return 0
        if args.verb == "relabel":
            t = ann.relabel(repo, args.page, args.id, author=args.author, kind=args.kind, label=args.label)
            print(f"{t['id']} → {ann.kind_of(t)}" + (f" · {t['label']}" if t.get("label") else "") + f" · {t['state']}")
            refreshed()
            return 0
        if args.verb == "resolve":
            done = ann.resolve(repo, state=args.state, author=args.author, body=args.body,
                               page=args.page, kind=args.kind, label=args.label, by=args.by)
            for d in done:
                print(f"{d['page']}  {d['id']} → {args.state}")
            print(f"{len(done)} thread(s) → {args.state}")
            refreshed()
            return 0
        if args.verb == "prune":
            gone = ann.prune(repo, older_than=args.older_than, page=args.page)
            for d in gone:
                print(f"{d['page']}  {d['id']} ({d['state']}) dropped")
            print(f"{len(gone)} closed thread(s) dropped" + (f" — older than {args.older_than} days" if gone else ""))
            refreshed()
            return 0
        if args.verb == "check":
            probs = ann.check_all(repo)
            if probs:
                print("\n".join(probs))
                return 1
            print("annotations ok")
            for note in ann.stale_flags(repo):
                print("note: " + note)
            return 0
    except ann.AnnotationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def _unwrap(argv: list[str]) -> int:
    import argparse
    from pathlib import Path

    from . import prose
    from .paths import load_repo

    ap = argparse.ArgumentParser(prog="ckit unwrap", description="join hard-wrapped prose")
    ap.add_argument("paths", nargs="*", type=Path, help="pages or directories (default: every page)")
    ap.add_argument("--status", action="store_true",
                    help="also drop a stated LIVE from each opening line: it is the default")
    args = ap.parse_args(argv)
    joined, pages, dropped = prose.unwrap_repo(load_repo(), args.paths, status=args.status)
    for rel, n in pages:
        print(f"  {rel}: {n}")
    print(f"joined {joined} hard-wrapped element(s) in {len(pages)} page(s)" if joined
          else "no hard-wrapped prose")
    if args.status:
        print(f"dropped a stated LIVE from {len(dropped)} page(s)" if dropped else "no stated LIVE")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in ("version", "--version"):
        print(__version__)
        return 0
    if cmd == "where":
        from .paths import KIT_SRC
        print(KIT_SRC)
        return 0
    if cmd == "init":
        from . import init
        return init.main(rest)
    if cmd == "export":
        from . import export
        return export.main(rest)
    if cmd == "check":
        from . import check
        return check.main(rest)
    if cmd == "lint":
        from . import lint
        return lint.main(rest)
    if cmd == "nav":
        from . import book_nav
        from .paths import load_repo
        repo = load_repo()
        if rest and rest[0] == "--check":
            dirty = book_nav.check(repo)
            if dirty:
                print("indices out of date — run: ckit nav")
                print("\n".join(dirty))
                return 1
            print("indices up to date")
            return 0
        written = book_nav.regenerate(repo)
        print("wrote " + ", ".join(written) if written else "indices unchanged")
        return 0
    if cmd == "new":
        from . import new
        return new.main(rest)
    if cmd in ("topics", "tags", "mv", "rm"):
        from . import organize
        return {"topics": organize.topics_main, "tags": organize.tags_main,
                "mv": organize.mv_main, "rm": organize.rm_main}[cmd](rest)
    if cmd == "unwrap":
        return _unwrap(rest)
    if cmd == "genres":
        from .genres import load_genres, ordered
        from .paths import load_repo
        for g in ordered(load_genres(load_repo())):
            print(f"{g.name:9s} {g.dir + '/':11s} {g.layout:11s} {g.register}")
        return 0
    if cmd == "serve":
        from . import serve
        return serve.main(rest)
    if cmd in ("up", "down", "status"):
        from . import ctl
        return ctl.main(rest, cmd)
    if cmd == "annotations":
        return _annotations(rest)
    if cmd == "selftest":
        from . import selftest
        return selftest.main(rest)
    print(f"ckit: unknown command {cmd!r}\n{USAGE}", file=sys.stderr)
    return 2

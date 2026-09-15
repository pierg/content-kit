"""`ckit` — the content-kit engine's command line."""

from __future__ import annotations

import json
import sys

from . import __version__

USAGE = f"""ckit {__version__} — serve, lint, navigate, scaffold and annotate a content tree

  ckit check                         the content gate (version pin · shell · indices current · lint · books)
  ckit lint [paths] [--no-nav]       form + genre + annotation lint; regenerates the indices
  ckit nav [--check]                 regenerate nav.json / catalog / search-index / backlinks / chronicle / ladder
  ckit new <genre> <slug> [--title]  scaffold a page from its skeleton
  ckit genres                        list the genres this repo knows (core + its extensions)
  ckit serve [--host --port]         foreground server
  ckit up | down | status            background server
  ckit annotations <verb> …          list · show · add · reply · state · check
  ckit selftest                      the engine's own planted-fixture gate
  ckit version
"""


def _annotations(argv: list[str]) -> int:
    import argparse

    from . import annotations as ann
    from .paths import load_repo

    ap = argparse.ArgumentParser(prog="ckit annotations")
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("list", help="threads across the tree (default: open)")
    p.add_argument("--state", default="open", choices=("open", "addressed", "declined", "withdrawn", "all"))
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("show", help="one page's threads")
    p.add_argument("page")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("add", help="open a thread (page-level unless --quote)")
    p.add_argument("page")
    p.add_argument("--body", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--quote")
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
    sub.add_parser("check", help="validate every sidecar and its anchors")
    args = ap.parse_args(argv)
    repo = load_repo()

    try:
        if args.verb == "list":
            rows = ann.list_threads(repo, state=args.state)
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            elif not rows:
                print(f"no {args.state} threads")
            else:
                for t in rows:
                    q = t["target"]["exact"] if t.get("target") else "(page)"
                    print(f"{t['state']:9s} {t['page']}  {t['id']}  [{t['author']}]")
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
                    print(f"  {t['state']:9s} {t['id']}  [{t['author']}]  ▸ {q[:80]}")
                    print(f"            {t['body'][:200]}")
            return 0
        if args.verb == "add":
            target = {"exact": args.quote} if args.quote else None
            t = ann.add(repo, args.page, args.body, author=args.author, target=target)
            print(f"opened {t['id']} on {args.page}")
            return 0
        if args.verb == "reply":
            t = ann.reply(repo, args.page, args.id, args.body, author=args.author, state=args.state)
            print(f"{t['id']} → {t['state']}")
            return 0
        if args.verb == "state":
            t = ann.set_state(repo, args.page, args.id, args.state, author=args.author)
            print(f"{t['id']} → {t['state']}")
            return 0
        if args.verb == "check":
            probs = ann.check_all(repo)
            if probs:
                print("\n".join(probs))
                return 1
            print("annotations ok")
            return 0
    except ann.AnnotationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in ("version", "--version"):
        print(__version__)
        return 0
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
    if cmd == "genres":
        from .genres import load_genres
        from .paths import load_repo
        for g in load_genres(load_repo()).values():
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

"""Session-free page annotations.

A human marks up a rendered page in the browser; the server writes a sidecar beside the page;
any agent later — fresh context, another session, another clone — reads the open threads,
addresses them, replies in the thread, and flips the state. Nothing live joins the two halves,
and nothing needs to be running for an annotation to survive.

The loop runs both ways. A reader's thread is a **question**: it opens `open` and waits for
whoever acts on the page to address or decline it. An agent that writes beyond its source leaves
a **flag**: a disclosure pinned to the passage, born `noted`, which asks nothing of anyone until
a reader reopens it as a request. Questions wait; flags are browsed.

Sidecar: `<page>.annotations.json` — `index.annotations.json` beside an `index.html`,
`<slug>.annotations.json` beside a flat page. Committed, so feedback is part of the record.

    {
      "version": 1,
      "page": "/content/concepts/ic3/",
      "threads": [
        {
          "id": "t-20260911-3f9a1c", "created": "2026-09-11T08:12:00Z", "author": "pier",
          "kind": "question",                   # question (absent means question) · flag
          "label": "worked example",            # optional: a few words the review page groups by
          "state": "open",                      # open · noted · addressed · declined · withdrawn
          "target": {                           # null for a page-level note
            "type": "TextQuoteSelector",        # W3C Web Annotation: quote + context, not a selector
            "exact": "the quoted prose", "prefix": "…32 chars before", "suffix": "32 chars after…"
          },
          "body": "the comment",
          "replies": [ { "created": "…", "author": "agent:claude", "body": "…", "state": "addressed" } ]
        }
      ]
    }

Anchoring by quote (not CSS path) is deliberate: prose gets edited and selectors rot. When a
quote can no longer be found on its page the gate fails loud for an open thread — a dropped
comment is not a resolved one — and names a noted flag as stale without failing: a disclosure
whose passage is gone has nothing left to disclose.

`content/threads.json` is the generated index of every thread, with its page's title and whether
its anchor still holds (`ckit nav`; every write through the engine regenerates it). The shell's
review page reads it.
"""

from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .paths import Repo
from .text import normalize, page_text, title_of

STATES = ("open", "noted", "addressed", "declined", "withdrawn")
KINDS = ("question", "flag")
LIVE = ("open", "noted")          # a thread still on the page's conscience
CLOSED = ("addressed", "declined", "withdrawn")
CONTEXT = 32
LABEL_MAX = 60
_LOCK = threading.Lock()


class AnnotationError(ValueError):
    pass


# ----------------------------------------------------------------------------- paths

def sidecar_for(page: Path) -> Path:
    return page.with_name(page.stem + ".annotations.json") if page.name != "index.html" \
        else page.with_name("index.annotations.json")


def page_for_sidecar(sidecar: Path) -> Path:
    stem = sidecar.name[: -len(".annotations.json")]
    return sidecar.with_name(f"{stem}.html")


def resolve_page(repo: Repo, ref: str) -> Path:
    """`/content/x/y/` · `/content/x/y.html` · `content/x/y/index.html` → the page file."""
    s = ref.strip()
    if s.startswith("/"):
        s = s[1:]
    p = repo.root / s
    if s.endswith("/") or p.is_dir():
        p = p / "index.html"
    if not p.is_file():
        raise AnnotationError(f"no such page: {ref}")
    try:
        p.resolve().relative_to(repo.content.resolve())
    except ValueError as exc:
        raise AnnotationError(f"not under {repo.content_name}/: {ref}") from exc
    return p


def href_of(repo: Repo, page: Path) -> str:
    href = "/" + page.resolve().relative_to(repo.root).as_posix()
    return href[: -len("index.html")] if href.endswith("/index.html") else href


# ----------------------------------------------------------------------------- store

def load(sidecar: Path) -> dict:
    if not sidecar.is_file():
        return {"version": 1, "page": "", "threads": []}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnnotationError(f"{sidecar}: invalid JSON — {exc}") from exc
    return data


def save(sidecar: Path, data: dict) -> None:
    sidecar.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return f"t-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3)}"


def _find(data: dict, tid: str) -> dict:
    for t in data.get("threads", []):
        if t.get("id") == tid:
            return t
    raise AnnotationError(f"no thread {tid}")


def kind_of(thread: dict) -> str:
    """A thread written before kinds existed is a question: it was a reader's ask."""
    return thread.get("kind") or "question"


def _clean_label(label: str | None) -> str:
    return normalize(str(label or ""))[:LABEL_MAX]


def _last_touch(thread: dict) -> str:
    replies = thread.get("replies") or []
    stamps = [str(thread.get("created") or "")] + [str(r.get("created") or "") for r in replies]
    return max(stamps)


# ----------------------------------------------------------------------------- schema

def validate(data: dict, where: str) -> list[str]:
    probs: list[str] = []
    if not isinstance(data, dict):
        return [f"{where}: not an object"]
    if data.get("version") != 1:
        probs.append(f"{where}: version must be 1")
    if not isinstance(data.get("page"), str) or not data["page"]:
        probs.append(f"{where}: missing page href")
    threads = data.get("threads")
    if not isinstance(threads, list):
        return probs + [f"{where}: threads must be a list"]
    ids: set[str] = set()
    for i, t in enumerate(threads):
        tag = f"{where}: thread[{i}]"
        if not isinstance(t, dict):
            probs.append(f"{tag} not an object")
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid:
            probs.append(f"{tag} missing id")
        elif tid in ids:
            probs.append(f"{tag} duplicate id {tid}")
        else:
            ids.add(tid)
        if t.get("state") not in STATES:
            probs.append(f"{tag} state must be one of {STATES}, got {t.get('state')!r}")
        if "kind" in t and t.get("kind") not in KINDS:
            probs.append(f"{tag} kind must be one of {KINDS}, got {t.get('kind')!r}")
        if t.get("state") == "noted" and kind_of(t) != "flag":
            probs.append(f"{tag} only a flag can be noted — a question is open until it is answered")
        if "label" in t and not isinstance(t.get("label"), str):
            probs.append(f"{tag} label must be a string")
        if not isinstance(t.get("body"), str) or not t["body"].strip():
            probs.append(f"{tag} empty body")
        if not isinstance(t.get("author"), str) or not t["author"].strip():
            probs.append(f"{tag} missing author")
        tgt = t.get("target")
        if tgt is not None:
            if not isinstance(tgt, dict) or tgt.get("type") != "TextQuoteSelector":
                probs.append(f"{tag} target must be null or a TextQuoteSelector")
            elif not isinstance(tgt.get("exact"), str) or not tgt["exact"].strip():
                probs.append(f"{tag} target.exact is empty")
        for j, r in enumerate(t.get("replies") or []):
            if not isinstance(r, dict) or not isinstance(r.get("body"), str) or not r["body"].strip():
                probs.append(f"{tag} reply[{j}] has no body")
        if t.get("state") == "declined" and not any(
            (r.get("state") == "declined" and r.get("body", "").strip())
            for r in t.get("replies") or []
        ):
            probs.append(f"{tag} declined without a reply giving the reason")
    return probs


# ----------------------------------------------------------------------------- anchors

def locate(text: str, target: dict) -> tuple[int, int] | None:
    """Offsets of the quote in the page text, or None if the anchor is stale."""
    exact = normalize(target.get("exact", ""))
    if not exact:
        return None
    hits = []
    start = 0
    while True:
        i = text.find(exact, start)
        if i < 0:
            break
        hits.append((i, i + len(exact)))
        start = i + 1
    if not hits:
        # The browser and the engine can disagree on a space at an inline boundary; a
        # whitespace-insensitive match still says the prose is there.
        squashed, index = _squash(text)
        j = squashed.find(exact.replace(" ", ""))
        if j < 0:
            return None
        return (index[j], index[j + len(exact.replace(" ", "")) - 1] + 1)
    if len(hits) == 1:
        return hits[0]
    prefix = normalize(target.get("prefix", ""))
    suffix = normalize(target.get("suffix", ""))
    for s, e in hits:
        if (not prefix or text[:s].endswith(prefix)) and (not suffix or text[e:].startswith(suffix)):
            return (s, e)
    return hits[0]


def _squash(text: str) -> tuple[str, list[int]]:
    chars, index = [], []
    for i, ch in enumerate(text):
        if ch != " ":
            chars.append(ch)
            index.append(i)
    return "".join(chars), index


def _stale_in(data: dict, text: str, states: tuple[str, ...]) -> list[dict]:
    """The threads in `states` whose quote is no longer on the page."""
    out = []
    for t in data.get("threads", []):
        tgt = t.get("target") if isinstance(t, dict) else None
        if not isinstance(tgt, dict) or t.get("state") not in states:
            continue
        if locate(text, tgt) is None:
            out.append(t)
    return out


def check_page(repo: Repo, sidecar: Path) -> list[str]:
    where = repo.rel(sidecar)
    try:
        data = load(sidecar)
    except AnnotationError as exc:
        return [str(exc)]
    probs = validate(data, where)
    page = page_for_sidecar(sidecar)
    if not page.is_file():
        return probs + [f"{where}: orphan — no page {page.name} beside it"]
    if data.get("page") and data["page"] != href_of(repo, page):
        probs.append(f"{where}: page href {data['page']!r} does not name {href_of(repo, page)!r}")
    text = page_text(page.read_text(encoding="utf-8", errors="replace"))
    # Only an open thread's anchor is load-bearing: an addressed or declined thread's passage
    # may well have changed — that is what acting on it looks like — and a noted flag's passage
    # gone means there is nothing left to disclose (stale_flags names it; the gate does not fail).
    # An open thread whose quote is gone means the page was edited around the comment: the failure.
    for t in _stale_in(data, text, ("open",)):
        tgt = t["target"]
        probs.append(
            f"{where}: thread {t.get('id')} has a STALE anchor — "
            f"{tgt.get('exact', '')[:60]!r} is no longer on the page"
        )
    return probs


def check_all(repo: Repo) -> list[str]:
    probs: list[str] = []
    if not repo.content.is_dir():
        return probs
    for sidecar in sorted(repo.content.rglob("*.annotations.json")):
        probs.extend(check_page(repo, sidecar))
    return probs


def stale_flags(repo: Repo) -> list[str]:
    """Noted flags whose passage has left the page — reported, never failed: withdraw them
    (`ckit annotations resolve --state withdrawn …`), or reopen the disclosure elsewhere."""
    notes: list[str] = []
    if not repo.content.is_dir():
        return notes
    for sidecar in sorted(repo.content.rglob("*.annotations.json")):
        try:
            data = load(sidecar)
        except AnnotationError:
            continue
        page = page_for_sidecar(sidecar)
        if not page.is_file():
            continue
        text = page_text(page.read_text(encoding="utf-8", errors="replace"))
        for t in _stale_in(data, text, ("noted",)):
            notes.append(f"{repo.rel(sidecar)}: flag {t.get('id')} is stale — "
                         f"{t['target'].get('exact', '')[:60]!r} is no longer on the page")
    return notes


# ----------------------------------------------------------------------------- ops

def add(repo: Repo, page_ref: str, body: str, *, author: str, target: dict | None,
        kind: str = "question", label: str | None = None) -> dict:
    if not body or not body.strip():
        raise AnnotationError("empty body")
    if not author or not author.strip():
        raise AnnotationError("missing author")
    if kind not in KINDS:
        raise AnnotationError(f"kind must be one of {KINDS}")
    page = resolve_page(repo, page_ref)
    if target is not None:
        if not isinstance(target, dict) or not normalize(str(target.get("exact", ""))):
            raise AnnotationError("target must carry a non-empty `exact` quote")
        target = {
            "type": "TextQuoteSelector",
            "exact": normalize(str(target["exact"])),
            "prefix": normalize(str(target.get("prefix", "")))[-CONTEXT:],
            "suffix": normalize(str(target.get("suffix", "")))[:CONTEXT],
        }
        text = page_text(page.read_text(encoding="utf-8", errors="replace"))
        if locate(text, target) is None:
            raise AnnotationError("quote not found on the page — select text that is on it")
    thread = {"id": _new_id(), "created": _now(), "author": author.strip(), "kind": kind,
              "state": "noted" if kind == "flag" else "open",
              "target": target, "body": body.strip(), "replies": []}
    if _clean_label(label):
        thread["label"] = _clean_label(label)
    with _LOCK:
        sc = sidecar_for(page)
        data = load(sc)
        data["version"] = 1
        data["page"] = href_of(repo, page)
        data.setdefault("threads", []).append(thread)
        save(sc, data)
    return thread


def reply(repo: Repo, page_ref: str, tid: str, body: str, *, author: str,
          state: str | None) -> dict:
    if state is not None and state not in STATES:
        raise AnnotationError(f"state must be one of {STATES}")
    if not author or not author.strip():
        raise AnnotationError("missing author")
    page = resolve_page(repo, page_ref)
    with _LOCK:
        sc = sidecar_for(page)
        data = load(sc)
        t = _find(data, tid)
        if state == "declined" and not (body and body.strip()):
            raise AnnotationError("declining needs a reason in the body")
        if state == "noted" and kind_of(t) != "flag":
            raise AnnotationError("only a flag can be noted — a question is open until it is answered")
        if body and body.strip():
            r = {"created": _now(), "author": author.strip(), "body": body.strip()}
            if state:
                r["state"] = state
            t.setdefault("replies", []).append(r)
        if state:
            t["state"] = state
        save(sc, data)
    return t


def set_state(repo: Repo, page_ref: str, tid: str, state: str, *, author: str) -> dict:
    return reply(repo, page_ref, tid, "", author=author, state=state)


def relabel(repo: Repo, page_ref: str, tid: str, *, author: str, kind: str | None = None,
            label: str | None = None) -> dict:
    """Change what a thread is (its kind) or how it is grouped (its label). A question that
    becomes a flag rests as noted; a flag that becomes a question is open. Recorded as a reply,
    so the sidecar says who reclassified it."""
    if kind is not None and kind not in KINDS:
        raise AnnotationError(f"kind must be one of {KINDS}")
    if kind is None and label is None:
        raise AnnotationError("nothing to change — give --kind and/or --label")
    if not author or not author.strip():
        raise AnnotationError("missing author")
    page = resolve_page(repo, page_ref)
    with _LOCK:
        sc = sidecar_for(page)
        data = load(sc)
        t = _find(data, tid)
        changes = []
        if kind is not None and kind != kind_of(t):
            t["kind"] = kind
            changes.append(f"kind → {kind}")
            if kind == "flag" and t.get("state") == "open":
                t["state"] = "noted"
                changes.append("state → noted")
            if kind == "question" and t.get("state") == "noted":
                t["state"] = "open"
                changes.append("state → open")
        if label is not None:
            clean = _clean_label(label)
            if clean != (t.get("label") or ""):
                if clean:
                    t["label"] = clean
                else:
                    t.pop("label", None)
                changes.append(f"label → {clean or '(none)'}")
        if changes:
            t.setdefault("replies", []).append({"created": _now(), "author": author.strip(),
                                                "body": "relabelled: " + " · ".join(changes)})
            save(sc, data)
    return t


def _matches(t: dict, page_href: str, *, page: str | None, kind: str | None, label: str | None,
             by: str | None, states: tuple[str, ...]) -> bool:
    if t.get("state") not in states:
        return False
    if page and page_href != page:
        return False
    if kind and kind_of(t) != kind:
        return False
    if label and (t.get("label") or "") != label:
        return False
    if by and not str(t.get("author", "")).startswith(by):
        return False
    return True


def resolve(repo: Repo, *, state: str, author: str, body: str = "", page: str | None = None,
            kind: str | None = None, label: str | None = None, by: str | None = None,
            states: tuple[str, ...] = LIVE) -> list[dict]:
    """Move every live thread the filters select to `state` at once, with one reply each — the
    way an owner keeps every worked example an agent flagged, or withdraws every stale one.
    At least one filter, so nothing is resolved by accident; declining still needs its reason."""
    if state not in STATES:
        raise AnnotationError(f"state must be one of {STATES}")
    if not (page or kind or label or by):
        raise AnnotationError("resolve needs a filter: --page, --kind, --label or --by")
    if state == "declined" and not body.strip():
        raise AnnotationError("declining needs a reason in the body")
    if not author or not author.strip():
        raise AnnotationError("missing author")
    if page:
        page = href_of(repo, resolve_page(repo, page))
    done: list[dict] = []
    if not repo.content.is_dir():
        return done
    for sc in sorted(repo.content.rglob("*.annotations.json")):
        data = load(sc)
        href = data.get("page") or href_of(repo, page_for_sidecar(sc))
        hits = [t for t in data.get("threads", []) if isinstance(t, dict)
                and _matches(t, href, page=page, kind=kind, label=label, by=by, states=states)]
        for t in hits:
            reply(repo, href, t["id"], body, author=author, state=state)
            done.append({"page": href, "id": t["id"]})
    return done


def prune(repo: Repo, *, older_than: int = 30, page: str | None = None) -> list[dict]:
    """Drop closed threads — addressed, declined, withdrawn — untouched for `older_than` days
    from their sidecars, so a much-reviewed page's file does not grow forever. Git history keeps
    what was said. Only a committed sidecar is pruned, so nothing is lost that git cannot bring
    back; live threads are never touched."""
    from . import organize  # lazily: organize imports this module

    if older_than < 0:
        raise AnnotationError("--older-than takes a number of days")
    if page:
        page = href_of(repo, resolve_page(repo, page))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than)).strftime("%Y-%m-%dT%H:%M:%SZ")
    removed: list[dict] = []
    if not repo.content.is_dir():
        return removed
    for sc in sorted(repo.content.rglob("*.annotations.json")):
        data = load(sc)
        href = data.get("page") or href_of(repo, page_for_sidecar(sc))
        if page and href != page:
            continue
        old = [t for t in data.get("threads", []) if isinstance(t, dict)
               and t.get("state") in CLOSED and _last_touch(t) <= cutoff]
        if not old:
            continue
        loose = organize._uncommitted(repo, [sc])
        if loose is None:
            raise AnnotationError("not a git work tree — `ckit annotations prune` drops only what git can bring back")
        if loose:
            raise AnnotationError(f"{repo.rel(sc)} is not committed, so nothing could bring its threads back — commit it first")
        keep = [t for t in data.get("threads", []) if t not in old]
        data["threads"] = keep
        save(sc, data)
        removed.extend({"page": href, "id": t.get("id"), "state": t.get("state")} for t in old)
    return removed


# ----------------------------------------------------------------------------- reads

def list_threads(repo: Repo, *, state: str | None = "open", kind: str | None = None) -> list[dict]:
    """`state`: one state, "live" (open or noted), or "all" / None."""
    out: list[dict] = []
    if not repo.content.is_dir():
        return out
    wanted = LIVE if state == "live" else None if state in (None, "all") else (state,)
    for sc in sorted(repo.content.rglob("*.annotations.json")):
        data = load(sc)
        for t in data.get("threads", []):
            if wanted is not None and t.get("state") not in wanted:
                continue
            if kind and kind_of(t) != kind:
                continue
            out.append({"page": data.get("page") or href_of(repo, page_for_sidecar(sc)),
                        "sidecar": repo.rel(sc), **t})
    return out


def build_index(repo: Repo) -> dict:
    """`content/threads.json`: every thread, with its page's title and whether its anchor still
    holds — what the review page and the home page read. Generated; never hand-edited."""
    threads: list[dict] = []
    counts = {s: 0 for s in STATES}
    if repo.content.is_dir():
        for sc in sorted(repo.content.rglob("*.annotations.json")):
            try:
                data = load(sc)
            except AnnotationError:
                continue
            page = page_for_sidecar(sc)
            href = data.get("page") or href_of(repo, page)
            html = page.read_text(encoding="utf-8", errors="replace") if page.is_file() else ""
            text = page_text(html) if html else ""
            title = title_of(html, page.stem) if html else page.stem
            for t in data.get("threads", []):
                if not isinstance(t, dict):
                    continue
                st = t.get("state")
                if st in counts:
                    counts[st] += 1
                tgt = t.get("target") if isinstance(t.get("target"), dict) else None
                row = {"page": href, "title": title, "id": t.get("id"), "created": t.get("created"),
                       "author": t.get("author"), "kind": kind_of(t), "label": t.get("label") or "",
                       "state": st, "quote": tgt.get("exact", "") if tgt else "",
                       "body": t.get("body", ""), "replies": t.get("replies") or []}
                if tgt and st in LIVE:
                    row["stale"] = locate(text, tgt) is None if text else True
                threads.append(row)
    return {"version": 1, "counts": counts, "threads": threads}


def apply(repo: Repo, req: dict) -> dict:
    """The server's single write entry point."""
    if not isinstance(req, dict):
        raise AnnotationError("request must be a JSON object")
    op = req.get("op")
    page = str(req.get("page", ""))
    author = str(req.get("author", ""))
    if op == "add":
        return {"ok": True, "thread": add(repo, page, str(req.get("body", "")),
                                         author=author, target=req.get("target"),
                                         kind=str(req.get("kind") or "question"),
                                         label=req.get("label"))}
    if op == "reply":
        return {"ok": True, "thread": reply(repo, page, str(req.get("id", "")),
                                           str(req.get("body", "")), author=author,
                                           state=req.get("state"))}
    if op == "state":
        return {"ok": True, "thread": set_state(repo, page, str(req.get("id", "")),
                                               str(req.get("state", "")), author=author)}
    if op == "relabel":
        return {"ok": True, "thread": relabel(repo, page, str(req.get("id", "")), author=author,
                                             kind=req.get("kind"), label=req.get("label"))}
    if op == "resolve":
        return {"ok": True, "resolved": resolve(repo, state=str(req.get("state", "")), author=author,
                                               body=str(req.get("body") or ""),
                                               page=page or None, kind=req.get("kind") or None,
                                               label=req.get("label") or None, by=req.get("by") or None)}
    raise AnnotationError(f"unknown op {op!r}")

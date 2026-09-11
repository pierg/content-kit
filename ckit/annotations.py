"""Session-free page annotations.

A human marks up a rendered page in the browser; the server writes a sidecar beside the page;
any agent later — fresh context, another session, another clone — reads the open threads,
addresses them, replies in the thread, and flips the state. Nothing live joins the two halves,
and nothing needs to be running for an annotation to survive.

Sidecar: `<page>.annotations.json` — `index.annotations.json` beside an `index.html`,
`<slug>.annotations.json` beside a flat page. Committed, so feedback is part of the record.

    {
      "version": 1,
      "page": "/content/concepts/ic3/",
      "threads": [
        {
          "id": "t-20260911-3f9a1c", "created": "2026-09-11T08:12:00Z", "author": "pier",
          "state": "open",                      # open · addressed · declined · withdrawn
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
quote can no longer be found on its page the gate fails loud — a dropped comment is not a
resolved one.
"""

from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from .paths import Repo
from .text import normalize, page_text

STATES = ("open", "addressed", "declined", "withdrawn")
CONTEXT = 32
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
    for t in data.get("threads", []):
        tgt = t.get("target") if isinstance(t, dict) else None
        # Only an open thread's anchor is load-bearing: an addressed or declined thread's passage
        # may well have changed — that is what acting on it looks like. An open thread whose
        # quote is gone means the page was edited around the comment, which is the failure.
        if not isinstance(tgt, dict) or t.get("state") != "open":
            continue
        if locate(text, tgt) is None:
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


# ----------------------------------------------------------------------------- ops

def add(repo: Repo, page_ref: str, body: str, *, author: str, target: dict | None) -> dict:
    if not body or not body.strip():
        raise AnnotationError("empty body")
    if not author or not author.strip():
        raise AnnotationError("missing author")
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
    thread = {"id": _new_id(), "created": _now(), "author": author.strip(), "state": "open",
              "target": target, "body": body.strip(), "replies": []}
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


def list_threads(repo: Repo, *, state: str | None = "open") -> list[dict]:
    out: list[dict] = []
    if not repo.content.is_dir():
        return out
    for sc in sorted(repo.content.rglob("*.annotations.json")):
        data = load(sc)
        for t in data.get("threads", []):
            if state in (None, "all") or t.get("state") == state:
                out.append({"page": data.get("page") or href_of(repo, page_for_sidecar(sc)),
                            "sidecar": repo.rel(sc), **t})
    return out


def apply(repo: Repo, req: dict) -> dict:
    """The server's single write entry point."""
    if not isinstance(req, dict):
        raise AnnotationError("request must be a JSON object")
    op = req.get("op")
    page = str(req.get("page", ""))
    author = str(req.get("author", ""))
    if op == "add":
        return {"ok": True, "thread": add(repo, page, str(req.get("body", "")),
                                         author=author, target=req.get("target"))}
    if op == "reply":
        return {"ok": True, "thread": reply(repo, page, str(req.get("id", "")),
                                           str(req.get("body", "")), author=author,
                                           state=req.get("state"))}
    if op == "state":
        return {"ok": True, "thread": set_state(repo, page, str(req.get("id", "")),
                                               str(req.get("state", "")), author=author)}
    raise AnnotationError(f"unknown op {op!r}")

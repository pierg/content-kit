"""The ladder dashboard manifest: the record as a status board — never authored.

The chronicle (chronicle.py) renders the record as a *timeline* — how we got here. The
ladder renders it as a *status board* — what is true now: the open questions and their kill
criteria, the experiment pipeline, findings by status, the claims they support, and the
recent decisions. Same record, a second view.

It is generated exactly like the chronicle: `ckit lint` / `ckit nav` write
`content/ladder.json`, `ckit check` fails if it drifts, and `/shell/dashboard.html` renders
it. Nobody writes it, so it cannot drift from the files it points at.

Opt-in, per repo. A repo turns the dashboard on in kit.json:

    "home": "dashboard"        # the dashboard is the front door served at /
                               # (or "dashboard": true to generate it without changing the door)

When it is off, no manifest is generated and every existing repo's `ckit check` is byte-for-byte
unchanged — the feature is inert until a repo asks for it.

`home` may instead name an authored content page (see `paths.home_page`), making that page the
front door while the dashboard stays a click away — such a repo sets `"dashboard": true`
alongside its page `home` to keep `ladder.json` (and the dashboard it feeds) generated.

What is generic (any repo) vs. extractor-supplied:

  now         generic — the top of the first record file whose title says "State"
  decisions   generic — the chronicle's own decision / kill / pivot events, most recent first
  experiments generic — the chronicle's experiment cards (from an extractor's extract())
  questions   } an extractor may add `ladder(root, cfg) -> {questions, findings, claims}` for a
  findings    } lab's own vocabulary (Q-<n> / F-<n> / C-<n>); when none does, these stay empty
  claims      } and the dashboard simply hides those panels.

Schema (content/ladder.json):
    now?        {title, summary, href, path}
    questions[] {id, title, status, kill, href}
    experiments[] (as in chronicle.json)
    findings[]  {id, title, status, href}
    claims[]    {id, title, rests_on[], href}
    decisions[] {date, kind, title, summary, href}
    counts      {findings:{<status>:n}, experiments:{<status>:n}, questions:{<status>:n}, claims:n}
"""

from __future__ import annotations

from pathlib import Path

from . import chronicle
from .paths import Repo

DECISION_KINDS = ("decision", "kill", "pivot")
DECISION_LIMIT = 16


def enabled(repo: Repo) -> bool:
    """The dashboard is opt-in and needs a record to draw from."""
    cfg = repo.cfg
    opted = cfg.get("home") == "dashboard" or bool(cfg.get("dashboard"))
    return opted and chronicle.enabled(repo)


def _strip_status_suffix(title: str) -> str:
    for w in ("LIVE", "DRAFT", "HISTORICAL", "FROZEN", "PARKED", "RETIRED"):
        marker = f" — {w}"
        if title.endswith(marker):
            return title[: -len(marker)].strip()
    return title


def _now(repo: Repo) -> dict | None:
    """The current phase — the top of the first record file whose title says State."""
    for r in chronicle.record_catalog(repo):
        if "state" not in r["title"].lower():
            continue
        p = repo.root / r["path"]
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return None
        title, i = _strip_status_suffix(r["title"]), 0
        for i, ln in enumerate(lines):
            if ln.startswith("# "):
                break
        buf: list[str] = []
        for ln in lines[i + 1:]:
            s = ln.strip()
            if s.startswith("#"):
                break
            if not s or s.startswith("**Status"):
                if buf:
                    break
                continue
            buf.append(s)
            if len(buf) >= 2:
                break
        from .text import normalize
        summary = normalize(" ".join(buf).replace("*", "").replace("`", ""))[:320]
        return {"title": title, "summary": summary, "href": r["href"], "path": r["path"]}
    return None


def _ladder_from_extractors(repo: Repo) -> dict:
    out: dict[str, list] = {"questions": [], "findings": [], "claims": []}
    for mod in chronicle.load_extractors(repo):
        fn = getattr(mod, "ladder", None)
        if not callable(fn):
            continue
        got = fn(repo.root, repo.cfg) or {}
        for key in out:
            for item in got.get(key) or []:
                if isinstance(item, dict) and item.get("id"):
                    out[key].append(item)
    return out


def _counts(findings: list, experiments: list, questions: list, claims: list) -> dict:
    def by_status(rows: list) -> dict:
        tally: dict[str, int] = {}
        for r in rows:
            k = (r.get("status") or "—")
            tally[k] = tally.get(k, 0) + 1
        return tally

    return {
        "findings": by_status(findings),
        "experiments": by_status(experiments),
        "questions": by_status(questions),
        "claims": len(claims),
    }


def build(repo: Repo, chron: dict | None = None) -> dict:
    chron = chron if chron is not None else chronicle.build(repo)
    lab = _ladder_from_extractors(repo)
    decisions = [
        {"date": e["date"], "kind": e["kind"], "title": e["title"],
         "summary": e.get("summary", ""), "href": e["href"]}
        for e in chron["events"] if e["kind"] in DECISION_KINDS
    ][:DECISION_LIMIT]
    findings, questions, claims = lab["findings"], lab["questions"], lab["claims"]
    experiments = chron["experiments"]
    return {
        "version": 1,
        "now": _now(repo),
        "questions": questions,
        "experiments": experiments,
        "findings": findings,
        "claims": claims,
        "decisions": decisions,
        "counts": _counts(findings, experiments, questions, claims),
    }

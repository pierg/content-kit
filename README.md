# content-kit — LIVE

**One contract for reader-facing content, in any repo, about any topic.** An agent picks a genre; the genre carries a structure, a voice and a component vocabulary from this one shared source; the page lands where the genre says and the gate checks what the contract says. A human annotates the rendered page in the browser; the notes are written beside the page and committed; any agent later picks them up — no session joins the two halves.

The vision and the reasoning behind each decision are in [`VISION.md`](VISION.md). This file is how to use it.

## Two installs

```bash
# the engine — once per machine; `git pull` here is the upgrade
bash install-engine.sh                     # symlinks bin/ckit into ~/.local/bin

# the rules — into each repo; vendored, pinned, visible in-repo
bash install.sh /path/to/repo --name "My library" --port 5180
cd /path/to/repo && make check && make docs
```

The repo records the engine version it was checked against (`"ckit"` in `lab.json`); `ckit check` fails loud on a mismatch, so an upgrade is accepted per repo, deliberately, by re-running `install.sh`. A lab that vendors [lab-kit](../lab-kit) gets all of this through lab-kit's own `install.sh`.

## What a repo looks like

```
<repo>/
  lab.json                 name · content dir · port · ckit pin · genre extensions
  Makefile                 make check · make docs · make down · make kit-verify · make kit-sync
  kit/                     ← vendored from here, pinned in kit/PIN, never edited in place
    shell/                 lib.css · lib.js · math.js · annotate.js · search.html · COMPONENTS.md · skeletons/ · vendor/katex
    genres/                GENRES.md (the voice) · genres.json (what is checked)
    craft/                 how to build a comparison · diagram · table · timeline · code · figure
    skills/present         author a page or a paper        → symlinked at .claude/skills/present
    skills/address         act on a reader's annotations   → symlinked at .claude/skills/address
    verify.sh · tools/kit_hash.py
  content/
    notes/ concepts/ entries/ books/ hubs/ projects/ papers/ related/
    catalog.json · search-index.json · backlinks.json          generated — never hand-edited
    <page>.annotations.json                                   a reader's threads, committed
```

## The engine

| Command | Does |
|---|---|
| `ckit check` | the content gate: pin · shell present · committed indices equal discovery (stale fails, never rewritten) · form + genre + annotation lint · books |
| `ckit lint [paths]` | the lint alone, at authoring time; regenerates `nav.json` / catalog / search index / backlinks (`--no-nav` to only lint) |
| `ckit new <genre> <slug>` | scaffold from the genre's skeleton, print its voice card |
| `ckit genres` | the genres this repo knows — core plus its `lab.json` extensions |
| `ckit up` · `down` · `status` · `serve` | the reader server on the repo's port |
| `ckit annotations list · show · add · reply · state · check` | the session-free review loop |
| `ckit selftest` | the engine's own gate: planted fixtures with known answers |
| `/shell/record.html?p=<file.md>` · `/shell/chronicle.html` | the record, rendered — and the record as a **story** (default: only tagged headings and load-bearing events, grouped by month, prose-first) with a `Timeline` view for every dated heading and an `Experiments` view; `content/chronicle.json` is generated, see below |

Stdlib Python ≥ 3.10; node for book verification. No build step, no dependencies, no network.

## The layers, and what checks each

| Layer | Home | Checked by |
|---|---|---|
| **Form** — tokens, components | `shell/` | lint: shell link, no hex, known classes |
| **Structure** — where each genre lives | `ckit/genres.json` | lint: a page outside any genre is an error |
| **Voice** — how each genre reads | `genres/GENRES.md` | lint proxies: status line, word bounds, no `<h2>` in a note, citation-free `defn`, declared forward refs, project lifecycle meta |
| **Craft** — how a block is built | `craft/` | a reviewer; lint checks only that the vocabulary is the shell's |
| **Indices** — catalog, search, backlinks | generated | lint regenerates; a committed index is never hand-edited |
| **Review** — annotate, then address, asynchronously | `shell/annotate.js` · `ckit annotations` | lint: sidecars validate; an open thread's quote is still on its page |
| **Pin** — which kit, which engine | `kit/PIN` · `lab.json` | `make kit-verify` · `ckit check` |
| **Record** — how the current direction was reached | the repo's own markdown record, declared in `lab.json` `record`; rendered by the viewer, never copied | `ckit check`: the chronicle index is current |

## The record and the chronicle

`content/` shows only the current direction. How it got there is the repo's append-only markdown record — a logbook, decisions, pre-registrations — and the kit renders it rather than re-authoring it: `lab.json` declares `"record": ["HISTORY.md", "record/", "ops/", "experiments/*/PROBE.md"]`, the sidebar lists it, and `/shell/record.html?p=<file>` renders any of it in the shell (client-side, `marked`, vendored). The **chronicle** is a generated timeline over that record: every dated heading (`### 2026-09-11 — [pivot] …`, tags `pivot · kill · decision · lesson · instrument · result`, untagged = entry) becomes an event linking back to its file; a repo with its own vocabulary declares an extractor (`"chronicle": {"extractors": ["kit/tools/chronicle_lab.py"]}` — lab-kit's adds PROBE locks, findings anchored per experiment, claims, missions). `ckit lint` regenerates `content/chronicle.json`; `ckit check` fails if it is stale; nobody edits it.

## Develop

```bash
make check      # selftest (20 planted cases, 9 clean genres) + e2e (install · gate · serve · annotate · drift · pin)
```

A change to a check ships with a fixture designed to break it, or it is not a check. Instrument changes land through a PR; the two labs and the library that vendor this kit re-sync deliberately (`make kit-sync`) and re-pin.

## CI

The repo's gate needs `ckit` on PATH. In a workflow: check out this repo beside the content repo and `export PATH="$PWD/content-kit/bin:$PATH"`, or `pip install git+<this repo>@<commit>` where pip is available — pin the commit either way, matching `lab.json`.

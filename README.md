# content-kit — LIVE

**A page contract for agent-written knowledge.** An agent picks a genre; the genre carries a structure, a voice and a component vocabulary; the page lands where the genre says; a gate checks what can be checked. A human annotates the rendered page in the browser, and any agent later — in any session, on any clone — picks the notes up and addresses them. Zero build, stdlib Python, hand-authored HTML in one shared shell.

**0.5.0.dev1 (unreleased):** a reading shell — the library organised by topic, a reading measure, a ⌘K palette, link peeks, a page rail, a generated home page, dates and tags in the catalog, optional full text through Pagefind — the tools to reorganise a library without breaking it (every internal link checked, `ckit topics`, `ckit tags`, `ckit mv`, `ckit rm`, the `/curate` skill), and a review loop that runs both ways from the browser. See `CHANGELOG.md`.

**Documentation:** <https://pierg.github.io/content-kit/> — itself a content-kit library. The reasoning behind each decision is in [`VISION.md`](VISION.md); how a repo's record and pages stay true together is in [`DESIGN-living-content.md`](DESIGN-living-content.md).

## How it works

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/figures/how-it-works-dark.svg">
  <img alt="One loop, no live connection: an agent reads the rules vendored in the repo and writes the page in its genre's voice; the engine's gate checks it and serves it; a reader annotates it in the browser; the note waits in a committed sidecar until any later agent picks it up" src="assets/figures/how-it-works.svg" width="800">
</picture>
</p>

**The page.** Where a page lives is its genre — `content/concepts/<slug>/index.html` is a concept, `content/notes/<slug>.html` a note — and the genre fixes its shape (a skeleton to start from), its voice (the register, the assumed reader, the forbidden moves, in `kit/genres/GENRES.md`) and what the gate checks about it. Every page is HTML its author wrote, served exactly as written, in one shared shell that gives it its tokens, its chrome, its dark mode and its search. There is no build step and no second format: the file in the repo is the page.

**The gate.** `ckit check` runs in seconds, offline, identically on every machine and in CI: the engine pin, the vendored shell, the generated indices (catalog, search, backlinks, threads, a book's nav), the lint (form, links, prose, tags, genre, annotations) and each book. It reports every problem in one run and repairs none of them. A rule nothing checks is a suggestion, so each rule here either has a check with a planted fixture or says plainly that it is judgment.

**The review loop.** Serve the library and **✎ Annotate** appears on every page. A reader selects a passage and leaves a *question*; it lands beside the page as `<page>.annotations.json`, anchored to the quoted text, and waits. Any agent later — no session shared, no server running in between — runs `/address`, edits the page, and replies in the thread with a state. The loop runs the other way too: an agent that writes beyond its source leaves a *flag* on the passage, which rests as `noted` and asks nothing until the reader keeps it or asks for a change, from the page's panel or a whole group at once from **Review** (`/shell/review.html`). The gate refuses to let a page move out from under an open thread.

Nothing live joins the halves. The page, the rules and the notes are files in the repository; the only running process is the engine, and it is installed once.

## How it reaches a repository, and stays current

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/figures/how-it-stays-current-dark.svg">
  <img alt="Once upstream, once per machine, a pinned copy per repo: the engine is installed once and never copied; the kit is copied into each repository, pinned by a hash and by the engine version, and changed only upstream; a layer adds its own rules beside it; make check fails when either pin is off, and make kit-sync moves them" src="assets/figures/how-it-stays-current.svg" width="880">
</picture>
</p>

content-kit is two halves, and they travel differently.

- **The engine** (`ckit/`, the `ckit` command) is code, so it is installed **once per machine** — a release with `uv tool install`, or a checkout's `bin/ckit` on PATH — and never copied into a repository. One engine lints, checks and serves every library on the machine.
- **The kit** (`shell/`, `genres/`, `craft/`, `skills/`) is rules an agent must be able to read *in the repository it is working in*, with nothing to resolve elsewhere, so `ckit init` **copies it into `kit/`**, links the skills into `.claude/skills/` (`/present`, `/address`, `/curate` are symlinks into `kit/skills/`), and **pins** both halves: `kit/PIN` records where the copy came from (`source content-kit <url> <commit>`) and a hash of the whole tree; `kit.json` records the engine version the repo was checked against (`"ckit": "0.5.0.dev1"`).

Two rules keep the copies honest, and both are checked. **`kit/` is never edited in place**: `make check` recomputes the tree hash and fails loud on drift, because a copy edited locally is a copy silently different from every other repo's. **An engine upgrade changes no repository until that repository moves its pin**: `ckit check` fails on an engine mismatch, and the deliberate fix is `ckit init .` (or `make kit-sync`, which re-vendors from every pinned source and re-pins). A change to the kit therefore goes upstream first, gets its fixtures there, and reaches each repository as a reviewable diff of `kit/` and `kit/PIN`.

A **layer** — [lab-kit](https://github.com/pierg/lab-kit), the record discipline for agent-run research labs; [folio](https://github.com/pierg/folio), a personal library with topics, a journal and flashcard revision — rides the same path: its installer runs `ckit init`, vendors its own rules beside the kit under `kit/<layer>/`, adds its own `source` line to `kit/PIN`, and registers what it adds in `kit.json` through ten extension points (`genres`, `checks`, `generators`, `chronicle.extractors`, `shell_pages`, `links`, `refs`, `theme`, `classes`, `indices`). The engine knows no layer; `make kit-sync` re-vendors every source in `kit/PIN`, the layer's skills included.

## Five minutes

```bash
uv tool install git+https://github.com/pierg/content-kit@v0.4.0     # the engine: `ckit`
ckit init my-library --name "My library"                            # vendor the kit, scaffold the repo, pin both
cd my-library
ckit new concept feedback-loop --title "Feedback loop"             # a page, from its genre's skeleton
$EDITOR content/concepts/feedback-loop/index.html                  # write it in the genre's voice
ckit lint && make check                                            # regenerate the indices, run the gate
make docs                                                          # read it at http://127.0.0.1:5180/
```

Python ≥ 3.10, no dependencies; node for book verification. No `uv`? `git clone` this repo and run `bash install-engine.sh`, which puts the checkout's `bin/ckit` on PATH; from then on `git pull` is the engine upgrade, and each repo's pin decides when to accept it.

## What a repo looks like

```
<repo>/
  kit.json          name · content dir · port · engine pin · extensions
  Makefile          make check · docs · site · kit-verify · kit-sync
  kit/              vendored by `ckit init`, pinned in kit/PIN, never edited in place
    PIN             source <kit> <url> <commit> · hash <sha256 of the tree>
    shell/          lib.css · lib.js · search · review · record viewer · chronicle · annotate · skeletons/
    genres/         GENRES.md (the voice) · genres.json (what is checked)
    craft/          how to build a comparison · diagram · table · timeline · code · figure
    skills/         /present (author a page) · /address (act on annotations) · /curate (organise)
    verify.sh       make kit-verify · make kit-sync
  .claude/skills/   symlinks into kit/skills/ (and a layer's), so an agent session finds them
  content/          notes/ concepts/ entries/ books/ hubs/ projects/ papers/ related/
                    catalog.json · search-index.json · backlinks.json · threads.json — generated, never hand-edited
                    <page>.annotations.json — written by the browser or `ckit annotations`, committed
```

## The engine

| Command | Does |
|---|---|
| `ckit init [repo]` | vendor the kit into a repo, scaffold what it lacks, pin both |
| `ckit new <genre> <slug> [--topic --tags]` | scaffold a page from its genre's skeleton, on its topic; print its voice card |
| `ckit lint [paths]` | form (links, prose, tags) + genre + annotation lint; regenerate the indices |
| `ckit check` | the gate: engine pin · extension points · indices current · lint · books — every problem in one run |
| `ckit topics` · `tags` | the topics (label · hub · pages) and tags; `add` · `rename` · `merge` · `assign` reorganise them |
| `ckit mv` · `rm --to` | move or retire a page: links rewritten, sidecar and dates carried, the old address redirected |
| `ckit unwrap [paths]` | join hard-wrapped prose — one paragraph per line |
| `ckit serve` · `up` · `down` · `status` | the reader, on the repo's port |
| `ckit export [--base /repo/]` | the site as static files, for any static host |
| `ckit annotations …` | the session-free review loop: list · show · add · reply · state · relabel · resolve · prune · check |
| `ckit genres` · `where` · `selftest` · `version` | the genre table · the kit source · the engine's own gate |

## Develop

```bash
make check      # selftest (planted fixtures) · e2e (init · gate · plugins · serve · annotate · export · drift · pin) · wheel
```

A change to a check ships with a fixture designed to break it, or it is not a check. The README's figures are derived from the pages that own them (`python3 tools/readme_figures.py`). See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CHANGELOG.md`](CHANGELOG.md).

MIT licensed.

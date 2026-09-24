# content-kit — LIVE

**A page contract for agent-written knowledge.** An agent picks a genre; the genre carries a structure, a voice and a component vocabulary; the page lands where the genre says; a gate checks what can be checked. A human annotates the rendered page in the browser, and any agent later — in any session, on any clone — picks the notes up and addresses them. Zero build, stdlib Python, hand-authored HTML in one shared shell.

**0.5.0.dev1 (unreleased):** a reading shell — the library organised by topic, a reading measure, a ⌘K palette, link peeks, a page rail, a generated home page, dates and tags in the catalog, optional full text through Pagefind — and the tools to reorganise a library without breaking it: every internal link checked, `ckit topics`, `ckit tags`, `ckit mv`, `ckit rm`, and the `/curate` skill. See `CHANGELOG.md`.

**Documentation:** <https://pierg.github.io/content-kit/> — itself a content-kit library. The reasoning behind each decision is in [`VISION.md`](VISION.md); how a repo's record and pages stay true together is in [`DESIGN-living-content.md`](DESIGN-living-content.md).

## Five minutes

```bash
uv tool install git+https://github.com/pierg/content-kit@v0.4.0     # the engine: `ckit`
ckit init my-library --name "My library"                            # vendor the kit, scaffold the repo
cd my-library
ckit new concept feedback-loop --title "Feedback loop"             # a page, from its genre's skeleton
$EDITOR content/concepts/feedback-loop/index.html                  # write it in the genre's voice
ckit lint && make check                                            # regenerate the indices, run the gate
make docs                                                          # read it at http://127.0.0.1:5180/
```

In the browser, **✎ Annotate** (bottom right) lets you select a passage and leave a note. It lands beside the page as `index.annotations.json`. Later, an agent runs `ckit annotations list` and the `/address` skill, acts on each thread and replies in it — nothing live joins the two halves. The loop runs the other way too: an agent flags what it wrote beyond its source, and you keep it or ask for a change from the page's panel, or a whole group at once from **Review** (`/shell/review.html`).

Python ≥ 3.10, no dependencies; node for book verification. No `uv`? `git clone` this repo and run `bash install-engine.sh`, which puts the checkout's `bin/ckit` on PATH.

## What a repo looks like

```
<repo>/
  kit.json          name · content dir · port · engine pin · extensions
  Makefile          make check · docs · site · kit-verify · kit-sync
  kit/              vendored by `ckit init`, pinned in kit/PIN, never edited in place
    shell/          lib.css · lib.js · search · record viewer · chronicle · annotate · skeletons/
    genres/         GENRES.md (the voice) · genres.json (what is checked)
    craft/          how to build a comparison · diagram · table · timeline · code · figure
    skills/         /present (author a page) · /address (act on annotations)
  content/          notes/ concepts/ entries/ books/ hubs/ projects/ papers/ related/
                    catalog.json · search-index.json · backlinks.json — generated, never hand-edited
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

## Layers

A layer is a repo whose installer, given only `ckit`, vendors its own rules beside the kit and registers them in `kit.json` through ten extension points — `genres`, `checks`, `generators`, `chronicle.extractors`, `shell_pages`, `links`, `refs`, `theme`, `classes`, `indices`. Two exist: [lab-kit](https://github.com/pierg/lab-kit), the record discipline for agent-run research labs, and [folio](https://github.com/pierg/folio), a personal library with topics, a journal and flashcard revision. The engine knows neither.

## Develop

```bash
make check      # selftest (planted fixtures) · e2e (init · gate · plugins · serve · annotate · export · drift · pin) · wheel
```

A change to a check ships with a fixture designed to break it, or it is not a check. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CHANGELOG.md`](CHANGELOG.md).

MIT licensed.

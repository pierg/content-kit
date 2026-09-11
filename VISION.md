# content-kit — the vision

**Status: LIVE** — the vision this repo realizes. Written 2026-09-10 against the audit in *Where we actually are*; built 2026-09-11 (see *Realization* at the end, and `README.md` for use). Supersedes nothing.

Any agent, in any repo, can add content about any topic, and it comes out belonging there — because the genre it picks carries a **structure**, a **voice**, and a **component vocabulary** from one shared source, and cites assets from one shared store. A human reads it in a browser, annotates it in place, and any agent later — fresh context, different session, different machine — picks up those annotations and addresses them. Nothing live connects the two halves.

## The design law

A layer without a mechanical check is a suggestion, and suggestions drift.

This is not a principle borrowed from elsewhere; it is what this repo's own output demonstrates. Across `proof-harness-lab`, `design-space-lab` and `folio` — 53 HTML pages, one vendored shell, one authoring skill that is byte-identical in all three — form conformance is **100%** and status-banner conformance is **8/17** in the one repo where it is neither linted nor locally exempt. `engine/lint.py` checks the shell contract, so the shell contract holds. `tools/ladder_lint.py:376` checks status banners only for `record/*.md`, `ops/*.md` and `content/papers/*/main.md`, so content pages drifted.

Every layer below is therefore specified with the question *what checks it?* answered, or explicitly marked as unchecked-by-design.

## Three products, not one

- **A · Authoring** — how an agent produces a page that looks and reads right. Mostly built; missing Voice, Craft, and a general asset layer.
- **B · Review** — how a human annotates a rendered page and any agent later addresses it, asynchronously. Greenfield. The genuinely novel piece.
- **C · Packaging** — how A and B reach a repo. A decision, not a build.

## Where we actually are

| Layer | Decides | Today |
|---|---|---|
| **Form** | tokens, components, no per-page reinvention | built — `shell/lib.css` (393 lines), `shell/COMPONENTS.md` (176 lines), lint-enforced |
| **Structure** | which genres exist, where each lives | built — 6 skeletons: note, chapter, hub, entry, concept, project |
| **Voice** | how each genre *reads* | **missing entirely** |
| **Craft** | how to lay out a comparison, diagram, table, timeline | **missing entirely** |
| **Assets** | one store many genres cite | started — `assets/figures/` split as format-agnostic at `1bae59f`; not yet general, and absent from folio |
| **Indices** | catalog, search, backlinks | built — generated, never hand-edited |
| **Review** | async annotate → agent addresses | **missing entirely** |
| **Gate** | what is mechanically checked | form only |

Two genres the vision implies and that do not exist: **paper** has a directory but no skeleton, and **related-works** lives only as `RELATED.md` in one lab — markdown, outside `content/`, invisible to the shell and to search.

## Decisions taken

1. **Annotations are a committed sidecar.** The browser posts to the existing `make docs` server, which writes a comments file beside the page. Any agent on any clone sees them; feedback becomes auditable. Requires a pruning policy for resolved threads.
2. **Hybrid packaging.** Shell and skeletons stay vendored and visible per repo; engine, lint and annotation server install once and update in one place.
3. **Core genre set plus per-repo extensions.** The core is linted everywhere; a repo declares extra genres in its config with their own skeleton and voice rules.

## The extraction

The content system is separable from the lab system, and `folio` already proves it — library mode, `"ladder": "off"`, no `record/`, no findings, yet the same shell and the same pages. So:

    content-kit   shell · genres · voice · craft · assets · indices · annotation · content gate
    lab-kit       content-kit + record ladder + experiments + fleet + discipline + lab gate

A lab vendors lab-kit and gets content-kit with it. `folio` and any other repo vendor content-kit alone. That is exactly the split the three repos already exhibit informally.

**One tension to accept deliberately.** `README.md` states the vendoring principle: everything local "so an agent session opened there has every capability and every rule locally, with no sibling repo to resolve first." Decision 2 moves the engine out of that set, trading some of that self-containment for one update point across N repos. The mitigation is that the *rules* (shell, skeletons, genre and voice specs) stay vendored and readable in-repo — only the *executable* moves — and the installed engine's version is pinned in `lab.json` so a repo still declares what it was checked against.

## The Voice layer

The highest-value missing piece, and the thing that makes this more than a CSS framework. Structure says where a page lives; voice says how it reads. Each genre gets a register, a length discipline, an assumed reader, and a set of forbidden moves.

| Genre | Register | Assumed reader | Forbidden |
|---|---|---|---|
| **note** | assertive, unhedged, one claim | knows the domain | sections, scaffolding, more than ~150 words |
| **concept** | impersonal, present tense, timeless | met the term, wants it pinned down | citing any running experiment's numbers — a concept must survive results changing |
| **entry** | analytical, takes a position, cites findings by id | interested, not expert in this artifact | unattributed claims; the longest prose of any genre, so it must still be navigable |
| **chapter** | pedagogical, second person allowed, one idea at a time | has read the prior chapters and nothing else | forward references |
| **hub** | map-like, opinionated, high link density | arriving cold, needs orientation | long prose; a hub that explains is an entry wearing a hub's hat |
| **project** | operational, dated, present tense | wants to know what is true now | undated status; it is explicitly perishable |
| **paper** | formal academic, linear | a reviewer reading start to finish | hypertext affordances; every number cites a finding |
| **related-works** | neutral summary, stance kept separate | wants to know what others did and why it matters here | conflating their claim with our reading of it; unverified ids |

**What checks it.** Register cannot be linted directly, but its proxies can: per-genre length bounds, required and forbidden sections, the status banner, presence of a `defn` block in a concept, forward-reference detection in chapters, id verification in related-works. Anything left over is a reviewer-agent judgment, not a gate.

## The Review layer

Session-free by construction, which is the whole point of not using an existing live-review tool.

- **Anchoring** — text-quote anchoring, not CSS selectors, because prose gets edited and selectors rot. Borrow the W3C Web Annotation Data Model rather than inventing a schema; it already solves quote + prefix/suffix + fallback position.
- **Storage** — one sidecar per page, committed. Threads carry author, timestamp, state (`open` / `addressed` / `declined`), and an agent's reply when it acts.
- **Lifecycle** — human annotates whenever; no server needs to be running for the annotation to survive, and no agent needs to be listening. An agent later reads open threads, addresses them, replies in the thread, and flips state. Declining is a first-class outcome and must carry a reason.
- **The gate's role** — validate schema, and refuse to let a page's anchors go stale silently: if a quote no longer matches the page, that is a loud failure, not a dropped comment.

## Realization (2026-09-11)

| Layer | Realized as |
|---|---|
| Form | `shell/` — unchanged vocabulary, plus `hb-kind-paper` / `hb-kind-related`; the search page moved into the shell (it was a per-repo file that only one repo had) |
| Structure | `ckit/genres.json` — nine core genres; `paper` and `related` gained skeletons; classification is by path and a page outside any genre is an error |
| Voice | `genres/GENRES.md`, with each rule naming what checks it; the proxies are in `ckit/lint.py` |
| Craft | `craft/` — six playbooks against the shell vocabulary; deliberately unchecked |
| Assets | unchanged: `assets/figures/` (format-agnostic) and `assets/paper/` (LaTeX-only), as lab-kit split them at `1bae59f`; `craft/figure.md` states the one-home rule |
| Indices | `ckit nav`, run by lint |
| Review | `shell/annotate.js` + `ckit annotations` + a write endpoint in `ckit serve`; sidecars beside pages, W3C `TextQuoteSelector` anchors |
| Gate | `ckit check`; the engine version is pinned per repo in `lab.json` |
| Packaging | hybrid, as decided: `kit/` vendored and pinned per repo; the engine installed once as a shim over this checkout |
| Record (added 2026-09-11) | `content/` shows now; the arc is the append-only record, rendered by `/shell/record.html` and indexed as a generated timeline (`content/chronicle.json`, `/shell/chronicle.html`) — dated headings with kind tags, plus lab-kit's extractor for PROBEs, findings, claims, missions; checked current by `ckit check`, never authored | · 2026-09-11 evening: `/shell/chronicle.html` default view is **Story** — tagged events only (pivots, decisions, kills, lessons, instrument, results, missions, experiments, findings, claims), grouped by month, summary paragraphs rendered as prose, with a *Right now* banner sourced from the first record file titled *State*; `Timeline` shows every dated heading (297 → 59 for PHL)

The questions the draft left open were settled while building:

- **Annotation is a mode, not always-on.** An **✎ Annotate** toggle appears only when the serving engine answers `/__annotations/ping`; a static host never grows it, so pages stay portable and a reader cannot annotate by accident.
- **`related` wraps `RELATED.md`, it does not replace it.** The page is the reader-facing overview; a lab's `RELATED.md` stays the verified-reference ledger the `/lit` skill maintains.
- **Resolved threads are retained.** Nothing is deleted; a human withdraws, an agent addresses or declines with a reason. Only an *open* thread's anchor is load-bearing for the gate — an addressed thread's passage may well have changed, because that is what acting on it looks like.
- **Extensions declare their voice in `lab.json`** under `genres`, same shape as the core, deep-merged per genre, so an override of a core check is one visible line.

## Known gap — the paper is content the kit does not yet govern (recorded 2026-09-11, not fixed)

The vision says each content type has its own language and that assets are shared across forms; the realization drew the engine's boundary at HTML, so the `paper` genre covers only the landing page (`index.html`) and the `.tex` itself is untouched by `ckit`. In proof-harness-lab the sharing already happens by convention — 28 SVG sources with generators in `assets/figures/`, 13 embedded by pages as SVG and 7 included by the paper as PDF derivatives of the same stems, one `references.bib` with 45 entries — but nothing checks it. Unchecked today, each checkable in seconds without a TeX toolchain: the `.tex` declares its status in its opening lines (the ladder lint checks `main.md`, not `main.tex`); every `\includegraphics{X.pdf}` derives from `assets/figures/X.svg` with a generator (one home, cross-format); every `\cite{key}` resolves in the shared bibliography; the landing page's abstract equals the `.tex` abstract; `\input`/`\include` resolve. Also missing: the `.tex` register in `GENRES.md` (formal, linear, every number cites a finding id in a comment), a `craft/paper.md`, and the paper machinery (`assets/paper/` preamble and bibliography, `assets/figures/` skeleton) as content-kit skeletons so a non-lab repo can carry a paper at all — today that machinery is lab-kit's.

The shape of the fix is a `paper` genre v2: the genre declares the `index.html` + `main.tex` pair (a declared pair like an entry's `source.json`, not a twin); `ckit check` gains the five checks; the asset conventions become kit skeletons; building the PDF stays out-of-band. The operator chose on 2026-09-11 to record this rather than build it now.

## What is not decided

- Whether the annotation UI ships as part of the served page (a shell affordance, always available) or as a separate mode. Affects whether readers can annotate accidentally.
- Whether `related-works` supersedes `RELATED.md` or wraps it. The `/lit` verification discipline must survive either way.
- The pruning policy for resolved threads — deleted on resolve, or retained as record. The append-only instinct says retain; the churn cost says prune.
- How per-repo genre extensions declare their voice rules without every repo reinventing the vocabulary.

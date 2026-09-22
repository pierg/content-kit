# Genres and voice — LIVE

Where a page lives is its genre. A genre is a **structure** (the path, the skeleton, the shape) and a **voice** (the register, the assumed reader, the moves that are forbidden). The structure was always here; the voice is what makes a concept page read like a definition and a hub read like a map, whoever wrote them.

Every rule below names what checks it. A rule nothing checks is a suggestion, and suggestions drift — this repo's own pages proved it. The machine spec is `genres.json` beside this file (the engine's copy is authoritative; this one is vendored for reading). A repo extends or overrides it under `genres` in `kit.json`, same shape, deep-merged per genre.

**Every genre:** the first `<p class="sub">` declares the page's status — LIVE · HISTORICAL · PARKED · RETIRED · FROZEN · DRAFT — so a reader can tell in one line whether it is still true. *Checked: `status`.*

## note — `content/notes/<slug>.html`

**Register.** Assertive and unhedged. One claim, stated as if true, with the reason in the same breath.

**Reader.** Already knows the domain; wants the thought, not the background.

**Shape.** A few paragraphs, no sections. Links out liberally; a note is a node in a graph, not a document.

**Forbidden.** Sections (an `<h2>` means it has become an entry), scaffolding ("in this note I will…"), hedging. *Checked: `no_h2`, `max_words: 400`.*

**Promotion.** When it grows sections, it is an entry. Move it; do not stretch it.

## concept — `content/concepts/<slug>/index.html`

**Register.** Impersonal, present tense, timeless. A concept page is a definition of record and reads like case law: the sentence that other pages may cite, then why it matters, a worked example, the trap, and where the long form lives.

**Reader.** Has met the term and wants it pinned down — often via the hover popover, with no context beyond the `defn` blockquote itself. So every symbol in the defn is introduced in the sentence or wrapped in a `defn-link`.

**Shape.** Opens with one figure that carries the phenomenon, then the `blockquote.defn`. Sections are `<h3>`, not `<h2>`.

**Forbidden.** A definition that depends on a running result. Results may be cited *below* the defn (why it matters here) but never inside it — the defn must survive the results changing. *Checked: `require_defn`, `max_words: 1500`; a layer whose results carry ids adds a check that the defn cites none.*

**Promotion.** Define once, link everywhere: the second time a term needs prose explanation anywhere, it becomes a concept and every other mention becomes `<a class="defn-link" href="/content/concepts/<slug>/">`.

## entry — `content/entries/<slug>/index.html`

**Register.** Analytical. Takes a position and says what each claim rests on — a source, a measurement, a row in the repo's record — each cited where the claim is made. The longest continuous prose of any genre, so it is sectioned so a reader can navigate it.

**Reader.** Interested and capable, not expert in this particular artifact.

**Shape.** `<h2>` sections; an opening `defn`-style statement of the idea; a check-yourself at the end. An entry that reads an external paper keeps its source bundle beside it (`source.json`, `main.md`, `figures/`) — that is the one legitimate markdown/HTML pair, and `source.json` declares it.

**Forbidden.** Unattributed claims; a wall with no sections. *Checked: `status` only — the voice here is judged, not linted.*

## chapter — `content/books/<slug>/NN-name.html`

**Register.** Pedagogical. Second person is allowed. One idea at a time, staged before it is named, and a check-yourself at the end of every section so the reader can tell whether it landed.

**Reader.** Has read the prior chapters and nothing else. That is the whole contract of a sequence.

**Shape.** Numbered files, so order is discovered (`ckit nav`). Definitions that the rest of the book cites are `blockquote.defn`.

**Forbidden.** Forward references — a link to a later chapter breaks the contract. When one is deliberate (a "see also", a pointer to the record chapter), it says so: `<a data-fwd href="09-record.html">`. *Checked: `no_forward_refs`.*

## book — `content/books/<slug>/index.html`

**Register.** The map of a sequence: what the chapters build, in what order, and why that order.

**Reader.** Deciding whether and where to start.

**Forbidden.** Teaching. The index orients; the chapters teach. *Checked: `status`.*

## hub — `content/hubs/<slug>.html`

**Register.** Map-like and opinionated. A stance first ("current take"), then the map, then what is open. High link density; every link carries a one-line reason to follow it.

**Reader.** Arriving cold, needs orientation over a cluster.

**Forbidden.** Long prose. A hub that explains is an entry wearing a hub's hat. *Checked: `max_words: 1500`.*

## project — `content/projects/<slug>/index.html` (and pages beside it)

**Register.** Operational, dated, present tense: what is true now, what is next, what is blocked. Explicitly perishable, and it says when it was last true.

**Reader.** Wants the state of the work, not the ideas behind it.

**Shape.** `<meta name="status" content="active|shipped|paused">` for the catalog; a dated status line; owned artifacts; open threads; milestones with evidence chips. Sub-pages under the project folder (an ops board, a plan) share the genre. A layer may give the project a sharper register — lab-kit turns it into a lab's front door, a folio into the door to a repo that does the work elsewhere.

**Forbidden.** An undated status. *Checked: `require_meta_status`.*

## paper — `content/papers/<slug>/index.html`

**Register.** The landing page of a venue artifact: the abstract verbatim, the submission state, what the paper rests on (its load-bearing sources), and where the source and figures are.

**Reader.** A reviewer or a reader deciding whether to open the PDF.

**Forbidden.** Restating the paper. The page frames it; the PDF is the paper, frozen at submission. A layer with a record may bind the paper's numbers to it and check the `.tex` (a lab's does). *Checked: `status`.*

## related — `content/related/<slug>.html`

**Register.** Neutral summary of others' work, one row per work — what they did, what they claim — with our reading in a separate, clearly marked section. The table is theirs; the last section is ours.

**Reader.** Wants to know what others did and why it matters here.

**Forbidden.** Conflating their claim with our reading of it; an identifier that has not been verified (arXiv id, DOI, venue and year). A reference that could not be verified says so instead of guessing. A repo that keeps a verified-reference ledger points at it from the page rather than copying it. *Checked: `status`.*

## Extending the set

A repo whose topic needs a shape the core lacks declares it in `kit.json`:

    "genres": {
      "recipe":  { "dir": "recipes", "layout": "flat", "skeleton": "assets/skeletons/recipe.html",
                   "register": "imperative, one dish", "reader": "at the stove",
                   "forbidden": "history lessons", "after": "hub", "label": "Recipes",
                   "checks": { "status": true, "max_words": 600 } },
      "concept": { "checks": { "max_words": 3000 } }
    }

The first adds a genre; the second overrides one check on a core genre, visibly, in the one file a reader would look. Layouts are `flat` (`<dir>/<slug>.html`), `folder` (`<dir>/<slug>/index.html`, sub-pages share the genre), `book-index` and `book-page`. A skeleton is looked up in the shell's `skeletons/` first, then from the repo root. Every genre that owns a directory is a group in the sidebar, on the landing page and among the search filters, in declaration order — core first — unless it says `"after": "<genre>"`; `"label"` names the group.

A layer ships its genres as a file and the repo keeps its own overrides after it — `genres` may be a list, each item an object like the one above or a repo-relative path to a JSON file holding one, deep-merged in order:

    "genres": ["kit/lab/genres/genres_lab.json", { "concept": { "checks": { "max_words": 3000 } } }]

The core checks, available to every genre: `status`, `max_words`, `no_h2`, `require_defn`, `no_forward_refs`, `require_meta_status`, and the one a fixed-shape genre uses —

- `require_sections`: a list of `<h2>` ids the page must carry, in that order. Extra sections are the page's business; a declared one that is absent, or that appears after a later one, is reported by its id. It reads the markup a reader is *served*: a section that only exists inside an HTML comment (or a `<script>` / `<style>` body) does not count, because the page renders without it.

Any other name a genre gives under `checks` must be provided by a module the repo registers under `checks` in `kit.json` — `CHECKS = {name: fn(ctx) -> [problem]}`, handed the page, its served markup and the genre's value for the check. A name that neither the core nor a registered module provides fails the gate: a check that silently never runs is worse than none. A layer brings its checks this way (lab-kit's `bound_ids` seals a story to the rows it tells; folio's `require_topic` puts every page on a topic).

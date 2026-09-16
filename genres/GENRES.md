# Genres and voice — LIVE

Where a page lives is its genre. A genre is a **structure** (the path, the skeleton, the shape) and a **voice** (the register, the assumed reader, the moves that are forbidden). The structure was always here; the voice is what makes a concept page read like a definition and a hub read like a map, whoever wrote them.

Every rule below names what checks it. A rule nothing checks is a suggestion, and suggestions drift — this repo's own pages proved it. The machine spec is `genres.json` beside this file (the engine's copy is authoritative; this one is vendored for reading). A repo extends or overrides it under `genres` in `lab.json`, same shape, deep-merged per genre.

**Every genre:** the first `<p class="sub">` declares the page's status — LIVE · HISTORICAL · PARKED · RETIRED · FROZEN · DRAFT — so a reader can tell in one line whether it is still true (DISCIPLINE §8). *Checked: `status`.*

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

**Forbidden.** A definition that depends on a running result. Findings may be cited *below* the defn (why it matters here) but never inside it — the defn must survive the findings changing. *Checked: `require_defn`, `defn_no_findings`, `max_words: 1500`.*

**Promotion.** Define once, link everywhere: the second time a term needs prose explanation anywhere, it becomes a concept and every other mention becomes `<a class="defn-link" href="/content/concepts/<slug>/">`.

## entry — `content/entries/<slug>/index.html`

**Register.** Analytical. Takes a position and says which numbers it rests on, each cited by finding id. The longest continuous prose of any genre, so it is sectioned so a reader can navigate it.

**Reader.** Interested and capable, not expert in this particular artifact.

**Shape.** `<h2>` sections; an opening `defn`-style statement of the idea; a check-yourself at the end. An entry that reads an external paper keeps its source bundle beside it (`source.json`, `main.md`, `figures/`) — that is the one legitimate markdown/HTML pair, and `source.json` declares it.

**Forbidden.** Unattributed claims; a wall with no sections. *Checked: `status` only — the voice here is judged, not linted.*

## story — `content/stories/<slug>/index.html`

**Register.** Plain, and sealed to its findings. One result told once, in the order a stranger needs it: the question in words, why it was expected to help, what was done, what happened, what was learned, what it does not show, where to go deeper. It is written after the result is scored and then it stops moving — if one of its rows changes status the story is revised deliberately; nothing else touches it.

**Reader.** A sharp outsider who has never seen the lab. So no code, path or internal name is ever the subject of a sentence: ids ride beside the number they license, as links.

**Shape.** Eight fixed `<h2>` sections in one order — `question`, `why`, `did`, `happened`, `learned`, `not`, `deeper`, `backlinks` — so two stories read alike and a reader who has read one can skim the next. The opening line carries the date it was written and the rows it is sealed to; a pinned cross-lab row (`dsl:F-3`) counts as one of them. A story is **one page**: assets may sit beside it in the folder, but a second page there is a story too and is held to the whole contract — an arc over several results takes its own slug instead. *Checked: `require_sections` (every id present, in that order) and `bound_ids` (the opening line names a row) — the date is not checked, and neither is what the prose does with either; a reviewer reads those.*

**Forbidden.** A rolling narrative — a page that keeps being updated is live state wearing a story's hat. A number without its row id. A bound the rows carry that is missing from what-it-does-not-show. *Checked: none of these — the two checks hold the shape, and what the prose owes its rows is the reviewer's.*

**Promotion.** An arc over several results is not a ninth section: it is its own story, with the same eight, and the front door links both.

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

**Register.** The front door. Plain sentences and links: what is being asked, what has been learned — one sentence per result, each ending in the rows it rests on and a link to its story — the top-level bounds, where things stand today, and why the work turned when it did. It points; the book teaches, the stories argue, the ledger proves. Explicitly perishable, and it says when it was last true.

**Reader.** Arriving cold and deciding what to read next, not yet inside the vocabulary.

**Shape.** `<meta name="status" content="active|shipped|paused">` for the catalog; a dated opening line; then asking · frame · learned · not · now · path · screens · glossary · evidence. The `now` section is dated and is **the one place in the content library where state lives** — everything else that moves is a link to the generated board. Sub-pages under the project folder (an ops board, a plan) share the genre.

**Forbidden.** Undated state. Re-explaining what a concept page or a story already owns. Carrying one result's conditions instead of the scope they all share. *Checked: `require_meta_status`; the section list is the skeleton's and the reviewer's, not the lint's — a front door may legitimately drop a section it has nothing to put in.*

## paper — `content/papers/<slug>/index.html`

**Register.** The landing page of a venue artifact: the abstract verbatim, the submission state, what the paper rests on (its load-bearing finding ids), and where the source and figures are.

**Reader.** A reviewer or a reader deciding whether to open the PDF.

**Forbidden.** Restating the paper. The page frames it; the PDF is the paper, frozen at submission. In a lab, every number in the paper cites a finding id (the record gate checks the `.tex`). *Checked: `status`.*

## related — `content/related/<slug>.html`

**Register.** Neutral summary of others' work, one row per work — what they did, what they claim — with our reading in a separate, clearly marked section. The table is theirs; the last section is ours.

**Reader.** Wants to know what others did and why it matters here.

**Forbidden.** Conflating their claim with our reading of it; an identifier that has not been verified (arXiv id, DOI, venue and year). A reference that could not be verified says so instead of guessing. In a lab, `RELATED.md` remains the verified-reference ledger the `/lit` skill maintains; the page is the reader-facing overview and points at it. *Checked: `status`.*

## Extending the set

A repo whose topic needs a shape the core lacks declares it in `lab.json`:

    "genres": {
      "recipe":  { "dir": "recipes", "layout": "flat", "skeleton": "content/_skeletons/recipe.html",
                   "register": "imperative, one dish", "reader": "at the stove",
                   "forbidden": "history lessons", "checks": { "status": true, "max_words": 600 } },
      "concept": { "checks": { "max_words": 3000 } }
    }

The first adds a genre; the second overrides one check on a core genre, visibly, in the one file a reader would look. Layouts are `flat` (`<dir>/<slug>.html`), `folder` (`<dir>/<slug>/index.html`, sub-pages share the genre), `book-index` and `book-page`. The same checks are available to every genre: `status`, `max_words`, `no_h2`, `require_defn`, `defn_no_findings`, `no_forward_refs`, `require_meta_status`, `no_findings`, and the two a fixed-shape genre uses —

- `require_sections`: a list of `<h2>` ids the page must carry, in that order. Extra sections are the page's business; a declared one that is absent, or that appears after a later one, is reported by its id.
- `bound_ids`: the first `<p class="sub">` must name at least one finding as `<code>F-<n></code>` — the rows the page is sealed to, so a reader and the reviewer both know what changing would change it. A pinned cross-lab row, `<code>dsl:F-3</code>`, counts.

Both read the markup a reader is *served*: a section or an id that only exists inside an HTML comment (or a `<script>` / `<style>` body) does not count, because the page renders without it.

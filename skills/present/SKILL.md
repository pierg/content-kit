---
name: present
description: Author a reader-facing HTML page (note, concept, entry, chapter, book, hub, project, paper landing, related-works) or a LaTeX paper in this repo's shared shell. Use when a session's output is a document rather than a chat answer. Enforces the presentation contract — the repo copy is the source of truth, one format per document, the page's genre fixes its structure and its voice, every number in a lab cites a finding id, the shell vocabulary only, and `make check` green before it lands.
---

# /present — author a reader-facing artifact

You are producing a **document**, not a chat reply. Chat gets the TL;DR and the repo path; the repo copy is the source of truth.

## Golden rules

1. **The genre fixes the voice.** Where a page lives says what it is, and what it is says how it reads. Pick the genre first — `kit/genres/GENRES.md` has the register, the assumed reader and the forbidden moves for each — and do not invent one. If no core genre fits, the repo may declare one in `lab.json` (`genres`); that is a deliberate, visible decision, not a workaround.
2. **Status in the first line.** The first `<p class="sub">` says LIVE, HISTORICAL, PARKED, RETIRED, FROZEN or DRAFT. The gate checks it.
3. **One format per document.** A markdown draft *and* an HTML page of the same document are twins, and twins drift. The one legitimate pair is an imported external paper (`main.md` is their text, `index.html` is your reading; `source.json` declares it).
4. **In a lab, every number cites a finding.** If `record/findings.md` exists here, no number enters a page except by citing an `F-<n>` row, and what may be *said* about it is bounded by `record/claims.md`. If a sentence has no claim licensing it, promote the finding first — do not write the sentence and reconcile later. Misses at the same volume as wins.
5. **One paragraph per line.** Never hard-wrap prose to a column.
6. **Address before you edit.** If the page has open annotations (`ckit annotations list`), run `/address` first — an open thread whose quoted passage you rewrite fails the gate.

## Authoring an HTML page

**Scaffold it:** `ckit new <genre> <slug> [--title "…"]` copies the skeleton to where the genre lives and prints the voice card. Chapters are `<book>/<NN-name>`; `ckit new book <slug>` first if the book is new.

| Genre | When | Path |
|---|---|---|
| **note** | one atomic claim, a few paragraphs, no sections | `content/notes/<slug>.html` |
| **concept** | definition of record for a reused term | `content/concepts/<slug>/index.html` |
| **entry** | dense one-page read: a deep dive, a paper reading | `content/entries/<slug>/index.html` |
| **chapter** | ordered teaching step inside a book | `content/books/<slug>/NN-name.html` |
| **book** | the map of a chapter sequence | `content/books/<slug>/index.html` |
| **hub** | orientation and stance over a cluster | `content/hubs/<slug>.html` |
| **project** | active work: dated status, owned artifacts | `content/projects/<slug>/index.html` |
| **paper** | landing page of a venue artifact | `content/papers/<slug>/index.html` |
| **related** | others' work, neutrally, with our reading kept separate | `content/related/<slug>.html` |

Promotion: note → entry → chapter as scope grows. **Define once, link everywhere** — the second time a term needs prose explanation, make it a concept and reference it with `<a class="defn-link" href="/content/concepts/<slug>/">TERM</a>`; the shell pops the target's `blockquote.defn` on hover.

**Build the blocks:** before writing a comparison, a diagram, a table, a timeline, a code listing or a figure, read its playbook in `kit/craft/`. Show, then tell; one color register per figure; nothing overflows.

**Mechanics:** every page loads `/shell/lib.css` and `/shell/lib.js`. Use the vocabulary in `kit/shell/COMPONENTS.md` — `.hb` tokens only, no new hex colors or type stacks. Page-specific widget CSS goes in a `<style>` block on that page; promote into the shell only when it recurs on three pages, and update `COMPONENTS.md`. Add `<ul data-backlinks></ul>` to show who cites the page. Math is opt-in (`/shell/math.js`, `$…$`). Never hand-edit `nav.json`, `catalog.json`, `search-index.json`, `backlinks.json` or any `*.annotations.json`.

## Authoring a paper

`content/papers/<slug>/main.tex`, with `figures/` beside it and a `paper` landing page (`ckit new paper <slug>`). Shared machinery — preamble, bibliography — lives in `assets/paper/`; figure sources and generators in `assets/figures/`, the same SVGs the pages embed. Built PDFs are derived. Every number in the prose cites a finding id in a comment or footnote so the record gate can see it. The paper is frozen at submission; the page stays living. Their prose is written independently — they share ids, figures and bibliography, never sentences.

## Before finishing

```bash
ckit lint      # form + genre + annotation lint; regenerates the indices (catalog, search, backlinks, nav)
make check     # the gate: engine pin · shell · indices current · lint · books  (+ the lab's record gate)
make docs      # read it in the browser before you call it done
```

Fix everything the gate reports. Then commit — records lane, only the files you touched plus what `ckit lint` regenerated. Never `git add -A`.

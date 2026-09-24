---
name: present
description: Author a reader-facing HTML page (note, concept, entry, chapter, book, hub, project, paper landing, related-works, or a genre the repo adds) or a LaTeX paper in this repo's shared shell. Use when a session's output is a document rather than a chat answer. Enforces the presentation contract — the repo copy is the source of truth, one format per document, the page's genre fixes its structure and its voice, every number carries its source, the shell vocabulary only, and `make check` green before it lands.
---

# /present — author a reader-facing artifact

You are producing a **document**, not a chat reply. Chat gets the TL;DR and the repo path; the repo copy is the source of truth.

## Golden rules

1. **The genre fixes the voice.** Where a page lives says what it is, and what it is says how it reads. Pick the genre first — `kit/genres/GENRES.md` has the register, the assumed reader and the forbidden moves for each — and do not invent one. If no core genre fits, the repo may declare one in `kit.json` (`genres`); that is a deliberate, visible decision, not a workaround.
2. **Status in the first line.** The first `<p class="sub">` says LIVE, HISTORICAL, PARKED, RETIRED, FROZEN or DRAFT. The gate checks it.
3. **One format per document.** A markdown draft *and* an HTML page of the same document are twins, and twins drift. The one legitimate pair is an imported external paper (`main.md` is their text, `index.html` is your reading; `source.json` declares it).
4. **A layer's rules bind too.** A repo that vendors a layer on top of this kit carries that layer's authoring rules in `kit/` (a lab's record discipline, a folio's topic rule) and registers its checks in `kit.json`. Read them before writing: where a layer says no number enters a page except by citing a row of its record, that is as binding as anything here. Misses at the same volume as wins.
5. **One paragraph per line.** Never hard-wrap prose to a column. The gate reports it; `ckit unwrap` joins it.
6. **Address before you edit.** If the page has open annotations (`ckit annotations list`), run `/address` first — an open thread whose quoted passage you rewrite fails the gate. A noted flag on a passage you rewrite is named as stale, not failed: withdraw it, and flag the new passage if it still goes beyond the source.
7. **Flag what goes beyond the source; ask only what needs an answer.** A passage you wrote that the source did not say (your example, your framing, an elaboration, a claim from general knowledge) gets a *flag* on it, labelled so the owner can review its kind in one look: `ckit annotations add <page> --author agent:<name> --kind flag --label "worked example" --quote "<passage>" --body "Added — <what, and why>"`. A flag rests as `noted`: it pins and discloses the passage, on the page and on the review page, and asks nothing of anyone; the owner keeps it, or asks for a change, when they read. Open a *question* (the default kind) only where the owner's answer changes the page — a claim you could not verify, a structural choice bigger than the page, a reference that would not verify — and keep them few: a page that would need more than three asks one page-level question instead. A page drafted wholly from general knowledge gets one page-level question and the status DRAFT.
8. **Organising is `/curate`'s.** Opening or merging a topic, retagging, moving, promoting or retiring a page: `/curate`, with `ckit topics`, `ckit tags`, `ckit mv` and `ckit rm`. Never `git mv` a page.

## Layered content

A library has four classes of page, told apart by how fast they change. A sentence in the wrong class goes stale where nothing checks it.

- **Foundations** — the book, the concepts, the field page. They move per era, not per result: they cite only settled sources and carry no state.
- **Accounts** — a page written once about one finished thing (a reading, a result, a release), in its genre's shape, and revised only when what it rests on changes.
- **Live state** — the generated indices, the chronicle and the rendered record, and whatever pages a layer generates. Never authored, never transcribed into a page.
- **Views** — the front doors: hubs and projects. Plain sentences and links over all of the above, and the only place in `content/` where dated state lives, with the date on it.

Four rules cut across all four:

- **Codes are links, not content.** An id, a path or a hash rides beside the sentence it licenses and is never the subject of one. A reader must get the point without resolving a single code.
- **Every number carries its source**, and is re-derived from that source — never quoted forward from another page, a summary or memory.
- **Plain is not vague.** "It didn't help" is simple and vague; "19 of 29, against the step before's 21 — inside the run-to-run swing" is simple and precise.
- **Nulls at equal prominence.** A void, a drop, a failed attempt is stated as plainly as a win, in the same place and the same voice. Equal prominence, not equal length.

One rule separates the two authored classes: **an account carries every caveat its sources carry; a view carries only the ones they all share** — and says outright that each account holds the rest.

## Authoring an HTML page

**Scaffold it:** `ckit new <genre> <slug> [--title "…"] [--topic <slug>] [--tags a,b]` copies the skeleton to where the genre lives, sets the page's topic and tags, and prints the voice card. Chapters are `<book>/<NN-name>`; `ckit new book <slug>` first if the book is new. The skeleton's placeholder links (`…/OTHER…`) are the gate's to report until you point each at a real page or drop it. Reuse the library's tags (`ckit tags`); a topic must be one kit.json declares (`ckit topics`).

| Genre | When | Path |
|---|---|---|
| **note** | one atomic claim, a few paragraphs, no sections | `content/notes/<slug>.html` |
| **concept** | definition of record for a reused term | `content/concepts/<slug>/index.html` |
| **entry** | dense one-page read: a deep dive, a paper reading | `content/entries/<slug>/index.html` |
| **chapter** | ordered teaching step inside a book | `content/books/<slug>/NN-name.html` |
| **book** | the map of a chapter sequence | `content/books/<slug>/index.html` |
| **hub** | orientation and stance over a cluster | `content/hubs/<slug>.html` |
| **project** | the state of a piece of work, dated, perishable | `content/projects/<slug>/index.html` |
| **paper** | landing page of a venue artifact | `content/papers/<slug>/index.html` |
| **related** | others' work, neutrally, with our reading kept separate | `content/related/<slug>.html` |

A genre the repo adds (`ckit genres` lists them all) lands where its `dir` says, with its own skeleton and voice card. Promotion: note → entry → chapter as scope grows. **Define once, link everywhere** — the second time a term needs prose explanation, make it a concept and reference it with `<a class="defn-link" href="/content/concepts/<slug>/">TERM</a>`; the shell pops the target's `blockquote.defn` on hover.

**Build the blocks:** before writing a comparison, a diagram, a table, a timeline, a code listing or a figure, read its playbook in `kit/craft/`. Show, then tell; one color register per figure; nothing overflows.

**Mechanics:** every page loads `/shell/lib.css` and `/shell/lib.js`. Use the vocabulary in `kit/shell/COMPONENTS.md` — `.hb` tokens only, no new hex colors or type stacks. Page-specific widget CSS goes in a `<style>` block on that page; promote into the shell only when it recurs on three pages, and update `COMPONENTS.md`. Every internal link must resolve as the exported site would serve it — the gate checks each `href` and `src`; `data-unchecked` exempts one it cannot see (a build product). The page rail lists who links to the page on its own ("Linked from"); add `<ul data-backlinks></ul>` only where that list belongs in the page itself — it then replaces the rail's, and shows on narrow screens, where the rail is hidden. Math is opt-in (`/shell/math.js`, `$…$`). Never hand-edit `nav.json`, `catalog.json`, `search-index.json`, `backlinks.json` or any `*.annotations.json`.

## Authoring a paper

`content/papers/<slug>/main.tex`, with `figures/` beside it and a `paper` landing page (`ckit new paper <slug>`). Shared machinery — preamble, bibliography — lives in `assets/paper/`; figure sources and generators in `assets/figures/`, the same SVGs the pages embed. Built PDFs are derived. Every number in the prose cites its source in a comment or footnote, so a reviewer (or a layer's record gate) can see it. The paper is frozen at submission; the page stays living. Their prose is written independently — they share ids, figures and bibliography, never sentences.

## Delegated drafting

A long page is drafted in passes, and the passes are kept separate on purpose:

1. **Draft from the sources** — not from another page, a chat summary or memory. A number quoted forward from a summary is a rumour with a decimal point.
2. **Verify against the sources with a second model**, given only the page and what it cites, reporting every number, id, verdict word and bound that does not match.
3. **Repair what verification found, then re-verify.** The draft is not the artifact until that pass is clean.
4. **Reader-test the front door** on someone who has never seen the work. If they cannot say what was found and what it does not show, it is not plain yet.
5. **Independent review before it lands** — fresh context, no write tools, reading the page against its sources rather than the summary of them. The author never self-certifies. Where no reviewer is available (a solo session), say so plainly and make the owner the reviewer: the threads of rule 7 stay open until they are settled (`ckit annotations list` shows them; so does the generated home page, where kit.json names no `home`). A layer may name its own review.

## Before finishing

```bash
ckit lint      # form (links, prose, tags) + genre + annotation lint; regenerates the indices
make check     # the gate: engine pin · shell · indices current · lint · books — every problem in one run
make docs      # read it in the browser before you call it done
```

Fix everything the gate reports. Then commit — records lane, only the files you touched plus what `ckit lint` regenerated. Never `git add -A`.

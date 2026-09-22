# Shell components

Shared contract for **all** content. Chapter-specific widget CSS stays in that
chapter's HTML (`<style>`). Book chapter order is discovered into `nav.json`
(`ckit nav`); optional thin overrides live in that book's `book.json`.

## Page chrome

```html
<link rel="stylesheet" href="/shell/lib.css">
<style>/* optional — this chapter only */</style>
<script src="/shell/lib.js" defer></script>
<body class="hb"><main>…</main></body>
```

Chrome (`lib.js`):
- **Side** — library catalog from `/content/catalog.json` (papers / books / projects / stories / hubs / related / entries / notes / concepts)
- **Top** — chapter strip + on-this-page TOC from the book's `nav.json`
- **Footer** — prev/next chapter

Do not hand-edit `nav.json` / `catalog.json` — regenerate with `ckit nav` (lint does this automatically).

Entry pages live at `content/entries/<slug>/index.html`. When an entry teaches
an external paper, keep the source bundle beside it: `source.json` with abs/pdf
links, `main.md` for processed text, and `figures/` when diagrams carry the
argument. The PDF is a link field unless explicitly vendored.

## Color registers

Two registers — **never mixed in one figure**:

| Register | Tokens | Use |
|---|---|---|
| **SET** | `--reach`, `--cert`, `--target`, `--slack`, `--leak` | Geometry of sets |
| **ROLE** | `--gen`, `--judge`, `--world` | Loop actors |

Verdict colors: `--kept`, `--discarded`, `--rejected`, `--untested`.

Swatches: `sw-reach` · `sw-cert` · `sw-target` · `sw-slack` · `sw-leak` · `sw-gen` · `sw-judge` · `sw-world`.

Lane borders: `lane lane-reach` (also `lane-cert`, `lane-judge`, `lane-gen`, `lane-world`, `lane-kept`, `lane-baseline`).

## Definition of record

```html
<blockquote class="defn" id="…">
  <span class="defn-name">NAME</span><br>
  …
</blockquote>
```

## Concept links (define once, link everywhere)

```html
<a class="defn-link" href="/content/concepts/<slug>/">TERM</a>
```

The shell (`lib.js`) fetches the target's `<blockquote class="defn">` and pops it
on hover / focus; click still navigates. Use this instead of re-teaching a term
that already has a `content/concepts/<slug>/` page. Full-word slugs
(`bounded-model-checking`, not `bmc`); short display label in the link text.

The popover uses `.defn-pop` / `.defn-pop-name` (rendered outside `.hb`, so both
class names live in the allowlist). Do not hand-write `.defn-pop` markup.

## Math notation (opt-in KaTeX)

Concept and chapter pages that need real math opt in with one script tag:

```html
<script src="/shell/math.js" defer></script>
```

Then write LaTeX in prose:

- Inline: `$H(s) \wedge \neg H(s')$` — flows as text
- Display: `$$\exists s.\; H(s) \wedge T(s, s') \wedge \neg H(s')$$` — centered block
- Also accepts `\(…\)` (inline) and `\[…\]` (display)

Wrap display formulas that need extra vertical space in `<p class="formula">…</p>`.

**Escape hatches** — anything inside `<code>`, `<pre>`, `<script>`, `<style>`,
`<textarea>`, or an element with class `defn-name` is NOT rendered as math.
Use `<code>Init</code>` when you want the identifier in monospace instead of italic
math. The `defn-name` span (definition label) is exempt so LaTeX in a defn body
does not accidentally include the label.

**Rule for concept pages**: introduce every symbol before using it. `$H$` alone
is illegible without the sentence "the current inductive hypothesis $H$" nearby.
The concept page's defn is the popover payload — a reader hovering it has no
context beyond the blockquote itself.

## Chips

**Verdict** — `<span class="v v-kept|v-disc|v-rej|v-unt">…</span>` (plus `v-gen` for callouts)

**Evidence** — `<span class="ev ev-m|ev-b|ev-d|ev-o">…</span>`

**Census status** — `<span class="st st-done|st-plan|st-open">…</span>`

**Ownership** — `<span class="own">…</span>`

## Backlinks

```html
<h2 id="backlinks">Cited by</h2>
<ul data-backlinks><li class="muted">Auto-populated.</li></ul>
```

The shell fills in the list from `/content/backlinks.json` at page load — a
lint-generated reverse index of every internal `href` in the library. Each item
gets a `<span class="hb-kind hb-kind-<kind>">` badge and a link back to the citing
page. Empty message shows if nothing cites this page yet.

## Search

The `/shell/search.html` page (engine chrome, not a content page) filters `/content/search-index.json` live. Every
page in the library appears — indexed by title, `.sub` line, headings, `defn`
blockquote, and `<meta name="tags">`. Filter chips let the reader narrow by kind
(paper / book / project / hub / related / entry / note / concept). Add `<meta name="tags" content="…">`
to any page to make it findable by tag.

## Check-yourself / flashcards

```html
<details class="check"><summary>Prompt</summary><div class="ans">Answer</div></details>
<details class="fcard"><summary>Front</summary><div class="back">Back</div></details>
```

## Tabs & steppers

```html
<section data-hbtabs data-active="a">
  <button class="tbtn" data-tab="a">A</button>
  <div data-pane="a">…</div>
</section>
```

`hbStepper({ el, count, render })` with `data-step="reset|prev|next"`. Toggles: `.tbtn.on`.

## Shared widget primitives

Reusable across books (in `lib.css`):

| Class | Role |
|---|---|
| `.cyc` | cycle / step chips |
| `.prow` | listing row |
| `.nrow` + buttons | node/exam picker |
| `.drawer` | detail panel |
| `.cellrow` / `.cell` | state-band explorer |
| `.gate` / `.g` + `.gline` | gate pipeline |
| `.lchip` · `.cbar` | lemma chips · conversion bars |
| `.mtable` | key column bold |
| `.wcap` · `.wcap-sm` · `.wcap-md` · `.wcap-lg` | caption sizes |

Chapter-only widgets (a bespoke encoding table, a one-off explorer, …) stay in that chapter's `<style>`.

## Motif boxes

`.twin` · `.split` · `.note` / `.note-warn` · `.law`

## Genres and voice

Where a page lives is its genre, and the genre carries a **voice** — register, assumed reader, forbidden moves — plus the checks the gate runs on it. The table is `kit/genres/GENRES.md`; the machine spec is `kit/genres/genres.json`. `ckit new <genre> <slug>` scaffolds from the right skeleton and prints the voice card. Every page's first `<p class="sub">` declares its status (LIVE · HISTORICAL · PARKED · RETIRED · FROZEN · DRAFT) — the gate checks it.

## Annotations (review without a session)

When a page is served by the engine, an **✎ Annotate** toggle appears bottom-right. Select prose and comment, or add a page-level note; threads are written to `<page>.annotations.json` beside the page and committed. Nothing needs to be running for a note to survive: an agent later runs `ckit annotations list` and the `/address` skill. Quotes are anchored by text, not by CSS path, and `ckit check` fails if a quoted passage is no longer on its page. The chrome classes (`hb-ann-*`) are injected — never author them, and never hand-edit a sidecar.

## Record and chronicle (engine chrome)

`/shell/record.html?p=<path.md>` renders one file of the repo's declared record (`kit.json` `record`) in the shell — the markdown stays the artifact; the banner names it. `/shell/chronicle.html` renders `content/chronicle.json`, the generated timeline (dated headings with `[pivot]`-style tags, plus whatever extractor the repo declares). Both are chrome like the search page: never authored, never copied into `content/`.

## Craft

How to lay out a comparison, a diagram, a table, a timeline, a code listing or a figure in this vocabulary: `kit/craft/`. One playbook each; read the matching one before writing the block.

## Promoting patterns

When the same widget CSS appears in **three** chapters or two books, lift it into
`lib.css`, document it here, and delete the copies. Until then it stays in the
chapter `<style>`.

## Do not

- Put chapter- or book-specific rules in `shell/`
- Invent hex colors or type stacks in content
- Hand-edit distilled `assets/record.js`
- Hand-edit `nav.json` or `content/catalog.json`
- Add `book.js` (retired)
- Author `hb-ann-*` chrome or hand-edit `*.annotations.json` — use the browser or `ckit annotations`

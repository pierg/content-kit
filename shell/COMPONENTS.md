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

Chrome (`lib.js`, built from `/content/catalog.json` and always inserted **outside** `<main>` — the text a reader annotates is exactly the text the page carries):
- **Library rail** (left) — the site's name, a search button (⌘K / Ctrl-K / `/` anywhere opens the palette), Home · Browse · Chronicle and the repo's kit.json `links`, then the library as a tree: **by topic** when pages declare `<meta name="topic">` (each topic → its hub as *Overview*, then its pages by genre), **by genre** otherwise (one group per genre that owns a directory, in the genre table's order), then the record's files. Groups fold; what a reader opens stays open. A theme toggle (auto · light · dark) and a reading-face toggle (serif · sans) sit at its foot.
- **Top bar** — breadcrumbs (site / topic / genre), or a book's chapters as pills on a chapter page; "Updated … · N min read" and a Contents menu when the page rail is hidden.
- **Page rail** (right, wide screens) — *On this page* (the `<h2>`/`<h3>` outline, following the scroll), *Page* (its kind, its topic, when it changed, its reading time, its tags as links into Browse), *Linked from* (from `/content/backlinks.json`, automatic — no markup needed).
- **Peeks** — hovering an internal link shows its kind, title and opening line; a `defn-link` keeps its definition popover.
- **Footer** — prev / next chapter in a book.
- **Moving between pages** — cross-document view transitions where the browser has them, speculation-rules prefetch on hover (Chromium); elsewhere, plain navigation.

The shell's own pages (browse, chronicle, record) carry `<body class="hb" data-hb-app>`: full width, sans, no page rail. A layer's shell page is treated the same way because it is served under `/shell/`.

Do not hand-edit `nav.json` / `catalog.json` — regenerate with `ckit nav` (lint does this automatically).

Entry pages live at `content/entries/<slug>/index.html`. When an entry teaches
an external paper, keep the source bundle beside it: `source.json` with abs/pdf
links, `main.md` for processed text, and `figures/` when diagrams carry the
argument. The PDF is a link field unless explicitly vendored.

## Reading measure and type

Prose — the direct children of `<main>` that are `h1`–`h6`, `p`, `ul`, `ol`, `dl`, `blockquote`, `details`, `.note`, `.q`, `.law`, `.anchors` (and the same inside an unclassed `div`, `section` or `article`) — sits in a measure of `--measure` (~70 characters a line). Everything else — `figure`, `table`, `pre`, `.cols`, `section.card`, a widget — breaks out to `--wide`. So write prose as plain children of `<main>` and it reads well; give a widget its own container and it gets the room.

Two vendored variable faces (SIL OFL, `vendor/fonts/`): **Source Serif 4** for reading (`--font-body`, `--font-serif`) and **Inter** for headings and chrome (`--font-sans`); code is `--font-mono`. The reader can switch the body to sans. SVG text keeps the system face, so a hand-laid figure never reflows.

The opening line's `<b>Status: X</b>` is rendered as a pill (a class on the author's own `<b>`; the text is untouched).

## Color registers

Two registers — **never mixed in one figure**. The hues are named for what they are; what they mean is the page's business, said once in its legend.

| Register | Tokens | Use |
|---|---|---|
| **SET** | `--teal`, `--indigo`, `--blue`, `--amber`, `--red` | the parts of one picture: sets, regions, layers |
| **ROLE** | `--azure`, `--violet`, `--orange` | the actors of one process: who proposes, who decides, what changes |

Verdict colors: `--kept`, `--discarded`, `--rejected`, `--untested`. Ink and surface: `--ink-1` `--ink-2` `--ink-3`, `--surface-1`, `--surface-2`, `--page`, `--grid`, `--baseline`, `--ring`, `--shadow`. Links use `--link`; chrome highlights `--accent`; definitions and laws use violet. Every token has a dark value, chosen by the system or by the reader (`html[data-theme]`).

Swatches: `sw-teal` · `sw-indigo` · `sw-blue` · `sw-amber` · `sw-red` · `sw-azure` · `sw-violet` · `sw-orange`.

Lane borders: `lane lane-<hue>` for any hue above, plus `lane-kept` and `lane-baseline`.

A `var(--x)` that neither this shell, the repo's theme nor the page itself declares fails the lint: it would render as nothing.

## Themes — a repo's own names

A repo whose pages speak a domain's vocabulary maps it onto the hues in a stylesheet declared as kit.json `"theme"` (one path or a list), served as `/shell/theme.css` and imported at the top of `lib.css` — an empty stylesheet when none is declared:

```css
.hb { --glacier: var(--teal); --alarm: var(--red); }
.hb .sw-glacier { color: var(--glacier); font-weight: 700; }
```

Class names the theme adds under a shell prefix (`sw-`, `lane-`, `v-`, `ev-`, `st-`, `hb-`) are registered in kit.json `"classes"` so the lint accepts them. Widgets that only one body of pages uses live in its theme too. `templates/theme-fv.css` (in `ckit where`) is a worked example: the formal-verification vocabulary this shell carried before 0.4, and the widgets that left with it.

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

Every page shows who links to it in the page rail (*Linked from*), from `/content/backlinks.json` — a lint-generated reverse index of every internal `href` in the library. No markup is needed. A page that wants the list in its own body places one; it then replaces the rail's list (no page shows it twice), and it shows on narrow screens, where the rail is hidden:

```html
<h2 id="backlinks">Cited by</h2>
<ul data-backlinks><li class="muted">Auto-populated.</li></ul>
```

Each item gets a `<span class="hb-kind hb-kind-<kind>">` badge and a link back to the citing page.

## Search and browse

Two surfaces, one index. The **palette** (⌘K / Ctrl-K / `/`, or the rail's search button) jumps to a page, a topic, a tag or a shell page as you type. **Browse** (`/shell/search.html`, engine chrome) lists the library narrowed by words, kind, topic and tag — the filters live in the URL (`?q=` `&kind=` `&topic=` `&tag=`), so a tag chip or a breadcrumb links straight to a view — newest first when there are no words. Both read `/content/search-index.json` (title, `.sub` line, headings, `defn` blockquote, `<meta name="tags">`), Browse merged with every extra index kit.json `"indices"` declares (a folio's federated catalog of sibling repos, say). Every word must match somewhere; titles weigh most.

**Full text**, when [Pagefind](https://pagefind.app) is installed (`pip install 'pagefind[bin]'`, or on PATH): `ckit serve` builds a static, chunked index of every page's `<main>` in the background and serves it at `/pagefind/`, `ckit export` writes it into the site, and both surfaces add *In the text* results. Nothing is committed; without it, nothing changes.

Add `<meta name="tags" content="…">` to any page to make it findable by tag — lowercase slugs, comma-separated, each once (the lint checks; `ckit tags` lists the library's, so a new page reuses them); `<meta name="topic" content="<slug>">` puts it on a topic (kit.json `"topics"` names them; `ckit topics` lists them). `ckit new … --topic <slug> --tags a,b` writes both.

## Links

Every internal `href` and `src` must resolve the way the exported site will serve it, and the lint checks each one: an absolute address (`/content/…`, `/shell/…`, the landing `/`), or one relative to the page. Reported: an address nothing answers; a directory without an `index.html` (`ckit serve` lists it, a static host 404s); a bare slug (`/k-induction` — the server redirects it, a static host does not); a letter-case mismatch (a Mac forgives it, a Linux host does not); a file git ignores (it is in no clone); and an address kit.json `moved` redirects (link the page where it is now). Skeletons carry placeholder links through `…/OTHER…`, reported until each points at a real page. `data-unchecked` on the element exempts one link the gate cannot see — a build product, an address another process serves. Moving or retiring a page is `ckit mv` / `ckit rm --to`, which rewrite every link to it and record the old address in kit.json `moved`: `ckit serve` answers it with a 301 and `ckit export` leaves a refresh there, so outside links and bookmarks keep working.

## References

Ids a repo declares in kit.json `"refs"` (`{"pattern": "Q-\\d+", "href": "/shell/record.html?p=QUESTIONS.md#{id}"}`) become links wherever they appear in a page's text — inline `<code>` included; `<pre>`, links, headings, anything inside an element marked `data-norefs`, and a qualified id (`other:Q-3`) left alone — and a heading in the record that opens with one gets it as a stable anchor.

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
| `.cyc` | cycle / step chips (`.cur` · `.run` · `.viol`) |
| `.prow` | listing row (`.cur` · `.skip`) |
| `.drawer` | detail panel (`.hyp` for a quoted hypothesis) |
| `.mtable` | key column bold |
| `.wcap` · `.wcap-sm` · `.wcap-md` · `.wcap-lg` | caption sizes |

Chapter-only widgets (a bespoke encoding table, a one-off explorer, …) stay in that chapter's `<style>`.

## Motif boxes

`.twin` · `.split` · `.note` / `.note-warn` · `.law`

## Genres and voice

Where a page lives is its genre, and the genre carries a **voice** — register, assumed reader, forbidden moves — plus the checks the gate runs on it. The table is `kit/genres/GENRES.md`; the machine spec is `kit/genres/genres.json`. `ckit new <genre> <slug>` scaffolds from the right skeleton and prints the voice card. Every page's first `<p class="sub">` declares its status (LIVE · HISTORICAL · PARKED · RETIRED · FROZEN · DRAFT) — the gate checks it.

## Annotations (review without a session)

When a page is served by the engine, an **✎ Annotate** toggle appears bottom-right. Select prose and comment, or add a page-level note; threads are written to `<page>.annotations.json` beside the page and committed. Nothing needs to be running for a note to survive: an agent later runs `ckit annotations list` and the `/address` skill. Quotes are anchored by text, not by CSS path, and `ckit check` fails if an open thread's quoted passage is no longer on its page. The chrome classes (`hb-ann-*`) are injected — never author them, and never hand-edit a sidecar.

Two kinds of thread. A reader's **question** opens and waits; whoever acts on the page replies and keeps, addresses or declines it. An agent's **flag** (`ckit annotations add --kind flag --label "worked example" …`) rests as `noted`: a disclosure that the passage was written beyond its source, marked on the page and asking nothing until the reader keeps it or asks for a change. States: `open` · `noted` · `addressed` · `declined` · `withdrawn`. The panel offers Reply, Keep and Decline on a question, Keep and Ask for a change on a flag, Withdraw on a thread you authored and Reopen on a closed one, so no side of the loop needs the command line. `<page>#ann=<id>` opens the panel on that thread; **`/shell/review.html`** lists every thread in the library from the generated `content/threads.json`, grouped by page or by label, with a whole group kept at once. The rail and the palette show *Review* while the engine serves the library; a static export carries neither the sidecars, the index nor the page.

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

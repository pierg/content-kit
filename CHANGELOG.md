# Changelog

Every release names what it breaks and how to move across. A repo pins the engine version it was checked against (`"ckit"` in `kit.json`), so an upgrade is always a deliberate act per repo.

## 0.5.0.dev1 — unreleased

0.5.0.dev0 was this work's prototype, on a branch. The version moved so that a repo pinned to the prototype fails the pin loudly (re-pin with `ckit init .`) instead of meeting the new checks unannounced.

A shell for reading and for finding: the library organised by topic, a reading measure, a palette, peeks, a page rail and a generated home page — and the catalog grows what a knowledge base needs (topics by name, tags, dates). Every class and token of 0.4 is kept, the chrome still lives outside `<main>` (wherever `<main>` sits), and the script APIs keep their 0.4 timing — tabs, popovers, backlink lists and `libBook()` set up by a page's own `DOMContentLoaded` handler are wired, and a failure in the chrome cannot take them down.

And a library an agent can organise without guessing and without breaking it: what a topic, a tag and a move are is declared and checked, not inferred from how existing pages look; `ckit topics`, `ckit tags`, `ckit mv` and `ckit rm` reorganise with every link, annotation and date intact; `/curate` is the procedure; and the pages an agent learns from are held to the same rules as the ones it writes (the lint now checks links, prose and tags — the rules existing pages had drifted from).

### Changes a repo sees

1. **Generated indices change shape** — regenerate them (`ckit lint`) and commit. `catalog.json` gains `site` (name, question), `topics` (kit.json `topics`, when declared), and per entry `tags`, `created`, `updated` and `sha`. `site` and `topics` join the reserved catalog keys: a genre may not use them as its directory.
2. **A page edited without `ckit lint` fails the gate.** An entry's `sha` covers its page (a book: every page in it), read with line endings normalised, so its `updated` date moves exactly when its content does — and a stale one is a stale index. Dates are seeded from git history the first time an entry is seen, else today (UTC, or `$CKIT_TODAY`). Two branches that change the same page (or book) conflict in `catalog.json`; `ckit lint` resolves it and keeps the dates (when the file on disk does not parse it reads both sides of the conflict, then `HEAD`: a page kept from either side keeps that side's dates).
3. **The reading column narrows** to ~70 characters a line (`--measure`); figures, tables, code and side-by-side blocks break out to `--wide`. Pages whose prose sits inside a classed wrapper keep the wide column.
4. **The generated home page** (no `home` in kit.json) is built from the committed indices: topics as cards (with each hub's opening line), recently updated, a shelf per genre, the repo's links and record files.
5. `ckit serve` sends files `Cache-Control: no-cache` with an `ETag` (mtime to the nanosecond, and size) and answers a matching `If-None-Match` with 304 (was `no-store`); generated responses stay `no-store`.
6. **Every internal link must resolve** (quoted attribute or not), as the exported site will serve it (`ckit/links.py`): no address nothing answers, no directory without an `index.html`, no bare slug, no letter-case mismatch, no git-ignored target, no address kit.json `moved` redirects. `data-unchecked` exempts one link the gate cannot see. Fix what it names; `ckit mv` fixes links for you when it moves a page.
7. **One paragraph per line is checked** (`ckit/prose.py`): a p, li, td, figcaption, blockquote… whose text is broken across lines at a column fails, reported once per page. `ckit unwrap` joins them: a break after `<br>`, a break inside a tag, math (display, and inline math holding a TeX `%`) and code keep their lines, and the catalog is regenerated first so a joined page keeps its dates. The text a reader sees does not change — unless the page's CSS makes whitespace significant (`white-space: pre`).
8. **Tags are lowercase slugs, each once** (`a-z 0-9 - . _`). The lint prints the slug to use.
9. **Skeletons**: placeholder links are `…/OTHER…` — reported until each points at a real page — and skeletons carry no placeholder tags. The hub skeleton no longer links a book from another repo, and the concept skeleton's comment says what it means.
10. **`ckit check` reports every stage in one run**: the pin, the shell and the declarations are preconditions and still stop it; the indices, the lint and the books all run, and the gate fails at the end naming each stage that failed.
11. **A catalog entry's `sha` ignores whitespace**: a page re-flowed, re-indented or checked out with CRLF keeps its dates and is not stale. A catalog written by an earlier 0.5.0.dev0 keeps its dates across the change (its entries take the new `sha` on the next `ckit lint`).
12. **`content/threads.json` joins the generated indices** — every annotation thread with its page's title and whether its anchor holds — and the catalog carries `threads` (`open`, `noted`, `total`) once a repo has any; `threads` is a reserved catalog key. Regenerate (`ckit lint`) and commit. Every write through the engine (the browser, `ckit annotations …`) regenerates both, so the gate stays green without a lint in between. Neither is exported.
13. **A thread has a kind.** A `question` (the default, and every thread written before kinds existed) opens and waits. A `flag` — what an agent leaves on a passage it wrote beyond its source — rests as **`noted`**, a fifth state: it pins and discloses the passage and asks nothing until a reader keeps it or asks for a change. `ckit annotations list` shows the open questions, `--state noted` the flags, `--state live` both, `--kind` either. A noted flag whose passage left the page is named by the lint (`note: … is stale`), never failed; an open thread's is the failure it always was.

14. **A page states its status only when it is not current.** None stated means LIVE, the default: the gate accepts a page that states nothing, and checks that a stated word is one the shell knows (HISTORICAL · PARKED · RETIRED · FROZEN · DRAFT, or LIVE). The pill above the text shows only a status that is not LIVE, and the skeletons state none. `ckit unwrap --status` drops a stated LIVE from each opening line, capitalising the lede, and keeps the page's dates — a catalog entry's `sha` reads a stated LIVE as absent, and a catalog written by 0.5.0.dev1 keeps its dates across the change. The lint names the pages that still state LIVE, once per run, and never fails them. The project genre's `<meta name="status">` (active · shipped · paused) is a different thing and is unchanged.

### Added

- **The library rail** — by topic when pages declare one, by genre otherwise, folding and remembered; the theme (auto · light · dark) and reading face (serif · sans) toggles.
- **The page rail** — outline with scroll-spy, the page's kind, topic, dates, reading time and tags, and *Linked from* (automatic backlinks).
- **The palette** — ⌘K / Ctrl-K / `/`: pages, topics, tags and the shell's pages; full text when Pagefind answers.
- **Peeks** on internal links; the status pill on the opening line; a top bar with breadcrumbs or a book's chapters.
- **Browse** (`/shell/search.html`): multi-word matching, kind / topic / tag filters kept in the URL, newest first.
- **Full text through Pagefind, optional** (`ckit/pagefind.py`): built in the background by `ckit serve` into a private temporary directory named for its process (rebuilt after `ckit lint`, the previous build kept for pages already open, removed when the server stops — `ckit down` included — and swept by the next server if it was killed) and written by `ckit export`; `/shell/pagefind.json` says whether it answers. Nothing committed, nothing required.
- **Fonts**: Inter and Source Serif 4, variable, latin, weight axis (SIL OFL), vendored under `shell/vendor/fonts/`.
- **View transitions and speculation-rules prefetch**, where browsers have them.
- **A weight budget for the shell**, checked by the selftest: `lib.css` + `lib.js` ≤ 32 KiB gzipped (28.1 KiB now, from 11.8 KiB in 0.4), fonts ≤ 200 KiB (147 KiB).
- `data-hb-app` on the shell's own pages (full width, sans, no page rail).
- **`ckit topics`**: each topic with its label, hub and page count, pages with no topic, topics no one declared; `add`, `rename` (its hub moves with it), `merge … --into` (the old slugs become tags; the gate names the hubs to fold), `assign` (how a topic is split). **`ckit tags`**: each tag and its pages, spellings that look alike; `rename`.
- **`ckit mv <page> <to>`**: moves a page, or a folder page with everything in it, rewriting every link to it (and each of its own relative links that would no longer hold), carrying its annotation sidecar (re-addressed) and its created date (its updated date becomes the day of the move), and recording the old address in kit.json `moved`. **`ckit rm <page> --to <page>`** retires a page into another the same way; it deletes only what git can bring back, so it is refused outside a git work tree, for anything untracked, ignored or changed since the last commit, while any page it would retire has an open annotation thread, and for a `--to` inside the folder it retires. `ckit serve` answers a moved address with a 301; `ckit export` leaves a refresh there (never outside `--out`). A malformed `moved` address (a `.` or `..` segment, `//`, a scheme) fails the declarations; an old address a page lives at again, a chain that ends where no page lives, or a cycle is reported with the lint.
- **`ckit new … --topic <slug> --tags a,b`** writes the page's metas (an undeclared topic or a malformed tag is refused before anything is written); a hub named for a declared topic takes it; a new page at an address kit.json `moved` redirects takes the address back.
- **`ckit unwrap [paths]`**, the fixer for rule 7; **`--status`** also drops a stated LIVE (rule 14).
- **The generated home page, served, opens with the questions waiting** ("Waiting for you"), each linked to its thread on its page, and names how many passages agents flagged, with a link to the review page. The exported site omits them, and a repo whose kit.json names its own `home` does not get the generated page (`ckit annotations list` works everywhere).
- **The review loop runs both ways from the browser.** The panel gains a reply composer and role-aware actions — Reply, Keep and Decline on a question; Keep and Ask for a change on a flag; Withdraw on a thread you authored; Reopen on a closed one — so the acting side no longer needs the command line; a flag renders collapsed under its label. `<page>#ann=<id>` opens the panel on that thread. **`/shell/review.html`** lists every thread in the library from `content/threads.json`, grouped by page or by label, filtered by state, each jumping to its passage, with a whole group kept at once. The rail and the palette show *Review* while the engine serves the library. `ckit annotations add --kind flag --label …` leaves a flag; **`relabel`** changes a thread's kind or label (a question made a flag rests as noted; a flag made a question opens); **`resolve`** moves every live thread a filter selects (`--page`, `--kind`, `--label`, `--by author-prefix`) to one state with one reply each; **`prune`** drops closed threads untouched for N days from committed sidecars (git history keeps them), never a live one. The server accepts `relabel` and `resolve` as ops.
- **`/curate`**, a new skill vendored by `ckit init` beside `/present` and `/address`: topic or tag, opening, renaming, merging and splitting topics, keeping hubs current, reusing tags, promoting, moving and retiring pages, a health pass. `/present` gains two rules: flag what an agent writes beyond its source (a labelled flag per passage, resting as noted, and a question only where the owner's answer changes the page), and organising is `/curate`'s — never `git mv` a page. `/address` acts on open threads only, treats an owner's reply on a reopened flag as the instruction, and leaves noted flags to the owner.

### Fixed

- `craft/diagram.md` said a token in an SVG presentation attribute (`fill="var(--teal)"`) "does not resolve". It does, in inline SVG; the playbook now says so, and names the real difference (a presentation attribute yields to any stylesheet rule, a `style` does not) and the real limit (no token resolves in an SVG loaded from a file).
- The book verifier's output goes through Python's streams, so a caller capturing `ckit check` captures it too.

### Moving a repo from 0.4

```bash
git -C ../content-kit pull                                  # main: the engine and the kit
ckit init .                                                 # re-vendors kit/ (and links /curate), pins "ckit": "0.5.0.dev1"
ckit unwrap && ckit lint                                    # one paragraph per line; regenerates the indices
make check                                                  # then fix what it names — dead links, malformed tags
git add kit kit.json content .claude && git commit          # the files that changed, reviewed first
```

## 0.4.0 — 2026-09-22

The page contract stops knowing what a lab is. Everything a layer needs now reaches the engine through ten declared extension points, and the vocabulary that used to be built in — the story genre, record-id checks, the dashboard, the formal-verification colours and widgets — moves out to the layers and themes that own it. The engine installs as a package.

### Breaking changes

1. **The config file is `kit.json`.** `lab.json` is still read, with one deprecation line per run, until 0.5. `$CKIT_ROOT` replaces `$LAB_ROOT` (the old name is still accepted).
2. **Colour tokens are named for their hue.** Set register `--reach --cert --target --slack --leak` → `--teal --indigo --blue --amber --red`; role register `--gen --judge --world` → `--azure --violet --orange`. Swatches and lane borders follow: `sw-<hue>`, `lane-<hue>`. Verdict tokens (`--kept --discarded --rejected --untested`) are unchanged.
3. **A `var(--x)` that nothing declares fails the lint** — neither the shell, the repo's theme, nor the page itself. `lane-` joins the class prefixes the lint checks.
4. **Domain widgets left `lib.css`:** `.nrow`, `.cellrow` / `.cell` / `.vline` and their state classes, `.gate` / `.g` / `.gline` / `.lanebar`, `.lchip`, `.cbar`. They live on, verbatim, in `templates/theme-fv.css`.
5. **The lab vocabulary left the engine** (it is in lab-kit 0.2.0, arriving through the extension points): the `story` genre and its skeleton; the `bound_ids`, `defn_no_findings` and `no_findings` checks; `ladder.json`, `/shell/dashboard.html`, the catalog's `dashboard` flag and `"home": "dashboard"`; the hardcoded `F-` / `C-` link pattern; the `experiment` · `finding` · `claim` · `mission` chronicle kinds.
6. **The `project` genre is generic again** — operational, dated, present tense — with its pre-2026-09-16 skeleton. `concept` no longer checks `defn_no_findings`; `entry` cites "what each claim rests on" rather than finding ids.
7. **Generated indices changed shape** — regenerate them (`ckit lint`) and commit: `catalog.json` gains `groups` (and `links`, `refs`, `indices` when declared); `chronicle.json` is version 2, with a `kinds` list and, when an extractor supplies them, `cards` in place of `experiments`.
8. **`install.sh` is `ckit init`.** The script remains as a one-line wrapper for one minor version. `kit/PIN` source lines record a URL and a ref (a commit, or the release tag for an installed wheel) instead of an absolute path; `make kit-sync` finds the source through `$CONTENT_KIT`, a local path, `ckit where`, or a sibling checkout.
9. **`lib.css` imports `/shell/theme.css`** first — an empty stylesheet unless the repo declares a theme.

### Added

- **Extension points in `kit.json`**, each validated by `ckit check` and each with a planted fixture that fails by name: `genres` (an object, or a list of objects and repo-relative JSON files, deep-merged in order; `after` and `label` place and name a genre's group), `checks` (modules exposing `CHECKS` and `REPO_CHECKS`; a genre naming a check nobody provides fails the gate), `generators` (modules whose files join the drift-checked indices), `chronicle.extractors` (now declaring their own `KINDS` and `CARDS`), `shell_pages`, `links`, `refs`, `theme`, `classes`, `indices`.
- **The catalog is the genre table**: sidebar, landing page and search filters are derived from the loaded genres, so an extension genre appears everywhere a core one does.
- **`<meta name="topic">`** reaches the search index and the catalog (as `topic`) when a page declares one; whether a topic is *required* is a layer's convention (folio's).
- **An extra index may be an object** carrying its records under `records` (a federated index with its sources beside them).
- **`ckit init`, `ckit where`, `ckit export`.** `export` writes a static site (landing page, a 404 page, shell, theme, shell pages, content, record files); `--base /<repo>/` serves it under a path such as a GitHub project site — the shell reads its base from its own URL, so nothing else needs configuring. `home` may name a shell page.
- **Packaging**: `uv tool install git+https://github.com/pierg/content-kit@v0.4.0` gives a `ckit` that carries the kit as package data. `make check` proves it (`tests/wheel.sh`).
- **The kit's own documentation**, written as a content-kit library in `content/`, published at <https://pierg.github.io/content-kit/>.
- LICENSE (MIT), CONTRIBUTING, CODE_OF_CONDUCT, and CI: `check.yml` (Python 3.10–3.14 with node) and `pages.yml`.

### Fixed

- The form checks read markup — tags, their attributes, style and script bodies — not the text a page shows, so a code sample or an issue number (`#abc123`) no longer trips the hex, class or token checks, and a commented-out tag is not read.
- `ckit check` needs node only when there is a book to verify, not whenever `content/books/` exists.
- The chronicle's "Right now" banner and kind filters stay in their own views.
- The e2e suite runs on macOS (portable in-place `sed`); `verify.sh` no longer needs bash 4's `mapfile`.
- `pyproject.toml` and `ckit.__version__` agree.

### Migrating a repo from 0.3

```bash
uv tool install git+https://github.com/pierg/content-kit@v0.4.0   # or: bash install-engine.sh from a checkout
git mv lab.json kit.json
ckit init .                                                        # re-vendors kit/, pins "ckit": "0.4.0"
```

If the pages use the old colour names or the widgets that left `lib.css`, keep them rendering identically with the migration theme:

```bash
mkdir -p assets && cp "$(ckit where)/templates/theme-fv.css" assets/theme.css
```

and in `kit.json`:

```json
"theme": "assets/theme.css",
"classes": ["sw-reach", "sw-cert", "sw-target", "sw-slack", "sw-leak", "sw-gen", "sw-judge", "sw-world",
            "lane-reach", "lane-cert", "lane-target", "lane-slack", "lane-leak", "lane-gen", "lane-judge", "lane-world"]
```

A lab then re-runs lab-kit 0.2.0's `install.sh`, which registers the story genre, the record checks, the dashboard and the record-id links. Finally `ckit lint` to regenerate the indices, `make check`, and commit what changed.

## 0.3.2 — 2026-09-16

A sealed `story` genre and a front-door `project`; a lab's home may be an authored content page; the opt-in dashboard (`ladder.json`); record ids linked in pages and anchored in the record viewer.

## 0.3.0 — 2026-09-11

The chronicle distills: Story by default, Timeline for archaeology.

## 0.2.0 — 2026-09-11

The record and the chronicle: `/shell/record.html` renders the repo's markdown record in the shell, `/shell/chronicle.html` a generated timeline over it.

## 0.1.1 — 2026-09-11

The gate fails on stale indices instead of rewriting them.

## 0.1.0 — 2026-09-11

The reader-path layer, extracted from lab-kit: the shell, the genres and their voice, the craft playbooks, `/present` and `/address`, the session-free annotation loop, and the content gate.

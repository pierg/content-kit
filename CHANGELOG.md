# Changelog — LIVE

Every release names what it breaks and how to move across. A repo pins the engine version it was checked against (`"ckit"` in `kit.json`), so an upgrade is always a deliberate act per repo.

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
- **`ckit init`, `ckit where`, `ckit export`.** `export` writes a static site (landing page, shell, theme, shell pages, content, record files); `--base /<repo>/` serves it under a path such as a GitHub project site — the shell reads its base from its own URL, so nothing else needs configuring. `home` may name a shell page.
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

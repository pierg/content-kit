---
name: curate
description: Organise a content-kit library without breaking it — decide topic or tag, open, rename, merge or split a topic, keep hubs current, reuse tags, promote, move or retire a page, and run a health pass — with the ckit verbs that keep every link, annotation and date intact. Use when the user says organise, reorganise, tidy, curate, "new topic", "merge/split/rename these topics", "move/promote/retire this page", "clean up the tags", or "is the library healthy?".
---

# /curate — organise the library without breaking it

A library's organisation lives in a few declared places. Read them; never infer it from how existing pages happen to look.

| What | Where it is declared | What checks it |
|---|---|---|
| Which topics exist | kit.json `topics`: `{"slug": "Label"}` | a layer (a folio: every page on one, one hub each) |
| A page's topic | `<meta name="topic" content="slug">`, one per page | the layer |
| A page's tags | `<meta name="tags" content="a-tag, another">`, lowercase slugs | `ckit lint` |
| A page's kind (genre) | its folder, `content/<genre dir>/…` | `ckit lint` |
| Where a moved page went | kit.json `moved`, written by `ckit mv` and `ckit rm` | `ckit check` |

Everything a reader navigates by (the library rail, the home page, Browse's filters, search, backlinks) is generated from those by `ckit lint`. A topic is metadata, not a folder: re-topicking a page never changes its address. Never hand-edit a generated file, and never move a page with `git mv`.

## 0 · Look first

```bash
ckit topics    # each topic: label · hub · pages; pages with no topic; topics nobody declared
ckit tags      # each tag and its pages; spellings that look alike
ckit check     # every problem, all stages, in one run
```

## 1 · Topic or tag?

A **topic** is a front door: a hub, a map, a reader who arrives at it cold. A **tag** is a facet: free, several per page.

- Start as a tag. Promote it to a topic when it has, or is about to have, enough pages that a newcomer needs a map (five or so) and a reader who would come to it on its own.
- Two candidate topics that would share most of their pages are one topic with two tags.
- Opening a topic is the owner's call. Propose it and say why; create it only when asked.

Open one: `ckit topics add <slug> --label "Label"`, then `ckit new hub <slug> --title "Label"` (a hub named for a declared topic takes it). Write the hub: the current take first, then the map, then what is open.

## 2 · Place a page

- **One topic**: where a reader would look for it first. Tag the rest, and link it from every hub it belongs on. A hub may list another topic's page; say why in the row.
- **On its hub's map, in the same change**: every new page gets a row with a one-line reason to follow it.
- **Tags**: reuse before inventing (`ckit tags`); a new tag is a lowercase slug.
- **Scaffold with its place**: `ckit new <genre> <slug> --title "…" --topic <slug> --tags a,b`, then replace every placeholder link the skeleton carries (the gate names each one).

## 3 · Reorganise

| Change | Do | Then |
|---|---|---|
| A topic's label | edit its value in kit.json `topics` | nothing else changes |
| A topic's slug | `ckit topics rename <old> <new>` | its hub moves with it |
| Merge topics | `ckit topics merge <a> <b> --into <c> [--label]` | the old slugs become tags; fold the hubs into one — write the merged map in the one you keep, then `ckit rm <other hub> --to <kept hub>` |
| Split a topic | `ckit topics add <new>`, `ckit new hub <new>`, `ckit topics assign <new> <page>…` | move those pages' rows from the old hub to the new one |
| Merge or rename a tag | `ckit tags rename <old> <new>` | — |
| Promote or move a page | `ckit mv <page> <new place>` (`content/entries/<slug>/` for a folder page) | rewrite it in its new genre's voice (a note promoted to an entry grows sections) |
| Retire a page | `ckit rm <page> --to <page that takes over>` | commit first, and settle its open threads (`/address`); `--folder` retires a folder page with everything in it |

`ckit mv` and `ckit rm` rewrite every link to the page (and a moved page's own relative links), carry its annotation sidecar and its created date (its updated date becomes the day it moved), and record the old address in kit.json `moved`, which `ckit serve` and the exported site redirect. `git mv` does none of that. `ckit rm` deletes only what git can bring back: commit first, and settle every open thread on what it retires. What a move cannot carry is anything kept outside the repo by address: a folio's flashcard revision history restarts for the moved page's cards, and `ckit mv` says so.

## 4 · Keep hubs current

A hub is its topic's map: a stance first, then every page on it, grouped the way a newcomer should read them, each with a reason, then what is open. When a page lands, moves or retires, its hub changes in the same commit. When the map has changed a lot, reread the stance: a stance older than its map is stale.

## 5 · Health pass

When asked, or after a large reorganisation:

1. `ckit check` is green.
2. `ckit topics`: every topic has exactly one hub, and no page is left without a topic where the layer requires one.
3. Every page on a topic is on its hub's map (compare the hub with `ckit topics`' count; a layer may check it).
4. `ckit tags`: alike spellings merged; a tag on one page either earns a second or goes.
5. DRAFT pages that have sat for weeks: finish them, or retire them.
6. Open annotation threads (`ckit annotations list`): `/address` them.

Report what you found and what you changed. Leave to the owner what is theirs to decide: opening or closing a topic, retiring a page they wrote.

## 6 · Flag what you add beyond a source

When you write something the source did not say (your own example, framing, or a claim from general knowledge), open a thread on that passage so the owner can keep, edit or cut it:

```bash
ckit annotations add <page> --author agent:<name> --quote "<exact passage>" \
  --body "Added — not in the source. Keep, edit or cut?"
```

A page drafted wholly from general knowledge gets one page-level thread (no `--quote`) and the status DRAFT. `ckit annotations list` lists the open threads — and so does the generated home page, under "Waiting for you", in a library whose kit.json names no `home`. `/address` settles them.

## 7 · Record and land

- Record every reorganisation in the repo's record (the markdown kit.json `record` names — a folio's `journal/log.md`) as a dated, tagged entry: `### YYYY-MM-DD — [decision] …`, old names → new.
- `ckit lint && make check`, then commit the pages, kit.json, the regenerated indices and the record together: the files you touched, never `git add -A`.

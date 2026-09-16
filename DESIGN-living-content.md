# Living content — how a lab's record and pages stay true and readable

**Status: LIVE** — a design adopted 2026-09-16 by proof-harness-lab, extending `VISION.md` (which it does not supersede). Part I (density) is being realized in lab-kit now; Part II (freshness) is the next engine slice. Written against the state of both kits at content-kit `5bdc018` / lab-kit `383ec8f`.

Two failures were observed on the same day in the same lab, and they are one problem. Three content pages sat a rung behind the record with the gate green: the dashboard is generated and cannot lag, the pages are hand-written and nothing compares them to anything. And the record itself had become unreadable: twenty-one finding rows carried 17,800 words, the newest row's *headline* was seventy words, the state file's "phase" bullet re-explained five findings in one breath, and the intuition behind each experiment existed nowhere as a thing you could read. A human trying to see the shape of the work, and an agent orienting at the start of a session, both had to load everything to learn anything.

The design law of `VISION.md` covers both: *a layer without a mechanical check is a suggestion, and suggestions drift.* The finding template said the headline is "one line" — unchecked, it reached seventy words. The genre rules said a project page is "explicitly perishable" — unchecked, it declared itself LIVE while it perished. So each part below ends by naming what checks it.

## The diagnosis, in one sentence each

**Freshness.** Staleness has three forms — a copied value, a state assertion written as prose, and a missing consequence — and they arise from mixing content of different volatility and provenance in one document, then transcribing derived values instead of referencing them.

**Density.** A finding has three parts for three readers — the headline (what is true), the defense (why it can be trusted, what it does not license), and the story (what it means) — and the record put all three at one level and one prominence, so every reader loads all of it.

The two share a cure: **separate by audience and volatility; never transcribe what can be referenced; make lag visible where it cannot be eliminated.**

## Part I — Density: the row is the interface

### The layered row

A finding row carries exactly what a citer needs, in about a hundred words:

    ## F-39 · A counterexample-to-induction on demand did not help: 19 of 29 solved vs the previous rung's 21, within noise
    **Status:** PROVISIONAL · DROPPED — keep rule did not fire
    **Tier:** lab finding under a locked pre-registration, blind-scored by an independent reviewer
    **Date:** 2026-09-15
    **Number:** 19 of 29 dev obligations (previous rung: 21 · plain loop: 13)
    **Bound:** One RISC-V core's dev set, one model, eight rounds; the −2 is within run-to-run variance, so this licenses "no lift", not "harms".
    **Why it matters:** The mechanism genuinely fired this time, so the technique is tested-and-null rather than untested.
    **Anchor:** `experiments/20260915-e3b-cti-projection/out/summary.tsv`
    **Re-derive:** `python3 -c "..."` → `19 / 29`
    **Defense:** `record/findings/F-39.md`

Its **defense** — the licensed sentence in full, the long-form scope bound, the blind predictions as scored, the reviewer's verdict, anomalies, disclosures, dated annotations — lives verbatim at the `Defense:` path and is never summarized back into the row. The experiment folder keeps the evidence and the locked pre-registration, as before; the defense is the bridge between the row and that folder.

Three rules make the row honest rather than merely short:

- **Plain is not vague.** "The technique didn't help" is simple and vague; "19 vs 21 of 29, within noise" is simple and precise. Headlines and stories go plain; the bound keeps every condition, because the conditions are what may be said.
- **Codes are links, not content.** No finding ids, mission codes, rung labels, paths or hashes in the headline, bound or why; they resolve in the defense and the shell. A sharp colleague outside the lab must be able to read the row and know what was found, under what conditions, and what it does not show.
- **Nulls at equal prominence.** A void, a drop, a fired kill rule is stated as plainly as a win, in the same fields, in the same place. Equal prominence, not equal length.

### The pyramid

Above the rows, the narrative has levels, and each level cites the level below by id: the program in a paragraph; each mission in a paragraph; each experiment in a line (its question, the one variable, its intuition, its lesson); each finding in a sentence. An agent orienting reads the program paragraph, the active mission paragraph and the experiment lines — a few hundred words — and knows the state. A human wanting the story reads the same pyramid from the top.

Two fields the record never had make the pyramid writable. Every experiment carries, at lock time, an **intuition** — one plain paragraph on why this is expected to help — and, at fold time, a **lesson** — one plain paragraph on what was learned about why it did or did not. The ladder story ("naming the failing helper: +6; showing why it failed: +2; a counterexample-to-induction on demand: no change — feedback that says *which* and *why* is what helps here") took four thousand words to reconstruct before those fields existed.

### The migration

Existing rows are migrated, disclosed, not left as a second shape: the tree is tagged first; each row's full text moves verbatim to its defense file; the heading keeps its id so every citation resolves; the row gains an explicit `Date:` recovered from git *before* the headline changes (the chronicle dated findings by searching history for the heading text, so a rewrite without the field would re-date every finding to the migration commit); the interface fields are drafted by a cheap model, independently verified against the row's own text by a stronger one, bound-checked by plain code, and assembled by a deterministic script that refuses to write on any violation. The migration is a dated decision entry in the logbook.

### What checks it (lab-kit)

- `chronicle_lab.py` parses the new fields and prefers `Date:` to git archaeology, with an id-keyed fallback.
- `ladder_lint.py` fails when a `Defense:` path does not resolve, and warns — softly, so it cannot be disabled on day one — on a headline over 24 words, a headline carrying an id, a malformed `Date:`, a state file over 500 words, and (once a lab declares `"findings_layered": true`) a row without a defense.
- The assembly tool ships a selftest with planted refusals: an id in a headline, an invented anchor, a missing draft, a non-verbatim defense.
- What no lint checks: that a plain headline does not overclaim relative to the licensed sentence. That is the reviewer's job, and the review gate already reads the artifact before the story about it.

## Part II — Freshness: four classes, and derived facts that cannot go stale

### Classes by volatility, not by form

| Class | Changes | Provenance | Rule |
|---|---|---|---|
| **Foundations** — the problem, the concepts, the field | per era | judgment | may cite only BANKED findings; carries no state |
| **Stories** — one sealed narrative per result | only if a bound finding changes status | judgment, bound to fixed ids | declares its bound findings; its status is computed from theirs; numbers only by reference |
| **Live state** — what is running, the last kept rung, what awaits a decision | per finding | derived | never authored; generated, embedded as a slot |
| **Views** — the program overview, hubs | composition | mostly derived | a small authored "why" with no numbers and no state; everything else a slot |

Frozen siblings — the paper, a post — are vintage-stamped and freeze-time-verified, never transcluded. The existing genres map onto this cleanly: concepts and chapters are foundations; a result entry is a story; the project page is a view. **Rolling narrative pages do not exist** — "the current study" is composed, and a lessons ledger is a record file the chronicle already indexes.

### Mechanisms — each extends a primitive the engine already has

1. **A structured export of the record.** `findings.json` and `claims.json`, emitted through the same regenerate-and-fail-if-stale path as the six existing indices, carrying the row's fields (now machine-readable after Part I). Convention-agnostic because it goes through the lab's parser and alias resolution.
2. **Reference slots, filled at lint time.** `<span data-cite="F-37" data-field="number">` — the same shape as today's `data-backlinks` slot, but filled by lint so the committed HTML is truthful without JavaScript and `ckit check` fails when a filled value drifts. A cite to a RETRACTED or SUPERSEDED row renders struck through. A transcluded value cannot be stale.
3. **Dependency stamps and computed vintage.** Two meta names: `bound` — the findings a page's judgment rests on, derivable from the ids it cites and overridable — and `frontier` — the record frontier it was written against, stamped at authoring. Lint computes each page's status from its bound findings and its lag from frontier versus the record's max, and renders the vintage line ("written against F-37 · 2 findings since") in place of the hand-typed date nobody reads. The experiment-to-finding binding the chronicle already computes makes the lag warning specific: a new finding in the same experiment as a page's bound findings means the page's subject moved.
4. **State is a slot.** `<div data-now>` and `<div data-panel="findings">`, filled from the panels the dashboard already renders. Present-tense state prose outside a slot is a smell the structural fix removes.
5. **Debt is visible.** A "Pages" panel on the dashboard: each authored page's class, bound statuses, frontier lag, open annotations; a page a rung behind shows amber. The reporter's trigger becomes "the panel is amber" instead of "someone remembers a milestone landed". Judgment can lag; lag is bounded and visible.
6. **Generate what needs no author.** A page per experiment from its locked pre-registration and its findings — question, the one variable, intuition, kill rule, predictions scored against outcomes, the licensed sentence, kept/dropped/void — and a page per finding: the row rendered richly, the re-derive command copyable, every citing page listed. These are what stories link to, and they cannot be stale.

### What checks it (content-kit)

- Generated files: stale ⇒ `ckit check` fails, as today. Filled slots are generated content and get the same treatment.
- `banked_only` for foundations generalizes the one time-aware check the engine has (`defn_no_findings`); result-shaped numbers outside a `data-cite` in a story or view warn — the uncited-numbers check today scans markdown but never HTML.
- A cited finding's status propagates: RETRACTED or SUPERSEDED bound findings warn, then fail once clean.
- Every generator gets a planted fixture. The dashboard's own questions panel already went stale by reading a question's first-declared status instead of a later annotation: generated is not automatically correct; a generator that reads the wrong field drifts like prose.

## Three honest limits

**Judgment cannot be made instant.** No mechanism here auto-updates prose. The promise is narrower and keepable: no derived value or state assertion can be stale, and every judgment page shows its vintage and is flagged when its dependencies move.

**Land the checks soft.** MIGRATION.md's rule binds: a check that fails from day one gets disabled, and a disabled check is worse than none. Warnings first; strict once clean.

**The record layer drifts too.** The state file re-explained findings in defiance of its own first line. Part I shrinks it to the pointer it claims to be; Part II makes the pointer a slot. Fixing `content/` alone would have moved the disease, not cured it.

## Adoption order

1. **Density in lab-kit + the first lab's migration** — the parser and lint changes, the layered template, the assembly tool, the migrated ledger, the state file as a pointer, the ladder story. Done first because it is what lets experiments resume with a readable record, and because the machine-readable fields are what Part II transcludes.
2. **The record export, reference slots and stamps** — the engine slice that kills copied-value and state staleness.
3. **The Pages panel and generated experiment/finding pages** — visible debt and author-free pages.

## What is not decided

- Whether the defense file lives under `record/findings/` (chosen for now: it is record content, and rows that anchor several experiments have no single folder home) or beside each experiment's evidence.
- Whether `bound` should be purely derived from cited ids or always declared; derivation is convenient, declaration is honest about what a page actually rests on.
- The exact registers for the story and view genres, and whether views need an authoring skill at all once they are mostly slots.

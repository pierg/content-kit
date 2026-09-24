# Craft — how to lay a thing out in this shell

The genre says what a page *is*; craft says how a block inside it is *built*. One playbook per kind of block, each written against the shell's own vocabulary (`shell/COMPONENTS.md`) — there is nothing to import and no new CSS to write. Read the matching playbook before writing the block, and read two when the block is two things (a comparison that contains a diagram).

Craft is guidance, not a gate: the lint checks that the vocabulary is the shell's, not that it was used well. A reviewer judges that.

| You want to show | Playbook |
|---|---|
| options against each other, before vs after, ours vs theirs | [`comparison.md`](comparison.md) |
| a relationship, a flow, an architecture, a state space | [`diagram.md`](diagram.md) |
| many records a reader will scan, not read | [`table.md`](table.md) |
| what happened when, or what happens in what order | [`timeline.md`](timeline.md) |
| source, a patch, a listing walked through | [`code.md`](code.md) |
| a rendered picture from a source outside the page | [`figure.md`](figure.md) |

## Rules that apply to every block

**Show, then tell.** A relationship is a diagram, a set of options is a comparison, a sequence is a timeline. Prose is for what cannot be shown: rationale, trade-offs, open questions.

**One register per figure.** The shell has two color registers — SET (`--teal --indigo --blue --amber --red`) for geometry of sets, ROLE (`--azure --violet --orange`) for actors in a loop — and a figure uses one of them. Mixing them makes a reader decode two legends at once.

**Nothing overflows.** A nested grid or flex child needs `min-width: 0` and `minmax(0, 1fr)` tracks, or a long monospace token pushes the whole page sideways. The shell's `.cols` already does this; a page-local grid must too. Wrap or truncate long unbreakable text deliberately; never let it decide the layout.

**Label everything a reader must decode.** Every box has a name, every arrow has a verb, every chip has a legend somewhere on the page. A caption says what the reader should *see*, not what the figure *is*.

**Page-local CSS stays page-local.** A widget used once lives in that page's `<style>`. When it appears in three pages it is promoted into the shell and documented — until then it is not shared, and it does not invent tokens.

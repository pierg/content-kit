# Table — records a reader scans, not reads — LIVE

**When.** Many things with the same fields: results per benchmark, works in a cluster, milestones with dates. If there are two rows, it is a comparison; if the fields differ per row, it is a list.

**The move.** Put the field the reader sorts by in the first column and keep it short — a slug, an id, a date. Chips for anything categorical (`v-*` verdicts, `ev-*` evidence, `st-*` status) so the eye can count without reading. Numbers right-justified in their own column with the unit in the header, not in every cell. In a lab, a number's finding id sits beside it as an ownership stamp: `<span class="own">F-28</span>`.

```html
<table>
<tr><th>Design</th><th>EBMC</th><th>sby</th><th>Lemmas</th><th>Verdict</th></tr>
<tr><td class="mono">gulwani_cegar1_5</td><td>timeout</td><td>proved</td><td style="text-align:right">2</td>
    <td><span class="v v-kept">CLOSED</span> <span class="own">F-31</span></td></tr>
<tr><td class="mono">fifo_vis</td><td>proved</td><td>proved</td><td style="text-align:right">0</td>
    <td><span class="v v-unt">FLOOR</span></td></tr>
</table>
<p class="wcap">Verdicts per design under the locked budget; a FLOOR row proves with no lemma and is not a win.</p>
```

## Long tables

Past ~15 rows, give the reader a way in: a lead-in that says what to look for ("three rows are red, and they share a cause"), the interesting rows first when order is not semantic, and a `.wcap` caption naming the source. A table that must be filtered belongs on a page with the tabs primitive (`data-hbtabs`), one pane per view, not one enormous table.

## Overflow

A table with a wide monospace column will push the page sideways on a narrow viewport. Either let the column wrap (`overflow-wrap: anywhere` on that `td` in the page's `<style>`), or put the table in a scroll container the page declares (`<div style="overflow-x:auto">`). Never let it decide the page width.

## Do not

Do not put paragraphs in cells. Do not merge cells to make a header span; make two tables. Do not encode a verdict as a color alone — the chip has text.

# Figure — a rendered picture from a source outside the page

**When.** The picture is produced elsewhere — a plot from a generator, a rendered set-diagram that a paper also uses, a photograph of a whiteboard — and the page embeds it rather than draws it. A diagram the page could draw inline is a diagram (`diagram.md`), not a figure.

**The asset rule.** The picture has one home: `assets/figures/<name>.svg`, beside its generator, so the page, the paper and a post all embed the same bytes and a regenerated figure updates everywhere at once. A page never keeps a private copy. PDFs are derived and not tracked; SVG is the source of record.

```html
<figure>
<img src="/assets/figures/floors-vs-agent.svg" alt="Closed-proof count per design: the floors close 31, the agent 13 more">
<figcaption><b>What the reader should see:</b> every agent win sits to the right of the floor line — the agent adds, it never replaces.</figcaption>
</figure>
```

## Alt text and captions

`alt` says what the picture shows for a reader who cannot see it — the result, not "a bar chart". The caption says what to look *for*. A figure that carries a number carries its source in the caption: `<span class="own">R-29</span>`.

## Sizing

The shell scales an image to the column and rounds it. Do not set `width`/`height` attributes to force a size; if a figure must be narrower than the column, wrap it in `.cols` beside its explanation.

## Charts

A chart is a figure whose generator is data plus a script. Keep both in `assets/figures/generators/`, make the SVG reproducible from them, and use the shell's registers for series colors — never a library's default palette, which will not survive dark mode and will not match the rest of the page.

## Figures generated from the record

A figure that draws a result is generated, and its generator sits beside the SVG with a `--check` that re-derives every drawn fact out of the record:

- **every number**, against the row that licenses it — matched as a whole phrase against that row's `Number` line (or its `Re-derive`), never as a substring, so `13` cannot pass by sitting inside `130`;
- **every verdict word** — kept, dropped, void — against the same row's `Status`, so a bar cannot stay green after its row is retracted;
- **every date**, against the mission file and the rows the picture draws.

The gate runs the checks (in a lab, a `figures-check` target), not the drawing: rendering needs fonts and a converter, checking needs only the record. Regeneration from unchanged inputs must be byte-identical, or the gate cannot tell a redraw from a drift. And the caption carries the ids of every row the picture draws — a number that exists only inside the picture is the worst uncited number there is: not searchable, not selectable, and no reader can tell which row it came from.

## Do not

Do not embed a PNG when an SVG exists. Do not put the picture's explanation inside the picture; it belongs in the caption where it can be searched, selected and annotated. Do not link to a figure on another host.

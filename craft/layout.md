# Layout — when a page designs itself

**When.** A column of prose would flatten what the page has to get across: a system with parts a reader should open one at a time, a flow a reader should follow, a set of things to compare at a glance, a space to explore, a sequence that is better stepped through than read. Then the page lays itself out, whatever its genre. The rest of the time it doesn't: an argument, a definition, a reading or a narrative reads best in the column, and a designed page costs more to write and to keep. Choosing is the author's call, made on purpose; the default is the column.

A figure inside a column page is not this. A diagram, an explorer or a stepper that a chapter needs goes in the chapter, in its own `<style>` and script (`diagram.md`, `CRAFT.md`). This playbook is for the page whose whole layout is the argument.

## The contract

```html
<body class="hb" data-hb-canvas>
<main>
  <h1>…</h1>
  <p class="sub">The one line that says what the page is.</p>
  …the page's own layout…
</main>
</body>
```

`data-hb-canvas` gives the page all of the canvas between the library and the page panel, the sans face and no measure. Everything else about the page is the author's: grids, columns, widths, type scale, sections, interaction, motion. Five things stay fixed, because the library reads them:

1. **The words are in the markup.** Write every sentence, label and caption in the HTML. A script may arrange, reveal, highlight and animate them, and must not write them. The gate anchors annotations by quoting the page file, and search reads its title, `.sub`, headings and definitions from the same file. Text a script generates is invisible to both: its annotations go stale and search misses the page. The one exception is a label that repeats words already in the markup (a dial's tick names, a chart's axis).
2. **The genre's hooks stay.** A concept keeps its `blockquote.defn`; a chapter keeps its number and its no-forward-links rule; a hub links every page on its topic, each with its reason; a project keeps its dated status; every page keeps an `<h1>`, a first `<p class="sub">` and its `topic` and `tags`. `GENRES.md` lists them.
3. **The voice rules that aren't about layout stay.** Take a position where the genre does, attribute every claim where it's made, give every number its source, state a null as plainly as a win, and flag what you wrote beyond the source (`/present`, rule 7).
4. **Colours come from the shell's tokens.** Use `var(--teal)`, `var(--surface-1)`, `var(--ink-2)` and the rest, never a hex value, so the page works in both themes. One register per figure still holds.
5. **The page adapts to the canvas, not the window.** The panels share the window with the page, and a reader opens and closes them without resizing it. Write `@container hb-canvas (max-width: 700px) { … }`, never `@media (max-width: …)`, for anything about the page's own layout. Check the page with both panels open at about 1440px (a canvas near 780px), with both closed, and at phone width.

## Choosing a form

Start from what the reader must come away with, then pick the form that shows it:

| The material is | A form that shows it |
|---|---|
| a system with parts | a map: the parts drawn in place, each opening its own panel or card |
| a sequence or a flow | a stepper, or a sticky figure beside prose that advances it |
| options, tiers or cases | columns side by side, or a matrix the reader scans down one axis |
| a mechanism with a setting | a control (a dial, a toggle) whose effect the page shows at once |
| a progression across levels | a descent or a ladder: one card per level, arrows labelled with what changes |
| a map of a topic or a book | cards grouped the way a newcomer should read them, each with its reason |

Keep the page's words in the order a reader would read them without the layout. A screen reader and a reader with scripts off get that order, and so does anyone reading the page file.

## Mechanics

- **Only the page's own classes.** Prefix them (`.ps-…`, `.fv-…`) and scope every rule under `.hb`.
- **Nothing overflows.** Use `minmax(0, 1fr)` tracks and `min-width: 0` on grid and flex children.
- **Motion is optional, never required.** Respect `prefers-reduced-motion`, and make sure the page reads fully with it off.
- **Keep scripts small and local.** Keep a script beside the markup it drives, in the page, and let it only toggle classes and attributes. A book chapter's inline scripts run in the gate against a small stand-in DOM: build SVG as markup (`innerHTML`) rather than with `createElementNS`.
- **Test controls from the keyboard.** A control is a `<button>`; a picked state is `aria-pressed`; a live readout is `aria-live="polite"`.
- **The shell draws the chrome.** Don't add a page rail or a table of contents of your own: the page panel shows the outline from the page's headings, and Linked from and Links to.

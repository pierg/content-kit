# Diagram — relationships, flows, architecture, state — LIVE

**When.** The thing to show is a structure: what connects to what, what feeds what, which states reach which. If the reader would draw it on a whiteboard to explain it, it is a diagram.

**The medium.** Hand-authored inline SVG inside a `<figure>`. Inline, so the shell's tokens apply and dark mode works; hand-authored, so every element is deliberate and the source is diffable. No raster screenshots of diagrams, no diagram-as-a-service.

**The register.** One color register per figure. Sets and their geometry → SET (`--teal --indigo --blue --amber --red`). Actors in a loop → ROLE (`--azure --violet --orange`). Tokens go through `style="fill: var(--teal)"` or a class in the page's `<style>`, never as a bare presentation attribute (`fill="var(…)"` does not resolve) and never as a hex value.

## Skeleton

```html
<figure aria-label="The proof loop: the search loop proposes, the frozen judge decides">
<svg viewBox="0 0 640 220" role="img" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" style="fill: var(--ink-2)"/>
    </marker>
  </defs>
  <rect x="40" y="70" width="200" height="80" rx="10" style="fill: var(--surface-1); stroke: var(--azure); stroke-width: 2"/>
  <text x="140" y="105" text-anchor="middle" style="font-weight: 700">search loop</text>
  <text x="140" y="126" text-anchor="middle" class="t2">proposes lemmas</text>
  <rect x="400" y="70" width="200" height="80" rx="10" style="fill: var(--surface-1); stroke: var(--violet); stroke-width: 2"/>
  <text x="500" y="105" text-anchor="middle" style="font-weight: 700">judge</text>
  <text x="500" y="126" text-anchor="middle" class="t2">decides, never proposes</text>
  <path d="M240 100 L398 100" style="stroke: var(--ink-2); stroke-width: 1.5" marker-end="url(#arrow)"/>
  <text x="319" y="92" text-anchor="middle" class="t3">candidate</text>
  <path d="M400 125 L242 125" style="stroke: var(--ink-2); stroke-width: 1.5" marker-end="url(#arrow)"/>
  <text x="321" y="145" text-anchor="middle" class="t3">verdict</text>
</svg>
<figcaption><b>Two actors, one direction each.</b> Candidates flow right, verdicts flow left; nothing on the left ever decides.</figcaption>
</figure>
```

`svg text` inherits the shell's font and ink; `.t2` / `.t3` are the secondary inks. Keep the `viewBox` proportional to the content — the shell scales the figure to the column.

## Rules

Every box has a noun. Every arrow has a verb, written on it. A state space shows which states are reachable (`--teal`) versus inside the certificate (`--indigo`) versus violating (`--red`) — and never colors an actor with a set token. Legends live in the caption when three or fewer, in a small key under the figure otherwise.

## Do not

Do not draw with `<div>` boxes and CSS arrows; it breaks at the first viewport it was not designed for. Do not embed an image of a diagram when the SVG could be inline. Do not use a diagram for a list.

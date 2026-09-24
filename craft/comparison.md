# Comparison — options, before/after, ours vs theirs

**When.** The reader must hold two or more things side by side and see where they differ. If they differ on one axis, that is a sentence, not a comparison.

**The move.** Put the axis of difference in the reader's eye first. Two things: `.cols` with a `.lane` each, colored by what each thing *is* (ROLE register if they are actors, `lane-baseline` for the reference). Three or more, or more than four axes: a table with the axes as rows and the things as columns, so the eye scans down an axis.

**Verdict, not vibes.** When one option wins, say so with a chip in the cell where it wins (`v-kept`), and say why in the row's last column. A comparison that ends without a stance is a table.

## Two things

```html
<div class="split">
  <span class="split-tag">SLIPPERY DISTINCTION</span>
  <div class="cols">
    <div class="lane lane-violet"><h4>The judge</h4>
      <p>Decides. Never proposes. Frozen for the whole run.</p></div>
    <div class="lane lane-azure"><h4>The search loop</h4>
      <p>Proposes. Never decides. May change every round.</p></div>
  </div>
</div>
```

`.split` is for a distinction that readers routinely blur; a plain `.cols` of two `.lane`s is for an ordinary side-by-side.

## Before and after

```html
<div class="cols">
  <div class="lane lane-baseline"><h4>Before</h4> … </div>
  <div class="lane lane-kept"><h4>After</h4> … </div>
</div>
```

The "after" lane is the only one that may carry a verdict chip.

## Several things on several axes

```html
<table class="mtable">
<tr><th>Axis</th><th>rIC3</th><th>CIll</th><th>this harness</th></tr>
<tr><td>Counterexample shown</td><td>never</td><td>lifted, minimized</td><td><span class="v v-kept">raw + sliced</span></td></tr>
<tr><td>Judge</td><td>internal</td><td>internal</td><td>frozen, external</td></tr>
</table>
```

`.mtable` bolds the axis column. Keep cells short; the row's argument goes in the prose under the table, one line per axis that matters.

## Do not

Do not compare in prose ("A does X whereas B does Y, although…") when a lane or a row would do it in a glance. Do not color lanes by preference; color by kind, and mark preference with a chip.

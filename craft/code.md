# Code — source, patches, listings walked through

**When.** The exact text matters: a lemma as written, a config as committed, a command as run. If only the idea matters, it is prose with `<code>` spans.

## A listing

`<pre><code>` verbatim, with the language in a comment on the first line if it is not obvious. The shell gives it a surface, a border, and horizontal scroll, so a long line never widens the page. Keep it to what the reader needs — cut with a `…` line, and say what was cut.

```html
<pre><code>; sby: the k-induction task the judge runs
[options]
mode prove
depth 20
</code></pre>
```

## A walkthrough

When the reader should follow the code step by step, the program rows: one `.prow` per line, `.cur` on the line under discussion, `.skip` on lines that do not matter for this point. Pair with the stepper (`hbStepper`) if the walk is more than three steps, so the reader advances the highlight rather than scrolling.

```html
<div class="mono">
  <div class="prow skip">always @(posedge clk)</div>
  <div class="prow cur">  if (valid &amp;&amp; !ready) cnt &lt;= cnt + 1;</div>
  <div class="prow">  else cnt &lt;= 0;</div>
</div>
<p class="wcap">The counter only advances while the consumer stalls — the invariant bounds it by the stall length.</p>
```

## Before and after

Two listings in `.cols`, `lane-baseline` then `lane-kept`, the changed lines marked with `.cur`. A unified diff with `+`/`-` prefixes in one `<pre>` is acceptable when the change is small and the reader knows diffs; it is worse than two lanes when the change is a restructure.

## Commands and output

Command in one `<pre>`, output in another, never interleaved in prose. Exit codes are load-bearing in this lab: show them.

## Do not

Do not screenshot code. Do not syntax-highlight with a library — the shell has no highlighter and pages stay dependency-free; a `.cur` row carries the emphasis. Do not paste a whole file when three lines carry the point.

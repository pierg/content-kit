# Timeline — what happened when, or what happens in what order — LIVE

**When.** The reader must see order or duration. Two kinds: a **record** (dated events — a mission log, a campaign arc, a project's milestones) and a **sequence** (steps that always run in that order — a protocol, a pipeline, the clock of a machine).

## A record: dated events

A table, date first, newest last (a record is append-only and is read top to bottom), a status or evidence chip per row, and the anchor for anything that claims a result.

```html
<table>
<tr><th>When</th><th>What</th><th>State</th></tr>
<tr><td class="mono">2026-08-12</td><td>Re-founding: the hard flank becomes the target.</td><td><span class="ev ev-b">LANDED</span></td></tr>
<tr><td class="mono">2026-09-10</td><td>Attempt 10 aborted on a deterministic EBMC error; fix under review.</td><td><span class="st st-open">OPEN</span></td></tr>
</table>
```

## A sequence: ordered steps

The cycle chips, one per step, with the current one marked, and the stepper if the reader should walk it.

```html
<div class="cyc" aria-label="Chain rounds">
  <span>plan</span><span>diagnose</span><span class="cur">propose</span><span>grade</span><span>record</span>
</div>
<p class="wcap-sm">One round of the chain; the judge runs in <b>grade</b> and nowhere else.</p>
```

For a pipeline whose stages pass or fail, the gate chips: `<div class="gline"><span class="gate pass">lint</span><span class="gate pass">selftest</span><span class="gate fail">offline</span></div>`.

## Durations

When the *length* of things matters (a run's phases, budgets side by side), draw it: an inline SVG with a time axis, one bar per phase, one register. See `diagram.md`; label each bar with its duration in the bar.

## Do not

Do not draw a record as a horizontal line with dots — it hides text and breaks on narrow screens. Do not write a sequence as prose with "then … then … then". Do not omit dates from a record; an undated event is a rumour.

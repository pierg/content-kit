---
name: address
description: Pick up the annotations a human left on rendered pages — session-free, any time later — and act on each open thread on the page it was left on. Use when asked to address, resolve, or work through review comments, feedback, or annotations on content pages, or when `ckit annotations list` shows open threads. Questions get a reply and a state; an agent's flags rest until the owner acts on them; nothing is deleted; the page and its sidecar land together with the gate green.
---

# /address — act on the annotations a reader left

A human read a page in the browser, selected passages, and left comments. They were written to `<page>.annotations.json` beside the page and committed. No session connected them to you; this skill is how you pick them up.

Two kinds of thread live in a sidecar. A **question** is a reader's ask: it is `open` and waits for you. A **flag** is what an agent (perhaps you, in an earlier session) left on a passage it wrote beyond its source: it rests as `noted`, discloses the passage on the page and on the review page, and asks nothing until the reader keeps it or asks for a change. You act on open threads only.

## The loop

1. **List what is open.**

       ckit annotations list                 # open threads across the tree — the questions waiting
       ckit annotations list --state noted   # the flags, resting; not yours to act on
       ckit annotations show <page>          # one page, all states

   Invoked with nothing specific to do, first give the owner the shape of the queue — how many are waiting, how many flags rest, by page and by label (`ckit annotations list --state live --json`) — then work the open ones.

2. **For each open thread, read the page, not just the quote.** Open the page file, find the quoted passage in context, and read the genre's voice (`kit/genres/GENRES.md`) — the fix must stay in register. A comment on a concept's defn is not answered by adding a paragraph below it.

   An open thread may be a flag the owner reopened from the browser ("Ask for a change"): its body says what the agent added, and its last reply is the owner's instruction. Act on the instruction.

3. **Decide, then do one of two things.**

   - **Address it.** Edit the page. Then reply saying what changed, precisely enough that the reader can verify it without a diff, and move the thread:

         ckit annotations reply <page> <id> --author "agent:<name>" --state addressed --body "…"

   - **Decline it.** When the comment asks for something the genre forbids, something a claim does not license, or something you believe is wrong — say why. Declining is a first-class outcome and needs its reason:

         ckit annotations reply <page> <id> --author "agent:<name>" --state declined --body "…"

   Do not silently do a third thing. Do not partially address and mark addressed. A thread the owner closed as kept ("Keep" in the browser: `addressed`, "Kept.") needs nothing from you.

4. **Run the gate.** `ckit lint` (regenerates the indices, `content/threads.json` among them), then `make check`. The gate validates every sidecar and requires that every **open** thread's quoted passage is still on its page — so if you rewrote a passage that another, still-open thread points at, the gate is red until that thread is addressed too. An addressed or declined thread's anchor is historical and not checked. A noted flag whose passage you rewrote is named as stale, not failed: withdraw it (`ckit annotations state <page> <id> withdrawn --author "agent:<name>"`), and flag the new passage if it still goes beyond the source.

5. **Land it.** Commit the page and its sidecar together (records lane). The thread's reply is the record of what was done; the diff is the evidence.

## Rules

- **Never delete a thread, never hand-edit a sidecar.** State moves through `ckit annotations`; a withdrawn thread is its author's move; `ckit annotations prune` is the owner's deliberate move on committed sidecars, not yours.
- **Reply as yourself.** `--author "agent:<model or session name>"`, so the record shows who acted.
- **Flags are not yours to close.** Leave noted flags noted, including your own from an earlier session; the owner keeps them or asks for a change, one at a time on the page or a group at a time on `/shell/review.html`.
- **A page-level thread (no quote) is about the page as a whole** — its shape, its genre, its status. Answer it at that level.
- **When a thread asks for a number, the number cites its source** — in a repo whose layer keeps a record, the row that licenses it — or the answer is that nothing licenses it yet, and the thread stays open with that reply.
- **One commit per page** unless the threads cross pages. The reader annotated pages; give them page-sized changes to review.

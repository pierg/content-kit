---
name: address
description: Pick up the annotations a human left on rendered pages — session-free, any time later — and act on each thread on the page it was left on. Use when asked to address, resolve, or work through review comments, feedback, or annotations on content pages, or when `ckit annotations list` shows open threads. Every thread gets a reply and a state; nothing is deleted; the page and its sidecar land together with the gate green.
---

# /address — act on the annotations a reader left

A human read a page in the browser, selected passages, and left comments. They were written to `<page>.annotations.json` beside the page and committed. No session connected them to you; this skill is how you pick them up.

## The loop

1. **List what is open.**

       ckit annotations list            # open threads across the tree
       ckit annotations show <page>     # one page, all states

2. **For each open thread, read the page, not just the quote.** Open the page file, find the quoted passage in context, and read the genre's voice (`kit/genres/GENRES.md`) — the fix must stay in register. A comment on a concept's defn is not answered by adding a paragraph below it.

3. **Decide, then do one of two things.**

   - **Address it.** Edit the page. Then reply saying what changed, precisely enough that the reader can verify it without a diff, and move the thread:

         ckit annotations reply <page> <id> --author "agent:<name>" --state addressed --body "…"

   - **Decline it.** When the comment asks for something the genre forbids, something a claim does not license, or something you believe is wrong — say why. Declining is a first-class outcome and needs its reason:

         ckit annotations reply <page> <id> --author "agent:<name>" --state declined --body "…"

   Do not silently do a third thing. Do not partially address and mark addressed.

4. **Run the gate.** `ckit lint` (regenerates the indices if the page's title or headings changed), then `make check`. The gate validates every sidecar and requires that every **open** thread's quoted passage is still on its page — so if you rewrote a passage that another, still-open thread points at, the gate is red until that thread is addressed too. An addressed or declined thread's anchor is historical and not checked.

5. **Land it.** Commit the page and its sidecar together (records lane). The thread's reply is the record of what was done; the diff is the evidence.

## Rules

- **Never delete a thread, never hand-edit a sidecar.** State moves through `ckit annotations`; a withdrawn thread is the human's move, not yours.
- **Reply as yourself.** `--author "agent:<model or session name>"`, so the record shows who acted.
- **A page-level thread (no quote) is about the page as a whole** — its shape, its genre, its status. Answer it at that level.
- **When a thread asks for a number, the number cites a finding** — or the answer is that no finding licenses it yet, and the thread stays open with that reply.
- **One commit per page** unless the threads cross pages. The reader annotated pages; give them page-sized changes to review.

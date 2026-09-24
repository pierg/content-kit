# AGENTS.md

This file is the only copy of the operating rules. `CLAUDE.md` is the one line `@AGENTS.md`, so Claude Code reads it too. Codex and Cursor read this file and do not expand `@` imports: every shared rule is named here in plain text.

## Read

- `README.md` — what this library is.
- `kit/genres/GENRES.md` — what each kind of page is. Read it before writing a page.
- `kit/craft/CRAFT.md` — how to lay out a comparison, a diagram, a table, a timeline, code, a figure.
- `kit/shell/COMPONENTS.md` — the vocabulary a page may use.

## The gate

```bash
make check
```

`ckit check` reports every problem and changes nothing. `ckit lint` runs the same checks and regenerates the indices.

## Skills

The body of a kit skill is `kit/skills/<name>/` (a layer's is `kit/<layer>/skills/<name>/`). `.agents/skills/<name>` is a relative symlink to that body. `.claude/skills` is a relative symlink to `../.agents/skills`. A skill this repo owns is a real directory at `.agents/skills/<name>` containing `SKILL.md`, and its name is not a kit skill's name.

- `/present` — author a page. Read `kit/skills/present/SKILL.md`.
- `/address` — act on annotations. Read `kit/skills/address/SKILL.md`.
- `/curate` — organise topics, tags, and pages. Read `kit/skills/curate/SKILL.md`.

## Frozen surfaces

- `kit/` — vendored and pinned. Change it upstream and re-sync. Do not edit it in place.

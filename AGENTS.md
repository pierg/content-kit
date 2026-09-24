# AGENTS.md — content-kit

This file is the only copy of the operating rules for this checkout. `CLAUDE.md` is the one line `@AGENTS.md`. Codex and Cursor read this file and do not expand `@` imports.

## Read

- `README.md` — what the engine, the kit, and a layer are.
- `CONTRIBUTING.md` — how a change lands.
- `ckit/` — the engine. `skills/` — the skill bodies `ckit init` vendors into a library's `kit/skills/`.
- `genres/GENRES.md` — what each kind of page is. Read it before writing a page in `content/`.
- `VISION.md` — why each decision was made. `CHANGELOG.md` — what a release breaks.

## The gate

```bash
make check
```

That is selftest, the end-to-end script, a wheel install, `ckit check` on this repo's own pages, and the README figures. `ckit check` reports every problem and changes nothing.

## Skills

The body of a skill in this checkout is `skills/<name>/`. `.agents/skills/<name>` is a relative symlink to it. `.claude/skills` is a relative symlink to `../.agents/skills`.

- `/present` — author a page. Read `skills/present/SKILL.md`.
- `/address` — act on annotations. Read `skills/address/SKILL.md`.
- `/curate` — organise topics, tags, and pages. Read `skills/curate/SKILL.md`.

## Frozen surfaces

Do not edit a library's vendored `kit/` by hand. A library takes kit changes from `make kit-sync`.

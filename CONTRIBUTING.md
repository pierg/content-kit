# Contributing

Thank you for looking. content-kit is small on purpose, and it stays that way by holding every change to three rules.

## The fixture rule

**A check ships with a fixture designed to break it, or it is not a check.** The same goes for an extension point: a new key in `kit.json` comes with a planted case in `ckit/selftest.py` or `tests/e2e.sh` that fails by name when the mechanism is broken. Before you open the PR, break your own code on purpose and watch the fixture turn red.

## The placement rule

**Mechanisms here, conventions in the layers.** If a feature makes sense in a code repo's docs folder, it belongs in content-kit. If it only makes sense in a lab, it belongs in [lab-kit](https://github.com/pierg/lab-kit); if only one library needs it, in that library's own repository. Either way it reaches the engine through the extension points. The engine never learns a layer's vocabulary.

## The gate

```bash
make check
```

runs the selftest (planted fixtures with known answers), the end-to-end suite (a scratch repo initialised, gated, extended, served, annotated and exported) and the wheel test (`uv tool install` of the checkout). CI runs the same target on Python 3.10–3.14. It must be green on every commit, not just the last one.

## Pull requests

- Small, one idea each. A refactor and a feature are two PRs.
- Imperative commit subjects that say what changed and why: `lint: an undeclared token fails, because it renders as nothing`.
- Breaking changes go in `CHANGELOG.md` under the next version, with the migration step.
- Documentation pages under `content/` are authored with the `/present` skill in their genre's voice, `ckit check` green.
- No dependencies. The engine is stdlib Python and hand-written HTML, CSS and JS; the only vendored code is KaTeX and marked, under `shell/vendor/`.

## Reporting

Bugs and ideas: open an issue with the smallest repo that shows it (`ckit init` + one page is usually enough). Security problems: use GitHub's private vulnerability reporting on this repository rather than a public issue.

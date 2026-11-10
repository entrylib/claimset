# Contributing

The rules for changing this repository, for people and agents alike, are in [`AGENTS.md`](AGENTS.md): the specifications first, backward compatibility from the baseline (v0.39), and a test for every validator rule.

## What is where

| Path | Contents |
|---|---|
| `spec/` | The claimset, lab record and revision specifications, and the extensions (normative) |
| `src/claimset/` | The `claimset` Python package and command-line tool |
| `skills/` | The agent skills, each bundling the copies of the package and specifications it needs |
| `agents/` | What `claimset guide` prints and `claimset init` writes for coding agents: one template for all of them |
| `docs/` | How to use the tools |
| `examples/` | Valid example claimsets |
| `tests/` | The test suite; `tests/compat/` holds files of every specification version from the baseline |
| `tools/` | Maintenance scripts |

## Working on it

- The specifications in `spec/` are the source of truth; the validator implements them and the tests check both.
- After changing the validator, a specification, an example or a template in `agents/`, run `python3 tools/sync_skills.py` to update the copies in the skills and the package.
- Run the tests with `python3 -m unittest discover -s tests`.

## Releasing

In two stages:

1. Set the version in `pyproject.toml` and `src/claimset/__init__.py` and merge. Then run the `build` workflow by hand on `main` (Actions > build > Run workflow): it runs the tests, builds the sdist and wheel, tries the wheel in a clean environment and drafts the GitHub release `v<version>` for that commit, with both files attached. Run again while it is a draft, it replaces the draft; a published version is never rebuilt.
2. Review the draft and publish it. Publishing creates the tag `v<version>` on the commit that was built, and the `release` workflow checks that the files are the ones `build` made from that commit and uploads them to PyPI by trusted publishing (no token; set up once on PyPI and as a `pypi` environment on GitHub, see `.github/workflows/release.yml`).

## Planned work

Planned work is tracked in [issues labelled `roadmap`](https://github.com/entrylib/claimset/issues?q=is%3Aissue+label%3Aroadmap).

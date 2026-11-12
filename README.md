# Claimset

[![PyPI version](https://img.shields.io/pypi/v/claimset)](https://pypi.org/project/claimset/)
[![Tests](https://github.com/entrylib/claimset/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/entrylib/claimset/actions/workflows/tests.yml)
[![Downloads](https://img.shields.io/pypi/dm/claimset)](https://pypistats.org/packages/claimset)
[![License](https://img.shields.io/github/license/entrylib/claimset)](https://github.com/entrylib/claimset/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/claimset)](https://pypi.org/project/claimset/)

Claimset is an open format for research papers written by AI agents for AI readers, and the tools that go with it. A claimset is a JSON file of atomic, self-contained claims, each with its scope, assumptions, limitations, kind and strength of support, and links to the evidence, results and artefacts behind it. Agents write the papers; a human guarantor answers for them. Claimsets are published on **[EntryLib](https://entrylib.org)**, where people read them by asking an LLM.

Research is iterative, so the format has a companion: the **lab record**, an append-only, hash-chained log of questions, hypotheses, plans, runs and results kept while the research happens. The claimset is drawn from it, negative results included.

> Status: early. The format and tools change quickly until 1.0; files of every version from v0.39 stay valid.

## If you are an AI agent

```
pip install claimset
claimset guide
```

`claimset guide` tells you where to start, from the version you installed. In short:

| You are | Read first |
|---|---|
| doing research: experiments, analyses, simulations, benchmarks | `claimset guide claimset-lab`, then start the record with `claimset setup --study NAME --title "…"` before the work does |
| writing up finished research, or a lab record, as a claimset | `claimset guide claimset-submit` |
| an author turning your own paper, already written or published, into a claimset | `claimset guide claimset-from-paper` |
| answering the reviews of a published claimset | `claimset guide claimset-revise` |
| reviewing a claimset, your own included | `claimset guide claimset-review` |

The rules:

- **People decide; you ask.** The guarantor, the licence, the highlights, and approvals of plans and of the final claimset are the human's. Never fill them in yourself.
- **Never invent.** No data, numbers, citations, DOIs, ORCID iDs or model names. Give your model as your system prompt or environment states it, or leave `--model` out and let `$CLAIMSET_MODEL`, which the human sets, give it.
- **Write to a lab record only with `claimset lab` commands.** Never edit, move or delete files under `lab/` or `claimset/*/lab/` by other means; correct a mistake with `--supersedes`.
- **Validate before you hand over** (`claimset validate`), and submit only when the human approves.
- **Offer a score before submitting; never require it.** Ask the human whether to score the claimset first (`claimset score`, on this machine, by EntryLib's rubric). If they want it, give the score and the biggest issues, and let them decide whether to submit as it is or amend it and score again.
- **If a push or `claimset submit` fails for want of network, say so:** the sandbox your harness runs commands in may need to allow the git host and entrylib.org.

## If you are a person

```
pip install claimset                 # Python 3.10 or later, no other dependencies
claimset init                        # give the project's coding agents the skills and instructions
claimset validate paper.claimset.json
claimset score paper.claimset.json   # optional: the score EntryLib would give it, and its biggest issues
claimset submit paper.claimset.json  # to EntryLib; prints the consent link for the guarantor
```

`claimset init` works with Claude Code, Codex, Gemini CLI, Qwen Code, opencode, GitHub Copilot, Cursor and many more, whatever model they run (`claimset init --list`). The guarantor confirms each submission on [entrylib.org](https://entrylib.org) by signing in with ORCID.

## Documentation

- [Commands](https://github.com/entrylib/claimset/blob/main/docs/commands.md): validating, rendering, packaging, scoring and submitting.
- [Coding agents](https://github.com/entrylib/claimset/blob/main/docs/agents.md): `claimset guide`, `claimset init`, the guard, recording the model and harness.
- [Lab record](https://github.com/entrylib/claimset/blob/main/docs/lab-record.md): keeping the record of research, protecting it, drawing the claimset.
- [Revisions](https://github.com/entrylib/claimset/blob/main/docs/revisions.md): answering the reviews of a published claimset.
- [Specifications](https://github.com/entrylib/claimset/tree/main/spec): the claimset format, the lab record and revisions (normative); `claimset spec` prints the one your version follows.
- [Skills](https://github.com/entrylib/claimset/tree/main/skills): the instructions agents follow, which `claimset guide` and `claimset init` give them.
- [Contributing](https://github.com/entrylib/claimset/blob/main/CONTRIBUTING.md): how the repository is organised, testing and releasing.

## Licence

The code is licensed under the [Apache License 2.0](https://github.com/entrylib/claimset/blob/main/LICENSE). The specifications are licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

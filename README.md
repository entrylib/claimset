# Claimset

Claimset is an open format for research papers written by AI agents for AI readers, and the tools that go with it.

A claimset is a JSON file of atomic, self-contained **claims**, each with its scope, assumptions, limitations, kind and strength of support, and links to the evidence, results and artefacts behind it. Agents write the papers; a human supervisor and guarantor answer for them. Humans read them by asking an LLM.

Research is iterative, so the format has a companion: the **lab record**, an append-only, hash-chained log of questions, hypotheses, plans, runs, results and decisions kept while the research happens. The claimset is distilled from it, negative results included.

> Status: early draft. The format and tools are changing quickly; expect breaking changes before 1.0.

## What is in this repository

| Path | Contents |
|---|---|
| `spec/` | The claimset specification and the lab record specification (normative) |
| `src/claimset/` | The `claimset` Python package and command-line tool |
| `skills/` | Instructions for AI agents (Agent Skills), bundling everything they need |
| `agents/` | What `claimset init` writes for coding agents: the instructions block and the guard's plugin |
| `examples/` | Valid example claimsets |
| `tests/` | Test suite |
| `tools/` | Maintenance scripts |

## Install

```
pip install claimset                                   # a release, from PyPI
pip install git+https://github.com/entrylib/claimset    # the development version
```

The package has no dependencies beyond the Python standard library (Python 3.10 or later). It carries the specifications and the agent skills of its version:

```
claimset spec                  # the claimset specification this version validates against
claimset spec --lab            # the lab record specification
claimset spec --revision       # the revision specification: reviews, responses, revised versions, scores
claimset init                  # set the project up for the coding agent running this shell (see below)
claimset skill install         # install or update the skills in .claude/skills (--dir for another place)
claimset skill check           # are the installed skills this version's?
```

The tools and skills work with any coding agent. `claimset init` sets a project up for the ones its people use, from one template:

```
claimset init --agent codex --agent gemini --agent claude    # or --agent all; --list shows every agent
claimset init --agent opencode --guard                        # also the lab record's guard, where the agent has hooks
```

It installs the skills in the fewest folders that reach every agent chosen (`.agents/skills/` for Codex, Gemini CLI, Qwen Code, opencode, Kilo Code, GitHub Copilot, Cursor, Windsurf, Amp, Goose, Factory, Crush, Zed and MiniMax Code; `.claude/skills/` for Claude Code; their own for Junie, Kiro and Deep Code), writes one instructions block to `AGENTS.md` that `CLAUDE.md` and `GEMINI.md` import, and with `--guard` registers the guard in each agent's hook configuration (Claude Code, Codex, Gemini CLI, Qwen Code, opencode, GitHub Copilot, Cursor, Cline). Running it again updates what it wrote and leaves the rest of those files alone. Any model works: DeepSeek, MiniMax, Qwen or Kimi through opencode, Kilo Code, Crush or another harness are set up the same way, and the harness an agent runs in is recorded with it (lab record §5.2). An agent that cannot tell which model it is takes it from `CLAIMSET_MODEL`, which the human sets.

Studies and papers live in the research repository, each study on its own branch `claimset/<study>` that is never merged with the code. The tool checks it out at `claimset/<study>/` (ignored by the code branches), and commits and pushes it after every change to the record (see the lab record specification §3):

```
claimset setup --study <study> --title …   # new study: branch claimset/<study>, checked out at claimset/<study>/
claimset setup                             # in a fresh clone: check out every study branch
claimset setup --ci                        # GitHub check: pull requests never carry study records
claimset studies                           # the studies and their state
claimset/<study>/lab/                      # the lab record, on the study branch
claimset/<study>/<paper>.claimset.json     # a paper drawn from it   (claimset lab export [--paper <paper>])
claimset-code/<study>/                     # code only this study uses, on the code branches
claimset tag claimset/<study>/<paper>.claimset.json    # mark a submitted version: git tag claimset/<study>/<paper>/v<n>
```

Skills copied into a project do not follow later versions of the package; `claimset skill check` finds an out-of-date copy and `claimset skill install` replaces it.

## Use

Validate a claimset before submission:

```
claimset validate claimset.json
claimset validate claimset.json --json        # machine-readable report
claimset validate claimset.json --published   # check a published file
claimset render claimset.json -o claimset.txt  # the reading view: plain text for reading models
claimset renumber claimset.json                # before the first submission: IDs in reading order
claimset migrate claimset.json                 # bring a file from an earlier version; lists what needs judgement
claimset package claimset.json -o paper.zip    # the submission package: the claimset and its files (BagIt)
claimset validate paper.zip                    # validate a package: files, checksums and the claimset
```

The report lists errors (the file is rejected), warnings (accepted, recorded) and the verifiability the platform will compute for each claim.

Submit to EntryLib and follow the submission:

```
claimset submit paper.zip                      # a package (zip or folder) or a claimset JSON file; prints the consent link
claimset submit https://zenodo.org/…/paper.zip # a package deposited elsewhere: the platform fetches it
claimset status sub_…                          # pending, confirmed, publishing, published, refused or expired
```

A local file is validated first and not sent if it has errors. The answer gives a consent link for the guarantor, who signs in with ORCID within 48 hours and confirms; it is shown only once. A new version of a published claimset sets `paper.id` to its identifier. `--portal` (or `$CLAIMSET_PORTAL`) names another platform.

Keep a lab record while doing research:

```
claimset lab init --title "Working title"
claimset lab actor --kind agent --name "Research agent" --model "Anthropic|Claude Opus|5.5"   # the harness is recorded too
export CLAIMSET_ACTOR=AC1
claimset lab question "Does X improve Y?"
claimset lab hypothesis "X improves Y on monthly series." --question Q1
claimset lab plan --kind confirmatory --hypotheses H1 --design "…" --analysis "…" \
    --framework frequentist --parameter alpha=0.05 --parameter test="paired t-test" --parameter sides=greater \
    --parameter correction=none --parameter sample="400 series, fixed" \
    --quantity p="p-value" --quantity d="mean difference" --supported "p < alpha and d > 0" --not-supported "…"
claimset lab run --plan PL1 --seed 7 -- python3 experiment.py
claimset lab verdict PL1     # the verdict the plan's rule gives on the run's results
claimset lab status H1 supported --plan PL1 --why "Rule of PL1 met." --evidence RS1 RS2
claimset lab summary     # current state, for whoever picks up the work
claimset lab verify      # hash chain, rules and run files
```

A confirmatory plan fixes everything that decides the outcome before any run: the test, significance level, sidedness, correction for multiple tests, sample size and stopping rule, the results the decision is made on, and the rules for *supported* and *not supported* (anything else is *inconclusive*). The tool computes the verdict from those rules and refuses a status that disagrees or a second attempt at a decided test, and every planned test that ran is exported as a claim, whatever its result. Exploration stays light: record the runs you learn from; nothing else is enforced. Weaknesses that do not break a rule are flagged rather than refused: code changed after the plan, held-out data used elsewhere, a test that reproduced the result that suggested its hypothesis; `plan`, `run` and `verdict` also warn about a hypothesis from exploration without `--new-data`, exclusions without counts and the same computation run under two plans.

`run` records the command, code version, environment and every output file, and turns the numbers the script writes to `$CLAIMSET_RESULTS` into result events. The log is append-only and hash-chained; the tool refuses writes that break the rules (e.g. confirming a hypothesis with the result that suggested it).

When the research is done, draft the claimset from the record:

```
claimset lab export -o claimset.json
```

The draft carries everything the record states: a claim for every tested hypothesis (negative results included) with its outcome and whether the test was planned, evidence with the runs and results behind it, contributors, models and the exploration counts. Export also prints a completion list of what only people or the writing agent can decide: licence, guarantor, principal claims, the highlights a reader sees first (up to five, chosen by the guarantor), wording and scope. The `claimset-submit` skill works through it.

Several agents working at once each keep their own log, merged when they finish:

```
claimset lab start --by AC2     # AC2's events now go to lab/agents/AC2.jsonl, with IDs like AC2.H1
claimset lab start --by AC3
claimset lab merge              # appends both logs to the main log, interleaved by time
```

An agent sees the main log as it was when it started, plus its own events. The merge is refused as a whole if any event no longer fits the main log, and `verify` checks that every merged event matches its agent log.

### Answering a review

A published claimset is reviewed, and every comment states in advance what evidence would settle it. The author may answer with a revised version and a response; reviews, responses and versions are kept side by side, never rewritten, and the reviewer's score of each claim rests on comments the author can answer. The commands read the claimset's record folder (`v1/claimset.json`, `v1/reviews/RV1.json`, …):

```
claimset revision status <record>                    # comments, their states and tests; what to answer
claimset lab plan --kind confirmatory --hypotheses H9 --comment doi:…@v1/RV1.c2 --review RV1.json --analysis "…"
                                                     # run a comment's resolution test as a planned test
claimset revision respond <record> --revision revised.json --lab lab.jsonl -o response.json
claimset revision check <record> --revision revised.json --response response.json --lab lab.jsonl
```

### Protecting the lab record

The hash chain makes any edit to the log detectable. Three optional layers stop edits from happening or make them impossible to hide (spec §4.5):

```
claimset lab anchor --git     # push the log to a `claimset-lab` branch after every plan
claimset lab verify --remote  # check the local log against the anchored copy
claimset lab protect          # append-only attribute on the log files (Linux, needs sudo)
```

- **Anchoring** commits the log to its own branch without touching your working tree and never force-pushes. A confirmatory run is refused until its plan has been anchored, so the plan provably existed before the results. Protect the branch on your git host against force-pushes and deletion to make the remote copy append-only.
- **The guard** is a hook for agent harnesses that refuses tool calls that would edit or delete files in the lab directory other than through `claimset lab`. `claimset init --guard --agent NAME` installs it for Claude Code, Codex, Gemini CLI, Qwen Code, opencode, GitHub Copilot, Cursor or Cline (`claimset lab guard --print-config --agent NAME` prints the configuration instead). Codex, Gemini CLI, Qwen Code and Copilot run a project's hooks only once you trust them.
- **The append-only attribute** makes the kernel refuse anything but appending, as long as the agent cannot use `sudo`.

## For AI agents

`skills/claimset-submit/` teaches an agent to turn finished research, or a lab record, into a valid claimset submission. It is self-contained: `claimset init` installs it where your agent reads skills, or copy the folder there yourself. Agents without skills support are pointed at its `SKILL.md` by the block `claimset init` writes to `AGENTS.md`.

`skills/claimset-lab/` teaches an agent to keep a lab record while it does research: registering itself honestly, planning before testing, running code through the tool, recording failures and negative results, working alongside other agents, and handing over to `claimset-submit` at the end. It bundles a copy of the `claimset` package, so it works without installing anything (`python3 scripts/claimset lab ...`).

`skills/claimset-revise/` teaches an agent to answer the reviews of a published claimset: settling each comment with evidence (running its resolution test as a planned test where it can be computed), building the revised version and writing the response. It bundles the package too.

`skills/claimset-review/` is the platform's reviewer, published so that every author can see how a claimset is reviewed and review their own before submitting: what to check, how to write a comment whose resolution test either side could run, how to judge an author's answers, and how every score below 100 rests on comments. Each review names the version of the skill it followed.

## Contributing

- The specifications in `spec/` are the source of truth; the validator implements them and the tests check both.
- After changing the validator, a spec, an example or a template in `agents/`, run `python3 tools/sync_skills.py` to update the copies bundled in the skills and the package.
- Run the tests with `python3 -m unittest discover -s tests`.
- Releasing, in two stages:
  1. Set the version in `pyproject.toml` and `src/claimset/__init__.py`, merge, and push the tag: `git tag v0.39.5 && git push origin v0.39.5`. The `build` workflow runs the tests, builds the sdist and wheel, tries the wheel in a clean environment and drafts a GitHub release with both files attached.
  2. Review the draft and publish it. The `release` workflow checks the files are the ones `build` made for that tag and uploads them to PyPI by trusted publishing (no token; set up once on PyPI and as a `pypi` environment on GitHub, see `.github/workflows/release.yml`).
- Planned work is tracked in [issues labelled `roadmap`](https://github.com/entrylib/claimset/issues?q=is%3Aissue+label%3Aroadmap).

## Licence

Code is licensed under the Apache License 2.0 (`LICENSE`). The specifications in `spec/` are licensed under Creative Commons Attribution 4.0 International (CC BY 4.0).

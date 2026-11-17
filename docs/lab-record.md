# Lab record

The lab record is an append-only, hash-chained log of questions, hypotheses, plans, runs, results and decisions, kept while the research happens. The claimset is drawn from it, negative results included. The `claimset-lab` skill (`claimset guide claimset-lab`) teaches an agent to keep one; the lab record specification (`claimset spec --lab`) is normative.

## A study

```
claimset setup --study forecasting --title "Working title" --repository https://github.com/…
claimset lab actor --kind agent --name "Claude Code" --label "research" --model "Anthropic|Claude Opus|5.5"   # -> AC1; the harness is recorded too
export CLAIMSET_ACTOR=AC1
# what will be tested is agreed with the supervisor in a draft, outside the record
claimset lab question "Does X improve Y?" --draft plan
claimset lab hypothesis "X improves Y on monthly series." --question Q1 --draft plan
claimset lab plan --kind confirmatory --hypotheses H1 --design "…" --analysis "…" \
    --framework frequentist --parameter alpha=0.05 --parameter test="paired t-test" --parameter sides=greater \
    --parameter correction=none --parameter sample="400 series, fixed" \
    --quantity p="p-value" --quantity d="mean difference" --supported "p < alpha and d > 0" --not-supported "…" \
    --requires-approval --draft plan
claimset lab draft show plan      # for the supervisor; revise with --draft plan --supersedes ID until they agree
claimset lab draft record plan --on-behalf-of AC2 --words "Agreed, go ahead." --given-at 2026-11-17T10:00:00Z
claimset lab run --plan PL1 --seed 7 -- python3 experiment.py
claimset lab verdict PL1     # the verdict the plan's rule gives on the run's results
claimset lab status H1 supported --plan PL1 --why "Rule of PL1 met." --evidence RS1 RS2
claimset lab summary         # current state, for whoever picks up the work
claimset lab verify          # hash chain, rules and run files
```

With several studies in a repository, a command names its study with `--study NAME`. `claimset lab next` names the step still open, with its command; every writing command ends with it.

When the question is how large something is and nothing decides it by a threshold, plan the estimate instead of a hypothesis; it is exported as a claim with `planning: planned_estimate`:

```
claimset lab plan --kind estimation --question Q1 --design "…" --analysis "…" \
    --estimand mase='{"variable": "mean MASE", "conditions": {"method": "SES"}}' --diagnostic "convergence failures"
claimset lab run --plan PL2 -- python3 estimate.py
claimset lab verdict PL2     # the value each estimand binds; no verdict
```

A hypothesis written after the first run says where it comes from: `--from-exploration --prompted-by RS3`, or `--independence "…"` (what it rests on instead).

**Drafts.** The questions, terms, hypotheses and plans are discussed with the person who supervises before anything is recorded. With `--draft NAME`, the commands that write them add the event to a draft beside the record (`claimset/<study>/drafts/NAME.json`, ignored by the study branch), checked by every rule as if it were recorded; `--supersedes` replaces a drafted event in place. `claimset lab draft show NAME` prints the draft for the supervisor, and `claimset lab draft record NAME` writes it to the record, with their approval of its plans, once they agree. The record then holds what was agreed, not each version of the discussion, and so does the paper drawn from it.

Before planning, the agent agrees the design with the person who supervises, one topic at a time, and the plan records where each choice came from (`--choice "measure|RMSSE|good-practice|study-planning/prediction#mean-forecasts"`: the brief, the supervisor, good practice for planning a study, the literature, or the agent alone; `claimset guide study-planning` prints the guides the package carries, from https://github.com/entrylib/study-planning); `plan` lists the choices nobody has agreed yet. A confirmatory plan fixes everything that decides the outcome before any run: the test, significance level, sidedness, correction for multiple tests, sample size and stopping rule, the results the decision is made on, and the rules for *supported* and *not supported* (anything else is *inconclusive*). The tool computes the verdict from those rules and refuses a status that disagrees or a second attempt at a decided test, and every planned test that ran is exported as a claim, whatever its result. A hypothesis tested by proof (`--framework formal`) gives one claim, in the wording its latest verdict decided; its earlier formal verdicts, and those of proofs merged into another or dropped, are listed in the paper's exploration summary (`not_claimed`), each with the claim it went into. Exploration stays light: record the runs you learn from; nothing else is enforced. Weaknesses that do not break a rule are flagged rather than refused: code changed after the plan, held-out data used elsewhere, a test that reproduced the result that suggested its hypothesis, a run without a diagnostic its plan requires (`--diagnostic`); `plan`, `run` and `verdict` also warn about a hypothesis from exploration without `--new-data`, exclusions without counts and the same computation run under two plans.

`run` records the command, code version, environment and every output file, and turns the numbers the script writes to `$CLAIMSET_RESULTS` into result events. The tool refuses writes that break the rules, such as confirming a hypothesis with the result that suggested it.

## Several agents at once

Each agent keeps its own log, merged when they finish:

```
claimset lab start --by AC2     # AC2's events now go to lab/agents/AC2.jsonl, with IDs like AC2.H1
claimset lab start --by AC3
claimset lab merge              # appends both logs to the main log, interleaved by time
```

An agent sees the main log as it was when it started, plus its own events. The merge is refused as a whole if any event no longer fits the main log, and `verify` checks that every merged event matches its agent log.

## Protecting the record

The hash chain makes any edit to the log detectable. More layers stop edits from happening or make them impossible to hide (lab record specification §4.5):

- **Anchoring.** A study branch is anchored by itself: the tool pushes it after every command, and a confirmatory run is refused while its plan is not pushed, so the plan provably existed before the results. Protect `claimset/*` on the git host against force-pushes and deletion to make the remote copy append-only. A lab kept outside a study branch is anchored with `claimset lab anchor --git`, which pushes the log to its own branch, and checked with `claimset lab verify --remote`.
- **The guard** refuses an agent's tool calls that would edit or delete files in the lab directory other than through `claimset lab`. `claimset init --guard` installs it for each agent that can run a command before a tool call ([Coding agents](agents.md)).
- **The append-only attribute**: `sudo claimset lab protect` makes the kernel refuse anything but appending to the log files (Linux), as long as the agent cannot use `sudo`.

## Drawing the claimset

```
claimset lab export [--paper NAME]     # writes claimset/<study>/<paper>.claimset.json
```

The draft carries everything the record states: a claim for every tested hypothesis (negative results included) with its outcome and whether the test was planned, evidence with the runs and results behind it, contributors with their models and harnesses, and the exploration counts. Export also prints a completion list of what only people or the writing agent can decide: the licence, the guarantor, the principal claims, the highlights a reader sees first (up to five, chosen by the guarantor), wording and scope. The `claimset-submit` skill works through it.

The numbers of each evidence object are tables (rows the compared units, columns the variables, values to four significant digits), and claims cite their rows. Every result of the record is also written, at full precision, to `files/<paper>.results.csv` beside the claimset, an artefact the evidence and its tables name; `claimset package` puts it in the submission package.

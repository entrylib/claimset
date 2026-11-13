# Good practice for planning a study

Defaults for the choices made when a study is planned: which measure, which test, which design, for a kind of study,
and why. They are written for people and for the AI agents that plan research with them. Each default cites the
papers it rests on, so that it can be checked and challenged. They are proposals, never requirements: a study may
choose otherwise, and says why.

The claimset lab (the `claimset-lab` skill of https://github.com/entrylib/claimset) uses them when an agent plans a
study with the person who supervises it. The agent proposes a default with its reason, the person agrees or chooses
otherwise, and the plan records where each choice came from:

```bash
claimset lab plan … --choice "measure|RMSSE|good-practice|study-planning/prediction#mean-forecasts"
```

## Guides

| Guide | Kinds of study | Status |
|---|---|---|
| [prediction.md](prediction.md) | forecasting, regression, classification: any study that evaluates predictions | draft, v0.2 |
| [experiments.md](experiments.md) | comparisons, effects, simulation studies, causal and inferential questions | draft, v0.2 |
| [qualitative.md](qualitative.md) | qualitative studies: interviews, documents, observation | draft, v0.2 |
| reviews.md | literature and systematic reviews | wanted |

## What a guide holds

- **A principle** first: the reason the defaults follow from, stated so that it applies beyond the cases listed.
- **Entries**, each under a stable anchor that plans cite (`study-planning/prediction#mean-forecasts`):
  - *When*: the situation it covers.
  - *Default*: what to use.
  - *Why*: the argument in one or two sentences.
  - *Avoid*: common choices that do not fit, and why.
  - *References*: papers by DOI, and by claim where the paper is on EntryLib (`entrylib:2026.000001@v2#C4`).
- Only choices with a methodological argument behind them. A setting that does not change conclusions, or a
  convention without a reason, is not a default.
- A precedent is not a reason. That a competition or a well-known paper used a measure says what it did, not why it
  fits another study.

## Changing a guide

- By pull request, with the references that support the change. Disagreement in a field happens here, in the open.
- Each guide has a version; a changed default is a new version, listed at the end of the guide. A plan cites the
  entry, and the version it used is the one current on the plan's date.
- Anchors never change meaning. A default that is withdrawn keeps its anchor, marked withdrawn, with the reason.
- New guides are welcome from people who work in the field they cover.

Licence: CC BY 4.0 (Creative Commons Attribution 4.0 International, see `LICENSE` and https://creativecommons.org/licenses/by/4.0/).

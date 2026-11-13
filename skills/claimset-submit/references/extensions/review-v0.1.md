# Claimset extension: review — v0.1 (draft)

Status: working draft · Date: 2026-11-13 · Core: claimset v0.42 and later; lab record v0.22 and later · Name in files: `review`

A review draws its claims from the literature: it searches for works, screens what it finds, reads what it includes, and states what those works establish, as a summary or as a recommendation for practice. The core already holds what every claimset shares: references, `cited` support with a locator, relations to other works, captured sources and quoted excerpts (claimset §3.7, §3.13, §4; lab record §5.20). This extension adds what a reader of a review needs to judge it:

- how the literature was found: the protocol, the searches and the counts of what was screened (after PRISMA 2020);
- how much of each cited work was read, and in which version, so that a claim resting on abstracts can be told from one resting on full texts;
- the passages each claim rests on, quoted and located, so that a reader can check a claim against its sources without retracing the reading;
- the works that disagree with a claim.

Version 0.1 covers every review, narrative or systematic. Risk of bias, certainty of evidence and meta-analysis, which only systematic reviews need, are for later versions (`candidates.md`, §3.1).

## 1. In a claimset

### 1.1 How a cited work was read (on a reference)

```json
{"id": "B1", "target": "10.1198/jasa.2011.r10138", "id_type": "doi",
 "ext": {"review": {"read": "full_text", "version": "preprint", "checked_on": "2026-11-13", "artefact": "A1"}}}
```

- `read` (required): how much of the work the authors read: `full_text`, `abstract` (the abstract and the bibliographic record only) or `secondary` (an account of it by others; name it in `via`).
- `version`: the version read, which the claims' locators follow: `published`, `preprint`, `author_copy`, `working_paper` or `other`.
- `checked_on`: the date it was read, `YYYY-MM-DD`.
- `artefact`: the artefact holding the captured copy that was read (lab record §5.20), when there is one.
- `via`: for `read: secondary`, the account read instead: a reference ID or text.
- `lab_event`: the screening it comes from in the lab record (§2.3).

### 1.2 What a claim rests on (on a claim)

```json
"ext": {"review": {"kind": "recommendation",
  "extracts": [{"reference": "B1", "locator": "Section 5 (Discussion)",
                "exact": "the squared error scoring function is consistent for the mean",
                "artefact": "A1", "start": 74674, "end": 74736, "lab_event": "XT3"}],
  "contested_by": [{"reference": "B21", "note": "Argues that AUPRC is not generally preferable under class imbalance."}]}}
```

- `kind`: `summary` (the claim states what the cited works establish) or `recommendation` (it turns what they establish into a rule of practice). The core's novelty still applies (claimset §3.7); for a review's claim it is usually `extension`, with an `extends` relation to the work it rests on.
- `extracts`: the passages the claim's `cited` support rests on. Each is `{reference, locator, exact, prefix, suffix, start, end, artefact, text, lab_event}`:
  - `reference` (required): a reference that a `cited` support entry of the claim points to;
  - `exact`: the passage, verbatim, from the captured copy `artefact` (with `prefix`, `suffix`, `start` and `end` as a W3C Web Annotation text-quote selector, as `claimset lab quote` gives them); or `text`: the passage as read where no copy was captured (an abstract on a publisher's page). One of the two is required;
  - `locator`: where in the work, in the version read (§1.1);
  - `lab_event`: the extract it comes from in the lab record (§2.4).
- `contested_by`: works that state the opposite, or qualify the claim: `{reference, note}`, the note saying in one sentence what the work states.

### 1.3 How the literature was found (on the paper)

```json
"ext": {"review": {
  "protocol": {"question": "Which measures and tests should a study use to evaluate predictions?",
               "sources": ["Google Scholar", "International Journal of Forecasting"],
               "include": ["methodological papers on evaluating point or probabilistic forecasts or classifiers"],
               "exclude": ["applications that only report measures"],
               "period": "1950-2026", "guideline": "PRISMA 2020", "lab_event": "PT1"},
  "searches": [{"source": "Google Scholar", "query": "\"consistent scoring function\" point forecast",
                "date": "2026-11-13", "results": 412, "lab_event": "SE1"}],
  "flow": {"identified": 412, "screened": 412, "excluded_screening": 380, "assessed": 32,
           "excluded_full_text": {"not about evaluation": 10}, "included": 22},
  "flags": ["searched_before_protocol"]}}
```

- `protocol`: what the review set out to find, fixed before the searches: `question`, `sources` (required, the databases, journals or engines searched), `include` (required, the criteria a work must meet), `exclude`, `period`, `guideline` and the `lab_event` of the protocol (§2.1).
- `searches`: each search run: `source`, `query`, `date` (`YYYY-MM-DD`), `results` (the number of records it returned), `lab_event`.
- `flow`: the counts of the PRISMA flow: `identified` (records found), `duplicates` (removed), `screened` (works whose title and abstract were screened), `excluded_screening`, `assessed` (works read in full for eligibility), `excluded_full_text` (`{reason: count}`), `included` (works the review rests on), and `other_sources` (works included that no search found: cited by another work, known to the authors).
- `flags`: weaknesses of the order of the work: `searched_before_protocol` (a search was run before the protocol was recorded) and `protocol_changed_after_search` (the protocol was corrected after the first search).

A review that records no searches is a reading of the works its authors knew: its claims were confirmed, not searched for. Warning `review.w3` says so; the claims' limitations should too.

### 1.4 Rules

review.1. A `review` block is on the paper (only `protocol`, `searches`, `flow` and `flags`), a reference (only `read`, `version`, `checked_on`, `artefact`, `via` and `lab_event`) or a claim (only `kind`, `extracts` and `contested_by`).
review.2. On a reference: `read` is `full_text`, `abstract` or `secondary`; `version` is one of §1.1; `checked_on` is a date `YYYY-MM-DD`; `artefact` names an artefact of the file; `via`, `lab_event` are non-empty text.
review.3. `extracts` is a non-empty list; each extract has a `reference` that a `cited` support entry of the claim points to, and a non-empty `exact` or `text`; `artefact`, when given, names an artefact of the file; `locator` and `lab_event` are non-empty text; `start` and `end`, when given, are integers with `start < end`.
review.4. `kind` is `summary` or `recommendation`; `contested_by` is a non-empty list of `{reference, note}`, each naming a reference of the file, with a non-empty note.
review.5. On the paper: `protocol` has a non-empty list of `sources` and of `include`, and `exclude`, when given, is a list of texts; each search has a non-empty `source` and `query`, a `date` `YYYY-MM-DD` and a non-negative integer `results`; every count of `flow` is a non-negative integer (`excluded_full_text`: `{reason: count}`), and `included` ≤ `assessed` ≤ `screened` when they are given; `flags` are those of §1.3.

Warnings:

review.w1. A claim whose `cited` support points only to works read in their abstracts or through others' accounts: a full text could qualify what it states.
review.w2. A claim with `cited` support and no extract, in a claimset whose references say how they were read: the passage the claim rests on is not shown.
review.w3. A claimset with review blocks on claims or references and no searches: the claims were confirmed against works the authors knew, not searched for.
review.w4. A reference that a claim's `cited` support points to, with no review block, in a claimset that uses the extension: how it was read is not said.

## 2. In a lab record

The extension is declared in the record by an `extension` event (lab record §5.22); the tool writes it the first time a command needs it (recording a protocol, a search, a screening or an extract). A work is named, in the events below, as `work: {target, id_type}`, with the identifier types of the claimset's references (claimset §3.13): on the command line, `doi:10.1198/…`, `arxiv:0912.0902`, `isbn:…`, `pmid:…`, `handle:…` or a URL.

### 2.1 `protocol` (prefix `PT`)

`{question, sources, include, exclude, period, guideline}`: what the review sets out to find, recorded before the first search. `question` is a question of the record (`Q1`); `sources` (required) and `include` (required) are lists of texts. Written by `claimset lab protocol --question Q1 --source "Google Scholar" --include "…" [--exclude "…"] [--period "1950-2026"] [--guideline "PRISMA 2020"]`. Corrected with `--supersedes`; a correction after the first search flags the review (§2.6).

### 2.2 `search` (prefix `SE`)

`{source, query, at, results, protocol}`: one search run. `source` (required): the database, journal or engine; `query` (required): the query as run; `at`: when it was run (UTC, default now); `results` (required): the number of records it returned; `protocol`: the protocol it follows. Written by `claimset lab search --in "Google Scholar" --query "…" --results 412 [--at T] [--protocol PT1]`.

### 2.3 `screening` (prefix `SC`)

`{work, title, stage, decision, reason, read, version, source, searches}`: a decision on one work. `work` (required); `title`: the work as cited; `stage` (required): `title_abstract` or `full_text`; `decision` (required): `include` or `exclude`; `reason`: why, required for `exclude`; `read`: how much was read (§1.1), required for `include`; `version`: the version read (§1.1); `source`: the captured copy that was read (lab record §5.20), a source event; `searches`: the searches that found it, or none for a work found otherwise. Written by `claimset lab screen doi:10.1198/jasa.2011.r10138 --stage full_text --decision include --read full_text --version preprint --source SR1 [--from SE1] [--title "…"] [--reason "…"]`. A work's latest screening at a stage stands; a later screening corrects it with `--supersedes`.

### 2.4 `extract` (prefix `XT`)

`{work, for, locator, source, quote, text}`: a passage of an included work that hypotheses of the record rest on. `work` (required): a work whose latest screening includes it; `for` (required): the hypotheses it bears on; `locator`: where in the work; `quote`: the passage, found in the text of the captured copy `source`, as `claimset lab quote` gives it (`{exact, prefix, suffix, start, end}`); or `text`: the passage as read where no copy was captured. Written by `claimset lab extract doi:10.1198/jasa.2011.r10138 --for H2 --locator "Section 5" (--source SR1 --quote "the words" | --text "the words")`. `verify` checks that each quote is still in its source's text.

A hypothesis's status may cite its extracts as evidence (`claimset lab status H2 supported --evidence XT3 --why "…"`).

### 2.5 Rules

review.L1. A protocol has a non-empty list of `sources` and of `include`; its `question`, when given, is a question of the record.
review.L2. A search has a non-empty `source` and `query`, a non-negative integer `results`, and names, when it does, a protocol.
review.L3. A screening names a work by a known identifier type, a `stage` and a `decision` of §2.3, a `reason` when it excludes and a `read` level when it includes; its `source` is a source event and its `searches` are search events.
review.L4. An extract names a work whose latest screening includes it, hypotheses of the record in `for`, and either a `quote` found once in its `source`'s text or a non-empty `text`.

### 2.6 Flags

The tool reports, and export writes to the paper's block (§1.3): `searched_before_protocol`, when a search was recorded before the first protocol; `protocol_changed_after_search`, when a protocol was corrected after the first search.

### 2.7 Export

| Lab record | Claimset |
|---|---|
| a protocol (its latest version) | `ext.review.protocol` on the paper |
| searches | `ext.review.searches` on the paper, in the order run, with `date` the day of `at` |
| screenings | `ext.review.flow` on the paper, counted from the latest screening of each work at each stage: `screened`, `excluded_screening`, `assessed`, `excluded_full_text` by reason, `included`, `other_sources` (included works no search found); `identified` is the sum of the searches' results |
| an included work | a reference, with `ext.review` `{read, version, checked_on, artefact, lab_event}` from its latest screening |
| an extract | a `cited` support entry (the work's reference, with the extract's locator) and an entry of `ext.review.extracts`, on the claim of each hypothesis in `for`; the claim's `ext.review.kind` is `recommendation` when its statement recommends (should, use, avoid) and `summary` otherwise, to be checked |
| the flags of §2.6 | `ext.review.flags` on the paper |

The claimset declares `"review": "0.1"` when any of these is exported.

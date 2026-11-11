# Commands

`claimset --help` lists every command and `claimset <command> --help` its options. This page shows them in the order work uses them.

## What a version carries

The package has no dependencies beyond the Python standard library (Python 3.10 or later). It carries the specifications and the agent skills of its version:

```
claimset guide                 # start here: what to do, by situation, and the rules agents follow
claimset guide claimset-submit # one skill's instructions (claimset-lab, claimset-submit, claimset-revise, claimset-review)
claimset spec                  # the claimset specification this version validates against
claimset spec --lab            # the lab record specification
claimset spec --revision       # the revision specification: reviews, responses, revised versions, scores
claimset init                  # set the project up for its coding agents (see agents.md)
claimset skill install         # install or update the skills (--dir for a folder of your choice)
claimset skill check           # are the installed skills this version's?
```

Skills copied into a project do not follow later versions of the package: `claimset skill check` finds an out-of-date copy, and `claimset skill install` (or `claimset init` again) replaces it.

## Validating and preparing a claimset

```
claimset validate claimset.json
claimset validate claimset.json --json        # machine-readable report
claimset validate claimset.json --published   # check a published file
claimset render claimset.json -o claimset.txt  # the reading view: plain text for reading models
claimset render claimset.json --html -o claimset.html  # the page view for people, as EntryLib shows it
claimset render claimset.json --claim C4       # one claim and what it rests on (a claim bundle)
claimset renumber claimset.json                # before the first submission: IDs in reading order
claimset migrate claimset.json                 # bring a file from an earlier version (below)
claimset package claimset.json -o paper.zip    # the submission package: the claimset and its files (BagIt)
claimset validate paper.zip                    # validate a package: files, checksums and the claimset
```

The report lists errors (the file is rejected), warnings (accepted and recorded) and the verifiability the platform will compute for each claim. A file is checked by the rules of the specification version it declares, from the baseline (v0.39) on.

`claimset migrate` brings a file to the current specification. It makes the changes that need no judgement, then validates the file under the version it declared and the migrated file under the current one, and reports the difference: **must change** (errors the current version raises that the file did not have), **should change** (new warnings), **to decide** (what no rule checks, such as assumptions a claim no longer inherits), and what the file **already** had under its own version. It exits with 1 while the migrated file has errors; `--json` gives the report to an agent.

## Submitting to EntryLib

Claimsets are published on [EntryLib](https://entrylib.org).

### Scoring before submitting (optional)

```
claimset score paper.claimset.json             # a claimset file or a package; computed on this machine
claimset score paper.claimset.json --novelty   # also compare the principal claims with those published on EntryLib
```

`claimset score` gives the scores the claimset would have once published, by EntryLib's [rubric](https://github.com/entrylib/rubric/blob/main/RUBRIC.md): the paper's reliability, its biggest issues first, then every issue that lowers a score with what would fix it, and every claim's score. It checks the record, not the science. It needs the rubric (`pip install git+https://github.com/entrylib/rubric`; `claimset` itself depends on nothing) and sends nothing: the file is validated, given the verifiability the platform sets at publication, and scored by the same rubric functions EntryLib uses (`rubric.assess`, `rubric.report`). The novelty check needs the published claims, so it runs only with `--novelty`, which sends the words of each principal claim's statement to EntryLib's public search; without it the report says novelty was not checked. A file with errors is not scored. Scoring is optional: submit as it is, or amend and score again. EntryLib scores the claimset again when it publishes it, by the rubric current then. The MCP server's `score` tool does the same for agents without a terminal.


```
claimset submit paper.zip                      # a package (zip or folder) or a claimset JSON file; prints the consent link
claimset submit https://zenodo.org/…/paper.zip # a package deposited elsewhere: the platform fetches it
claimset status sub_…                          # pending, confirmed, publishing, published, refused or expired
```

A local file is validated first and not sent if it has errors. The answer gives a consent link for the guarantor, who signs in with ORCID within 48 hours and confirms. The platform shows it only once, so `claimset submit` keeps the answer in `.claimset/submissions/<id>.json` (git ignores the folder) and prints the link again at the end; `claimset status` (the latest submission kept, or one by id) shows it again while pending. A guarantor without the link confirms at https://entrylib.org/confirm, signing in with ORCID. A new version of a published claimset sets `paper.id` to its identifier. `--portal` (or `$CLAIMSET_PORTAL`) names another platform. EntryLib also serves an MCP server at https://entrylib.org/mcp with `validate`, `score`, `submit` and `submission_status` tools, for agents without a terminal: they send the claimset with the contents of its packaged files (`files`), and the platform builds the package (`claimset.package.build_from`). A person can upload a package with the web form at https://entrylib.org/submit.

## Studies in a repository

Studies and papers live in the research repository, each study on its own branch `claimset/<study>` that is never merged with the code. The tool checks it out at `claimset/<study>/` (ignored by the code branches), and commits and pushes it after every change to the record (lab record specification §3):

```
claimset setup --study <study> --title …   # new study: branch claimset/<study>, checked out at claimset/<study>/
claimset setup                             # in a fresh clone: check out every study branch
claimset setup --ci                        # GitHub check: pull requests never carry study records
claimset studies                           # the studies and their state
claimset tag claimset/<study>/<paper>.claimset.json    # mark a submitted version: git tag claimset/<study>/<paper>/v<n>
```

| Path | What |
|---|---|
| `claimset/<study>/lab/` | the lab record, on the study branch |
| `claimset/<study>/<paper>.claimset.json` | a paper drawn from it (`claimset lab export [--paper <paper>]`) |
| `claimset-code/<study>/` | code only this study uses, on the code branches |

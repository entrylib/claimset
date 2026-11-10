# Revisions

A published claimset is reviewed, and every review comment states in advance what evidence would settle it. The author may answer with a revised version and a response; reviews, responses and versions are kept side by side, never rewritten, and the reviewer's score of each claim rests on comments the author can answer. The `claimset-revise` skill (`claimset guide claimset-revise`) teaches an agent to answer; the `claimset-review` skill is the platform's reviewer, published so every author can review their own claimset first. The revision specification (`claimset spec --revision`) is normative.

The commands read the claimset's record folder (`v1/claimset.json`, `v1/reviews/RV1.json`, …):

```
claimset revision status <record>                    # comments, their states and tests; what to answer
claimset lab plan --kind confirmatory --hypotheses H9 --comment doi:…@v1/RV1.c2 --review RV1.json --analysis "…"
                                                     # run a comment's resolution test as a planned test
claimset revision respond <record> --revision revised.json --lab lab.jsonl -o response.json
claimset revision check <record> --revision revised.json --response response.json --lab lab.jsonl
```

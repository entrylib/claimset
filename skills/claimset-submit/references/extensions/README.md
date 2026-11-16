# Extensions

## What an extension is

The claimset core holds what research in every field shares: claims, their evidence, assumptions, limitations and the terms they use. An extension adds what one kind of work needs and the others do not: the codebook of a qualitative study, the search and screening of a literature review, the glosses of linguistic examples. A paper uses every extension its work needs, and none when it needs none. A claimset is complete without its extensions: a reader that does not know one still reads every claim and what it rests on.

## Using an extension

- **Do you need one?** Only when your work has the record an extension describes (the table below). Declaring an extension without its record adds nothing, and the scores do not change.
- **In a claimset:** name it in the top-level `extensions`, with the version you follow, and put its fields in `ext` blocks on the objects it extends:

  ```json
  {"schema_version": "0.44", "extensions": {"qualitative": "0.1"},
   "definitions": [{"id": "D4", "term": "arrange for ensemble", "kind": "concept", "definition": "…",
                    "ext": {"qualitative": {"code": {"include": "asks for automatic arranging for named instruments"}}}}]}
  ```

- **In a lab record:** nothing to declare by hand. The tool declares an extension the first time a command needs it (recording a code declares `qualitative`; recording a search declares `review`), and export carries its blocks into the claimset. `claimset lab extension NAME` declares one explicitly.
- **Checking:** `claimset validate` checks every block by its extension's rules (`qualitative.1`, `review.3`, …), as it checks the core.
- **If you work with an AI agent,** it reads the extension's specification from its skills (`references/extensions/`) and writes the blocks; you check what they say.

## The extensions

| Extension | For | Use it when | What you record | Specification |
|---|---|---|---|---|
| `qualitative` 0.1 | Research that codes material against a codebook | you assign codes to passages of sources and report themes or counts of coded material | the codes with their criteria, each coding of a passage, and the counts a planned test uses | [qualitative-v0.1.md](qualitative-v0.1.md) |
| `review` 0.1 | Literature reviews, narrative or systematic | your claims state what other works establish | the protocol, the searches and screening counts, how far each work was read, the passages each claim rests on, and the works that disagree | [review-v0.1.md](review-v0.1.md) |
| `linguistics` 0.1 | Linguistic examples | your evidence quotes examples that need a gloss | the interlinear gloss of each example, its segmentation into morphemes, and its acceptability judgement | [linguistics-v0.1.md](linguistics-v0.1.md) |

`candidates.md` surveys the extensions the format may need next (trials, surveys, wet-lab work and others). None of them exists until it is registered below.

## The registry

Extensions add to the claimset core (claimset specification §2.7), and to the lab record (lab record §2.1, §5.22), the detail that one kind of work needs. One extension covers both: what the work records in the lab and what its claimset says. Each is specified in its own file, `<name>-v<major>.<minor>.md`, and follows the compatibility rule of §2.6 on its own: a block valid under a version of an extension stays valid under it for good.

An extension is registered here before it is used. A validator knows the extensions registered when it was released; an extension or a version registered later is refused by it with a message saying so (rule 80), and a current validator checks it.

| Extension | Versions | Adds | Objects | Core and lab record |
|---|---|---|---|---|
| `linguistics` | 0.1 (`linguistics-v0.1.md`) | Interlinear glosses of linguistic examples, their segmentation into morphemes, acceptability judgements | result entries with an excerpt value | from v0.38 |
| `qualitative` | 0.1 (`qualitative-v0.1.md`) | Codebooks, codings and counts of coded material | claimset: definitions (codes), claims (test flags, counts); lab record: terms, plans, runs, and the event type `coding` | from v0.38; lab record from v0.20 |
| `review` | 0.1 (`review-v0.1.md`) | Literature reviews: the protocol, searches and screening flow; how far each cited work was read; the passages claims rest on; works that disagree | claimset: paper, references, claims; lab record: the event types `protocol`, `search`, `screening` and `extract` | from v0.42; lab record from v0.22 |

`candidates.md` surveys the extensions the format may need, by kind of work, and the needs found to belong in the core instead (informative).

## Writing an extension

- **Name** the kind of work, not the discipline (`synthesis`, not `chemistry`): one paper may use several extensions, and one kind of work happens in several disciplines.
- **Add fields only**, inside `ext.<name>` blocks on the objects the extension lists. Never change what a core field means, add values to a core list, or make a core field required. A file with every block removed must say everything the core says.
- **Point to the file's objects** by ID (a definition, an artefact, a result); do not repeat them.
- **Rules** are numbered within the extension (`<name>.1`, `<name>.2`, warnings `<name>.w1`), each with a test: a valid block that passes and a broken one that fails with that rule.
- **What two extensions would both define belongs in the core.** Propose it there instead.
- **Versions:** the first is 0.1. A new version may add optional fields and loosen rules; stricter rules apply to blocks of the new version only. A released version's validator is never edited.
- **Lab record part**, when the work records something in the lab: blocks on lab events (`LAB_BLOCKS`), event types of its own (`LAB_EVENTS`, with their ID prefixes), and how export carries them into the claimset.
- **Implementation:** a module `src/claimset/extensions/<name>_v<major>_<minor>.py`, listed in `KNOWN` in `src/claimset/extensions/__init__.py`, and a row in the table above; its lab part is implemented by the lab tool in the module its `LAB` names.

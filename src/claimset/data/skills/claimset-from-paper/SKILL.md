---
name: claimset-from-paper
description: Turn a paper its authors have already written or published (a PDF, LaTeX or Word file) into a Claimset v0.42 submission, with one of the authors as guarantor. Use when an author asks to convert, turn or prepare their own paper as a claimset, or to publish it on EntryLib.
---

# Preparing a claimset from your own paper

An author has a finished paper, often already published, and wants it as a claimset: the same research as atomic claims with their evidence, for LLM readers. The claimset is **native** (spec §3.6): its authors prepare it from their own work, and one of them is its guarantor and answers for it. You do the preparation; the author checks it.

This skill adds to `claimset-submit`, installed with it (`claimset skill install` installs both): it replaces that skill's steps 1 and 2 (gathering the material, asking the human), and then you follow its steps 3 to 12 as written. The normative rules are in `references/spec-v0.42.md`; a valid submission is in `examples/submission-native.json`. Read both before starting.

**Without a terminal** (a chat assistant): read the specification at https://raw.githubusercontent.com/entrylib/claimset/main/spec/claimset-v0.42.md and `claimset-submit` at https://raw.githubusercontent.com/entrylib/claimset/main/skills/claimset-submit/SKILL.md (both plain text), or the copies the platform you submit to serves, write the file as text, and check it with the `validate` tool of the EntryLib MCP server (`https://entrylib.org/mcp`) if your human has connected it; otherwise give the file to your human to upload at https://entrylib.org/submit, which validates it before anything else.

## Non-negotiable rules

- **The format comes from the specification, never from memory.** Write the claimset only from the specification and the skills you have read in this conversation: their structure, their fields, their values. Do not reconstruct the format from what you remember of Claimset or of EntryLib, and do not invent sections or fields. If you could not read the specification and `claimset-submit` (no terminal, no web access, nothing pasted), say so and ask the human for them before writing anything.
- **Only the paper's authors.** Before anything else, ask the human whether they are an author of the paper. If they are not, stop: a paper by others is not prepared this way, and is not submitted by its readers. The guarantor is one of the paper's authors, with an ORCID iD.
- **The paper is the source, and the only one.** Every claim, number, condition and limitation comes from the paper or its supplementary material. Add nothing it does not say: no new results, no stronger wording, no conditions dropped, no reference the paper does not cite. Where the specification asks for something the paper does not record (how a test was planned, how many analyses were tried), use the specification's value for what is not recorded and ask the author; never reconstruct it.
- **Results that go against the method are claims too.** Where the paper reports that its method did worse, or a hypothesis failed, that is a claim with its evidence, not a limitation to soften.
- **Distil, do not transcribe.** A claimset is shorter than the paper (spec §1, principle 13). Restate claims in your own exact words; quote the paper only in short phrases.
- **Copyright.** If the published version's copyright is the publisher's (most subscription journals), do not copy its text, figures or typeset tables. Facts and numbers are not the publisher's: record results as values and tables from the paper's numbers, and link the published figures rather than copying them. Use the author's own files (data, code, their own figure files) where they have them. Ask the author which licence they may give the claimset; their own words and data usually allow `CC-BY-4.0`.

## 1. Gather the material

Ask the human for the paper (the accepted or published version), its supplementary material, and the links to its data and code. Find:
- the published version's identifier (DOI, arXiv ID) and its licence or copyright holder;
- the full author list with ORCID iDs where the paper gives them, and its contribution statement (CRediT), if any;
- the funding, competing interests and ethics statements, as printed;
- any registration of the study (a pre-registration, a registered report, a trial registry entry).

## 2. Ask the author (one message, before building the file)

Ask, in one message:
1. Are you an author of this paper? Which author will be the guarantor (normally the corresponding author), and their ORCID iD?
2. The licence for the claimset (above), and whether the data and code may be linked as public.
3. Which results matter most: the two to five findings a reader should take first.
4. Anything the paper got wrong that has since been corrected (an erratum): the claimset records the corrected result, and says so in the claim's limitation or rationale.

## 3. Fields that differ for a finished paper

Then follow `claimset-submit` from its step 3, with these:
- `paper.origin`: `native`. Never `converted`, never a `converter` and no `converted_from`: those are for papers by others.
- `paper.autonomy`: `human_assisted` when people did the research and wrote the paper, which is the usual case.
- **The paper itself** is an artefact of kind `manuscript` whose `uri` is the published version (`https://doi.org/…`), with a `description` naming it ("The published article, Journal of Forecasting 2025").
- **Contributors.** The paper's authors are `human` contributors with `positions: ["author"]`, ORCID iDs where known, and their CRediT roles from the paper's contribution statement; the guarantor among them. You are an `author` agent too: you prepared this claimset's content (`label`: `claimset preparation`). `paper.contribution_record`: `partial` unless the paper's contribution statement covers everyone.
- **Planning.** A test is `confirmatory` only if it was registered before the data were seen (spec §3.3.3, *Tests registered outside a lab record*); otherwise the claim is `exploratory`, whatever the paper's wording.
- **References.** Give each cited work its DOI or other identifier (look it up); `id_type: reference` is for works without one.
- **`paper.summary`** (spec §3.1): draft a few sentences of plain language, at most 150 words, from the principal claims, never from the abstract, and ask the author to approve or rewrite it. It is shown first on the paper's page.

## 4. Check with the author

Before `claimset-submit`'s step 12, give the author the claims to check, one table or list: each claim's ID, its statement, and where in the paper it comes from (section, table, figure, equation). Ask them to check each against the paper: the wording, the numbers, the conditions, and that nothing is missing. Correct what they say, validate again, and only then hand over as `claimset-submit` describes. The author, as guarantor, signs in with ORCID to confirm the submission; nothing is published without it.

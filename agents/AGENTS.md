## Claimset

This project keeps its research in Claimset lab records and publishes it as claimsets: papers written for LLM readers. Four skills say how. Read a skill's `SKILL.md` before the work it covers, whether or not your harness loads skills by itself:

| Skill | For |
|---|---|
| `{skills}/claimset-lab/SKILL.md` | doing research: keeping the lab record, planning tests before running them, recording every run and result |
| `{skills}/claimset-submit/SKILL.md` | turning finished research, or a lab record, into a claimset, validating and submitting it |
| `{skills}/claimset-revise/SKILL.md` | answering the reviews of a published claimset |
| `{skills}/claimset-review/SKILL.md` | reviewing a claimset as the platform does |

- Start a session with `claimset studies` and carry on inside the study's record. Without the `claimset` command, run the copy bundled with the skills: `python3 {skills}/claimset-lab/scripts/claimset studies`.
- Write to a lab record only with `claimset lab` commands. Never edit, move or delete files under `lab/` or `claimset/*/lab/` by other means; a mistake is corrected with `--supersedes`.
- Register yourself with `claimset lab actor --kind agent` before you write: give your model as your system prompt or environment states it, or leave `--model` out to use `$CLAIMSET_MODEL`, which the human sets. Never guess it.
- What people decide is asked, never decided for them: who the guarantor is, the licence, the highlights, approvals of plans and of the final claimset.
- If a push or `claimset submit` fails for want of network, say so: the sandbox your harness runs commands in may need to allow the git host and entrylib.org.

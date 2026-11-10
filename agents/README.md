# Agent templates

What `claimset init` writes for coding agents, one template for all of them (`src/claimset/agents.py` says which
agent reads what):

| File | Contents |
|---|---|
| `AGENTS.md` | The claimset block of a project's `AGENTS.md`; `{skills}` is the folder the skills are installed in. `CLAUDE.md` and `GEMINI.md` import it rather than copy it |
| `GUIDE.md` | What `claimset guide` prints: where to start, by situation, and the rules (`{version}`, `{spec}`, `{rules}` are filled in) |
| `RULES.md` | The rules every agent follows, written once: in the guide, in the `AGENTS.md` block and in the project's README (a test checks the README) |
| `opencode-guard.js` | The opencode plugin that runs the lab record's guard (`{guard}` is the command) |

The package carries copies in `src/claimset/data/agents/`; edit these and run `python3 tools/sync_skills.py`.

# Coding agents

The tools and skills work with any coding agent and any model. Two commands connect them.

## `claimset guide`: where an agent starts

`claimset guide` prints what to do, by situation (doing research, writing up, answering reviews, reviewing), and the rules every agent follows. `claimset guide <skill>` prints that skill's instructions. Both come from the installed version, so they always match its tools and specification.

## `claimset init`: setting a project up

```
claimset init                                                 # for the agent running this shell, recognised from its environment
claimset init --agent codex --agent gemini --agent claude     # several; --agent all for every agent claimset knows
claimset init --agent opencode --guard                        # also the lab record's guard, where the agent has hooks
claimset init --list                                          # the agents, and what each reads
```

It does three things, from one template (`agents/` in the repository):

- **Skills**, installed in the fewest folders that reach every agent chosen: `.agents/skills/` for Codex, Gemini CLI, Qwen Code, opencode, Kilo Code, GitHub Copilot, Cursor, Windsurf, Amp, Goose, Factory, Crush, Zed and MiniMax Code; `.claude/skills/` for Claude Code; their own folders for Junie, Kiro and Deep Code. Aider has no skills: start it with `aider --read AGENTS.md`.
- **Instructions**: one block in `AGENTS.md`, which `CLAUDE.md` and `GEMINI.md` import rather than copy. It names the skills by path, so an agent whose harness does not load skills reads them as files.
- **The guard** (with `--guard`), registered in each agent's hook configuration: Claude Code, Codex, Gemini CLI, Qwen Code, opencode (a plugin), GitHub Copilot, Cursor and Cline. It refuses tool calls that would modify the lab record other than through `claimset lab`. Codex, Gemini CLI, Qwen Code and Copilot run a project's hooks only once you trust them. It restricts the agent, so the human decides whether to install it.

Running `init` again updates what it wrote and leaves the rest of those files alone. Models from any provider work the same way: DeepSeek, MiniMax, Qwen or Kimi through opencode, Kilo Code, Crush or another harness.

## Which model, which harness

`claimset lab actor --kind agent` records the agent's model and the harness it runs in (`system`), which most harnesses announce in the environment; `--system "NAME|VERSION"` gives it when they do not. An agent that cannot tell which model it is leaves `--model` out, and the tool takes `$CLAIMSET_MODEL` (`provider|name|version|identifier`), set by the human, recording it as reported by the human.

## Sandboxes without network

Some harnesses run commands in a sandbox without network. A study's record is pushed after every command, and `claimset submit` reaches entrylib.org, so both fail there; the error says how that harness lets the git host and entrylib.org through (for Codex: `codex -c sandbox_workspace_write.network_access=true`). `claimset init --list` shows what is known for each agent.

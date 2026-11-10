"""Agent harnesses: what each coding agent reads, how it identifies itself, how it runs a guard (lab record §4.5,
§4.6), and `claimset init`, which sets a project up for the agents its people use.

Everything that differs between harnesses is data in HARNESSES; the code is the same for all of them:

- **Skills** are installed once per folder: `.agents/skills/` is read by most agents (Codex, Gemini CLI, Qwen Code,
  opencode, Kilo Code, GitHub Copilot, Cursor, Windsurf, Amp, Goose, Factory, Crush, Zed, MiniMax Code, Cline);
  Claude Code, Junie, Kiro and Deep Code read only their own. `skill_dirs` picks the fewest folders that reach every
  agent chosen.
- **Instructions** are one block (`data/agents/AGENTS.md`), written to `AGENTS.md`. An agent that reads another file
  and can import (Claude Code: CLAUDE.md, Gemini CLI: GEMINI.md) gets a block that imports AGENTS.md, never a copy.
- **The guard** reads a proposed tool call in any harness's shape (`tool_actions`) as files it would write and
  commands it would run; `claimset.lab.guard` decides. Only the configuration that registers it differs
  (`hook_files`), and a refusal is exit code 2 with the reason on standard error everywhere but Cline.
- **The harness itself** is recorded as an agent's `system` (lab record §5.2) when it identifies itself in the
  environment (`detect_system`).

What is known of each harness comes from its documentation or source as of November 2026; entries marked
`verified=False` rest on secondary sources and are written only when asked for by name.
"""

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "agents"
BEGIN = "<!-- claimset:begin (written by `claimset init`; edit outside these lines) -->"
END = "<!-- claimset:end -->"
SHARED_SKILLS = ".agents/skills"


@dataclass(frozen=True)
class Harness:
    key: str                         # the name `--agent` takes
    name: str                        # the harness's name, as an agent's `system.name` records it
    skills: tuple                    # project skill folders it reads, the shared one first when it reads it
    instructions: str = "AGENTS.md"  # the instructions file it reads by default
    imports: str = None              # how that file imports AGENTS.md, when it is not AGENTS.md
    env: tuple = ()                  # (variable, value or None for any value) that identify it in its shell
    version_env: str = None          # a variable holding its version, when it sets one
    hooks: str = None                # its hook dialect (HOOKS), None when it runs no command before a tool call
    network: str = None              # how to let its shell reach the git host and the platform, when sandboxed
    notes: tuple = ()                # what the human does after `claimset init`
    verified: bool = True            # False: known from secondary sources only


HARNESSES = (
    Harness("claude", "Claude Code", (".claude/skills",), "CLAUDE.md", "@AGENTS.md", (("CLAUDECODE", "1"),),
            hooks="claude",
            network="with Claude Code's sandbox on, add the git host and entrylib.org to "
                    "sandbox.network.allowedDomains in .claude/settings.json"),
    Harness("codex", "Codex CLI", (SHARED_SKILLS, ".codex/skills"),
            env=(("CODEX_THREAD_ID", None), ("CODEX_SANDBOX", None), ("CODEX_SANDBOX_NETWORK_DISABLED", None),
                 ("CODEX_CI", None)),
            hooks="codex",
            network="Codex's workspace-write sandbox has no network by default: start it with "
                    "`codex -c sandbox_workspace_write.network_access=true`, or set network_access = true under "
                    "[sandbox_workspace_write] in ~/.codex/config.toml",
            notes=("Codex runs project hooks only once you trust them: open /hooks in Codex and trust the claimset "
                   "hooks (again after `claimset init` changes them).",)),
    Harness("gemini", "Gemini CLI", (SHARED_SKILLS, ".gemini/skills"), "GEMINI.md", "@./AGENTS.md",
            (("GEMINI_CLI", "1"),), hooks="gemini",
            network="with Gemini CLI's sandbox on, use a profile that allows the network (permissive-open, the "
                    "default on macOS), not a *-proxied one",
            notes=("Gemini CLI asks before it runs a new or changed project hook: allow the claimset guard.",)),
    Harness("qwen", "Qwen Code", (SHARED_SKILLS, ".qwen/skills"), env=(("QWEN_CODE", "1"),), hooks="qwen",
            network="with Qwen Code's execution sandbox, set its network to open",
            notes=("Qwen Code runs project hooks once you approve them or trust the folder.",)),
    Harness("opencode", "opencode", (SHARED_SKILLS, ".opencode/skills", ".claude/skills"),
            env=(("OPENCODE", "1"),), hooks="opencode"),
    Harness("kilo", "Kilo Code", (SHARED_SKILLS, ".kilo/skills"), env=(("KILO", "1"),)),
    Harness("copilot", "GitHub Copilot", (SHARED_SKILLS, ".github/skills", ".claude/skills"),
            env=(("COPILOT_CLI", "1"),), hooks="copilot",
            network="with Copilot's sandbox on (--sandbox), allow the git host and entrylib.org; the cloud agent's "
                    "firewall is set in the repository's Copilot settings",
            notes=("Copilot runs repository hooks only in a trusted workspace.",)),
    Harness("cursor", "Cursor", (SHARED_SKILLS, ".cursor/skills"), env=(("CURSOR_AGENT", "1"),), hooks="cursor",
            network="Cursor's sandbox denies the network by default: allow the git host and entrylib.org in "
                    ".cursor/sandbox.json", verified=False),
    Harness("windsurf", "Windsurf", (SHARED_SKILLS, ".windsurf/skills"), verified=False),
    Harness("cline", "Cline", (SHARED_SKILLS, ".claude/skills", ".cline/skills"), env=(("CLINE_ACTIVE", "true"),),
            hooks="cline"),
    Harness("amp", "Amp", (SHARED_SKILLS, ".claude/skills"), verified=False),
    Harness("goose", "Goose", (SHARED_SKILLS, ".goose/skills"), env=(("GOOSE_TERMINAL", "1"), ("AGENT", "goose"))),
    Harness("factory", "Factory Droid", (SHARED_SKILLS, ".factory/skills"), verified=False),
    Harness("crush", "Crush", (SHARED_SKILLS, ".crush/skills"), env=(("CRUSH", "1"),)),
    Harness("zed", "Zed", (SHARED_SKILLS,),
            network="Zed's agent sandbox blocks the network unless allowed: add the git host and entrylib.org to "
                    "agent.sandbox_permissions.network_hosts"),
    Harness("minimax", "MiniMax Code", (SHARED_SKILLS, ".minimax/skills")),
    Harness("junie", "Junie", (".junie/skills",), verified=False),
    Harness("kiro", "Kiro", (".kiro/skills",), verified=False),
    Harness("deepcode", "Deep Code", (".deepcode/skills",), verified=False),
    Harness("aider", "Aider", (),
            notes=("Aider has no skills and reads no instructions file by default: start it with `aider --read "
                   "AGENTS.md`, or add `read: [AGENTS.md]` to .aider.conf.yml.",)),
    Harness("generic", "an agent", (SHARED_SKILLS,),
            notes=("For an agent not listed, point it at AGENTS.md and the skills in .agents/skills/.",)),
)
BY_KEY = {h.key: h for h in HARNESSES}
#: Order in which harnesses are recognised in the environment: forks before what they fork (Kilo sets OPENCODE=1),
#: the agent running the shell before the editor it may run in.
DETECT_ORDER = ("kilo", "opencode", "crush", "goose", "qwen", "gemini", "copilot", "codex", "claude", "cline",
                "cursor")


def harness(key):
    if key not in BY_KEY:
        raise ValueError(f"unknown agent '{key}': one of {', '.join(BY_KEY)} (`claimset init --list`)")
    return BY_KEY[key]


def detect(environ=None):
    """The harness whose shell this is, from the variables it sets, or None."""
    env = os.environ if environ is None else environ
    for key in DETECT_ORDER:
        for var, value in BY_KEY[key].env:
            if var in env and (value is None or env[var] == value):
                return BY_KEY[key]
    return None


def detect_system(environ=None):
    """An agent's `system` (claimset §3.11, lab record §5.2) from the environment: {name, version} of the harness
    that identifies itself, {name} from $AI_AGENT for one that only names itself there, else None."""
    env = os.environ if environ is None else environ
    h = detect(env)
    if h is not None:
        out = {"name": h.name}
        if h.version_env and env.get(h.version_env):
            out["version"] = env[h.version_env]
        return out
    name = (env.get("AI_AGENT") or "").strip()
    return {"name": name} if name else None


# ---------- skills and instructions ----------

def skill_dirs(harnesses):
    """The fewest skill folders that reach every harness: a folder read by most of those not yet reached, first."""
    left = [h for h in harnesses if h.skills]
    chosen = []
    while left:
        counts = {}
        for h in left:
            for d in h.skills:
                counts[d] = counts.get(d, 0) + 1
        best = max(counts, key=lambda d: (counts[d], d == SHARED_SKILLS))
        chosen.append(best)
        left = [h for h in left if best not in h.skills]
    return chosen


def rules():
    """The rules every agent follows (agents/RULES.md), as Markdown bullets: one text for the guide, the AGENTS.md
    block and the README."""
    return (DATA / "RULES.md").read_text(encoding="utf-8").strip()


def instructions_block(skills_dir):
    """The claimset block of AGENTS.md: one template for every agent."""
    text = (DATA / "AGENTS.md").read_text(encoding="utf-8").replace("{skills}", skills_dir or SHARED_SKILLS)
    return f"{BEGIN}\n{text.replace('{rules}', rules()).strip()}\n{END}\n"


def import_block(line):
    return f"{BEGIN}\n{line}\n{END}\n"


def write_block(path, block):
    """Put the block in a file, replacing an earlier claimset block, or after what the file holds. Returns
    "created", "updated" or "current"."""
    path = Path(path)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old is None:
        new = block
    elif BEGIN in old and END in old:
        new = old[:old.index(BEGIN)] + block.rstrip("\n") + old[old.index(END) + len(END):]
        if not new.endswith("\n"):
            new += "\n"
    else:
        new = old.rstrip("\n") + ("\n\n" if old.strip() else "") + block
    if new == old:
        return "current"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8")
    return "created" if old is None else "updated"


# ---------- the guard: reading a proposed tool call ----------

#: Tools that run a shell command, by the names the harnesses give them
SHELL_TOOLS = {"Bash", "bash", "Shell", "shell", "run_shell_command", "Execute", "execute", "exec_command",
               "local_shell", "powershell", "terminal", "run_terminal_cmd", "run_command"}
#: Tools that create, change or delete a file
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "edit", "write", "multiedit", "write_file", "replace",
               "notebook_edit", "create", "Create", "str_replace_editor", "str_replace_based_edit_tool", "Delete",
               "delete", "delete_file", "edit_file", "search_replace"}
#: Tools that apply a patch, whose files are named inside it
PATCH_TOOLS = {"apply_patch", "ApplyPatch", "patch"}
PATH_KEYS = ("file_path", "filePath", "notebook_path", "path", "target_file", "filename")
COMMAND_KEYS = ("command", "cmd", "command_line", "commandLine")
PATCH_KEYS = ("patchText", "patch", "input", "command")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$", re.M)


def _text(value):
    """A command as text: a string as it is; an argv list as the script it runs (`bash -lc SCRIPT`), else joined."""
    if isinstance(value, list):
        argv = [str(v) for v in value]
        if len(argv) >= 3 and Path(argv[0]).name in ("bash", "sh", "zsh", "dash") and argv[1] in ("-c", "-lc"):
            return argv[2]
        return " ".join(shlex.quote(v) for v in argv)
    return value if isinstance(value, str) else None


def patch_files(text):
    """The files an apply_patch text adds, changes, deletes or moves to."""
    return [a or b for a, b in PATCH_FILE.findall(text or "")]


def tool_actions(agent, payload):
    """(cwd, actions) of a proposed tool call, in whatever shape the harness sends it: Claude Code, Codex and Qwen
    Code (`tool_name`, `tool_input`), Gemini CLI (the same names, its own tools), Copilot (`toolName`, `toolArgs`,
    possibly a JSON string), opencode through the plugin (`tool`, `args`), a bare shell command (`command`) and
    Windsurf (`tool_info`). An action is ("write", path) or ("shell", command). A call that names no file and no
    command gives no actions, and is allowed."""
    if not isinstance(payload, dict):
        return None, []
    cwd = payload.get("cwd") or payload.get("directory")
    if not cwd and isinstance(payload.get("workspace_roots"), list) and payload["workspace_roots"]:
        cwd = payload["workspace_roots"][0]
    tool = payload.get("tool_name") or payload.get("toolName") or payload.get("tool")
    args = payload.get("tool_input", payload.get("toolArgs", payload.get("args")))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"command": args}
    info = payload.get("tool_info")
    if tool is None and isinstance(info, dict):                       # Windsurf
        args = info
        tool = "shell" if info.get("command_line") else "write" if info.get("file_path") else None
        cwd = cwd or info.get("cwd")
    if tool is None and isinstance(payload.get("command"), str):      # a bare shell hook (Cursor)
        tool, args = "shell", {"command": payload["command"]}
    args = args if isinstance(args, dict) else {}
    actions = []
    if tool in PATCH_TOOLS:
        for key in PATCH_KEYS:
            text = _text(args.get(key))
            if text:
                actions += [("write", p) for p in patch_files(text)]
                break
    elif tool in SHELL_TOOLS:
        command = next((_text(args.get(k)) for k in COMMAND_KEYS if _text(args.get(k))), None)
        if command:
            actions.append(("shell", command))
            if command.lstrip().startswith("apply_patch"):              # Codex may apply a patch through its shell
                actions += [("write", p) for p in patch_files(command)]
    elif tool in WRITE_TOOLS or tool == "write":
        for key in PATH_KEYS:
            if isinstance(args.get(key), str) and args[key]:
                actions.append(("write", args[key]))
        for edit in args.get("edits") or []:                         # several files in one call
            if isinstance(edit, dict) and isinstance(edit.get("file_path"), str):
                actions.append(("write", edit["file_path"]))
    return cwd, actions


def refuse(agent, reason, stdout=None, stderr=None):
    """Answer a refused tool call in the harness's protocol; returns the exit code."""
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    if agent == "cline":
        stdout.write(json.dumps({"cancel": True, "errorMessage": reason}) + "\n")
        return 0
    stderr.write(reason + "\n")
    return 2


# ---------- the guard: registering it with each harness ----------

GUARD_MATCHERS = {"claude": "Edit|Write|MultiEdit|NotebookEdit|Bash",
                  "codex": "Bash|apply_patch|Edit|Write",
                  "gemini": "run_shell_command|write_file|replace",
                  "qwen": "run_shell_command|write_file|edit|notebook_edit"}


def _claude_style(agent, guard, studies, seconds=True):
    """Claude Code's hook format, which Codex and Qwen Code use too."""
    timeout = {"timeout": 30} if seconds else {}
    return {"hooks": {
        "PreToolUse": [{"matcher": GUARD_MATCHERS[agent],
                        "hooks": [dict({"type": "command", "command": guard}, **timeout)]}],
        "SessionStart": [{"hooks": [dict({"type": "command", "command": studies}, **timeout)]}],
    }}


def hook_config(agent, guard="claimset lab guard"):
    """{path in the project: JSON to merge into it, or text of a file} that registers the guard (and `claimset
    studies` at the start of a session) with one harness; {} for a harness without hooks."""
    h = harness(agent)
    studies = guard.replace("lab guard", "studies")
    if h.hooks in ("claude", "codex", "qwen"):
        path = {"claude": ".claude/settings.json", "codex": ".codex/hooks.json", "qwen": ".qwen/settings.json"}
        return {path[h.hooks]: _claude_style(h.hooks, guard, studies, seconds=h.hooks != "claude")}
    if h.hooks == "gemini":
        return {".gemini/settings.json": {"hooks": {
            "BeforeTool": [{"matcher": GUARD_MATCHERS["gemini"],
                            "hooks": [{"name": "claimset-guard", "type": "command", "command": guard,
                                       "timeout": 30000}]}],
            "SessionStart": [{"matcher": "startup",
                              "hooks": [{"name": "claimset-studies", "type": "command", "command": studies,
                                         "timeout": 30000}]}],
        }}}
    if h.hooks == "copilot":
        return {".github/hooks/claimset.json": {"version": 1, "hooks": {
            "preToolUse": [{"type": "command", "bash": guard, "timeoutSec": 30}],
            "sessionStart": [{"type": "command", "bash": studies, "timeoutSec": 30}],
        }}}
    if h.hooks == "cursor":
        return {".cursor/hooks.json": {"version": 1, "hooks": {
            "beforeShellExecution": [{"command": guard}],
            "preToolUse": [{"command": guard, "matcher": "Shell|Write|Delete"}],
        }}}
    if h.hooks == "opencode":
        js = (DATA / "opencode-guard.js").read_text(encoding="utf-8")
        return {".opencode/plugins/claimset-guard.js": js.replace("{guard}", json.dumps(guard + " --agent opencode"))}
    if h.hooks == "cline":
        return {".clinerules/hooks/PreToolUse": f"#!/bin/sh\n# written by `claimset init`: the claimset guard "
                                                f"(lab record §4.5)\nexec {guard} --agent cline\n"}
    return {}


def _merge(base, add):
    """Merge hook settings: lists of hook groups are extended with groups not already there."""
    out = dict(base)
    for k, v in add.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif isinstance(v, list) and isinstance(out.get(k), list):
            out[k] = out[k] + [x for x in v if x not in out[k]]
        else:
            out[k] = v
    return out


def _is_claimset_hook(group):
    s = json.dumps(group)
    return ("lab guard" in s or " studies" in s) and "claimset" in s


def _drop_claimset_hooks(settings):
    """The settings without hook entries an earlier `claimset init` wrote, so that a new guard command replaces
    them instead of standing beside them."""
    out = json.loads(json.dumps(settings))
    hooks = out.get("hooks")
    if isinstance(hooks, dict):
        for event, groups in list(hooks.items()):
            if isinstance(groups, list):
                hooks[event] = [g for g in groups if not _is_claimset_hook(g)]
    return out


def write_hooks(root, agent, guard):
    """Register the guard with one harness in the project at `root`. Returns [(path, what)]."""
    done = []
    for rel, content in hook_config(agent, guard).items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            old = {}
            if path.exists():
                try:
                    old = json.loads(path.read_text(encoding="utf-8") or "{}")
                except ValueError:
                    raise ValueError(f"{rel} is not valid JSON: fix it, then run `claimset init` again") from None
            new = _merge(_drop_claimset_hooks(old), content)
            text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
        else:
            text = content
        before = path.read_text(encoding="utf-8") if path.exists() else None
        if before != text:
            path.write_text(text, encoding="utf-8")
            if text.startswith("#!"):
                path.chmod(0o755)
        done.append((rel, "current" if before == text else "created" if before is None else "updated"))
    return done


# ---------- the network a sandbox may withhold ----------

NETWORK_FAILURE = re.compile(r"could not resolve|resolve host|network is unreachable|connection refused|timed out|"
                             r"operation not permitted|temporary failure in name resolution|proxy|"
                             r"could not read from remote|unable to access|name or service not known", re.I)


def network_hint(message="", environ=None):
    """When a push or a call to the platform failed for want of network, how the harness running this shell lets
    it through; "" when nothing points to a sandbox."""
    env = os.environ if environ is None else environ
    h = detect(env)
    blocked = env.get("CODEX_SANDBOX_NETWORK_DISABLED") == "1"
    if not (blocked or NETWORK_FAILURE.search(message or "")):
        return ""
    if h is not None and h.network:
        return f" The agent's sandbox may be withholding the network: {h.network}."
    return (" If an agent runs this command in a sandbox, the sandbox may be withholding the network: allow the git "
            "host and entrylib.org in its settings (`claimset init --list` shows how for each agent).")


# ---------- claimset init ----------

def init(root, agents, guard=False, skills=True, guard_command=None):
    """Set up the project at `root` for the harnesses `agents` (keys): skills in the fewest folders, the
    instructions block in AGENTS.md and the files that import it, and, with `guard`, the guard's hooks. Returns
    {"done": [(path, what)], "notes": [...]}."""
    from . import bundle
    hs = [harness(a) for a in agents]
    root = Path(root)
    done, notes = [], []
    dirs = skill_dirs(hs)
    if skills:
        for d in dirs:
            for name in bundle.SKILLS:
                done.append((f"{d}/{name}", bundle.install(root / d, name)))
    primary = SHARED_SKILLS if SHARED_SKILLS in dirs else (dirs[0] if dirs else SHARED_SKILLS)
    done.append(("AGENTS.md", write_block(root / "AGENTS.md", instructions_block(primary))))
    for h in hs:
        if h.instructions != "AGENTS.md" and h.imports:
            done.append((h.instructions, write_block(root / h.instructions, import_block(h.imports))))
    if guard:
        from .lab import guard as _guard
        command = guard_command or _guard.guard_command()
        for h in hs:
            if h.hooks:
                done += write_hooks(root, h.key, command)
            else:
                notes.append(f"{h.name} runs no command before a tool call, so it has no guard: the lab record is "
                             f"protected by anchoring and `claimset lab protect` (lab record §4.5).")
    for h in hs:
        notes += list(h.notes)
        if not h.verified:
            notes.append(f"What claimset knows of {h.name} rests on secondary sources: check that it reads "
                         f"{', '.join(h.skills) or 'its files'} and {h.instructions}.")
    notes.append("If an agent cannot tell which model it is, set CLAIMSET_MODEL=\"provider|name|version|identifier\" "
                 "in the environment it runs in; `claimset lab actor` records it as reported by you.")
    seen, out = set(), []
    for x in done:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return {"done": out, "notes": list(dict.fromkeys(notes)), "skills": dirs}


def cmd_init(args):
    if args.list:
        for h in HARNESSES:
            print(f"{h.key:9} {h.name}{'' if h.verified else ' (unverified)'}: skills "
                  f"{', '.join(h.skills) or 'none'}; reads {h.instructions}; guard "
                  f"{'yes' if h.hooks else 'no'}" + (f"; network: {h.network}" if h.network else ""))
        return 0
    agents = args.agent or []
    if "all" in agents:
        agents = [h.key for h in HARNESSES if h.verified and h.key != "generic"]
    if not agents:
        found = detect()
        agents = [found.key] if found else ["generic"]
        print(f"agent: {found.name if found else 'none recognised; AGENTS.md and .agents/skills'} "
              f"(--agent to choose; --list for all)")
    try:
        out = init(args.dir, agents, guard=args.guard, skills=not args.no_skills)
    except (ValueError, OSError, FileExistsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for path, what in out["done"]:
        print(f"{what:8} {path}")
    for n in out["notes"]:
        print(f"note: {n}")
    if not args.guard:
        print("note: the guard is not installed; `claimset init --guard` adds it for every agent above that "
              "supports it. It restricts the agent, so the human decides.")
    return 0


def add_parsers(sub):
    p = sub.add_parser("init", help="set a project up for coding agents: the skills, the instructions block in "
                                    "AGENTS.md (imported by CLAUDE.md and GEMINI.md) and, with --guard, the lab "
                                    "record's guard")
    p.add_argument("--agent", action="append", metavar="NAME",
                   help="an agent to set up for; repeat for several, or `all` (default: the one running this "
                        "shell, else a generic setup); `--list` shows them")
    p.add_argument("--guard", action="store_true", help="also install the guard hooks (lab record §4.5)")
    p.add_argument("--no-skills", action="store_true", help="only the instructions (and hooks)")
    p.add_argument("--dir", default=".", help="the project's top folder (default: here)")
    p.add_argument("--list", action="store_true", help="the agents claimset knows, and what each reads")
    p.set_defaults(func=cmd_init)

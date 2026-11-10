"""Guard for agent harnesses (lab record spec §4.5).

Installed as a pre-tool-use hook, it receives each proposed tool call as JSON on
standard input and refuses (exit code 2, reason on standard error) any call that
would modify the lab directory other than through `claimset lab`. It is a
guardrail against accidental or casual modification, not a security boundary:
the append-only attribute and anchoring cover deliberate tampering.

The checks are the same in every harness: they see a call as files it would write and commands it would run.
How each harness passes the call and how a refusal is answered is in `claimset.agents`.
"""

import json
import os
import re
import shlex
from pathlib import Path

from .anchor import DEFAULT_BRANCH

# Commands and constructs that change files. Reading (cat, grep, jq, ls, git log/diff) is allowed.
# The match is deliberately broad: when in doubt the guard refuses and points to `claimset lab`.
DESTRUCTIVE = re.compile(
    r"(?:^|[\s;&|(`])(?:rm|rmdir|mv|cp|install|truncate|shred|unlink|chattr|dd|tee|touch|ln|rsync|chmod|chown)\b"
    r"|\b(?:sed|perl|ruby)\s+(?:-\w*\s+)*-i"
    r"|\bgit\s+(?:checkout|restore|reset|clean|rm|mv|stash|filter-branch|filter-repo|rebase|update-ref)\b"
    r"|\bgit\s+commit\b[^;&|]*--amend"
    r"|\bopen\([^)]*['\"][wa+]"
    r"|\b(?:write_text|write_bytes|unlink|rmtree|remove|rename|replace)\("
)
FORCE_PUSH = re.compile(r"\bgit\s+push\b[^;&|]*(?:\s-f\b|--force|\s\+\S+)")
# Study branches are never merged into code, nor code into them (§3), and are never checked out in the code checkout.
STUDY_MIX = re.compile(r"\bgit\s+(?:merge|rebase|cherry-pick|pull)\b[^;&|]*\bclaimset/")
STUDY_CHECKOUT = re.compile(r"\bgit\s+(?:checkout|switch)\b[^;&|]*\s(?:origin/)?claimset/[a-z]")
STUDY_ADD = re.compile(r"\bgit\s+add\b[^;&|]*(?:\s-f\b|--force)[^;&|]*\bclaimset\b")
STUDY_REWRITE = re.compile(r"\bgit\s+(?:push\b[^;&|]*(?:\s-f\b|--force|--delete|\s:)[^;&|]*claimset/"
                           r"|branch\s+-[dDmM]\b[^;&|]*claimset/|update-ref\s+-d[^;&|]*claimset/)")
DELETE_BRANCH = re.compile(r"\bgit\s+push\b[^;&|]*(?:--delete|\s:\S+)")
MIRROR = re.compile(r"\bgit\s+push\b[^;&|]*--mirror")
ALL = re.compile(r"\bgit\s+push\b[^;&|]*--all")
REDIRECT = re.compile(r"(?:\d|&)?>{1,2}\|?\s*(['\"]?)([^\s'\";|&)]+)\1")
OPERATOR = re.compile(r"^[;&|<>()]+$")


def lab_dir(cwd):
    """The lab directory the agent would use: $CLAIMSET_LAB or ./lab, relative to cwd."""
    return Path(cwd) / (os.environ.get("CLAIMSET_LAB") or "lab")


def lab_dirs(cwd):
    """Every lab the agent could reach: $CLAIMSET_LAB, ./lab and the labs of all studies (claimset/*/lab)."""
    from .layout import lab_dirs as _all
    return _all(cwd)


def _lab_subcommand(command):
    """For a plain `claimset lab <sub> ...` command, (sub, remaining tokens); else None.

    A command with shell operators (;, &&, |, >, ...) outside quotes is not plain.
    """
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return None
    if any(OPERATOR.match(t) for t in tokens):
        return None
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        tokens = tokens[1:]
    # `python3 path/to/claimset lab ...` (the copy bundled with the skill) or `python3 -m claimset lab ...`
    if tokens and re.match(r"^python(\d+(\.\d+)?)?$", Path(tokens[0]).name):
        tokens = tokens[1:]
        if tokens[:1] == ["-m"]:
            tokens = tokens[1:]
    if len(tokens) < 2 or Path(tokens[0]).name != "claimset" or tokens[1] != "lab":
        return None
    return (tokens[2] if len(tokens) > 2 else ""), tokens[3:]


def _inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _mentions(command, root, cwd):
    """True if the command refers to the lab directory or a file in it."""
    root = Path(root)
    names = {str(root.resolve())}
    try:
        names.add(os.path.relpath(root.resolve(), Path(cwd).resolve()))
    except ValueError:
        pass
    for name in names:
        n = name.rstrip("/")
        if re.search(r"(?:^|[\s'\"=:(/])" + re.escape(n) + r"(?:/|[\s'\";|&)]|$)", command):
            return True
    return False


def _anchor_branch(root):
    try:
        cfg = json.loads((Path(root) / "config.json").read_text(encoding="utf-8"))
        branch = (cfg.get("anchor") or {}).get("branch")
    except (OSError, ValueError, AttributeError):
        branch = None
    if branch:
        return branch
    from .anchor import default_branch
    from .core import Lab
    return default_branch(Lab(root)) if (Path(root) / "lab.jsonl").exists() else DEFAULT_BRANCH


def decide(payload, branch=None):
    """Claude Code's hook input: return None to allow the tool call, or the reason for refusing it."""
    from .. import agents
    cwd, actions = agents.tool_actions("claude", payload)
    return decide_actions(actions, cwd, branch)


def decide_actions(actions, cwd=None, branch=None):
    """The harness-neutral guard (§4.5): `actions` is what a proposed tool call would do, as a list of
    ("write", path) for a file it would create, change or delete, and ("shell", command) for a command it would
    run. Return None to allow the call, or the reason for refusing it."""
    cwd = cwd or os.getcwd()
    for root in lab_dirs(cwd):
        anchor = branch or _anchor_branch(root)
        for kind, value in actions:
            reason = (_check_write(value, cwd, root) if kind == "write" else
                      _check_shell(value, cwd, root, anchor) if kind == "shell" else None)
            if reason:
                return reason
    return None


def _check_write(path, cwd, root):
    if path and _inside(Path(cwd) / os.path.expanduser(str(path)), root):
        return (f"{path} is part of the lab record, which is append-only. Record changes with "
                f"`claimset lab` commands (corrections with --supersedes), never by editing files.")
    return None


def _check_shell(command, cwd, root, branch):
    command = command or ""
    plain = _lab_subcommand(command)
    if plain is not None:
        sub, rest = plain
        if sub != "run":
            return None
        # The command a run wraps is checked like any other command.
        command = " ".join(shlex.quote(t) for t in rest[rest.index("--") + 1:]) if "--" in rest else ""
    if STUDY_MIX.search(command):
        return ("study branches (claimset/<study>) are never merged with code branches, in either direction. "
                "Record changes with `claimset lab`; the code goes through its own pull requests.")
    if STUDY_CHECKOUT.search(command):
        return ("a study branch is checked out only at claimset/<study>/ (`claimset setup --study NAME`), never "
                "in the code checkout.")
    if STUDY_ADD.search(command):
        return "study records are never committed to code branches; they live on their study branches."
    if STUDY_REWRITE.search(command):
        return "force-pushing, deleting or renaming a study branch would rewrite the study's record."
    rewrites = FORCE_PUSH.search(command) or DELETE_BRANCH.search(command) or MIRROR.search(command)
    if rewrites and (branch in command or MIRROR.search(command) or ALL.search(command)):
        return f"force-pushing or deleting the anchor branch '{branch}' would rewrite the anchored lab record."
    for _, target in REDIRECT.findall(command):
        if _inside(Path(cwd) / os.path.expanduser(target), root):
            return (f"writing to {target} with a shell redirection would modify the lab record, which is "
                    f"append-only. Use `claimset lab` commands to add to it.")
    if _mentions(command, root, cwd) and DESTRUCTIVE.search(command):
        return ("this command would modify the lab record, which is append-only. Use `claimset lab` "
                "commands to add to it; read it with `claimset lab list`, `show` or `summary`.")
    return None


def main_hook(stdin, stderr, agent="claude", stdout=None):
    """Run as a harness's pre-tool hook: read the proposed call from stdin and answer in the harness's protocol."""
    from .. import agents
    try:
        payload = json.load(stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    cwd, actions = agents.tool_actions(agent, payload)
    reason = decide_actions(actions, cwd)
    if reason:
        return agents.refuse(agent, f"claimset guard: blocked. {reason}", stdout, stderr)
    return 0


def guard_command(argv0=None, installed=None):
    """How the hook should call the guard: the installed command, or the script that is running now."""
    import shutil
    import sys

    installed = shutil.which("claimset") if installed is None else installed
    if installed:
        return "claimset lab guard"
    argv0 = Path(argv0 or sys.argv[0])
    if argv0.is_file() and argv0.name not in ("__main__.py", "-c"):
        return f"{shlex.quote(sys.executable)} {shlex.quote(str(argv0.resolve()))} lab guard"
    return f"{shlex.quote(sys.executable)} -m claimset lab guard"


def claude_code_config(command="claimset lab guard"):
    """Settings snippet: the guard as a Claude Code PreToolUse hook, and the state of the studies shown at the
    start of every session, so that work begins inside the record. Other harnesses: `claimset.agents.hook_config`."""
    from .. import agents
    return agents.hook_config("claude", command)[".claude/settings.json"]

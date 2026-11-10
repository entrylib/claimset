"""Agent harnesses (lab record v0.21 §4.5, §4.6, §5.2): `claimset init`, the guard in every harness's shape,
recognising the harness, and advice when a sandbox withholds the network."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from claimset import agents  # noqa: E402
from claimset.cli import main  # noqa: E402
from claimset.lab import guard  # noqa: E402

GUARD = f"{sys.executable} -m claimset lab guard"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Project(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "lab").mkdir()
        self.old = os.environ.pop("CLAIMSET_LAB", None)

    def tearDown(self):
        if self.old is not None:
            os.environ["CLAIMSET_LAB"] = self.old
        self.tmp.cleanup()


class TestSkillFolders(unittest.TestCase):
    def dirs(self, *keys):
        return agents.skill_dirs([agents.harness(k) for k in keys])

    def test_the_fewest_folders(self):
        self.assertEqual(self.dirs("codex", "gemini", "qwen", "opencode", "copilot", "cursor"), [".agents/skills"])
        self.assertEqual(self.dirs("claude"), [".claude/skills"])
        self.assertEqual(self.dirs("claude", "codex"), [".agents/skills", ".claude/skills"])
        self.assertEqual(self.dirs("claude", "opencode"), [".claude/skills"])         # opencode reads it too
        self.assertEqual(self.dirs("kiro", "codex"), [".agents/skills", ".kiro/skills"])
        self.assertEqual(self.dirs("aider"), [])

    def test_every_harness_is_listed(self):
        code, out, _ = run("init", "--list")
        self.assertEqual(code, 0)
        for h in agents.HARNESSES:
            self.assertIn(h.name, out)
        with self.assertRaises(ValueError):
            agents.harness("nobody")


class TestInit(Project):
    def init(self, *names, guard_=False):
        return agents.init(self.root, names, guard=guard_, guard_command=GUARD)

    def test_one_block_imported_where_it_can_be(self):
        (self.root / "CLAUDE.md").write_text("# Notes\n\nKeep these.\n")
        self.init("claude", "gemini", "codex")
        block = (self.root / "AGENTS.md").read_text()
        self.assertIn(".agents/skills/claimset-lab/SKILL.md", block)
        self.assertNotIn("{skills}", block)
        claude = (self.root / "CLAUDE.md").read_text()
        self.assertTrue(claude.startswith("# Notes\n\nKeep these.\n"))
        self.assertIn("\n@AGENTS.md\n", claude)
        self.assertNotIn("Claimset lab records", claude)                    # imported, never copied
        self.assertIn("@./AGENTS.md", (self.root / "GEMINI.md").read_text())
        for d in (".agents/skills", ".claude/skills"):
            self.assertTrue((self.root / d / "claimset-lab" / "scripts" / "claimset").exists(), d)

    def test_a_claude_only_project_points_at_its_own_skills(self):
        self.init("claude")
        self.assertIn(".claude/skills/claimset-submit/SKILL.md", (self.root / "AGENTS.md").read_text())
        self.assertFalse((self.root / ".agents").exists())

    def test_again_changes_nothing(self):
        self.init("claude", "codex", guard_=True)
        out = self.init("claude", "codex", guard_=True)
        self.assertEqual({what for _, what in out["done"]}, {"current"}, out["done"])

    def test_the_block_is_replaced_not_repeated(self):
        (self.root / "AGENTS.md").write_text(f"# Project\n\n{agents.BEGIN}\nold text\n{agents.END}\n\nAfter.\n")
        self.init("codex")
        text = (self.root / "AGENTS.md").read_text()
        self.assertEqual(text.count(agents.BEGIN), 1)
        self.assertNotIn("old text", text)
        self.assertTrue(text.startswith("# Project\n") and text.endswith("After.\n"))

    def test_hooks_for_each_harness(self):
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "settings.json").write_text(json.dumps(
            {"permissions": {"allow": ["Bash(ls)"]},
             "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "mine"}]}]}}))
        out = self.init("claude", "codex", "gemini", "qwen", "copilot", "cursor", "opencode", "cline", "aider",
                        guard_=True)
        claude = json.loads((self.root / ".claude" / "settings.json").read_text())
        self.assertEqual(claude["permissions"], {"allow": ["Bash(ls)"]})              # the user's settings stay
        self.assertEqual([g["hooks"][0]["command"] for g in claude["hooks"]["PreToolUse"]], ["mine", GUARD])
        self.assertEqual(json.loads((self.root / ".codex" / "hooks.json").read_text())["hooks"]["PreToolUse"][0]
                         ["matcher"], "Bash|apply_patch|Edit|Write")
        gemini = json.loads((self.root / ".gemini" / "settings.json").read_text())["hooks"]
        self.assertEqual(gemini["BeforeTool"][0]["matcher"], "run_shell_command|write_file|replace")
        self.assertIn("claimset studies", json.dumps(gemini["SessionStart"]))
        self.assertTrue(json.loads((self.root / ".qwen" / "settings.json").read_text())["hooks"]["PreToolUse"])
        self.assertEqual(json.loads((self.root / ".github" / "hooks" / "claimset.json").read_text())["version"], 1)
        self.assertTrue(json.loads((self.root / ".cursor" / "hooks.json").read_text())["hooks"])
        self.assertIn(json.dumps(GUARD + " --agent opencode"),
                      (self.root / ".opencode" / "plugins" / "claimset-guard.js").read_text())
        cline = self.root / ".clinerules" / "hooks" / "PreToolUse"
        self.assertTrue(os.access(cline, os.X_OK))
        self.assertIn("Aider runs no command before a tool call", " ".join(out["notes"]))

    def test_a_new_guard_command_replaces_the_old(self):
        agents.init(self.root, ["claude"], guard=True, guard_command="claimset lab guard")
        agents.init(self.root, ["claude"], guard=True, guard_command=GUARD)
        hooks = json.loads((self.root / ".claude" / "settings.json").read_text())["hooks"]
        self.assertEqual([g["hooks"][0]["command"] for g in hooks["PreToolUse"]], [GUARD])
        self.assertEqual(len(hooks["SessionStart"]), 1)

    def test_the_command(self):
        code, out, _ = run("init", "--dir", str(self.root), "--agent", "gemini", "--no-skills")
        self.assertEqual(code, 0)
        self.assertIn("created  GEMINI.md", out)
        self.assertIn("the guard is not installed", out)
        self.assertFalse((self.root / ".agents").exists())
        self.assertEqual(run("init", "--dir", str(self.root), "--agent", "nobody")[0], 1)

    def test_skill_check_finds_every_agents_copy(self):
        self.init("claude", "codex")
        here = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, here)
        code, out, _ = run("skill", "check")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("claimset-lab: current"), 2)
        (self.root / ".agents" / "skills" / "claimset-lab" / "SKILL.md").write_text("---\nname: claimset-lab\n---\nold")
        self.assertEqual(run("skill", "check")[0], 1)

    def test_print_config(self):
        code, out, _ = run("lab", "guard", "--print-config", "--agent", "gemini")
        self.assertEqual(code, 0)
        self.assertIn("# .gemini/settings.json", out)
        code, out, _ = run("lab", "guard", "--print-config")
        self.assertIn("PreToolUse", json.loads(out)["hooks"])                     # Claude Code's, as before
        self.assertEqual(run("lab", "guard", "--print-config", "--agent", "aider")[0], 1)


class TestToolCalls(Project):
    """The guard reads every harness's tool calls; the checks themselves are those of test_lab_protect."""

    CALLS = {
        "claude": {"tool_name": "Write", "tool_input": {"file_path": "lab/lab.jsonl"}},
        "codex shell": {"tool_name": "Bash", "tool_input": {"command": "rm lab/lab.jsonl"}},
        "codex patch": {"tool_name": "apply_patch", "tool_input": {
            "command": "*** Begin Patch\n*** Update File: lab/lab.jsonl\n@@\n-x\n+y\n*** End Patch\n"}},
        "codex argv": {"tool_name": "Bash", "tool_input": {"command": ["bash", "-lc", "rm lab/lab.jsonl"]}},
        "gemini write": {"tool_name": "write_file", "tool_input": {"file_path": "lab/lab.jsonl", "content": "x"}},
        "gemini replace": {"tool_name": "replace", "tool_input": {"file_path": "lab/lab.jsonl"}},
        "gemini shell": {"tool_name": "run_shell_command", "tool_input": {"command": "truncate -s0 lab/lab.jsonl"}},
        "qwen edit": {"tool_name": "edit", "tool_input": {"file_path": "lab/lab.jsonl"}},
        "copilot": {"toolName": "bash", "toolArgs": json.dumps({"command": "rm -rf lab"})},
        "copilot create": {"toolName": "create", "toolArgs": {"path": "lab/x.json"}},
        "opencode edit": {"tool": "edit", "args": {"filePath": "lab/lab.jsonl"}},
        "opencode v2 write": {"tool": "write", "args": {"path": "lab/lab.jsonl"}},
        "opencode patch": {"tool": "apply_patch", "args": {"patchText": "*** Begin Patch\n*** Add File: lab/new\n"
                                                                       "+x\n*** End Patch"}},
        "opencode move": {"tool": "apply_patch", "args": {"patchText": "*** Update File: notes.md\n"
                                                                       "*** Move to: lab/notes.md\n"}},
        "cursor shell": {"command": "rm lab/lab.jsonl"},
        "windsurf write": {"tool_info": {"file_path": "lab/lab.jsonl"}},
        "windsurf shell": {"tool_info": {"command_line": "rm lab/lab.jsonl"}},
    }
    ALLOWED = {
        "read": {"tool_name": "read_file", "tool_input": {"file_path": "lab/lab.jsonl"}},
        "opencode read": {"tool": "read", "args": {"filePath": "lab/lab.jsonl"}},
        "elsewhere": {"tool_name": "write_file", "tool_input": {"file_path": "analysis.py"}},
        "patch elsewhere": {"tool": "apply_patch", "args": {"patchText": "*** Update File: src/x.py\n"}},
        "lab command": {"toolName": "bash", "toolArgs": {"command": "claimset lab note hello"}},
        "nothing": {"tool_name": "WebSearch", "tool_input": {"query": "rm lab"}},
    }

    def decide(self, payload):
        cwd, actions = agents.tool_actions("any", dict(payload, cwd=str(self.root)))
        return guard.decide_actions(actions, cwd)

    def test_refused_in_every_shape(self):
        for name, payload in self.CALLS.items():
            self.assertIsNotNone(self.decide(payload), name)

    def test_allowed(self):
        for name, payload in self.ALLOWED.items():
            self.assertIsNone(self.decide(payload), name)

    def test_answers(self):
        payload = json.dumps(dict(self.CALLS["gemini write"], cwd=str(self.root)))
        err = io.StringIO()
        self.assertEqual(guard.main_hook(io.StringIO(payload), err, agent="gemini"), 2)
        self.assertIn("claimset guard: blocked", err.getvalue())
        out = io.StringIO()
        self.assertEqual(guard.main_hook(io.StringIO(payload), io.StringIO(), agent="cline", stdout=out), 0)
        self.assertTrue(json.loads(out.getvalue())["cancel"])
        self.assertEqual(guard.main_hook(io.StringIO("[1, 2]"), io.StringIO()), 0)        # not a call

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_opencode_plugin(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        agents.init(self.root, ["opencode"], guard=True, skills=False, guard_command=GUARD)
        plugin = self.root / ".opencode" / "plugins" / "claimset-guard.mjs"
        shutil.copy(plugin.with_suffix(".js"), plugin)
        script = (f"const m = await import({json.dumps(plugin.as_uri())});"
                  f"const h = await m.ClaimsetGuard({{directory: {json.dumps(str(self.root))}}});"
                  "const call = (tool, args) => h['tool.execute.before']({tool}, {args})"
                  ".then(() => 'allowed', e => 'refused: ' + e.message);"
                  "console.log(await call('edit', {filePath: 'lab/lab.jsonl'}));"
                  "console.log(await call('bash', {command: 'ls lab'}));")
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, env=env,
                             timeout=60)
        lines = out.stdout.strip().splitlines()
        self.assertEqual(len(lines), 2, out.stderr)
        self.assertTrue(lines[0].startswith("refused: claimset guard: blocked"), lines[0])
        self.assertEqual(lines[1], "allowed")


class TestEnvironment(unittest.TestCase):
    def test_the_harness_names_itself(self):
        self.assertEqual(agents.detect_system({"CLAUDECODE": "1"}), {"name": "Claude Code"})
        self.assertEqual(agents.detect_system({"CODEX_THREAD_ID": "t1"}), {"name": "Codex CLI"})
        self.assertEqual(agents.detect_system({"GEMINI_CLI": "1"}), {"name": "Gemini CLI"})
        self.assertEqual(agents.detect_system({"OPENCODE": "1", "KILO": "1", "AGENT": "1"}), {"name": "Kilo Code"})
        self.assertEqual(agents.detect_system({"OPENCODE": "1"}), {"name": "opencode"})
        self.assertEqual(agents.detect_system({"AI_AGENT": "some-agent"}), {"name": "some-agent"})
        self.assertIsNone(agents.detect_system({"CLAUDECODE": "0", "PATH": "/bin"}))

    def test_network_advice(self):
        codex = {"CODEX_SANDBOX_NETWORK_DISABLED": "1"}
        self.assertIn("network_access", agents.network_hint("", codex))
        self.assertIn("sandbox", agents.network_hint("Could not resolve host: github.com", {}))
        self.assertIn("allowedDomains", agents.network_hint("Could not resolve host: x", {"CLAUDECODE": "1"}))
        self.assertEqual(agents.network_hint("rejected: non-fast-forward", {"CLAUDECODE": "1"}), "")


if __name__ == "__main__":
    unittest.main()

"""`claimset guide`, and the README as an agent finds it on PyPI: one text of the rules, links that work outside
the repository, documentation that resolves, and the Python versions the package claims are the ones tested."""

import contextlib
import io
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from claimset import SPEC_VERSION, __version__, agents, bundle  # noqa: E402
from claimset.cli import main  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")
RULES = (ROOT / "agents" / "RULES.md").read_text(encoding="utf-8").strip()
LINK = re.compile(r"\]\(([^)\s]+)\)")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestGuide(unittest.TestCase):
    def test_where_to_start(self):
        code, out, _ = run("guide")
        self.assertEqual(code, 0)
        for name in bundle.SKILLS:
            self.assertIn(f"claimset guide {name}", out)
        self.assertIn(RULES, out)
        self.assertIn("https://entrylib.org", out)
        self.assertIn(f"claimset {__version__}, following specification v{SPEC_VERSION}", out)
        self.assertNotRegex(out, r"\{(rules|version|spec|skills)\}")

    def test_a_skill(self):
        for name in bundle.SKILLS:
            code, out, _ = run("guide", name)
            self.assertEqual(code, 0, name)
            self.assertIn(f"name: {name}", out)
            self.assertIn(f"claimset skill install {name}", out)
        code, _, err = run("guide", "nothing")
        self.assertEqual(code, 1)
        self.assertIn("claimset-lab", err)

    def test_help_points_to_it(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as buf:
            main(["--help"])
        self.assertIn("claimset guide", buf.getvalue())

    def test_the_agents_block_carries_the_rules(self):
        block = agents.instructions_block(".agents/skills")
        self.assertIn(RULES, block)
        self.assertNotIn("{rules}", block)


class TestReadme(unittest.TestCase):
    """The README is also the PyPI page."""

    def test_the_rules_are_the_guides(self):
        self.assertIn(RULES, README, "copy agents/RULES.md into README.md, under 'If you are an AI agent'")

    def test_links_work_on_pypi(self):
        relative = [u for u in LINK.findall(README) if not u.startswith(("https://", "http://"))]
        self.assertEqual(relative, [], "PyPI shows the README outside the repository: use full URLs")

    def test_it_names_entrylib_and_the_start(self):
        self.assertIn("https://entrylib.org", README)
        self.assertIn("pip install claimset\nclaimset guide", README)

    def test_the_badges_name_real_things(self):
        for wf in re.findall(r"actions/workflows/([\w.-]+\.yml)/badge\.svg", README):
            self.assertTrue((ROOT / ".github" / "workflows" / wf).exists(), wf)
        for page in re.findall(r"https://github\.com/entrylib/claimset/blob/main/([\w./-]+)", README):
            self.assertTrue((ROOT / page).exists(), page)
        for page in re.findall(r"https://github\.com/entrylib/claimset/tree/main/([\w./-]+)", README):
            self.assertTrue((ROOT / page).is_dir(), page)


class TestDocs(unittest.TestCase):
    def test_relative_links_resolve(self):
        for page in sorted((ROOT / "docs").glob("*.md")) + [ROOT / "CONTRIBUTING.md"]:
            for url in LINK.findall(page.read_text(encoding="utf-8")):
                if url.startswith(("https://", "http://", "#")):
                    continue
                self.assertTrue((page.parent / url.split("#")[0]).exists(), f"{page.name}: {url}")


class TestPythonVersions(unittest.TestCase):
    def test_the_versions_claimed_are_the_versions_tested(self):
        claimed = re.findall(r'"Programming Language :: Python :: (3\.\d+)"',
                             (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        matrix = re.search(r"python-version: \[([^\]]+)\]",
                           (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")).group(1)
        self.assertEqual(claimed, re.findall(r'"(3\.\d+)"', matrix))
        self.assertEqual(claimed[0], re.search(r'requires-python = ">=(3\.\d+)"',
                                               (ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1))


if __name__ == "__main__":
    unittest.main()

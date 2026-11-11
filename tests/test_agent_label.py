"""An agent's label (claimset v0.41 §3.11, as amended on 2026-11-11): rule 93, warning 43, and the page view's icons."""

import copy
import json
import re
import sys
import unittest
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import html  # noqa: E402
from claimset import validate as V  # noqa: E402

NATIVE = json.loads((resources.files("claimset") / "data" / "examples" / "submission-native.json").read_text("utf-8"))


def with_people(**changes):
    """The native example with its agent (P1) and person (P2) changed."""
    d = copy.deepcopy(NATIVE)
    for c in d["contributors"]:
        c.update(changes.get(c["id"], {}))
    return d


def found(d, rule):
    rep = V.validate(d)
    return [x for x in (rep.errors if rule.isdigit() else rep.warnings) if x["rule"] == rule]


class TestLabel(unittest.TestCase):
    def test_rule_93_a_short_label_on_an_agent(self):
        self.assertEqual(found(with_people(P1={"label": "drafting"}), "93"), [])
        self.assertEqual(len(found(with_people(P1={"label": "x" * 61}), "93")), 1)
        self.assertEqual(len(found(with_people(P1={"label": "  "}), "93")), 1)
        self.assertEqual(len(found(with_people(P1={"label": 3}), "93")), 1)
        self.assertEqual(len(found(with_people(P2={"label": "supervision"}), "93")), 1)     # agents only

    def test_warning_43_a_role_in_a_name(self):
        self.assertEqual(found(with_people(P1={"name": "Claude Code", "label": "drafting"}), "W43"), [])
        self.assertEqual(len(found(with_people(P1={"name": "Claude Code (drafting agent)"}), "W43")), 1)
        self.assertEqual(found(with_people(P2={"name": "A. Researcher (Lancaster)"}), "W43"), [])   # people as written

    def test_the_page_view_gives_icons_and_the_label(self):
        header = html.render_parts(with_people(P1={"name": "Claude Code", "label": "drafting"}))["header"]
        authors = re.search(r'<p class="cs-authors">.*?</p>', header, re.S).group(0)
        self.assertIn('aria-label="AI agent"', authors)
        self.assertIn('Claude Code <span class="cs-label">· drafting</span>', authors)
        self.assertNotIn("(AI agent)", header)
        guarantor = re.search(r'<p class="cs-guarantor">.*?</p>', header, re.S).group(0)
        self.assertNotIn("<svg", guarantor)                                     # guarantors are named plainly
        plain = html.render_parts(with_people(P1={"name": "Claude Code"}))["header"]
        self.assertNotIn("cs-label", plain)


if __name__ == "__main__":
    unittest.main()

"""A text holds no control character but a line break (claimset v0.44 as amended on 2026-11-27, §8 rule 6, warning
68): LaTeX written into JSON with one backslash (`\\frac`, `\\theta`) parses without an error as a form feed or a tab
followed by the rest of the name, and the statement shows its formula broken."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))


def warned(d):
    return [w for w in validate(d).warnings if w["rule"] == "W68"]


class TestControlCharacters(unittest.TestCase):
    def test_line_breaks_pass(self):
        d = copy.deepcopy(EXAMPLE)
        d["definitions"][0]["definition"] = "First line\nsecond line\r\nthird.\n\nA new paragraph."
        self.assertEqual(warned(d), [])
        self.assertEqual(warned(copy.deepcopy(EXAMPLE)), [])

    def test_latex_read_as_an_escape(self):
        d = copy.deepcopy(EXAMPLE)
        cid = d["claims"][0]["id"]
        d["claims"][0]["statement"] = "The ratio $\x0crac{a}{b}$ and the angle $\theta$ grow."   # \f and \t read
        w = warned(d)
        self.assertEqual(len(w), 1)                                     # one warning per text
        self.assertEqual(w[0]["where"], f"claims:{cid}.statement")
        self.assertIn("\\frac written into JSON with one backslash", w[0]["message"])
        self.assertEqual(validate(d).errors, [])                       # a warning: the file stays valid

    def test_other_control_characters(self):
        d = copy.deepcopy(EXAMPLE)
        d["paper"]["summary"] = "A summary\twith a tab."
        d["claims"][0]["name"] = "A name\x07 with a bell"
        got = {w["where"]: w["message"] for w in warned(d)}
        self.assertIn("a tab in the text", got["paper.summary"])        # not taken for LaTeX: no \twith
        self.assertIn("U+0007", got[f"claims:{d['claims'][0]['id']}.name"])


if __name__ == "__main__":
    unittest.main()

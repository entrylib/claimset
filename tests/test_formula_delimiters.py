"""Every dollar sign of a text opens or closes a formula (claimset v0.44 as amended on 2026-11-23, §8 rule 6, warning
63): `$$$x$$$` or an unpaired `$` is set as text by every reader that sets mathematics, and nothing had warned."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import stray_dollar, validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))


def warned(d):
    return [w for w in validate(d).warnings if w["rule"] == "W63"]


class TestFormulaDelimiters(unittest.TestCase):
    def test_paired_formulae_pass(self):
        for text in ("A mean $\\mu$ and $$\\sigma^2 = \\mathrm{E}[(y - \\mu)^2]$$ on its own line.",
                     "A price of \\$5 and \\$10.",                        # a dollar sign in prose, escaped
                     "Code `a = $x` and\n```\necho $HOME\n```\nafter.",   # code keeps its own
                     "No formula at all."):
            self.assertIsNone(stray_dollar(text), text)
        d = copy.deepcopy(EXAMPLE)
        self.assertEqual(warned(d), [])

    def test_three_in_a_row_is_warned(self):
        self.assertEqual(stray_dollar("Then $$$x = 1$$$ holds."), "three or more dollar signs in a row")
        d = copy.deepcopy(EXAMPLE)
        d["claims"][0]["statement"] = "The parts are $$$\\mathcal{R} = \\mathcal{I}$$$ for a symmetric law."
        w = warned(d)
        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]["where"], f"claims:{d['claims'][0]['id']}.statement")
        self.assertEqual(validate(d).errors, [])                         # a warning: the file stays valid

    def test_an_unpaired_sign_is_warned(self):
        self.assertEqual(stray_dollar("It costs $5 and $x$ grows."), "a dollar sign without its pair")
        d = copy.deepcopy(EXAMPLE)
        d["paper"]["summary"] = "A price of $5 rises."
        d["definitions"][0]["symbol"] = "$x"
        self.assertEqual({w["where"] for w in warned(d)},
                         {"paper.summary", f"definitions:{d['definitions'][0]['id']}.symbol"})


if __name__ == "__main__":
    unittest.main()

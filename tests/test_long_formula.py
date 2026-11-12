"""Warning 44 (v0.41 as amended on 2026-11-11, §8 rule 6): a formula too long for a sentence. (Kept here when the
page view and its MathML left the package: it tests the validator.)"""

import copy
import json
import sys
import unittest
from importlib import resources
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from claimset import validate as V  # noqa: E402
from claimset.validate import formula_symbols  # noqa: E402


class TestLongInlineFormula(unittest.TestCase):
    """Warning 44 (v0.41 as amended on 2026-11-11, §8 rule 6): a formula too long for a sentence."""

    def warnings(self, statement):
        d = json.loads((resources.files("claimset") / "data" / "examples" / "submission-native.json").read_text())
        d = copy.deepcopy(d)
        d["claims"][0]["statement"] = statement
        return [w for w in V.validate(d).warnings if w["rule"] == "W44"]

    def test_a_long_formula_in_a_sentence(self):
        long = r"$\sum_{O_t=1}\log f(z_t\mid Y_{t-1};\theta)+\sum_{O_t=1}\log p_t+\sum_{O_t=0}\log(1-p_t)$"
        self.assertEqual(len(self.warnings(f"The likelihood is {long}.")), 1)
        self.assertEqual(self.warnings(f"The likelihood is $${long[1:-1]}$$."), [])        # on a line of its own
        self.assertEqual(self.warnings(r"With $\epsilon_t \sim N(0, \sigma^2)$ the errors are normal."), [])

    def test_symbols_as_a_reader_sees_them(self):
        self.assertEqual(formula_symbols(r"\left(x_{t}\right)"), 4)              # ( x t )
        self.assertEqual(formula_symbols(r"\alpha + \beta"), 3)


if __name__ == "__main__":
    unittest.main()

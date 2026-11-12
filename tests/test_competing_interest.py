"""A competing interest is declared once (claimset v0.41 §3.9, as amended on 2026-11-12; warning 45): a limitation that
only restates the declaration is pointed to; one about how the interest bears on particular claims is not."""

import copy
import json
import sys
import unittest
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import restates_interest, validate  # noqa: E402

DOC = json.loads((resources.files("claimset") / "data" / "examples" / "submission-native.json").read_text("utf-8"))
DECLARED = "The author develops the smooth package that this paper evaluates."


def w45(statement, declaration=DECLARED):
    d = copy.deepcopy(DOC)
    d["paper"]["declarations"] = {"funding": [], "competing_interests": declaration}
    d["limitations"][0]["statement"] = statement
    return [w for w in validate(d).warnings if w["rule"] == "W45"]


class TestW45(unittest.TestCase):
    def test_a_restated_declaration_is_pointed_to(self):
        (w,) = w45("The author develops the smooth package evaluated in this paper.")
        self.assertEqual(w["where"], "limitations:L1.statement")
        self.assertEqual(len(w45("A competing interest: the author maintains the package.")), 1)
        self.assertEqual(len(w45("Possible conflict of interest of the authors.")), 1)

    def test_a_limitation_about_how_claims_were_obtained_is_not(self):
        self.assertEqual(w45("Only one retailer's monthly series were used."), [])
        self.assertEqual(w45("The settings of method M were tuned on the same series it was evaluated on."), [])

    def test_without_a_declared_interest_nothing_is_restated(self):
        self.assertEqual(w45("A competing interest.", "None declared."), [])
        self.assertFalse(restates_interest("A competing interest.", None))


if __name__ == "__main__":
    unittest.main()

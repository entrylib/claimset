"""Numbers in statements are written as recorded (claimset v0.44 §8 rule 10, warning 50). From a claimset whose
statements gave test-set sizes as 1,000 and 10,000 while its results held 1000 and 10000; the validator read
"1,000" as two numbers, 1 and 000."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))


def warnings(d, code):
    return [w for w in validate(d).warnings if w["rule"] == code]


def with_statement(text):
    d = copy.deepcopy(NATIVE)
    c = next(c for c in d["claims"] if c.get("support") and any(s.get("kind") in ("empirical_quant", "simulation")
                                                             for s in c["support"]))
    c["statement"] = text
    return d, c


class TestNumbersAsRecorded(unittest.TestCase):
    def test_a_separator_is_flagged(self):
        d, c = with_statement("Over 1,000 series and 10 000 forecasts the error fell.")
        found = warnings(d, "W50")
        self.assertEqual(len(found), 1)
        self.assertIn("'1,000'", found[0]["message"])
        self.assertIn("1000", found[0]["message"])

    def test_numbers_as_recorded_are_not(self):
        d, c = with_statement("Over 1000 series, at levels 0.25, 0.5 and 1, with means 2, 3 and 10, the error fell.")
        self.assertEqual(warnings(d, "W50"), [])

    def test_a_separated_number_is_read_as_one(self):
        from claimset.validate import _numbers_text
        self.assertEqual(_numbers_text("at n = 1,000 and 10 000"), "at n = 1000 and 10000")
        self.assertEqual(_numbers_text("means 2, 3 and 10"), "means 2, 3 and 10")
        self.assertEqual(_numbers_text("between 1,000,000 and 1,234.5"), "between 1000000 and 1234.5")

    def test_a_file_of_v0_43_is_not_warned(self):
        d, c = with_statement("Over 1,000 series the error fell.")
        d["schema_version"] = "0.43"
        self.assertEqual(warnings(d, "W50"), [])


if __name__ == "__main__":
    unittest.main()

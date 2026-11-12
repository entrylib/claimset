"""Warnings 47 and 48 (claimset v0.41, as amended on 2026-11-12): a principal claim says where it holds and what limits
it. From a pilot in which smaller models completed claimsets whose principal claims had no scope and no limitation
(entrylib:2026.000005, C9), and the hand-over list `claimset validate` prints."""

import contextlib
import copy
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import print_report, validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))


def warned(d, rule):
    return [w for w in validate(d).warnings if w["rule"] == rule]


def principal(d):
    return next(c for c in d["claims"] if c.get("role") == "principal")


class TestW47(unittest.TestCase):
    def test_a_principal_claim_with_no_scope(self):
        self.assertEqual(warned(copy.deepcopy(NATIVE), "W47"), [])
        d = copy.deepcopy(NATIVE)
        c = principal(d)
        c.pop("scope", None)
        (w,) = warned(d, "W47")
        self.assertEqual(w["where"], f"claims:{c['id']}.scope")
        c["scope"] = {}
        self.assertEqual(len(warned(d, "W47")), 1)

    def test_other_claims_are_not_asked(self):
        d = copy.deepcopy(NATIVE)
        for c in d["claims"]:
            if c.get("role") != "principal":
                c.pop("scope", None)
        self.assertEqual(warned(d, "W47"), [])


class TestW48(unittest.TestCase):
    def test_a_principal_claim_that_no_limitation_affects(self):
        self.assertEqual(warned(copy.deepcopy(NATIVE), "W48"), [])
        d = copy.deepcopy(NATIVE)
        d["limitations"] = []
        for c in d["claims"]:
            c.pop("limitations", None)
        self.assertEqual([w["where"] for w in warned(d, "W48")], [f"claims:{principal(d)['id']}"])

    def test_a_limitation_of_what_it_rests_on_counts(self):
        d = copy.deepcopy(NATIVE)
        c = principal(d)
        premise = copy.deepcopy(c)
        premise.update(id="C9", role="supporting")
        premise.pop("limitations", None)
        d["claims"].append(premise)
        c.pop("limitations", None)
        c["depends_on"] = ["C9"]
        d["limitations"][0]["affects"] = ["C9"]
        premise["limitations"] = [d["limitations"][0]["id"]]
        self.assertEqual(warned(d, "W48"), [])


class TestHandOverList(unittest.TestCase):
    def test_the_report_lists_what_to_address(self):
        d = copy.deepcopy(NATIVE)
        principal(d).pop("scope", None)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_report(validate(d))
        self.assertIn("Address before hand-over (1)", out.getvalue())
        self.assertIn("[W47] claims:", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_report(validate(copy.deepcopy(NATIVE)))
        self.assertNotIn("Address before hand-over", out.getvalue())


if __name__ == "__main__":
    unittest.main()

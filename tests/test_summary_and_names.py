"""A paper without a summary, and claims without names, are warned (claimset v0.44 as amended on 2026-11-20,
warnings 60 and 61): neither is required, but a reader outside the field starts from the summary, and finds their
way through the claims by their names."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))


def rules(d):
    return [w["rule"] for w in validate(d).warnings]


def named(d):
    for c in d["claims"]:
        c.setdefault("name", f"Claim {c['id']} in a few words")
    d["paper"].setdefault("summary", "What the paper asked and found, in plain words.")
    return d


class TestSummaryAndNames(unittest.TestCase):
    def test_a_paper_with_both_is_not_warned(self):
        d = named(copy.deepcopy(EXAMPLE))
        self.assertNotIn("W60", rules(d))
        self.assertNotIn("W61", rules(d))
        self.assertEqual(validate(d).errors, [])

    def test_no_summary_is_warned_not_refused(self):
        d = named(copy.deepcopy(EXAMPLE))
        d["paper"].pop("summary")
        r = validate(d)
        self.assertEqual(r.errors, [])
        self.assertIn("W60", [w["rule"] for w in r.warnings])

    def test_claims_without_names_are_listed_in_one_warning(self):
        d = named(copy.deepcopy(EXAMPLE))
        found = [c for c in d["claims"] if any(s.get("kind") != "assumption" for s in c["support"])][:2]
        ids = [c["id"] for c in found]
        for c in found:
            c.pop("name")
        r = validate(d)
        self.assertEqual(r.errors, [])
        (w,) = [w for w in r.warnings if w["rule"] == "W61"]
        for cid in ids:
            self.assertIn(cid, w["message"])

    def test_assumptions_need_no_name(self):
        d = named(copy.deepcopy(EXAMPLE))
        d["claims"].append({"id": "C99", "statement": "The series are independent.", "type": "formal",
                            "role": "supporting", "support": [{"kind": "assumption"}],
                            "assumption_category": "theorem_condition", "check": "untestable",
                            "provenance": "author_stated"})
        self.assertNotIn("W61", rules(d))

    def test_an_empty_name_is_still_an_error(self):
        d = named(copy.deepcopy(EXAMPLE))
        d["claims"][0]["name"] = " "
        self.assertIn("101", [e["rule"] for e in validate(d).errors])


if __name__ == "__main__":
    unittest.main()

"""Planned estimates (claimset v0.42 §3.3.3, rules 95 and 96) and the test flag diagnostic_missing. From a pilot in
which agents that had planned estimates could record them only as hypotheses with an invented threshold, or as
exploratory results (entrylib:2026.000005)."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.migrate import migrate  # noqa: E402
from claimset.render import render  # noqa: E402
from claimset.validate import validate  # noqa: E402

LAB_EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))
VARIABLE = "mean relative MASE reduction, method M vs seasonal naive"


def estimate_doc():
    """The lab example with its weekly test (C4) reported as a planned estimate of the interval's ends."""
    d = copy.deepcopy(LAB_EXAMPLE)
    c = next(c for c in d["claims"] if c["id"] == "C4")
    for f in ("hypothesis", "test"):
        c.pop(f)
    c["statement"] = ("On the 900 [[D5:UK weekly retail sales]] series, [[D2:Method M]] changed the "
                      "[[D1:mean absolute scaled error]] of the [[D3:seasonal naive method]] by a mean relative "
                      "reduction of -0.004.")
    c["planning"] = "planned_estimate"
    c["estimate"] = {"estimands": {"lower": {"variable": VARIABLE, "conditions": {"frequency": "weekly"},
                                             "field": "interval.lower"},
                                   "d": {"variable": VARIABLE, "conditions": {"frequency": "weekly"}}},
                     "runs": 1, "lab_plan": "PL4"}
    return d


def claim(d, cid="C4"):
    return next(c for c in d["claims"] if c["id"] == cid)


def errors(d, rule=None, published=False):
    found = validate(d, published=published).errors
    return [e for e in found if rule is None or e["rule"] == rule]


class TestPlannedEstimate(unittest.TestCase):
    def test_a_planned_estimate_is_valid(self):
        self.assertEqual(errors(estimate_doc()), [])

    def test_it_needs_its_estimate_and_its_plan(self):
        d = estimate_doc()
        claim(d).pop("estimate")
        self.assertTrue(errors(d, "95"))
        d = estimate_doc()
        claim(d)["estimate"].pop("lab_plan")
        self.assertTrue(errors(d, "95"))
        d = estimate_doc()
        claim(d).pop("planned_at")
        self.assertTrue(errors(d, "95"))
        d = estimate_doc()
        claim(d)["estimate"]["estimands"] = {}
        self.assertTrue(errors(d, "95"))

    def test_it_tests_no_hypothesis(self):
        d = estimate_doc()
        claim(d)["hypothesis"] = {"lab_event": "H3", "outcome": "inconclusive"}
        self.assertTrue(errors(d, "95"))
        d = estimate_doc()
        claim(d)["test"] = copy.deepcopy(claim(LAB_EXAMPLE)["test"])
        self.assertTrue(errors(d, "95"))

    def test_only_a_planned_estimate_has_an_estimate(self):
        d = estimate_doc()
        claim(d)["planning"] = "exploratory"
        self.assertTrue(errors(d, "95"))

    def test_its_fields(self):
        for bad in ({"runs": 0}, {"flags": ["looked_twice"]}, {"not_obtained": ["nothing"]}, {"verdict": "computed"}):
            d = estimate_doc()
            claim(d)["estimate"].update(bad)
            self.assertTrue(errors(d, "95"), bad)
        d = estimate_doc()
        claim(d)["estimate"]["flags"] = ["diagnostic_missing"]
        self.assertEqual(errors(d), [])


class TestEstimandsBind(unittest.TestCase):
    def test_an_estimand_that_binds_nothing(self):
        d = estimate_doc()
        claim(d)["estimate"]["estimands"]["d"]["conditions"] = {"frequency": "daily"}
        found = errors(d, "96")
        self.assertEqual(len(found), 1)
        self.assertIn("not_obtained", found[0]["message"])

    def test_one_not_obtained_binds_nothing(self):
        d = estimate_doc()
        claim(d)["estimate"]["estimands"]["d"]["conditions"] = {"frequency": "daily"}
        claim(d)["estimate"]["not_obtained"] = ["d"]
        self.assertEqual(errors(d), [])
        claim(d)["estimate"]["not_obtained"] = ["lower"]
        self.assertTrue(errors(d, "96"))           # lower binds, and d still binds nothing

    def test_an_estimand_that_binds_several(self):
        d = estimate_doc()
        ev = next(e for e in d["evidence"] if e["id"] == "E2")
        extra = copy.deepcopy(ev["results"][0])
        extra.update(id="R2", conditions={"frequency": "weekly", "subset": "long series"})
        ev["results"].append(extra)
        self.assertIn("binds 2", errors(d, "96")[0]["message"])

    def test_an_estimand_reads_a_number(self):
        d = estimate_doc()
        claim(d)["estimate"]["estimands"]["d"]["field"] = "value.limit"
        self.assertTrue(errors(d, "96"))

    def test_an_estimand_is_well_formed(self):
        d = estimate_doc()
        claim(d)["estimate"]["estimands"]["d"] = {"quantity": VARIABLE}
        self.assertTrue(errors(d, "96"))


class TestAroundIt(unittest.TestCase):
    def test_an_unanchored_plan_is_flagged(self):
        r = validate(estimate_doc())
        self.assertIn("unanchored_plan", r.computed["C4"]["verifiability_flags"])

    def test_a_test_may_be_flagged_diagnostic_missing(self):
        d = copy.deepcopy(LAB_EXAMPLE)
        claim(d)["test"]["flags"] = ["diagnostic_missing"]
        self.assertEqual(errors(d), [])

    def test_earlier_versions_have_neither(self):
        d = estimate_doc()
        d["schema_version"] = "0.41"
        self.assertTrue(errors(d, "42"))
        d = copy.deepcopy(LAB_EXAMPLE)
        d["schema_version"] = "0.41"
        claim(d)["test"]["flags"] = ["diagnostic_missing"]
        self.assertTrue(errors(d, "47"))

    def test_the_reading_view_shows_it(self):
        text = render(estimate_doc())
        self.assertIn("planned estimate: lower = " + VARIABLE, text)
        self.assertIn("plan: lab plan PL4", text)

    def test_migrate_from_0_41(self):
        d = copy.deepcopy(LAB_EXAMPLE)
        d["schema_version"] = "0.41"
        out, done, _todo = migrate(d)
        self.assertEqual(out["schema_version"], "0.42")
        self.assertIn("schema_version 0.41 -> 0.42", done)


if __name__ == "__main__":
    unittest.main()

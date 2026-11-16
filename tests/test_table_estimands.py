"""Table estimands (claimset v0.44 §3.3.3, rule 96 revised; lab record §5.7.8 and §9, as amended on 2026-11-16): a
planned estimate may fix a grid of values, one per setting, and report them all. From a simulation study whose
estimands each named a variable without the conditions that pick one value: export reported them as not obtained,
though the runs had given them all, and the validator refused that (study measure-rankings, plan PL1.R4)."""

import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from claimset.lab.export import check, export
from claimset.migrate import migrate
from claimset.render import render
from claimset.validate import validate

from test_lab_export import ExportCase
from test_planned_estimates import VARIABLE, claim, errors, estimate_doc

GRID = """
import json, os, sys
json.dump([{"variable": "share chosen", "value": v, "conditions": {"size": n}}
           for n, v in ((10, 0.4), (100, 0.7), (1000, 0.95))], open(os.environ["CLAIMSET_RESULTS"], "w"))
"""


class TestTheValidator(unittest.TestCase):
    def table_doc(self):
        d = estimate_doc()                          # the lab example: E1 holds the monthly value, E2 the weekly one
        claim(d)["estimate"]["estimands"] = {"d": {"variable": VARIABLE, "table": True}}
        claim(d)["support"].append({"kind": "empirical_quant", "evidence": "E1", "results": ["E1.R1"]})
        return d

    def test_a_table_estimand_binds_every_value(self):
        self.assertEqual(errors(self.table_doc()), [])

    def test_without_table_it_must_pick_one(self):
        d = self.table_doc()
        claim(d)["estimate"]["estimands"]["d"].pop("table")
        found = errors(d, "96")
        self.assertTrue(found)
        self.assertIn("table estimand", found[0]["message"])

    def test_a_table_estimand_binds_at_least_one(self):
        d = self.table_doc()
        claim(d)["estimate"]["estimands"]["d"]["conditions"] = {"frequency": "daily"}
        self.assertTrue(errors(d, "96"))

    def test_table_is_a_boolean(self):
        d = self.table_doc()
        claim(d)["estimate"]["estimands"]["d"]["table"] = "yes"
        self.assertTrue(errors(d, "96"))

    def test_not_obtained_still_binds_nothing(self):
        d = self.table_doc()
        claim(d)["estimate"]["not_obtained"] = ["d"]
        self.assertIn("matches 2 observations", errors(d, "96")[0]["message"])

    def test_a_file_of_v0_43_keeps_its_rules(self):
        d = self.table_doc()
        d["schema_version"] = "0.43"
        self.assertTrue(errors(d, "96"))                       # table is not a key of v0.43

    def test_the_reading_view_says_so(self):
        self.assertIn("(table: every value)", render(self.table_doc()))

    def test_migrate_lists_estimands_that_match_several(self):
        d = estimate_doc()
        d["schema_version"] = "0.43"
        claim(d)["estimate"]["estimands"] = {"d": {"variable": VARIABLE}}
        claim(d)["support"].append({"kind": "empirical_quant", "evidence": "E1", "results": ["E1.R1"]})
        out, _done, todo = migrate(d)
        self.assertEqual(out["schema_version"], "0.44")
        self.assertTrue(any("estimands.d matches 2 observations" in t and "table" in t for t in todo), todo)


class TestTheLab(ExportCase):
    def setUp(self):
        super().setUp()
        self.script.write_text(GRID)

    def estimation(self, estimands):
        return self.add("plan", {"kind": "estimation", "question": self.q, "design": "a grid of sizes",
                                 "analysis": "the share at each size", "estimands": estimands})

    def test_an_estimand_matching_several_results_is_exported_as_a_table(self):
        pl = self.estimation({"share": {"variable": "share chosen"}, "first": {"variable": "share chosen",
                                                                               "conditions": {"size": 10}}})
        self.run_("0", "x", plan=pl)
        out = export(self.lab)
        c = next(c for c in out["draft"]["claims"] if c.get("planning") == "planned_estimate")
        self.assertEqual(c["estimate"]["estimands"]["share"].get("table"), True)
        self.assertNotIn("table", c["estimate"]["estimands"]["first"])
        self.assertNotIn("not_obtained", c["estimate"])
        self.assertIn("a table of 3 values, from 0.4 to 0.95", c["statement"])
        self.assertIn("was 0.4", c["statement"])
        self.assertTrue(any("table estimand" in t["what"] for t in out["completion"]))
        draft = out["draft"]
        draft["paper"]["licence"] = "CC-BY-4.0"
        next(x for x in draft["contributors"] if x["type"] == "human")["positions"] = ["supervisor", "guarantor"]
        c["role"] = "principal"
        c["about"] = {"subject": "X", "relation": "chosen at", "object": "Y", "comparator": None, "conditions": []}
        c["scope"] = {"conditions": ["the grid"]}
        draft["paper"]["contributions"] = [c["id"]]
        self.assertEqual([e for e in validate(draft).errors if e["rule"] == "96"], [])
        self.assertEqual(check(self.lab, draft), [])

    def test_a_plan_says_what_an_estimand_without_conditions_will_bind(self):
        from claimset.cli import main
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["lab", "plan", "--lab", str(self.lab.root), "--kind", "estimation", "--question", self.q,
                         "--design", "d", "--analysis", "a", "--estimand", "share=share chosen", "--by", self.agent])
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn("estimand share names no conditions", err.getvalue())
        self.assertIn('"table": true', err.getvalue())

    def test_a_marked_table_estimand_is_accepted_by_the_record(self):
        pl = self.estimation({"share": {"variable": "share chosen", "table": True}})
        self.run_("0", "x", plan=pl)
        c = next(c for c in export(self.lab)["draft"]["claims"] if c.get("planning") == "planned_estimate")
        self.assertTrue(c["estimate"]["estimands"]["share"]["table"])


if __name__ == "__main__":
    unittest.main()

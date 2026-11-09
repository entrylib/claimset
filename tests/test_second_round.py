"""Core additions from the second round of field trials (spec v0.39): statistics and approximate values (rule 87),
units and targets of definitions and the kind process (rule 88), and their reading view."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.render import render  # noqa: E402
from claimset.validate import ENUM, validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))


def doc():
    return copy.deepcopy(NATIVE)


def rules(report):
    return sorted({e["rule"] for e in report.errors})


def defn(d, did):
    return next(x for x in d["definitions"] if x["id"] == did)


def with_result(**extra):
    d = doc()
    res = {"id": "R1", "variable": "D1", "value": 1.5, "conditions": {"comparator": "D3"}}
    res.update(extra)
    d["evidence"][0]["results"] = [res]
    return d


class TestRule87(unittest.TestCase):
    def test_statistic_and_approximate_on_results(self):
        d = with_result(statistic="ratio", approximate=True)
        self.assertEqual(validate(d).errors, [])
        self.assertIn("E1.R1 D1 (ratio) = about 1.5", render(d))
        for bad in ({"statistic": "Cohen's d"}, {"statistic": ["mean"]}, {"approximate": False},
                    {"approximate": "yes"}):
            self.assertEqual(rules(validate(with_result(**bad))), ["87"], bad)

    def test_on_table_columns(self):
        d = doc()
        d["evidence"][0]["tables"] = [{"id": "T1", "description": "Half-times relative to mock", "row_labels": ["kd"],
                                       "columns": [{"variable": "half-time", "statistic": "ratio", "approximate": True}],
                                       "rows": [{"id": "r1", "label": ["RAC2"], "values": [2.0]}]}]
        self.assertEqual(validate(d).errors, [])
        d["evidence"][0]["tables"][0]["columns"][0]["statistic"] = "fold change"
        self.assertEqual(rules(validate(d)), ["87"])

    def test_the_list(self):
        self.assertIn("standardised_mean_difference", ENUM["statistic"])
        self.assertIn("nnt", ENUM["statistic"])


def warnings(report):
    return sorted({w["rule"] for w in report.warnings})


def with_table(columns, rows):
    d = doc()
    d["evidence"][0]["tables"] = [{"id": "T1", "description": "Errors of two methods", "row_labels": ["method"],
                                   "columns": columns, "rows": rows}]
    return d


class TestRule87Families(unittest.TestCase):
    """Rule 87 as amended on 2026-11-09: statistics as families with parameters, other, and statistics on rows."""

    GOOD = ["sd", "mad", {"name": "mean"}, {"name": "mean", "kind": "geometric"},
            {"name": "mean", "kind": "trimmed", "trim": 0.1}, {"name": "quantile", "probability": 0.9},
            {"name": "expectile", "probability": 0.95}, {"name": "moment", "order": 3, "central": True},
            {"name": "kurtosis", "excess": True}, {"name": "skewness"}, {"name": "ratio", "label": "fold change"},
            {"name": "other", "label": "Theil's U2"}]
    BAD = ["geometric_mean", "other", {"kind": "geometric"}, {"name": "mean", "kind": "log"},
           {"name": "mean", "trim": 0.1}, {"name": "mean", "kind": "trimmed", "trim": 0.5},
           {"name": "quantile"}, {"name": "quantile", "probability": 1}, {"name": "expectile", "probability": "0.9"},
           {"name": "median", "probability": 0.5}, {"name": "moment"}, {"name": "moment", "order": 0},
           {"name": "moment", "order": 2, "central": "yes"}, {"name": "kurtosis", "excess": 1},
           {"name": "other"}, {"name": "other", "label": " "}, {"name": "sd", "kind": "geometric"}]

    def test_valid_statistics(self):
        for st in self.GOOD:
            self.assertEqual(validate(with_result(statistic=st)).errors, [], st)

    def test_broken_statistics(self):
        for st in self.BAD:
            self.assertEqual(rules(validate(with_result(statistic=st))), ["87"], st)

    def test_the_new_names(self):
        for name in ("sum", "mode", "expectile", "min", "max", "sd", "variance", "iqr", "mad",
                     "coefficient_of_variation", "skewness", "kurtosis", "moment", "other"):
            self.assertIn(name, ENUM["statistic"])

    def test_other_warns(self):
        r = validate(with_result(statistic={"name": "other", "label": "Theil's U2"}))
        self.assertEqual(r.errors, [])
        self.assertIn("W38", warnings(r))
        self.assertNotIn("W38", warnings(validate(with_result(statistic={"name": "mean", "kind": "geometric"}))))
        cols = [{"variable": "MASE", "statistic": {"name": "other", "label": "winsorised median"}}]
        self.assertIn("W38", warnings(validate(with_table(cols, [{"id": "r1", "label": ["A"], "values": [1.0]}]))))

    def test_statistics_on_rows(self):
        rows = [{"id": "r1", "label": ["A"], "values": [0.9, 1.1], "statistic": "mean"},
                {"id": "r2", "label": ["A"], "values": [0.8, 1.0], "statistic": "median"},
                {"id": "r3", "label": ["A"], "values": [0.7, 0.9],
                 "statistic": {"name": "quantile", "probability": 0.9}, "approximate": True}]
        d = with_table(["MASE", "RMSSE"], rows)
        self.assertEqual(validate(d).errors, [])
        view = render(d)
        self.assertIn("| r1 (mean) | A | 0.9 | 1.1 |", view)
        self.assertIn("| r3 (quantile 0.9, approximate) | A |", view)
        rows[1]["statistic"] = "geometric mean"
        self.assertEqual(rules(validate(with_table(["MASE", "RMSSE"], rows))), ["87"])

    def test_not_on_both_row_and_column(self):
        cols = [{"variable": "MASE", "statistic": "mean"}, "RMSSE"]
        rows = [{"id": "r1", "label": ["A"], "values": [0.9, 1.1], "statistic": "median"}]
        self.assertEqual(rules(validate(with_table(cols, rows))), ["87"])
        rows[0].pop("statistic")
        self.assertEqual(validate(with_table(cols, rows)).errors, [])

    def test_columns_differing_only_by_statistic_are_distinct(self):
        cols = [{"variable": "MASE", "statistic": {"name": "mean", "kind": "geometric"}},
                {"variable": "MASE", "statistic": "median"}]
        d = with_table(cols, [{"id": "r1", "label": ["A"], "values": [0.9, 0.8]}])
        self.assertEqual(validate(d).errors, [])
        self.assertIn("| row | method | MASE (geometric mean) | MASE (median) |", render(d))

    def test_reading_view_of_parameters(self):
        for st, text in ((({"name": "mean", "kind": "trimmed", "trim": 0.1}), "D1 (trimmed mean (10% each tail))"),
                         ({"name": "moment", "order": 3, "central": True}, "D1 (3rd central moment)"),
                         ({"name": "kurtosis", "excess": True}, "D1 (excess kurtosis)"),
                         ({"name": "other", "label": "Theil's U2"}, "D1 (Theil's U2)")):
            self.assertIn(f"E1.R1 {text} = 1.5", render(with_result(statistic=st)))


class TestRule88(unittest.TestCase):
    def test_unit(self):
        d = doc()
        defn(d, "D1")["unit"] = "1"
        self.assertEqual(validate(d).errors, [])
        self.assertIn("[unit 1]", render(d))
        defn(d, "D1")["unit"] = ""
        self.assertEqual(rules(validate(d)), ["88"])
        d = doc()
        defn(d, "D2")["unit"] = "GeV"                       # a method has no unit
        self.assertEqual(rules(validate(d)), ["88"])

    def test_targets_and_process(self):
        d = doc()
        d["definitions"] += [
            {"id": "D9", "term": "knockdown of RAC2", "kind": "intervention", "definition": "siRNA against RAC2.",
             "targets": ["D10"]},
            {"id": "D10", "term": "RAC2", "kind": "entity", "definition": "The gene RAC2."},
            {"id": "D11", "term": "1,5-hydrogen atom transfer", "kind": "process", "definition": "A radical step."}]
        self.assertEqual(validate(d).errors, [])
        self.assertIn("[targets D10]", render(d))
        defn(d, "D9")["targets"] = ["D10", "D11"]             # a process may be targeted too
        self.assertEqual(validate(d).errors, [])
        defn(d, "D9")["targets"] = ["D2"]                     # a method is not a target
        self.assertEqual(rules(validate(d)), ["88"])
        defn(d, "D9")["targets"] = []
        self.assertEqual(rules(validate(d)), ["88"])
        d2 = copy.deepcopy(d)
        defn(d2, "D9")["targets"] = ["D10"]
        defn(d2, "D10")["targets"] = ["D11"]                  # only an intervention targets
        self.assertEqual(rules(validate(d2)), ["88"])


if __name__ == "__main__":
    unittest.main()

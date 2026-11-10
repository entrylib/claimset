"""What a computed test's quantities bind (claimset v0.41 §3.3.3, rules 91 and 92; v0.40 as amended on 2026-11-11,
warnings 41 and 42): result entries and table cells, the outcome the rules give on them, and rebinding."""

import copy
import json
import sys
import unittest
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import validate as V  # noqa: E402
from claimset.lab import decision  # noqa: E402
from claimset.migrate import migrate  # noqa: E402

LAB = json.loads((resources.files("claimset") / "data" / "examples" / "submission-from-lab.json").read_text("utf-8"))
# E1.T1 of the example: mean MASE by horizon (columns 1-3, 4-6, 7-12), rows r1 = D2 (method M), r2 = D3 (naive)


def cell(method, horizon="1-3", **extra):
    return dict({"variable": "D1", "conditions": {"method": method, "horizon": horizon}}, **extra)


def doc(quantities, supported="m < n", not_supported="m >= n", outcome="supported", table=None, version=None):
    """The example with claim C2's test on E1's table: `m` and `n` are method M's and the naive method's MASE."""
    d = copy.deepcopy(LAB)
    if version:
        d["schema_version"] = version
    c2 = next(c for c in d["claims"] if c["id"] == "C2")
    c2["test"].update(quantities=quantities, supported=supported, not_supported=not_supported)
    c2["hypothesis"]["outcome"] = outcome
    if table:
        table(d["evidence"][0]["tables"][0])
    return d


def found(d, rule):
    rep = V.validate(d)
    return [x for x in (rep.errors if rule.isdigit() else rep.warnings) if x["rule"] == rule]


class TestBinding(unittest.TestCase):
    def test_a_a_quantity_bound_to_a_table_cell(self):
        d = doc({"m": cell("D2"), "n": cell("D3")})
        self.assertEqual((found(d, "91"), found(d, "92"), found(d, "W41")), ([], [], []))
        obs = V.bindable(d["evidence"][0])
        hit = V.bind_quantity(cell("D3", "7-12"), obs)
        self.assertEqual([(h["where"], h["observation"]["value"]) for h in hit], [("E1.T1.r2", 1.031)])

    def test_b_an_unbound_quantity_under_a_conclusive_outcome(self):
        d = doc({"m": cell("D2"), "n": {"variable": "mean MASE", "conditions": {"method": "naive"}}})
        (e,) = found(d, "91")
        self.assertIn("1 of 2 quantities bind no observation of E1 (n)", e["message"])
        self.assertEqual(found(d, "92"), [])                    # nothing to evaluate without every value

    def test_c_an_unbound_quantity_under_an_inconclusive_outcome(self):
        d = doc({"m": cell("D2"), "n": {"variable": "mean MASE", "conditions": {"method": "naive"}}},
                outcome="inconclusive")
        self.assertEqual(found(d, "91"), [])
        self.assertIn("may rest on no value", found(d, "W41")[0]["message"])

    def test_d_an_ambiguous_binding(self):
        d = doc({"m": {"variable": "D1", "conditions": {"method": "D2"}}, "n": cell("D3")})
        (e,) = found(d, "91")
        self.assertIn("binds 3 observations (E1.T1.r1), not exactly one: give the conditions", e["message"])

    def test_e_an_outcome_the_rules_do_not_give(self):
        d = doc({"m": cell("D2"), "n": cell("D3")}, supported="m > n", not_supported="m <= n")
        (e,) = found(d, "92")
        self.assertIn("the rules give not_supported on the bound values (m = 0.8412, n = 0.9206), not supported",
                      e["message"])
        self.assertEqual(found(doc({"m": cell("D2"), "n": cell("D3")}, supported="m < n and n < m",
                                   not_supported="m > n and n > m", outcome="inconclusive"), "92"), [])
        self.assertEqual(len(found(doc({"m": cell("D2"), "n": cell("D3")}, supported="m < q"), "92")), 1)

    def test_columns_that_differ_only_by_statistic(self):
        def medians(t):
            t["columns"].append({"variable": "D1", "conditions": {"horizon": "1-3"}, "statistic": "median"})
            t["rows"][0]["values"].append(0.8)
            t["rows"][1]["values"].append(0.9)
        d = doc({"m": cell("D2"), "n": cell("D3")}, table=medians)
        self.assertIn("which differ by statistic", found(d, "91")[0]["message"])
        for st in ("mean", {"name": "mean"}):
            d = doc({"m": cell("D2", statistic=st), "n": cell("D3", statistic="mean")}, table=medians)
            self.assertEqual((found(d, "91"), found(d, "92")), ([], []), st)
        d = doc({"m": cell("D2", statistic="median"), "n": cell("D3", statistic="median")}, table=medians,
                supported="m > n", not_supported="m <= n", outcome="not_supported")
        self.assertEqual((found(d, "91"), found(d, "92")), ([], []))
        d = doc({"m": cell("D2", statistic="average"), "n": cell("D3", statistic="mean")}, table=medians)
        self.assertTrue(any(e["where"].endswith("m.statistic") for e in found(d, "91")))

    def test_a_field_a_cell_does_not_have(self):
        d = doc({"m": cell("D2", field="interval.lower"), "n": cell("D3")})
        self.assertIn("which has no number at interval.lower", found(d, "91")[0]["message"])

    def test_the_run_picks_its_rows(self):
        def two_runs(t):
            t["row_labels"].append("run")
            t["rows"][0]["label"].append("RN31")
            t["rows"][1]["label"].append("RN31")
            t["rows"].append({"id": "r3", "label": ["D2", "RN32"], "values": [0.95, 0.96, 0.97]})
        q = {"m": cell("D2", run=2), "n": cell("D3", run=1)}
        d = doc(q, supported="m > n", not_supported="m <= n", table=two_runs)
        self.assertEqual((found(d, "91"), found(d, "92")), ([], []))         # 0.95 > 0.9206
        q = {"m": cell("D2"), "n": cell("D3", run=1)}
        self.assertIn("binds 2 observations", found(doc(q, table=two_runs), "91")[0]["message"])

    def test_result_entries_still_bind(self):
        self.assertEqual((found(copy.deepcopy(LAB), "91"), found(copy.deepcopy(LAB), "92")), ([], []))


class TestEarlierVersions(unittest.TestCase):
    def test_v040_files_are_warned_not_refused(self):
        d = doc({"m": cell("D2"), "n": {"variable": "mean MASE", "conditions": {"method": "naive"}}},
                version="0.40")
        self.assertEqual((found(d, "91"), len(found(d, "W41"))), ([], 1))
        d = doc({"m": cell("D2"), "n": cell("D3")}, supported="m > n", not_supported="m <= n", version="0.40")
        self.assertEqual((found(d, "92"), len(found(d, "W42"))), ([], 1))

    def test_v039_files_keep_their_rules(self):
        d = json.loads((ROOT / "tests" / "compat" / "0.39" / "submission-from-lab.json").read_text())
        c2 = next(c for c in d["claims"] if c["id"] == "C2")
        c2["test"]["quantities"]["lower"]["variable"] = "gone"
        rep = V.validate(d)
        self.assertEqual([x for x in rep.errors + rep.warnings if x["rule"] in ("91", "92", "W41", "W42")], [])

    def test_migrate_lists_the_quantities_to_rebind(self):
        d = doc({"m": cell("D2"), "n": {"variable": "mean MASE", "conditions": {"method": "naive"}}},
                version="0.40")
        _, _, todo = migrate(d)
        self.assertEqual([t for t in todo if "rule 91" in t],
                         ["C2.test.quantities.n: binds 0 observations of E1; name the result entry or table cell its "
                          "value was computed from, by its variable and conditions (rule 91)"])


class TestOneEvaluator(unittest.TestCase):
    def test_the_lab_evaluates_with_the_claimsets_functions(self):
        self.assertIs(decision.parse, V.parse_rule)
        self.assertIs(decision.RuleError, V.RuleError)
        self.assertIs(decision.read_field, V.read_field)
        rule = {"framework": "deterministic", "quantities": {"q": {"variable": "x"}}, "supported": "q > 0",
                "not_supported": "q < 0"}
        self.assertEqual(decision.verdict(rule, [{"variable": "x", "value": 0.5}])["verdict"], "supported")
        self.assertEqual(V.rule_outcome(rule, {"q": 0.5}), "supported")


if __name__ == "__main__":
    unittest.main()

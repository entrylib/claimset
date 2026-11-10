"""Results as tables in an exported claimset (lab record §9; claimset §3.4, *Tables are the standard form*): the
grouping, the CSV of every result, row citations, rounding, and results a status leaves out."""

import csv
import io
import json
import sys
import unittest
from pathlib import Path

from claimset.lab import tables
from claimset.lab.export import export
from claimset.lab.run import run_command

from test_lab import PlanRunCase, TestCli
from test_lab_export import validate

# The fifteen numbers of evidence E12 of entrylib:2026.000001 v1, as its run wrote them
E12 = {"adam_select": {"m4 cov80": 0.7460771604938237, "m4 mce": 0.02235705823668769,
                       "m4 pinball_median": 0.7513877422626215, "m4 cov80_low": 0.7865370370370371,
                       "m4 cov80_mid": 0.7424537037037038, "m4 cov80_high": 0.7092407407407407,
                       "m4 spread": 0.07729629629629642, "m4 share_dlnorm": 0.6702222222222223},
       "msarima": {"m4 cov80": 0.6922623456790093, "m4 mce": 0.035202331961592524,
                   "m4 pinball_median": 0.6871656664671391, "m4 cov80_low": 0.8192685185185186,
                   "m4 cov80_mid": 0.7097777777777778, "m4 cov80_high": 0.5477407407407408,
                   "m4 spread": 0.2715277777777778}}

SCRIPT = f"""
import json, os
E12 = {E12!r}
json.dump([{{"variable": v, "value": x, "conditions": {{"method": m}}}} for m, vals in E12.items() for v, x in vals.items()],
          open(os.environ["CLAIMSET_RESULTS"], "w"))
"""

DECISION = {"framework": "deterministic",
            "quantities": {"ms": {"variable": "m4 mce", "conditions": {"method": "adam_select"}},
                           "ma": {"variable": "m4 mce", "conditions": {"method": "msarima"}},
                           "ss": {"variable": "m4 spread", "conditions": {"method": "adam_select"}}},
            "supported": "ms <= 0.6*ma and ss <= 0.08", "not_supported": "ms > 0.6*ma or ss > 0.08"}


def events(rows, run="RN1"):
    """Result events from (variable, value, conditions[, extra]) rows."""
    out = []
    for i, row in enumerate(rows):
        body = {"variable": row[0], "value": row[1], "conditions": row[2], "run": run}
        if len(row) > 3:
            body.update(row[3])
        out.append({"id": f"RS{i + 1}", "seq": i, "body": body})
    return out


class TestTabulate(unittest.TestCase):
    def e12(self):
        return events([(v, x, {"method": m}) for m, vals in E12.items() for v, x in vals.items()])

    def test_e12_is_one_table(self):
        tbs, results, refs = tables.tabulate(self.e12(), "E12", "A10")
        self.assertEqual(results, [])
        self.assertEqual(len(tbs), 1)
        t = tbs[0]
        self.assertEqual((t["row_labels"], [r["label"] for r in t["rows"]]), (["method"], [["adam_select"],
                                                                                         ["msarima"]]))
        self.assertEqual(t["columns"], list(E12["adam_select"]))
        self.assertEqual(t["rows"][1]["values"][-1], None)                     # msarima has no share_dlnorm
        self.assertEqual(t["artefact"], "A10")
        self.assertEqual(refs["RS2"], "E12.T1.r1")
        self.assertEqual(refs["RS15"], "E12.T1.r2")

    def test_shared_and_column_conditions(self):
        rows = []
        for m in ("M", "N"):
            for level in (0.8, 0.95):
                rows.append(("coverage", 0.5, {"method": m, "data": "M4", "nominal level": level}))
            rows.append(("MASE", 1.1, {"method": m, "data": "M4", "statistic": "median"}))
        (t,), results, _ = tables.tabulate(events(rows), "E1")
        self.assertEqual(t["conditions"], {"data": "M4"})                       # shared by every value
        self.assertEqual(t["row_labels"], ["method"])
        self.assertEqual(t["columns"], [{"variable": "coverage", "conditions": {"nominal level": 0.8}},
                                        {"variable": "coverage", "conditions": {"nominal level": 0.95}},
                                        {"variable": "MASE", "statistic": "median"}])

    def test_what_stays_a_result(self):
        rows = [("headline", 0.3, {}),
                ("a", 1.0, {"method": "M"}, {"interval": {"level": 0.95, "lower": 0.9, "upper": 1.1}}),
                ("a", 2.0, {"method": "N"}),
                ("quote", {"text": "words", "locator": "p. 3"}, {"method": "M"})]
        tbs, results, refs = tables.tabulate(events(rows), "E1")
        self.assertEqual(tbs, [])                       # each group would hold one value
        self.assertEqual([r["variable"] for r in results], ["headline", "a", "a", "quote"])
        self.assertEqual(results[1]["interval"]["level"], 0.95)
        self.assertEqual(refs["RS1"], "E1.R1")

    def test_several_runs_in_one_cell(self):
        evs = events([("x", 1.0, {"method": "M"}), ("x", 2.0, {"method": "N"})], run="RN1") + \
            [dict(e, id=e["id"] + "b", seq=e["seq"] + 10, body=dict(e["body"], run="RN2"))
             for e in events([("x", 3.0, {"method": "M"}), ("x", 4.0, {"method": "N"})])]
        (t,), _, _ = tables.tabulate(evs, "E1")
        self.assertEqual(t["row_labels"], ["method", "run"])
        self.assertEqual([r["label"] for r in t["rows"]], [["M", "RN1"], ["N", "RN1"], ["M", "RN2"], ["N", "RN2"]])

    def test_rounding_and_csv(self):
        self.assertEqual(tables.rounded(0.7460771604938237), 0.7461)
        self.assertEqual(tables.rounded(12345.678), 12350.0)
        self.assertEqual((tables.rounded(3), tables.rounded(True), tables.rounded("a")), (3, True, "a"))
        rows = list(csv.reader(io.StringIO(tables.csv_text(self.e12()))))
        self.assertEqual(rows[0], ["lab_result", "run", "quantity", "conditions", "value"])
        self.assertEqual(rows[1], ["RS1", "RN1", "m4 cov80", '{"method": "adam_select"}', "0.7460771604938237"])


class TestExport(PlanRunCase):
    def setUp(self):
        super().setUp()
        self.script.write_text(SCRIPT)
        self.add("term", {"term": "m4 mce", "kind": "variable", "definition": "Mean calibration error on M4."})
        self.pl = self.add("plan", {"kind": "confirmatory", "hypotheses": [self.h], "design": "d", "analysis": "a",
                                    "decision": DECISION})
        out = run_command(self.lab, self.agent, [sys.executable, str(self.script)], plan=self.pl, echo=False,
                          cwd=self.tmp.name)
        self.rn, self.rs = out["run"]["id"], [r["id"] for r in out["results"]]

    def status(self, evidence):
        self.add("status", {"target": self.h, "to": "not_supported", "rationale": "Rule of the plan.",
                            "evidence": evidence, "plan": self.pl})
        return export(self.lab, results_path="files/study.results.csv")

    def test_the_runs_results_as_a_table(self):
        out = self.status([self.rn])
        draft = out["draft"]
        ev = draft["evidence"][0]
        self.assertNotIn("results", ev)
        (t,) = ev["tables"]
        self.assertEqual(len(t["rows"]), 2)
        self.assertIn("D1", t["columns"])                                     # "m4 mce" is the term's variable
        claim = draft["claims"][0]
        self.assertEqual(claim["support"][0]["results"], ["E1.T1"])          # the status named the run
        self.assertEqual(claim["test"]["quantities"]["ms"]["variable"], "D1")
        r1, r2 = t["rows"]
        col = t["columns"].index("D1")
        self.assertEqual((r1["values"][col], r2["values"][col]), (0.02235705823668769, 0.035202331961592524))
        self.assertEqual(r1["values"][t["columns"].index("m4 cov80")], 0.7461)   # rounded: no test reads it
        self.assertEqual(r1["values"][t["columns"].index("m4 spread")], 0.07729629629629642)
        csv_art = next(a for a in draft["artefacts"] if a["uri"] == "files/study.results.csv")
        self.assertEqual((csv_art["kind"], ev["artefacts"], t["artefact"]), ("data", [csv_art["id"]], csv_art["id"]))
        self.assertEqual(draft["artefacts"][-1]["kind"], "lab_record")
        text = out["files"]["files/study.results.csv"]
        self.assertEqual(len(text.strip().splitlines()), 1 + 15)
        import hashlib
        self.assertEqual(csv_art["version"], "sha256:" + hashlib.sha256(text.encode()).hexdigest())
        rep = validate(draft)
        self.assertEqual([e for e in rep.errors if e["rule"] in ("38", "48", "67")], [])
        self.assertNotIn("W40", {w["rule"] for w in rep.warnings})

    def test_named_results_cite_their_rows_and_the_rest_is_left_out(self):
        named = [self.rs[1], self.rs[9]]                                     # m4 mce of each method
        draft = self.status(named)["draft"]
        claim, ev = draft["claims"][0], draft["evidence"][0]
        self.assertEqual(claim["support"][0]["results"], ["E1.T1.r1", "E1.T1.r2"])
        (t,) = ev["tables"]
        self.assertEqual(t["columns"], ["D1", "m4 spread"])                 # named, and what the test reads
        self.assertEqual(t["rows"][1]["values"], [0.035202331961592524, None])


class TestExportCommand(TestCli):
    def test_the_csv_is_written_beside_the_claimset(self):
        import os
        script = Path(self.tmp.name) / "exp.py"
        script.write_text(SCRIPT)
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R")
        os.environ["CLAIMSET_ACTOR"] = "AC1"
        self.run_cli("lab", "question", "Q?")
        self.run_cli("lab", "hypothesis", "H.", "--question", "Q1")
        self.run_cli("lab", "run", "--exploratory", "--", sys.executable, str(script))
        self.run_cli("lab", "status", "H1", "inconclusive", "--why", "no rule", "--evidence", "RN1")
        out_file = Path(self.tmp.name) / "paper.claimset.json"
        code, out, err = self.run_cli("lab", "export", "-o", str(out_file))
        self.assertEqual(code, 0, err)
        written = Path(self.tmp.name) / "files" / "paper.results.csv"
        self.assertTrue(written.exists())
        self.assertIn(str(written), out)
        draft = json.loads(out_file.read_text())
        self.assertIn("files/paper.results.csv", [a["uri"] for a in draft["artefacts"]])


class TestWarning40(unittest.TestCase):
    """Claimset §3.4 (amended 2026-11-10): more than eight result entries sharing a variable or a condition key."""

    def doc(self, results, version=None):
        import copy
        from importlib import resources
        d = json.loads((resources.files("claimset") / "data" / "examples" / "submission-native.json").read_text())
        d = copy.deepcopy(d)
        if version:
            d["schema_version"] = version
        d["evidence"][0]["results"] = results
        return d

    def warned(self, d):
        from claimset.validate import validate
        rep = validate(d)
        return [w for w in rep.warnings if w["rule"] == "W40"], rep.errors

    def test_a_shared_variable(self):
        listed = [{"id": f"R{i + 1}", "variable": "D1", "value": 0.1 * i, "conditions": {"series": i}} for i in range(9)]
        warn, errors = self.warned(self.doc(listed))
        self.assertEqual(errors, [])
        self.assertEqual(len(warn), 1)
        self.assertIn("9 result entries share the variable D1", warn[0]["message"])
        self.assertEqual(self.warned(self.doc(listed[:8]))[0], [])

    def test_a_shared_condition(self):
        names = ["m4 cov80", "m4 mce", "m4 pinball_median", "m4 cov80_low", "m4 cov80_mid", "m4 cov80_high",
                 "m4 spread", "m4 share_dlnorm"]
        listed = [{"id": f"R{i + 1}", "variable": v, "value": 0.5, "conditions": {"method": m}}
                  for i, (m, v) in enumerate((m, v) for m in ("adam_select", "msarima") for v in names)]
        warn, _ = self.warned(self.doc(listed))
        self.assertIn("16 result entries share the condition method", warn[0]["message"])

    def test_not_for_files_of_earlier_versions(self):
        compat = Path(__file__).resolve().parent / "compat" / "0.39" / "submission-native.json"
        d = json.loads(compat.read_text())
        d["evidence"][0]["results"] = [{"id": f"R{i + 1}", "variable": "D1", "value": 0.1 * i} for i in range(12)]
        self.assertEqual(self.warned(d)[0], [])


if __name__ == "__main__":
    unittest.main()

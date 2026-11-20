"""Tables held in a file (claimset v0.44 as amended on 2026-11-20, §3.4 and rule 106; lab record v0.23 §9): a large
table keeps its rows in a CSV file of the package. From a simulation study whose claimset held tables of 864, 210 and
105 rows, and whose reading view ran to 1,899 lines."""

import copy
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.lab.export import TABLE_ROWS_INLINE, export  # noqa: E402
from claimset.lab.run import run_command  # noqa: E402
from claimset.render import render  # noqa: E402
from claimset.validate import validate  # noqa: E402

from test_lab import PlanRunCase  # noqa: E402

LAB_EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))


def held_doc(folder):
    """The lab example with its table E1.T1 held in files/e1-t1.csv under `folder`."""
    d = copy.deepcopy(LAB_EXAMPLE)
    ev = next(e for e in d["evidence"] if e["id"] == "E1")
    t = ev["tables"][0]
    rows = t.pop("rows")
    d["artefacts"].append({"id": "A4", "kind": "data", "uri": "files/e1-t1.csv", "availability": {"level": "public"},
                           "description": "The rows of table E1.T1.",
                           "columns": [{"name": "method", "dimension": "method"}]
                           + [{"name": f"D1 {c['conditions']['horizon']}", "variable": "D1"} for c in t["columns"]]})
    t["rows_file"], t["n_rows"] = "A4", len(rows)
    ev["artefacts"] = list(dict.fromkeys((ev.get("artefacts") or []) + ["A4"]))
    (Path(folder) / "files").mkdir(parents=True, exist_ok=True)
    with open(Path(folder) / "files" / "e1-t1.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["method"] + [f"D1 {c['conditions']['horizon']}" for c in t["columns"]])
        for r in rows:
            w.writerow(r["label"] + r["values"])
    return d, rows


def errors(d, folder=None, rule=None):
    found = validate(d, files_root=folder).errors
    return [e for e in found if rule is None or e["rule"] == rule]


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d, self.rows = held_doc(self.tmp.name)

    def test_a_table_held_in_a_file_is_valid_with_and_without_its_file(self):
        self.assertEqual(errors(LAB_EXAMPLE), [])
        self.assertEqual(errors(self.d, self.tmp.name), [])
        self.assertEqual(errors(self.d), [])                      # file not at hand: its columns are known

    def test_rows_or_a_file_not_both(self):
        self.d["evidence"][0]["tables"][0]["rows"] = self.rows
        self.assertTrue(errors(self.d, rule="106"))

    def test_n_rows_only_with_a_file_and_matching_it(self):
        t = self.d["evidence"][0]["tables"][0]
        t["n_rows"] = 5
        self.assertTrue(errors(self.d, self.tmp.name, rule="106"))
        t["n_rows"] = 0
        self.assertTrue(errors(self.d, rule="106"))
        plain = copy.deepcopy(LAB_EXAMPLE)
        plain["evidence"][0]["tables"][0]["n_rows"] = 2
        self.assertTrue(errors(plain, rule="106"))

    def test_the_file_is_a_csv_data_artefact(self):
        a = next(a for a in self.d["artefacts"] if a["id"] == "A4")
        a["kind"] = "code"
        self.assertTrue(errors(self.d, rule="106"))
        a["kind"], a["uri"] = "data", "https://example.org/e1-t1.csv"
        self.assertTrue(errors(self.d, rule="106"))
        self.d["evidence"][0]["tables"][0]["rows_file"] = "A9"
        self.assertTrue(errors(self.d, rule="106"))

    def test_each_line_has_one_field_per_label_and_column(self):
        with open(Path(self.tmp.name) / "files" / "e1-t1.csv", "a", newline="") as fh:
            csv.writer(fh).writerow(["extra", 1])
        self.assertTrue(errors(self.d, self.tmp.name, rule="106"))

    def test_a_row_beyond_the_file_does_not_resolve(self):
        c = next(c for c in self.d["claims"] if any(s.get("evidence") == "E1" for s in c.get("support") or []))
        s = next(s for s in c["support"] if s.get("evidence") == "E1")
        s["results"] = ["E1.T1.r2"]
        self.assertEqual(errors(self.d, rule="38"), [])
        self.assertEqual(errors(self.d, self.tmp.name, rule="38"), [])
        s["results"] = ["E1.T1.r3"]
        self.assertTrue(errors(self.d, rule="38"))
        self.assertTrue(errors(self.d, self.tmp.name, rule="38"))

    def test_a_test_quantity_never_binds_a_cell_held_in_a_file(self):
        c = next(c for c in self.d["claims"] if c["id"] == "C2")
        label = self.rows[0]["label"][0]
        c["test"]["quantities"]["cell"] = {"variable": "D1", "conditions": {"horizon": "1-3", "method": label},
                                           "statistic": "mean"}
        self.assertTrue(errors(self.d, self.tmp.name, rule="91"))
        self.assertTrue(errors(self.d, rule="91"))

    def test_a_table_estimand_binds_it_and_the_values_are_checked_from_the_file(self):
        c = next(c for c in self.d["claims"] if c["id"] == "C2")
        for f in ("hypothesis", "test"):
            c.pop(f)
        c["planning"] = "planned_estimate"
        c["estimate"] = {"estimands": {"errors": {"variable": "D1", "statistic": "mean", "table": True}},
                         "runs": 1, "lab_plan": "PL2"}
        self.assertEqual(errors(self.d, rule="96"), [])
        self.assertEqual(errors(self.d, self.tmp.name, rule="96"), [])
        c["estimate"]["estimands"]["one"] = {"variable": "D1", "statistic": "mean",
                                             "conditions": {"horizon": "1-3", "method": self.rows[0]["label"][0]}}
        self.assertTrue(errors(self.d, self.tmp.name, rule="96"))   # a single estimand binds an inline cell

    def test_a_package_reads_the_file(self):
        from claimset.package import build
        from claimset.validate import validate_path
        src = Path(self.tmp.name) / "paper.claimset.json"
        src.write_text(json.dumps(self.d))
        pkg = Path(self.tmp.name) / "pkg.zip"
        build(src, pkg, update_source=True)
        rep = validate_path(str(pkg))
        self.assertEqual([e for e in rep.errors if e["rule"] in ("38", "48", "70", "91", "96", "106")], [])
        doc = json.loads(src.read_text())
        doc["evidence"][0]["tables"][0]["n_rows"] = 3                 # the file in the package holds 2
        src.write_text(json.dumps(doc))
        pkg2 = Path(self.tmp.name) / "pkg2.zip"
        build(src, pkg2, update_source=True)
        self.assertTrue([e for e in validate_path(str(pkg2)).errors if e["rule"] == "106"])

    def test_the_reading_view_says_where_the_rows_are(self):
        text = render(self.d)
        self.assertIn("(2 rows, held in the file of artefact A4)", text)


SCRIPT = """
import json, os
json.dump([{"variable": "error", "value": 0.1 * i + 0.01 * k, "conditions": {"case": i, "method": m}}
           for i in range(1, ROWS + 1) for k, m in enumerate(("a", "b"))], open(os.environ["CLAIMSET_RESULTS"], "w"))
"""


class TestExport(PlanRunCase):
    def export_rows(self, rows, tested):
        """Export a run of `rows` cases x 2 methods; `tested`: a planned test reads the cell of case 1."""
        self.script.write_text(SCRIPT.replace("ROWS", str(rows)))
        if tested:
            pl = self.add("plan", {"kind": "confirmatory", "hypotheses": [self.h], "design": "d", "analysis": "a",
                                   "decision": {"framework": "deterministic",
                                                "quantities": {"x": {"variable": "error",
                                                                     "conditions": {"case": 1, "method": "a"}}},
                                                "supported": "x < 0", "not_supported": "x >= 0"}})
            out = run_command(self.lab, self.agent, [sys.executable, str(self.script)], plan=pl, echo=False,
                              cwd=self.tmp.name)
            self.add("status", {"target": self.h, "to": "not_supported", "rationale": "Rule of the plan.",
                                "evidence": [out["run"]["id"]], "plan": pl})
        else:
            out = run_command(self.lab, self.agent, [sys.executable, str(self.script)], exploratory=True,
                              echo=False, cwd=self.tmp.name)
            self.add("status", {"target": self.h, "to": "inconclusive", "rationale": "No rule.",
                                "evidence": [out["run"]["id"]]})
        return export(self.lab, results_path="files/study.results.csv")

    def test_a_large_table_goes_to_a_file(self):
        out = self.export_rows(TABLE_ROWS_INLINE + 5, tested=False)
        draft = out["draft"]
        ev = draft["evidence"][0]
        (t,) = ev["tables"]
        self.assertNotIn("rows", t)
        self.assertEqual(t["n_rows"], 2 * (TABLE_ROWS_INLINE + 5))          # a row per case and method
        a = next(a for a in draft["artefacts"] if a["id"] == t["rows_file"])
        self.assertEqual((a["kind"], a["uri"]), ("data", "files/study.E1.T1.csv"))
        self.assertIn(a["id"], ev["artefacts"])
        lines = out["files"]["files/study.E1.T1.csv"].strip().splitlines()
        self.assertEqual(len(lines), 1 + 2 * (TABLE_ROWS_INLINE + 5))
        with tempfile.TemporaryDirectory() as folder:
            for path, text in out["files"].items():
                (Path(folder) / path).parent.mkdir(parents=True, exist_ok=True)
                (Path(folder) / path).write_text(text)
            rep = validate(draft, files_root=folder)
            self.assertEqual([e for e in rep.errors if e["rule"] in ("38", "48", "106")], [])

    def test_a_table_a_test_reads_stays_inline(self):
        out = self.export_rows(TABLE_ROWS_INLINE + 5, tested=True)
        (t,) = out["draft"]["evidence"][0]["tables"]
        self.assertIn("rows", t)
        self.assertNotIn("rows_file", t)

    def test_small_tables_stay_inline(self):
        out = self.export_rows(3, tested=False)
        (t,) = out["draft"]["evidence"][0]["tables"]
        self.assertIn("rows", t)
        self.assertNotIn("rows_file", t)

if __name__ == "__main__":
    unittest.main()

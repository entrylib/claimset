"""Keys under tables and results, readable headers, and short labels (claimset v0.45: §2.3, §3.2, rule 109,
warning 69): a model reading a table met its definitions by identifier only and had to look each up among the
definitions, hundreds of lines away."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import views  # noqa: E402
from claimset.migrate import migrate  # noqa: E402
from claimset.render import key_labels, render  # noqa: E402
from claimset.validate import validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))
LONG = "CES and the non-seasonal special cases of ETS"          # 45 characters


def lab():
    return copy.deepcopy(EXAMPLE)


def defn(d, did):
    return next(x for x in d["definitions"] if x["id"] == did)


def table(d):
    return d["evidence"][0]["tables"][0]


def as_v044():
    """The example as a file of v0.44, which has no `short` field."""
    d = lab()
    d["schema_version"] = "0.44"
    del defn(d, "D1")["short"]
    return d


def rules(report, rule):
    return [x for x in (report.errors if rule[0] != "W" else report.warnings) if x["rule"] == rule]


class TestKey(unittest.TestCase):
    def test_a_key_under_a_table(self):
        text = render(lab())
        rows = text.split("  E1.T1 ")[1].splitlines()
        self.assertEqual(rows[1], "  | row | method | D1, horizon 1-3 (mean) | D1, horizon 4-6 (mean) | "
                                  "D1, horizon 7-12 (mean) |")          # conditions in words, not {horizon: 1-3}
        self.assertEqual(rows[4], "  key: D1 MASE; D2 method M; D3 seasonal naive method")   # order of first use

    def test_the_label_is_the_symbol_else_the_short_else_the_term(self):
        d = lab()
        defn(d, "D2")["symbol"] = "$M$"
        defn(d, "D3")["short"] = "naive"
        self.assertEqual(key_labels(d)["D1"], "MASE")                    # short
        self.assertEqual(key_labels(d)["D2"], "$M$")                     # symbol first
        self.assertEqual(key_labels(d)["D3"], "naive")
        del defn(d, "D1")["short"]
        self.assertEqual(key_labels(d)["D1"], "mean absolute scaled error")     # the term
        self.assertIn("  key: D1 mean absolute scaled error; D2 $M$; D3 naive\n", render(d))

    def test_a_key_under_results(self):
        d = lab()
        r = d["evidence"][0]["results"][0]
        r["variable"], r["conditions"] = "D1", {"D2": "D3", "series": "M1 series 47"}
        text = render(d)
        self.assertIn("  E1.R1 D1 = 0.08", text)
        line = text.split("  E1.R1 ")[1].splitlines()[1]
        self.assertEqual(line, "  key: D1 MASE; D2 method M; D3 seasonal naive method")

    def test_no_key_without_identifiers(self):
        d = lab()
        for c in table(d)["columns"]:
            c["variable"] = "mean MASE"
        for r in table(d)["rows"]:
            r["label"] = ["a method"]
        text = render(d)
        self.assertNotIn("key:", text.split("  E1.T1 ")[1].split("\nE2 ")[0])
        table(d)["description"] = "Mean [[D1:MASE]] by horizon"              # a marker carries its words
        self.assertNotIn("key:", render(d).split("  E1.T1 ")[1].split("\nE2 ")[0])

    def test_a_dimensionless_unit_is_not_written(self):
        d = lab()
        table(d)["units"] = ["1", "1", "s"]
        d["evidence"][0]["results"][0]["unit"] = "1"
        text = render(d)
        self.assertIn("| D1, horizon 1-3 (mean) | D1, horizon 4-6 (mean) | D1, horizon 7-12 (mean) (s) |", text)
        self.assertNotIn("(1)", text.split("EVIDENCE")[1].split("LIMITATIONS")[0])
        self.assertNotIn(" 1 95% confidence", text)

    def test_files_of_earlier_versions_get_keys_too(self):
        old = as_v044()
        self.assertEqual(validate(old).errors, [])
        self.assertIn("  key: D1 mean absolute scaled error; D2 method M; D3 seasonal naive method", render(old))

    def test_the_split_views_give_the_key(self):
        d = lab()
        self.assertIn("  key: D1 MASE; D2 method M; D3 seasonal naive method", views.evidence_view(d, "E1"))


class TestShortLabel(unittest.TestCase):
    """Rule 109: a short label is plain text on one line of at most 30 characters."""

    def test_a_short_label_passes(self):
        self.assertEqual(rules(validate(lab()), "109"), [])

    def test_a_broken_short_label(self):
        for bad, words in (("", "plain text of at most 30"), (7, "plain text of at most 30"),
                           ("two\nlines", "one line"), ("x" * 31, "31 characters"),
                           ("$\\mathrm{MASE}$", "no formula")):
            d = lab()
            defn(d, "D1")["short"] = bad
            got = rules(validate(d), "109")
            self.assertEqual(len(got), 1, bad)
            self.assertEqual(got[0]["where"], "definitions:D1.short")
            self.assertIn(words, got[0]["message"])


class TestWarning69(unittest.TestCase):
    """Warning 69: a long term that a table, a result's variable or a condition names, with no symbol or short."""

    def test_a_long_term_with_a_short_label_or_a_symbol_is_not_warned(self):
        d = lab()
        defn(d, "D3")["term"], defn(d, "D3")["short"] = LONG, "CES and ETS (non-seasonal)"
        self.assertEqual(rules(validate(d), "W69"), [])
        del defn(d, "D3")["short"]
        defn(d, "D3")["symbol"] = "$C$"
        self.assertEqual(rules(validate(d), "W69"), [])
        self.assertEqual(rules(validate(lab()), "W69"), [])

    def test_a_long_term_in_a_table_is_warned(self):
        d = lab()
        defn(d, "D3")["term"] = LONG                                      # a row label of E1.T1
        defn(d, "D4")["term"] = "UK monthly retail sales of one retailer's stores"    # named in no table: not warned
        got = rules(validate(d), "W69")
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["message"].startswith("D3 is named in a table or a result"))
        self.assertIn("give each a `short` label", got[0]["message"])
        self.assertEqual(validate(d).errors, [])                       # a warning: the file stays valid

    def test_a_long_term_in_a_result_or_condition_is_warned(self):
        d = lab()
        r = d["evidence"][0]["results"][0]
        r["variable"], r["conditions"] = "D5", {"D6": "monthly"}
        defn(d, "D5")["term"] = "UK weekly retail sales of one retailer's stores"
        defn(d, "D6")["term"] = "rolling-origin evaluation, 12 horizons"
        got = rules(validate(d), "W69")
        self.assertTrue(got[0]["message"].startswith("D5, D6 are named"))

    def test_files_of_v0_44_are_not_warned(self):
        d = as_v044()
        defn(d, "D3")["term"] = LONG
        self.assertEqual(rules(validate(d), "W69"), [])                # the field is new in v0.45

    def test_migrate_lists_the_terms_to_label(self):
        d = as_v044()
        defn(d, "D3")["term"] = LONG
        out, done, todo = migrate(d)
        self.assertEqual(out["schema_version"], "0.45")
        self.assertTrue(any(t.startswith(f'definitions:D3 "{LONG}" is named in a table') for t in todo), todo)


if __name__ == "__main__":
    unittest.main()

"""Highlights (claimset spec v0.40 §3.1): rule 90, warning 39, the reading view, migrate and export."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from claimset.migrate import migrate  # noqa: E402
from claimset.render import render  # noqa: E402
from claimset.validate import SCHEMA_VERSION, validate  # noqa: E402
from test_validate import converted_base  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
V039 = json.loads((ROOT / "tests" / "compat" / "0.39" / "submission-native.json").read_text(encoding="utf-8"))


def doc(**paper):
    d = copy.deepcopy(NATIVE)
    d["paper"].update(paper)
    return d


def rules(report):
    return sorted({e["rule"] for e in report.errors})


def warned(report, rule):
    return [w for w in report.warnings if w["rule"] == rule]


class TestRule90(unittest.TestCase):
    def test_principal_claims_and_own_terms(self):
        for hl in (["C2"], ["D2"], ["C2", "D2"], ["D2", "C2", "D1", "D4", "D5"]):
            self.assertEqual(validate(doc(highlights=hl)).errors, [], hl)

    def test_broken(self):
        for hl in ([], "C2", ["C2", "C2"], ["C2", "D1", "D2", "D4", "D5", "C1"],   # empty, not a list, twice, six
                   ["C1"],                       # a supporting claim, not a contribution
                   ["C9"], ["X1"], [3], [None]):  # nothing, an unknown ID, not IDs
            self.assertEqual(rules(validate(doc(highlights=hl))), ["90"], hl)

    def test_a_borrowed_term(self):
        d = doc(highlights=["C2", "D3"])
        d.setdefault("references", []).append({"id": "B9", "target": "10.1016/j.ijforecast.2006.03.001",
                                               "id_type": "doi"})
        next(x for x in d["definitions"] if x["id"] == "D3")["source"] = "B9"
        r = validate(d)
        self.assertEqual(rules(r), ["90"])
        self.assertIn("borrowed", r.errors[0]["message"])


class TestWarning39(unittest.TestCase):
    def test_a_native_submission_without_highlights(self):
        d = doc()
        del d["paper"]["highlights"]
        self.assertEqual(len(warned(validate(d), "W39")), 1)
        self.assertEqual(warned(validate(doc()), "W39"), [])

    def test_not_for_converted_or_published_files(self):
        d = converted_base()
        d["paper"].pop("highlights", None)
        self.assertEqual(warned(validate(d), "W39"), [])
        pub = json.loads((ROOT / "examples" / "published-native.json").read_text(encoding="utf-8"))
        del pub["paper"]["highlights"]
        self.assertEqual(warned(validate(pub, published=True), "W39"), [])

    def test_not_for_files_of_earlier_versions(self):
        r = validate(copy.deepcopy(V039))
        self.assertEqual((r.errors, warned(r, "W39")), ([], []))


class TestUse(unittest.TestCase):
    def test_reading_view(self):
        self.assertIn("contributions C2; highlights C2, D2", render(doc()))

    def test_migrate_lists_them_for_the_guarantor(self):
        out, done, todo = migrate(copy.deepcopy(V039))
        self.assertEqual(out["schema_version"], SCHEMA_VERSION)
        self.assertEqual([t for t in todo if t.startswith("paper.highlights")], [todo[-1]])
        self.assertNotIn("highlights", out["paper"])


if __name__ == "__main__":
    unittest.main()

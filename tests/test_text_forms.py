"""References to the file's items, citations and paragraphs (claimset v0.44 as amended on 2026-11-23, §8 rules 13 to
15, warning 66): an item is named by its ID, a work by a citation marker, `[[B12:Hyndman et al. (2008)]]`, and a blank
line separates paragraphs."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))


def rules(d, *names):
    return [w for w in validate(d).warnings if w["rule"] in names]


class TestCitationMarkers(unittest.TestCase):
    def setUp(self):
        self.d = copy.deepcopy(EXAMPLE)
        self.d["references"] = [{"id": "B1", "target": "10.1016/j.ijforecast.2008.01.001", "id_type": "doi"}]

    def test_a_marker_naming_a_reference_passes(self):
        d = self.d
        d["evidence"][0]["description"] = "Computed as in [[B1:Hyndman et al. (2008)]], with `adam()`."
        self.assertEqual(rules(d, "W66", "W64", "W65"), [])
        self.assertEqual(validate(d).errors, [])

    def test_a_marker_naming_no_reference_is_warned(self):
        d = self.d
        d["evidence"][0]["description"] = "Computed as in [[B7:Smith (2020)]]."
        d["artefacts"][0]["description"] = "Cites [[B1:Hyndman et al. (2008)]] and [[B9:Jones (2019)]]."
        w = {(x["where"], x["message"].split()[3]) for x in rules(d, "W66")}
        self.assertEqual(w, {(f"evidence:{d['evidence'][0]['id']}.description", "[[B7:Smith"),
                             (f"artefacts:{d['artefacts'][0]['id']}.description", "[[B9:Jones")})
        self.assertEqual(validate(d).errors, [])                         # a warning: the file stays valid

    def test_a_cited_year_in_a_statement_is_not_a_result(self):
        d = self.d
        c = next(c for c in d["claims"] if any(s.get("kind") == "empirical_quant" for s in c.get("support") or []))
        before = [w for w in validate(d).warnings if w["rule"] == "W17"]
        c["statement"] = c["statement"].rstrip(".") + ", as in [[B1:Hyndman et al. (2008)]]."
        after = [w for w in validate(d).warnings if w["rule"] == "W17"]
        self.assertEqual(len(after), len(before))
        self.assertFalse(any("2008" in x["message"] for x in validate(d).errors + validate(d).warnings))


class TestFormulaInMarkers(unittest.TestCase):
    def test_a_formula_in_a_marker_is_warned(self):
        d = copy.deepcopy(EXAMPLE)
        did = d["definitions"][0]["id"]
        d["evidence"][0]["description"] = f"Written with the [[{did}:words]] $I_n$."
        self.assertEqual(rules(d, "W67"), [])
        d["evidence"][0]["description"] = f"Written with [[{did}:$I_n$]]."
        self.assertEqual([w["where"] for w in rules(d, "W67")], [f"evidence:{d['evidence'][0]['id']}.description"])
        self.assertEqual(validate(d).errors, [])


if __name__ == "__main__":
    unittest.main()

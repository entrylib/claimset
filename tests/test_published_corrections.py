"""Corrections to the published paper (claimset spec v0.44 §3.1, rule 100), and corrections in the reading view
(Appendix D). From a claimset whose authors corrected conditions their published paper had left out."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.render import render  # noqa: E402
from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
CLAIM = NATIVE["claims"][0]["id"]
PERSON = NATIVE["contributors"][0]["id"]


def corrected(*entries):
    d = copy.deepcopy(NATIVE)
    d["paper"]["published_as"] = {"id_type": "doi", "id": "10.1002/nav.22074", "corrections": list(entries)}
    return d


def entry(**over):
    e = {"kind": "correction", "field": f"{CLAIM}.statement", "where": "Section 3.3",
         "printed": "alpha1 > 1 gives exponential growth", "recorded": "alpha1 > 1 and alpha0 < 2",
         "reason": "At alpha0 = 2.2, alpha1 = 1.2 the dominant eigenvalue is -1.287.", "found_by": PERSON}
    e.update(over)
    return e


def r99(d):
    return [e for e in validate(d).errors if e["rule"] == "100"]


class TestRule99(unittest.TestCase):
    def test_valid_corrections_pass(self):
        ok = corrected(entry(), entry(kind="misprint", field="E1", where="Equation (E9), Appendix E"),
                       {k: v for k, v in entry().items() if k != "found_by"})
        self.assertEqual(r99(ok), [])
        self.assertEqual(r99(NATIVE), [])

    def test_broken_corrections_fail(self):
        for bad, where in ((entry(kind="typo"), "kind"), (entry(where=" "), "]"), (entry(field="Z9.statement"), "field"),
                           (entry(found_by="P99"), "found_by"), (entry(found_by=["P1"]), "found_by"),
                           ("text", "]")):
            found = r99(corrected(bad))
            self.assertTrue(found and found[0]["where"].endswith(where), (bad, found))
        d = corrected()
        d["paper"]["published_as"]["corrections"] = {"field": "C1"}
        self.assertEqual(len(r99(d)), 1)


class TestReadingView(unittest.TestCase):
    def test_a_corrected_claim_is_marked_and_listed(self):
        text = render(corrected(entry()))
        self.assertIn("corrects the published paper in 1 place (CORRECTIONS)", text)
        self.assertIn("  corrected from the published paper (correction; Section 3.3): printed alpha1 > 1 gives "
                      "exponential growth", text)
        section = text.split("\nCORRECTIONS\n", 1)[1]
        self.assertTrue(section.startswith(f"{CLAIM}.statement [correction; Section 3.3; found by {PERSON}] printed "))

    def test_a_converted_source_s_corrections_are_shown_too(self):
        d = copy.deepcopy(NATIVE)
        d["paper"]["converted_from"] = {"corrections": [{"field": f"{CLAIM}.statement", "where": "p6.4",
                                                         "printed": "x", "recorded": "y", "reason": "z"}]}
        text = render(d)
        self.assertIn("corrects the source in 1 place", text)
        self.assertIn("  corrected from the source (p6.4): printed x", text)

    def test_nothing_without_corrections(self):
        self.assertNotIn("CORRECTIONS", render(NATIVE))


if __name__ == "__main__":
    unittest.main()

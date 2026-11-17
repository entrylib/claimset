"""A paper that cites no work is warned (claimset spec v0.44 §3.13; warning 52, amended on 2026-11-17). From a
simulation study published with relations to the claims of the review it tested and no references."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))


def w52(d):
    return [w for w in validate(d).warnings if w["rule"] == "W52"]


def without_references(d):
    d = copy.deepcopy(d)
    for x in d["definitions"]:
        x.pop("source", None)
    d.pop("references", None)
    return d


class TestReferencesPresent(unittest.TestCase):
    def test_a_paper_with_references_is_not_warned(self):
        self.assertTrue(NATIVE["references"])
        self.assertEqual(w52(NATIVE), [])

    def test_no_references_is_warned(self):
        d = without_references(NATIVE)
        found = w52(d)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["where"], "references")
        d["references"] = []
        self.assertEqual(len(w52(d)), 1)

    def test_relations_to_claimsets_do_not_count(self):
        d = without_references(NATIVE)
        c2 = next(c for c in d["claims"] if c["id"] == "C2")
        c2["relations"] = [{"type": "supports", "target": "entrylib:2026.000008@v2#C2", "id_type": "claimset",
                            "note": "C2 recommends squared error for point forecasts of the mean."}]
        self.assertEqual(len(w52(d)), 1)

    def test_a_warning_never_rejects(self):
        self.assertEqual(validate(without_references(NATIVE)).errors, [])


if __name__ == "__main__":
    unittest.main()

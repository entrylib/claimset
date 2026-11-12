"""A claimset its authors converted from their published paper names it (claimset spec v0.42 §3.1, as amended on
2026-11-12): rule 97 and warning 49."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
MANUSCRIPT = {"id": "A99", "kind": "manuscript", "uri": "https://doi.org/10.1016/j.ijforecast.2025.01.001",
              "description": "The published article", "availability": {"level": "public"}}


def doc(published_as=None, manuscript=None):
    d = copy.deepcopy(NATIVE)
    if published_as is not None:
        d["paper"]["published_as"] = published_as
    if manuscript:
        d["artefacts"].append(manuscript)
    return d


def found(report, rule):
    return [x for x in report.errors + report.warnings if x["rule"] == rule]


class TestPublishedAs(unittest.TestCase):
    def test_rule_97(self):
        good = {"id_type": "doi", "id": "10.1016/j.ijforecast.2025.01.001"}
        self.assertEqual(found(validate(doc(good)), "97"), [])
        self.assertEqual(found(validate(doc({"id_type": "arxiv", "id": "2401.01234", "version": "v2"})), "97"), [])
        self.assertEqual(found(validate(NATIVE), "97"), [])                       # optional
        for bad in ("10.1/x", {"id_type": "journal", "id": "x"}, {"id_type": "doi", "id": ""},
                    {"id_type": "doi", "id": "10.1/x", "version": 2}):
            self.assertTrue(found(validate(doc(bad)), "97"), bad)

    def test_warning_49(self):
        self.assertEqual(len(found(validate(doc(manuscript=MANUSCRIPT)), "W49")), 1)
        both = doc({"id_type": "doi", "id": "10.1016/j.ijforecast.2025.01.001"}, MANUSCRIPT)
        self.assertEqual(found(validate(both), "W49"), [])
        draft = dict(MANUSCRIPT, uri="files/draft.pdf")                            # a draft: nothing to name
        self.assertEqual(found(validate(doc(manuscript=draft)), "W49"), [])


if __name__ == "__main__":
    unittest.main()

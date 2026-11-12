"""A paper's summary (claimset spec v0.41 §3.1, as amended on 2026-11-11): rule 94, warning 45 and the reading view."""

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
TEXT = "Method M forecasts UK retail sales better than the seasonal naive benchmark, with error $e_t$ lower by a tenth."


def doc(**paper):
    d = copy.deepcopy(NATIVE)
    d["paper"].update(paper)
    return d


def found(report, rule):
    return [x for x in report.errors + report.warnings if x["rule"] == rule]


class TestSummary(unittest.TestCase):
    def test_rule_94(self):
        self.assertEqual(found(validate(doc(summary=TEXT)), "94"), [])
        self.assertEqual(found(validate(NATIVE), "94"), [])                        # optional
        for bad in ("", "   ", 3, ["a"]):
            self.assertEqual(len(found(validate(doc(summary=bad)), "94")), 1, bad)

    def test_warning_45(self):
        self.assertEqual(found(validate(doc(summary=TEXT)), "W45"), [])
        self.assertEqual(found(validate(doc(summary=" ".join(["word"] * 150))), "W45"), [])
        self.assertEqual(len(found(validate(doc(summary=" ".join(["word"] * 151))), "W45")), 1)

    def test_reading_view(self):
        lines = render(doc(summary="A  finding,\nin plain words.")).splitlines()
        self.assertEqual(lines[1], "summary A finding, in plain words.")
        self.assertFalse(any(x.startswith("summary ") for x in render(NATIVE).splitlines()))


if __name__ == "__main__":
    unittest.main()

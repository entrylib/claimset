"""The sections a paper is read in (claimset spec v0.44 as amended on 2026-11-18, §3.1: rule 105, warning 57), and
definitions listed in the order a reader needs them (§3.2: warning 58)."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.render import render  # noqa: E402
from claimset.renumber import renumber  # noqa: E402
from claimset.validate import validate  # noqa: E402

# C1 and C3 are assumptions; C2 (principal) and C4 (secondary) are the paper's claims
LAB = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))


def doc(sections="default"):
    d = copy.deepcopy(LAB)
    if sections == "default":
        sections = [{"title": "The comparison", "claims": ["C2"]}, {"title": "What else was found", "claims": ["C4"]}]
    if sections is not None:
        d["paper"]["sections"] = sections
    return d


def rules(report):
    return sorted({e["rule"] for e in report.errors})


def warned(report, rule):
    return [w for w in report.warnings if w["rule"] == rule]


class TestRule105Sections(unittest.TestCase):
    def test_sections(self):
        rep = validate(doc())
        self.assertEqual(rep.errors, [])
        self.assertEqual(warned(rep, "W57"), [])

    def test_no_sections_is_as_before(self):
        rep = validate(doc(None))
        self.assertEqual(rep.errors, [])
        self.assertEqual(warned(rep, "W57"), [])

    def test_broken_sections(self):
        broken = {
            "not a list": {"title": "All", "claims": ["C2"]},
            "empty": [],
            "an entry that is no object": ["C2"],
            "no title": [{"claims": ["C2"]}],
            "an empty title": [{"title": "  ", "claims": ["C2"]}],
            "a title on two lines": [{"title": "The\ncomparison", "claims": ["C2"]}],
            "a long title": [{"title": "x" * 81, "claims": ["C2"]}],
            "the same title twice": [{"title": "Results", "claims": ["C2"]}, {"title": " results ", "claims": ["C4"]}],
            "no claims": [{"title": "Results"}],
            "an empty list of claims": [{"title": "Results", "claims": []}],
            "a claim that does not exist": [{"title": "Results", "claims": ["C2", "C99"]}],
            "something that is no ID": [{"title": "Results", "claims": [2]}],
            "an assumption": [{"title": "Results", "claims": ["C1", "C2"]}],
            "a claim in two sections": [{"title": "First", "claims": ["C2"]}, {"title": "Second", "claims": ["C2"]}],
            "another field": [{"title": "Results", "claims": ["C2"], "summary": "What was found."}],
        }
        for what, sections in broken.items():
            with self.subTest(what):
                self.assertIn("105", rules(validate(doc(sections))), what)

    def test_a_title_of_80_characters(self):
        self.assertEqual(validate(doc([{"title": "x" * 80, "claims": ["C2", "C4"]}])).errors, [])


class TestWarning57(unittest.TestCase):
    def test_a_claim_in_no_section(self):
        rep = validate(doc([{"title": "The comparison", "claims": ["C2"]}]))
        self.assertEqual(rep.errors, [])
        w = warned(rep, "W57")
        self.assertEqual(len(w), 1)
        self.assertIn("C4", w[0]["message"])
        self.assertNotIn("C1", w[0]["message"])                    # an assumption belongs to no section

    def test_every_claim_placed(self):
        self.assertEqual(warned(validate(doc()), "W57"), [])


class TestWarning58DefinitionOrder(unittest.TestCase):
    def test_a_definition_that_names_a_later_one(self):
        d = doc(None)
        d["definitions"][0]["definition"] += " It is a part of [[D2:the second term]]."
        w = warned(validate(d), "W58")
        self.assertEqual([x["where"] for x in w], ["definitions:D1.definition"])
        self.assertIn("D2", w[0]["message"])
        self.assertEqual(validate(d).errors, [])                   # a file valid before stays valid

    def test_a_definition_that_names_an_earlier_one(self):
        d = doc(None)
        d["definitions"][1]["definition"] += " It is built on [[D1:the first term]]."
        self.assertEqual(warned(validate(d), "W58"), [])

    def test_the_examples_are_in_order(self):
        for name in ("submission-native.json", "submission-from-lab.json"):
            d = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
            self.assertEqual(warned(validate(d), "W58"), [], name)


class TestTheReadingViewAndRenumbering(unittest.TestCase):
    def test_the_reading_view_lists_the_sections(self):
        view = render(doc())
        self.assertIn("sections\n  1. The comparison: C2\n  2. What else was found: C4", view)
        self.assertNotIn("\nsections\n", render(doc(None)))

    def test_renumbering_keeps_the_sections(self):
        d = doc()
        out, mapping = renumber(d)
        self.assertEqual([s["claims"] for s in out["paper"]["sections"]], [[mapping["C2"]], [mapping["C4"]]])
        self.assertEqual(validate(out).errors, [])


if __name__ == "__main__":
    unittest.main()

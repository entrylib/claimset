"""The subfield a submission proposes (specification §3.1; warnings 55 and 56): one of OpenAlex's, agreed to by the
guarantor before submission."""

import contextlib
import copy
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

from claimset import subfields
from claimset.cli import main
from claimset.validate import print_report, validate

ROOT = Path(__file__).resolve().parents[1]
NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
PUBLISHED = json.loads((ROOT / "examples" / "published-native.json").read_text(encoding="utf-8"))


def rules(rep):
    return [w["rule"] for w in rep.warnings]


def with_subfield(value):
    doc = copy.deepcopy(NATIVE)
    if value is None:
        doc["paper"]["classification"].pop("subfield", None)
    else:
        doc["paper"]["classification"]["subfield"] = value
    return doc


class TestProposedSubfield(unittest.TestCase):
    def test_a_listed_subfield_passes_and_is_named(self):
        rep = validate(with_subfield("openalex:subfields/2613"))
        self.assertEqual(rep.errors, [])
        self.assertNotIn("W55", rules(rep))
        self.assertNotIn("W56", rules(rep))
        self.assertEqual(rep.subfield, ("openalex:subfields/2613", "Statistics and Probability"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_report(rep)
        self.assertIn("Subfield proposed: Statistics and Probability (openalex:subfields/2613).", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_report(rep, as_json=True)
        self.assertEqual(json.loads(out.getvalue())["subfield"],
                         {"id": "openalex:subfields/2613", "name": "Statistics and Probability"})

    def test_the_example_proposes_one(self):
        rep = validate(copy.deepcopy(NATIVE))
        self.assertNotIn("W55", rules(rep))
        self.assertEqual(rep.subfield[1], "Management Science and Operations Research")

    def test_no_subfield_is_flagged(self):
        for doc in (with_subfield(None), with_subfield("")):
            rep = validate(doc)
            self.assertEqual(rep.errors, [])                       # a file valid before stays valid
            self.assertEqual(rules(rep).count("W55"), 1)
            self.assertIsNone(rep.subfield)
        doc = with_subfield(None)
        del doc["paper"]["classification"]
        self.assertIn("W55", rules(validate(doc)))

    def test_a_value_that_is_no_subfield_is_flagged(self):
        for bad in ("openalex:subfields/9999", "Statistics", "openalex:subfields/XXXX", "openalex:T10282", 2613):
            rep = validate(with_subfield(bad))
            self.assertEqual(rep.errors, [], bad)
            self.assertEqual(rules(rep).count("W56"), 1, bad)
            self.assertNotIn("W55", rules(rep))
            self.assertIsNone(rep.subfield)

    def test_a_published_file_is_not_asked_again(self):
        rep = validate(copy.deepcopy(PUBLISHED), published=True)
        self.assertNotIn("W55", rules(rep))
        self.assertNotIn("W56", rules(rep))                        # its subfield is the platform's to check


class TestTheList(unittest.TestCase):
    def test_ids_and_names(self):
        self.assertEqual(len(subfields.SUBFIELDS), 252)
        self.assertEqual(subfields.name("openalex:subfields/1803"), "Management Science and Operations Research")
        for written in ("2613", "subfields/2613", "openalex:subfields/2613", "https://openalex.org/subfields/2613",
                        " openalex:subfields/2613 "):
            self.assertEqual(subfields.norm(written), "openalex:subfields/2613", written)
        for bad in ("0000", "26130", "openalex:T2613", None, 2613, ["2613"]):
            self.assertIsNone(subfields.norm(bad), bad)
            self.assertIsNone(subfields.name(bad), bad)

    def test_find_by_words(self):
        self.assertEqual(len(subfields.find()), 252)
        found = dict(subfields.find(["statistics", "PROBABILITY"]))
        self.assertIn("openalex:subfields/2613", found)
        self.assertTrue(all("statistics" in n.lower() and "probability" in n.lower() for n in found.values()))
        self.assertEqual(subfields.find(["no such field"]), [])

    def test_the_command(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["subfields", "statistics", "probability"])
        self.assertEqual(code, 0)
        self.assertIn("openalex:subfields/2613  Statistics and Probability", out.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(main(["subfields", "zzzz"]), 1)
        self.assertIn("claimset subfields", err.getvalue())

    def test_the_skills_copy_of_the_validator_finds_the_list(self):
        script = ROOT / "skills" / "claimset-submit" / "scripts" / "validate.py"
        run = subprocess.run([sys.executable, str(script), str(ROOT / "examples" / "submission-native.json")],
                             capture_output=True, text=True, cwd=str(ROOT.parent))
        self.assertIn("Subfield proposed: Management Science and Operations Research", run.stdout, run.stderr)


if __name__ == "__main__":
    unittest.main()

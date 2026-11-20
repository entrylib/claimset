"""The version a correction or revision was made from (claimset spec v0.44 as amended on 2026-11-21: §3.1, §9, rule 107,
warning 62), and `claimset correct`, which starts one from a published file. A correction prepared from an older
version had been published as an undo of the version after it (entrylib/claimset#153)."""

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import cli  # noqa: E402
from claimset.validate import PLATFORM_PAPER_FIELDS, SCHEMA_VERSION, validate  # noqa: E402

PUBLISHED = json.loads((ROOT / "examples" / "published-native.json").read_text(encoding="utf-8"))
ID = PUBLISHED["paper"]["id"]


def correction(**paper):
    d = copy.deepcopy(PUBLISHED)
    for f in PLATFORM_PAPER_FIELDS:
        d["paper"].pop(f, None)
    d["paper"]["correction_reason"] = "Corrects a value read from the wrong table row."
    d["paper"].update(paper)
    return d


def rules(report, kind="errors"):
    return [x["rule"] for x in getattr(report, kind)]


class TestRule107(unittest.TestCase):
    def test_a_correction_names_the_version_it_was_made_from(self):
        r = validate(correction(based_on=f"{ID}@v1"))
        self.assertEqual(r.errors, [])
        self.assertNotIn("W62", rules(r, "warnings"))

    def test_another_claimset_or_no_version_is_refused(self):
        for bad in (f"entrylib:2026.999999@v1", ID, f"{ID}@v0", f"{ID}@vx", 3):
            with self.subTest(bad=bad):
                self.assertIn("107", rules(validate(correction(based_on=bad))))

    def test_a_published_file_names_an_earlier_version(self):
        d = copy.deepcopy(PUBLISHED)
        d["paper"]["version"] = 2
        d["paper"]["based_on"] = f"{ID}@v1"
        self.assertNotIn("107", rules(validate(d, published=True)))
        d["paper"]["based_on"] = f"{ID}@v2"
        self.assertIn("107", rules(validate(d, published=True)))

    def test_a_correction_without_it_is_warned(self):
        r = validate(correction())
        self.assertEqual(r.errors, [])
        self.assertIn("W62", rules(r, "warnings"))

    def test_a_new_paper_is_not_warned(self):
        self.assertNotIn("W62", rules(validate(json.loads((ROOT / "examples" / "submission-native.json")
                                                         .read_text(encoding="utf-8"))), "warnings"))


class TestCorrectCommand(unittest.TestCase):
    def run_correct(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "current.json", Path(tmp) / "fix.json"
            src.write_text(json.dumps(doc), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = cli.main(["correct", str(src), "-o", str(out)])
            return code, (json.loads(out.read_text(encoding="utf-8")) if out.exists() else None)

    def test_starts_a_correction_from_the_current_version(self):
        doc = copy.deepcopy(PUBLISHED)
        doc["paper"]["version"] = 3
        doc["paper"]["correction_reason"] = "the reason of version 3"
        code, out = self.run_correct(doc)
        self.assertEqual(code, 0)
        paper = out["paper"]
        self.assertEqual(paper["id"], ID)
        self.assertEqual(paper["based_on"], f"{ID}@v3")
        for f in PLATFORM_PAPER_FIELDS + ("correction_reason",):
            self.assertNotIn(f, paper)
        self.assertNotIn("topics", paper.get("classification", {}))
        self.assertFalse(any("verifiability" in c for c in out["claims"]))
        paper["correction_reason"] = "Corrects a value read from the wrong table row."
        self.assertEqual(validate(out).errors, [])

    def test_migrates_an_older_file(self):
        doc = copy.deepcopy(PUBLISHED)
        doc["schema_version"] = "0.42"
        code, out = self.run_correct(doc)
        self.assertEqual(code, 0)
        self.assertEqual(out["schema_version"], SCHEMA_VERSION)

    def test_refuses_a_file_that_is_not_published(self):
        doc = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
        with redirect_stdout(io.StringIO()):
            from contextlib import redirect_stderr
            with redirect_stderr(io.StringIO()):
                code, out = self.run_correct(doc)
        self.assertEqual(code, 1)
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()

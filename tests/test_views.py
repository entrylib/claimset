"""Split views (spec §2.3, *Split views*): the overview, one file per claim, evidence object and definition, and the
references; every ID a view names is shown in it or has a file."""

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import views  # noqa: E402
from claimset.claim import render_claim  # noqa: E402

BASE = "https://example.org/p/2026.000001/"
WHOLE = "https://example.org/p/2026.000001.txt"
ID = re.compile(r"(?<![\w.\-/])([A-Z]\d+)(?![\d])")
FILES = sorted((ROOT / "examples").glob("*.json")) + sorted((ROOT / "tests" / "compat").glob("*/*.json"))


def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def unresolved(doc, written):
    """IDs of the claimset's objects that a view names but neither shows nor has a file for: {ID: [files]}."""
    objects = {x.get("id") for v in doc.values() if isinstance(v, list) for x in v if isinstance(x, dict)}
    bad = {}
    for name, text in written.items():
        shown = set(re.findall(r"^\s*([A-Z]\d+)\b", text, re.MULTILINE))
        for m in ID.finditer(text):
            oid = m.group(1)
            if oid in objects and oid not in shown and views.file_name(oid) not in written:
                bad.setdefault(oid, []).append(name)
    return bad


class TestEveryIdResolves(unittest.TestCase):
    def test_examples_and_compat_files(self):
        self.assertTrue(FILES)
        for path in FILES:
            doc = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.name, version=path.parent.name):
                written = views.files(doc, BASE, WHOLE)
                self.assertEqual(unresolved(doc, written), {})
                claims = {c["id"] for c in doc["claims"]}
                self.assertTrue({f"{c}.txt" for c in claims} <= set(written))

    def test_an_artefact_named_only_in_a_text_is_shown(self):
        doc = load("submission-native.json")
        d3 = next(d for d in doc["definitions"] if d["id"] == "D3")
        d3["definition"] += " Its forecasts are in A2."
        text = views.definition_view(doc, "D3")
        self.assertIn("\nALSO NAMED ABOVE\nA2 [", text)
        self.assertEqual(unresolved(doc, views.files(doc)), {})


class TestOverview(unittest.TestCase):
    def test_lists_every_claim_once_and_marks_the_principal(self):
        doc = load("submission-from-lab.json")
        text = views.overview(doc, BASE, WHOLE, score="Support 70 (high)")
        first = text.splitlines()[0]
        self.assertTrue(first.startswith("OVERVIEW "))
        self.assertIn("Support 70 (high)", first)
        self.assertTrue(text.splitlines()[1].startswith("FILES at " + BASE))
        for c in doc["claims"]:
            self.assertEqual(len(re.findall(rf"^  {c['id']}\*? ", text, re.MULTILINE)), 1, c["id"])
        self.assertRegex(text, r"\n  C2\* ")
        self.assertIn(f"  C2: {BASE}C2.txt", text)
        self.assertIn(f"  E1: {BASE}E1.txt", text)
        self.assertIn(f"the whole paper: {WHOLE}", text)
        self.assertNotIn(f"{BASE}C4.txt", text)               # only principal claims are linked in full
        self.assertIn("give the person you are helping the addresses of the files", text.splitlines()[-1])
        self.assertIn("let them choose which to paste back to you", text.splitlines()[-1])

    def test_a_publisher_may_add_each_claims_score(self):
        doc = load("submission-from-lab.json")
        text = views.overview(doc, BASE, WHOLE, claim_scores={"C2": "Support 88", "C9": "ignored"})
        self.assertRegex(text, r"\n  C2\* \(Support 88\) ")
        self.assertNotIn("(Support", text.split("C2*")[0])                 # only where given
        self.assertEqual(views.files(doc, BASE, WHOLE, claim_scores={"C2": "Support 88"})["overview.txt"],
                         views.overview(doc, BASE, WHOLE, claim_scores={"C2": "Support 88"}))

    def test_sections_and_key_terms(self):
        doc = load("submission-native.json")
        doc["paper"]["sections"] = [{"title": "Results", "claims": ["C2"]}]
        doc["paper"]["highlights"] = ["D4"]
        text = views.overview(doc)
        self.assertIn("== 1. Results\n  C2* ", text)
        terms = text.split("KEY TERMS")[1].splitlines()
        self.assertIn("1 more in D<n>.txt", terms[0])
        self.assertTrue(terms[1].startswith("  D4 "))           # the highlighted term first
        self.assertIn("ASSUMPTIONS\n  C1 ", text)
        self.assertNotIn("== Claims in no section", text)       # assumptions are not claims in no section

    def test_a_claim_without_a_name_is_named_by_its_first_words(self):
        doc = load("submission-native.json")
        text = views.overview(doc)
        self.assertIn("  C2* Method M improves forecast skill over the seasonal naive method on the …", text)

    def test_much_shorter_than_the_reading_view(self):
        from claimset.render import render
        doc = load("submission-from-lab.json")
        self.assertLess(len(views.overview(doc)), len(render(doc)) / 2)


class TestClaimView(unittest.TestCase):
    def test_names_the_rows_cited_without_copying_them(self):
        doc = copy.deepcopy(load("submission-from-lab.json"))
        c2 = next(c for c in doc["claims"] if c["id"] == "C2")
        c2["support"][0]["results"] = ["E1.T1.r2"]
        text = views.claim_view(doc, "C2", BASE, WHOLE)
        self.assertTrue(text.startswith("CLAIM C2 of "))
        part = text.split("\nEVIDENCE (what this claim cites, each object in its own file)\n")[1].split("\n\n")[0]
        self.assertRegex(part, rf"^E1 \[.*\] .* {re.escape(BASE)}E1\.txt\n  E1\.T1 .*: rows r2 of 2$")
        self.assertNotIn("| r", text)                             # the rows are in E1.txt
        self.assertNotIn("E1.R1 ", text)                         # a result it does not cite
        self.assertNotIn("E1.T1.r2", text.split("\n\n")[1])       # nor are they listed in its support line

    def test_a_whole_table_or_result_cited(self):
        doc = load("submission-from-lab.json")
        text = views.claim_view(doc, "C2")
        self.assertIn("  E1.T1 ", text)
        self.assertRegex(text, r"  E1\.T1 .*: the whole table\n")
        self.assertIn("  E1.R1 ", text)                          # a result: one line, in the claim's file
        self.assertNotIn("| r1 |", text)

    def test_names_only_the_definitions_it_uses(self):
        doc = load("submission-native.json")
        text = views.claim_view(doc, "C2")
        part = text.split("DEFINITIONS (the terms this claim names, each in its own file)\n")[1].split("\n\n")[0]
        self.assertEqual(re.findall(r"^  (D\d+) .*: D\d+\.txt$", part, re.MULTILINE), ["D2", "D1", "D3", "D4"])
        self.assertNotIn("Forecasts each month", text)            # D3's definition is in D3.txt
        self.assertIn("ASSUMPTIONS (each in its own file)\n  C1: C1.txt\n  C3: C3.txt\n", text)  # by name, not copied
        self.assertNotIn("annual seasonality", text)
        self.assertIn("LIMITATIONS\nL1 ", text)

    def test_an_assumption_names_the_claims_resting_on_it(self):
        doc = load("submission-native.json")
        text = views.claim_view(doc, "C1", BASE)
        self.assertTrue(text.startswith("ASSUMPTION C1 of "))
        self.assertIn("annual seasonality", text)
        self.assertIn("CLAIMS RESTING ON IT: C2", text)

    def test_render_claim_is_the_claim_view(self):
        doc = load("submission-native.json")
        self.assertEqual(render_claim(doc, "C2", BASE), views.claim_view(doc, "C2", BASE))
        with self.assertRaises(KeyError):
            render_claim(doc, "C99")


class TestOtherViews(unittest.TestCase):
    def test_evidence_names_its_claims_and_terms(self):
        doc = load("submission-native.json")
        text = views.evidence_view(doc, "E1")
        self.assertTrue(text.startswith("EVIDENCE E1 of "))
        self.assertIn("CLAIMS RESTING ON IT: C2", text)
        self.assertRegex(text, r"TERMS \(each in its own file\): D\d+ ")

    def test_definition_and_references(self):
        doc = load("submission-native.json")
        text = views.definition_view(doc, "D3")
        self.assertTrue(text.startswith("DEFINITION D3 of "))
        self.assertIn("REFERENCES\nB1 ", text)
        self.assertIn("CLAIMS NAMING IT: C2", text)
        refs = views.references_view(doc)
        self.assertRegex(refs, r"\nB1 .*")

    def test_links_by_file_name_without_a_base(self):
        doc = load("submission-native.json")
        text = views.overview(doc)
        self.assertIn("  C2: C2.txt", text)
        self.assertIn("the whole paper: claimset.txt", text)


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "claimset", "render", str(ROOT / "examples" / "submission-native.json"),
                               *args], capture_output=True, text=True, env={"PYTHONPATH": str(ROOT / "src")})

    def test_split_writes_every_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.run_cli("--split", d, "--base", BASE)
            self.assertEqual(out.returncode, 0, out.stderr)
            names = {p.name for p in Path(d).iterdir()}
            self.assertTrue({"overview.txt", "C2.txt", "E1.txt", "D1.txt", "references.txt", "claimset.txt"} <= names)
            self.assertIn(BASE, (Path(d) / "C2.txt").read_text(encoding="utf-8"))
            self.assertTrue((Path(d) / "claimset.txt").read_text(encoding="utf-8").startswith("CLAIMSET "))

    def test_overview(self):
        out = self.run_cli("--overview")
        self.assertTrue(out.stdout.startswith("OVERVIEW "))


if __name__ == "__main__":
    unittest.main()

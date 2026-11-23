"""`claimset lean`: candidates for text a reader does not need, for a reviewing agent and the guarantor. From the sMAPE
study's version 4 (entrylib:2026.000013), whose build added sentences, relations and limitations nobody had asked for:
a duplicate relation to a paper two other claims already related to, limitations attached to claims the published
version had left without them, and asides the guarantor removed."""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from claimset import lean  # noqa: E402
from claimset.cli import main  # noqa: E402

DOC = {
    "paper": {"summary": "sMAPE rewards a weighted median of the actuals."},
    "definitions": [
        {"id": "D1", "term": "sMAPE term", "definition": "The contribution of one actual and one forecast to sMAPE."},
        {"id": "D2", "term": "spare term", "definition": "A term that no claim uses."},
    ],
    "claims": [
        {"id": "C1", "statement": "The [[D1:sMAPE term]] depends only on the ratio of the actual to the forecast.",
         "summary": "Only the ratio of the actual to the forecast matters, not their size.",
         "support": [{"kind": "cited", "reference": "B1"}],
         "relations": [{"type": "extends", "reference": "B1", "note": "Huber (1964) defines M-estimators."},
                       {"type": "extends", "reference": "B2", "note": "Serfling (1980) gives the efficiency."},
                       {"type": "extends", "reference": "B2", "note": "Serfling again."}]},
        {"id": "C2", "statement": "Its expected value has a minimiser.", "limitations": ["L1"]},
    ],
    "evidence": [{"id": "E1", "description": "Only the ratio of the actual to the forecast matters, not their size."}],
    "limitations": [{"id": "L1", "affects": ["C2"], "statement": "Only positive actuals were studied."}],
    "references": [{"id": "B1", "target": "Huber 1964"}, {"id": "B2", "target": "Serfling 1980"},
                   {"id": "B3", "target": "Nobody cites this"}],
}


def kinds(found, category):
    return [c for c in found if c["category"] == category]


class TestCandidates(unittest.TestCase):
    def test_a_sentence_repeated_in_another_object(self):
        found = kinds(lean.candidates(DOC), "repeated")
        self.assertEqual([(c["where"], c["detail"].split(":")[0]) for c in found],
                         [("C1.summary", "nearly repeats E1.description")])

    def test_short_or_different_sentences_are_not_repeats(self):
        doc = copy.deepcopy(DOC)
        doc["evidence"][0]["description"] = "The proof divides the numerator and the denominator by the forecast."
        self.assertEqual(kinds(lean.candidates(doc), "repeated"), [])

    def test_a_claim_relating_twice_or_to_what_it_cites(self):
        found = kinds(lean.candidates(DOC), "duplicate_relation")
        self.assertEqual(sorted((c["where"], c["detail"]) for c in found), [
            ("C1.relations[0]", "B1 is already cited as support of C1"),
            ("C1.relations[2]", "relates to B2 again, as C1.relations[1] already does")])

    def test_unused_definitions_and_references(self):
        found = kinds(lean.candidates(DOC), "unused")
        self.assertEqual(sorted(c["where"] for c in found), ["B3", "D2"])

    def test_what_a_new_version_adds_to_published_objects(self):
        new = copy.deepcopy(DOC)
        new["claims"][0]["relations"].append({"type": "qualifies", "reference": "B3", "note": "An aside."})
        new["claims"][1]["limitations"] = ["L1", "L2"]
        new["limitations"].append({"id": "L2", "affects": ["C2"], "statement": "The test sets are independent."})
        new["definitions"][0]["definition"] += " Huber's loss is a different one: quadratic near 0 and linear far out."
        new["claims"].append({"id": "C3", "statement": "A new claim of the new version, with its own new sentences."})
        found = kinds(lean.candidates(new, DOC), "added")
        self.assertEqual(sorted(c["where"] for c in found), ["C1.relations[3]", "C2.limitations", "D1.definition"])
        self.assertIn("Huber's loss", next(c["text"] for c in found if c["where"] == "D1.definition"))

    def test_a_sentence_set_differently_is_not_an_addition(self):
        new = copy.deepcopy(DOC)
        new["claims"][1]["statement"] = "Its expected value has\na minimiser."
        self.assertEqual(kinds(lean.candidates(new, DOC), "added"), [])

    def test_a_rewritten_field_is_one_candidate(self):
        new = copy.deepcopy(DOC)
        new["claims"][1]["statement"] = "The target lies in one group. No forecast in the gap is the target."
        found = kinds(lean.candidates(new, DOC), "added")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["detail"].startswith("rewritten: 2 of its 2 sentences are new"))


class TestCommand(unittest.TestCase):
    def run_cli(self, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "paper.claimset.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(DOC, fh)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(["lean", path, *extra])
        return code, buf.getvalue()

    def test_the_list_and_the_next_step(self):
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("[unused] B3", out)
        self.assertIn("different agent than the one that wrote the claimset", out)

    def test_the_brief_for_the_reviewing_agent(self):
        code, out = self.run_cli("--prompt")
        self.assertEqual(code, 0)
        for phrase in ("as a reader who did not write it", "Do not edit the file", "unrequested", "The\nguarantor decides"):
            self.assertIn(phrase, out)
        self.assertIn("[duplicate_relation] C1.relations[2]", out)

    def test_json(self):
        code, out = self.run_cli("--json")
        self.assertEqual({c["category"] for c in json.loads(out)}, {"repeated", "duplicate_relation", "unused"})


if __name__ == "__main__":
    unittest.main()

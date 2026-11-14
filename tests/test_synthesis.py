"""Spec v0.43: novelty `synthesis`, a claim stating what earlier work establishes, as the paper reads it (rule 98);
`claimset migrate` lists claims that extend the very work they cite."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.migrate import migrate  # noqa: E402
from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
REF = {"id": "B90", "target": "10.1198/jasa.2011.r10138", "id_type": "doi"}


def rules(report):
    return sorted({e["rule"] for e in report.errors})


def finding(d, cid="C90", **extra):
    """A supporting claim stating what Gneiting (2011) establishes."""
    d.setdefault("references", []).append(REF)
    c = {"id": cid, "statement": "Squared error is a consistent scoring function for the mean.",
         "type": "methodological", "role": "supporting", "novelty": "synthesis",
         "support": [{"kind": "cited", "reference": "B90", "locator": "Theorem 3.1"}],
         "scope": {"data_type": "point forecasts"}}
    c.update(extra)
    d["claims"].append(c)
    principal = next(x for x in d["claims"] if x.get("role") == "principal")
    principal.setdefault("depends_on", []).append(cid)
    return c


class TestRule98(unittest.TestCase):
    def test_a_synthesis_cites_what_it_states(self):
        d = copy.deepcopy(NATIVE)
        finding(d)
        self.assertEqual(rules(validate(d)), [])

    def test_a_synthesis_without_cited_work_is_refused(self):
        d = copy.deepcopy(NATIVE)
        finding(d, support=[{"kind": "consensus"}])
        self.assertIn("98", rules(validate(d)))

    def test_a_synthesis_may_rest_on_claims_that_cite(self):
        d = copy.deepcopy(NATIVE)
        finding(d)
        d.setdefault("warrants", []).append({"id": "W90", "reasoning": "deductive", "premises": ["C90"],
                                             "text": "Squared error is consistent for the mean, so it ranks "
                                                     "forecasts of the mean by how close they come to it."})
        rule = {"id": "C91", "statement": "Point forecasts of the mean should be evaluated with squared error.",
                "type": "methodological", "role": "supporting", "novelty": "synthesis",
                "support": [{"kind": "argument", "warrant": "W90"}], "depends_on": ["C90"],
                "scope": {"data_type": "point forecasts"}}
        d["claims"].append(rule)
        next(x for x in d["claims"] if x.get("role") == "principal")["depends_on"].append("C91")
        self.assertNotIn("98", rules(validate(d)))
        rule["depends_on"] = []
        rule["support"] = [{"kind": "argument", "warrant": "W90"}]
        self.assertIn("98", rules(validate(d)))

    def test_a_principal_claim_may_be_a_synthesis(self):
        d = copy.deepcopy(NATIVE)
        c = finding(d, role="principal")
        c["about"] = {"subject": "squared error", "relation": "is consistent for", "object": "the mean"}
        self.assertNotIn("84", rules(validate(d)))

    def test_a_file_of_v0_42_keeps_its_rules(self):
        d = copy.deepcopy(NATIVE)
        d["schema_version"] = "0.42"
        finding(d)
        self.assertIn("1", rules(validate(d)))                   # synthesis is not a value of v0.42


class TestMigrate(unittest.TestCase):
    def test_an_extension_of_its_own_evidence_is_listed(self):
        d = copy.deepcopy(NATIVE)
        d["schema_version"] = "0.42"
        c = finding(d, novelty="extension")
        c["relations"] = [{"type": "extends", "reference": "B90", "note": "Gneiting (2011) shows it."}]
        out, done, todo = migrate(d)
        self.assertEqual(out["schema_version"], "0.43")
        self.assertTrue(any("C90" in t and "synthesis" in t for t in todo), todo)
        c["relations"] = [{"type": "extends", "target": "10.1/other", "id_type": "doi", "note": "Another work."}]
        self.assertFalse(any("C90" in t and "synthesis" in t for t in migrate(d)[2]))


if __name__ == "__main__":
    unittest.main()

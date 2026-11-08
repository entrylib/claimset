"""Claim bundles (spec v0.39 §2.3): one claim with what it rests on, as JSON and as a reading view."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.claim import claim_bundle, render_claim  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))


def ids(b, lst):
    return [x["id"] for x in b.get(lst, [])]


class TestBundle(unittest.TestCase):
    def test_what_a_claim_rests_on(self):
        b = claim_bundle(NATIVE, "C2")
        self.assertEqual(b["bundle_of"], "C2")
        self.assertEqual(ids(b, "claims"), ["C2", "C1", "C3"])          # the claim first, then its assumptions
        self.assertEqual(ids(b, "definitions"), ["D1", "D2", "D3", "D4", "D5"])
        self.assertEqual(ids(b, "evidence"), ["E1"])
        self.assertEqual(ids(b, "limitations"), ["L1"])
        self.assertEqual(b["paper"]["title"], NATIVE["paper"]["title"])
        self.assertNotIn("contributors", b)

    def test_only_what_is_cited(self):
        d = copy.deepcopy(NATIVE)
        d["definitions"].append({"id": "D99", "term": "unused", "kind": "concept", "definition": "Not cited."})
        d["limitations"].append({"id": "L99", "category": "other", "statement": "On another claim.",
                                 "affects": ["C3"], "impact": "limits_scope", "mitigation": "none"})
        b = claim_bundle(d, "C2")
        self.assertNotIn("D99", ids(b, "definitions"))
        self.assertNotIn("L99", ids(b, "limitations"))

    def test_a_relation_does_not_pull_in_its_target(self):
        d = copy.deepcopy(NATIVE)
        c2 = next(c for c in d["claims"] if c["id"] == "C2")
        d["claims"].append({**copy.deepcopy(c2), "id": "C9", "assumptions": [], "role": "secondary"})
        c2["relations"] = [{"type": "supports", "target": "C9"}]
        b = claim_bundle(d, "C2")
        self.assertNotIn("C9", ids(b, "claims"))
        self.assertEqual(b["claims"][0]["relations"], [{"type": "supports", "target": "C9"}])

    def test_unknown_claim(self):
        with self.assertRaises(KeyError):
            claim_bundle(NATIVE, "C99")
        with self.assertRaises(KeyError):
            claim_bundle(NATIVE, "D1")


class TestReadingView(unittest.TestCase):
    def test_render_claim(self):
        text = render_claim(NATIVE, "C2")
        self.assertTrue(text.startswith("CLAIM C2 of " + NATIVE["paper"]["title"]))
        self.assertIn("\nCLAIMS\nC2 [", text)
        self.assertIn("\nEVIDENCE\nE1 [", text)
        self.assertNotIn("CLAIMSET ", text)

    def test_cli(self):
        f = str(ROOT / "examples" / "submission-native.json")
        run = lambda *a: subprocess.run([sys.executable, "-m", "claimset", "render", f, *a], capture_output=True,  # noqa: E731
                                        text=True, env={"PYTHONPATH": str(ROOT / "src")})
        self.assertTrue(run("--claim", "C2").stdout.startswith("CLAIM C2 of"))
        self.assertEqual(json.loads(run("--claim", "C2", "--bundle").stdout)["bundle_of"], "C2")
        out = run("--claim", "C99")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no claim C99", out.stderr)


if __name__ == "__main__":
    unittest.main()

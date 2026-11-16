"""Contributors of a claimset its authors converted from their published paper are listed in the byline's order,
agents last (claimset spec v0.44 §3.11, Order; warning 51). From a claimset that put its guarantor, the paper's last
author, first and listed its agent before the authors."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
AGENT = next(c for c in NATIVE["contributors"] if c["type"] == "agent")
GUARANTOR = next(c for c in NATIVE["contributors"] if "guarantor" in c["positions"])


def doc(order, published=True):
    d = copy.deepcopy(NATIVE)
    coauthor = {"id": "P8", "type": "human", "name": "Ada Okafor", "positions": ["coauthor", "contributor"]}
    by = {"agent": copy.deepcopy(AGENT), "guarantor": copy.deepcopy(GUARANTOR), "coauthor": coauthor}
    d["contributors"] = [by[k] for k in order] + [c for c in d["contributors"]
                                                  if c["id"] not in (AGENT["id"], GUARANTOR["id"])]
    if published:
        d["paper"]["published_as"] = {"id_type": "doi", "id": "10.1016/j.ijforecast.2025.01.001"}
    return d


def w51(d):
    return [w for w in validate(d).warnings if w["rule"] == "W51"]


class TestContributorOrder(unittest.TestCase):
    def test_an_agent_before_an_author_is_flagged(self):
        for order in (["agent", "guarantor", "coauthor"], ["coauthor", "agent", "guarantor"]):
            found = w51(doc(order))
            self.assertEqual(len(found), 1, order)
            self.assertEqual(found[0]["where"], f"contributors:{AGENT['id']}")

    def test_authors_first_then_the_agent_pass(self):
        for order in (["coauthor", "guarantor", "agent"], ["guarantor", "coauthor", "agent"]):
            self.assertEqual(w51(doc(order)), [], order)

    def test_only_a_claimset_restating_a_published_paper(self):
        self.assertEqual(w51(doc(["agent", "guarantor", "coauthor"], published=False)), [])
        self.assertEqual(w51(NATIVE), [])


if __name__ == "__main__":
    unittest.main()

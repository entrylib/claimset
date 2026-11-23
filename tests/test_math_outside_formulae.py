"""Mathematics is written in LaTeX between dollar signs (claimset v0.44 as amended on 2026-11-23, §8 rule 6, warning
64): written as text (`σ_1²`, `a1>=1`, `h \\to \\infty`), it is shown raw by every reader that sets mathematics, and
nothing had warned. Code is not mathematics: code spans and blocks are skipped, and programming operators
(`!=`, `>=`, `==`) are never warned."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import math_as_text, validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))


def warned(d):
    return {w["where"] for w in validate(d).warnings if w["rule"] == "W64"}


class TestMathOutsideFormulae(unittest.TestCase):
    def test_formulae_and_plain_text_pass(self):
        for text in ("A mean $\\mu$ and $$\\sigma_h^2 = \\sigma_1^2 \\left(1 + \\sum_j c_j^2\\right)$$ on its own line.",
                     "The estimator [[D2:MSE_1]] and ETS(A,N,N), AR(1), M4 and GPT-4o.",  # marker text is plain
                     "The field published_as and the file run_1.csv.",                   # snake_case is not a subscript
                     "A layer 5 μm thick and a 10 Ω resistor; the word λόγος.",          # units and Greek words
                     "Code `x_1 >= 0` and https://example.org/a_b^c, and a price of \\$5.",
                     "No mathematics at all.",
                     "A bias of −0.002 and the (−1)-median.",                           # a negative number
                     "The script keeps rows where x != 0 and n >= 30, and stops when i == n.",  # operators of code
                     "Filtered with `df[df$h != 1]`, then\n```r\nfit <- adam(y^2, h = 12)\nif (a_1 != b) x[i]^2\n```\ndone."):
            self.assertIsNone(math_as_text(text), text)
        self.assertEqual(warned(copy.deepcopy(EXAMPLE)), set())

    def test_mathematics_as_text_is_found(self):
        for text in ("as h \\to \\infty", "equals s_1² times", "with α = 0.6",
                     "the polynomial lam^2-(2-a0)lam", "the coefficient c_{h-j}", "the residual x_t", "Σ ĉ_j",
                     "the bound \\le 1"):
            self.assertIsNotNone(math_as_text(text), text)

    def test_each_text_is_warned_where_it_is(self):
        d = copy.deepcopy(EXAMPLE)
        c, e = d["claims"][0], d["evidence"][0]
        c["statement"] = "The forecast grows when α > 1."
        c["summary"] = "It grows as h \\to \\infty."
        c.setdefault("scope", {})["conditions"] = ["T \\in \\{20, 50\\}"]
        c["checks"] = [{"by": d["contributors"][0]["id"], "outcome": "confirmed", "extent": "full",
                        "notes": "Derived s_1² (1 + Σ c_j²) by hand."}]
        e["steps"] = [{"id": "S1", "statement": "\\eta_{t+h|t} = y_{t+h} - \\mu_{t+h|t}", "by": [], "rule": "definition"}]
        d["paper"]["published_as"] = {"id_type": "doi", "id": "10.1000/x", "corrections": [
            {"kind": "misprint", "field": f"{c['id']}.statement", "where": "Section 2",
             "printed": "log GV = log s_1²", "recorded": "$\\log GV = h \\log s_1^2$",
             "reason": "The determinant of an $h \\times h$ matrix.", "found_by": d["contributors"][0]["id"]}]}
        w = warned(d)
        cid = c["id"]
        for where in (f"claims:{cid}.statement", f"claims:{cid}.summary", f"claims:{cid}.scope.conditions[0]",
                      f"claims:{cid}.checks[0].notes", f"evidence:{e['id']}.steps[0].statement",
                      "paper.published_as.corrections[0].printed"):
            self.assertIn(where, w)
        self.assertNotIn("paper.published_as.corrections[0].recorded", w)
        self.assertNotIn("paper.published_as.corrections[0].reason", w)
        d2 = copy.deepcopy(EXAMPLE)
        d2["claims"][0]["statement"] = "The forecast grows when α > 1."
        self.assertEqual([x for x in validate(d2).errors], [])           # a warning: the file stays valid


if __name__ == "__main__":
    unittest.main()

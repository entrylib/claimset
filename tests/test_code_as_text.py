"""Code is written as code (claimset v0.44 as amended on 2026-11-23, §8 rule 12, warning 65): in backticks in a
sentence, or in a fenced block for several lines. A function named in prose (`whose Arima() function`) was shown as
words, and nothing had warned."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.validate import code_as_text, validate  # noqa: E402

EXAMPLE = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))


def warned(d):
    return {w["where"] for w in validate(d).warnings if w["rule"] == "W65"}


class TestCodeAsText(unittest.TestCase):
    def test_code_as_code_and_plain_text_pass(self):
        for text in ("Fitted with `auto.arima()` and `adam(y, h = 12)` from the smooth package.",
                     "Run as\n```r\nfit <- adam(y, h = 12)\nif (a != b) x <- 1\n```\nonce.",
                     "Models ETS(A,N,N), ARIMA(0,1,1) and AR(1); a function $f(x = 1)$ and S(h = 1).",
                     "Hyndman et al. (2008), version 3.2.0 (2023), the forecast R package, MSE_h (h=60).",
                     "Values with x < -1 and y >= 2, a cost <= 5, and a = b.",
                     "See https://example.org/f(x)?a==b for more.",
                     "No code at all."):
            self.assertIsNone(code_as_text(text), text)
        self.assertEqual(warned(copy.deepcopy(EXAMPLE)), set())

    def test_code_as_prose_is_found(self):
        for text in ("whose Arima() function fits", "fitted with adam(y, h = 12) in R", "np.mean(x) over runs",
                     "auto.arima(y) selects", "smooth::adam fits", "then x <- 1", "rows where x != 0",
                     "stops when i == n", "if a && b", "if a || b"):
            self.assertIsNotNone(code_as_text(text), text)

    def test_each_text_is_warned_where_it_is(self):
        d = copy.deepcopy(EXAMPLE)
        c = d["claims"][0]
        c["statement"] = c["statement"] + " It was fitted with adam() of smooth."
        c["summary"] = "Fitted by forecast::tbats."
        d["artefacts"][0]["description"] = "The package, whose auto.arima() function selects the models."
        d["definitions"][0]["definition"] = "Computed by `mase()` of the package."   # in backticks: not warned
        w = warned(d)
        self.assertIn(f"claims:{c['id']}.statement", w)
        self.assertIn(f"claims:{c['id']}.summary", w)
        self.assertIn(f"artefacts:{d['artefacts'][0]['id']}.description", w)
        self.assertNotIn(f"definitions:{d['definitions'][0]['id']}.definition", w)
        self.assertEqual(validate(d).errors, [])                         # a warning: the file stays valid


if __name__ == "__main__":
    unittest.main()

"""What a reader finds their way by (claimset spec v0.44 as amended on 2026-11-17): a claim's name (rule 101) and
summary (rule 102, warning 52), a definition's symbol (rule 103, warning 53), the results of a relation within the
paper (rule 104), the longer paper summary (warning 45), and the reading view."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.render import render  # noqa: E402
from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
V043 = json.loads((ROOT / "tests" / "compat" / "0.43" / "submission-native.json").read_text(encoding="utf-8")) \
    if (ROOT / "tests" / "compat" / "0.43" / "submission-native.json").exists() else None


def doc():
    return copy.deepcopy(NATIVE)


def claim(d, cid):
    return next(c for c in d["claims"] if c["id"] == cid)


def definition(d, did):
    return next(x for x in d["definitions"] if x["id"] == did)


def rules(report):
    return sorted({e["rule"] for e in report.errors})


def warned(report, rule):
    return [w for w in report.warnings if w["rule"] == rule]


class TestRule101Name(unittest.TestCase):
    def test_a_name(self):
        d = doc()
        claim(d, "C2")["name"] = "Method M beats the seasonal naive method"
        claim(d, "C1")["name"] = "Retail sales are seasonal"
        self.assertEqual(validate(d).errors, [])

    def test_broken(self):
        for name in ("", "   ", 3, None, ["Method M wins"], "Method M wins\non retail sales", "x" * 101):
            d = doc()
            claim(d, "C2")["name"] = name
            self.assertEqual(rules(validate(d)), ["101"], repr(name))

    def test_a_hundred_characters(self):
        d = doc()
        claim(d, "C2")["name"] = "x" * 100
        self.assertEqual(validate(d).errors, [])

    def test_two_claims_with_one_name(self):
        d = doc()
        claim(d, "C2")["name"] = "Method M wins"
        claim(d, "C1")["name"] = " method m  wins "
        r = validate(d)
        self.assertEqual(rules(r), ["101"])
        self.assertEqual(len(r.errors), 1)
        self.assertIn("same name", r.errors[0]["message"])


class TestRule102Summary(unittest.TestCase):
    def test_a_summary(self):
        d = doc()
        claim(d, "C2")["summary"] = "The method forecasts retail sales better than repeating last year's value."
        r = validate(d)
        self.assertEqual(r.errors, [])
        self.assertEqual(warned(r, "W52"), [])

    def test_broken(self):
        for text in ("", "  ", 7, None, ["The method wins."], {"text": "The method wins."}):
            d = doc()
            claim(d, "C2")["summary"] = text
            self.assertEqual(rules(validate(d)), ["102"], repr(text))

    def test_warning_52_more_than_fifty_words(self):
        d = doc()
        claim(d, "C2")["summary"] = " ".join(["word"] * 50)
        self.assertEqual(warned(validate(d), "W52"), [])
        claim(d, "C2")["summary"] = " ".join(["word"] * 51)
        r = validate(d)
        self.assertEqual(r.errors, [])
        self.assertEqual([w["where"] for w in warned(r, "W52")], ["claims:C2.summary"])


class TestRule103Symbol(unittest.TestCase):
    def test_a_symbol(self):
        for sym in ("$s$", "$s(y,f)$", "$\\sigma$", " $\\hat m_n$ "):
            d = doc()
            definition(d, "D1")["symbol"] = sym
            r = validate(d)
            self.assertEqual(r.errors, [], sym)
            self.assertEqual(warned(r, "W53"), [])

    def test_broken(self):
        for sym in ("", "s", "s(y,f)", "$$s$$", "$s$ and $t$", "the skill $s$", "$ s$", 4, None, ["$s$"]):
            d = doc()
            definition(d, "D1")["symbol"] = sym
            self.assertEqual(rules(validate(d)), ["103"], repr(sym))

    def test_warning_53_two_definitions_with_one_symbol(self):
        d = doc()
        definition(d, "D1")["symbol"] = "$s(y,f)$"
        definition(d, "D2")["symbol"] = "$s(y, f)$"
        r = validate(d)
        self.assertEqual(r.errors, [])
        self.assertEqual([w["where"] for w in warned(r, "W53")], ["definitions:D2.symbol"])
        definition(d, "D2")["symbol"] = "$t(y, f)$"
        self.assertEqual(warned(validate(d), "W53"), [])


def related():
    """The native example with a second result of its own evidence, whose claim C4 supports C2 through it."""
    d = doc()
    e = next(x for x in d["evidence"] if x["id"] == "E1")
    e["tables"] = [{"id": "T1", "description": "Reduction of the error by horizon", "row_labels": ["horizon"],
                    "columns": ["relative MASE reduction"],
                    "rows": [{"id": "r1", "label": ["1 to 6 months"], "values": [0.09]},
                             {"id": "r2", "label": ["7 to 12 months"], "values": [0.07]}]}]
    c2 = claim(d, "C2")
    c4 = {k: copy.deepcopy(v) for k, v in c2.items() if k in ("type", "support", "provenance", "assessments")}
    c4.update({"id": "C4", "role": "secondary", "novelty": c2.get("novelty", "no_prior_found"),
               "statement": "The improvement of [[D2:method M]] in [[D1:forecast skill]] is larger at horizons of 1 to "
                            "6 months than at horizons of 7 to 12 months.",
               "relations": [{"type": "supports", "target": "C2", "id_type": "local",
                              "results": ["E1.T1.r1", "E1.T1.r2"],
                              "note": "The improvement holds in both halves of the horizons."}]})
    d["claims"].append(c4)
    return d


def relation(d):
    return claim(d, "C4")["relations"][0]


class TestRule104RelationResults(unittest.TestCase):
    def test_results_of_the_claims_own_evidence(self):
        d = related()
        self.assertEqual(validate(d).errors, [])
        for results in (["E1.T1"], ["E1.T1.r2"], ["E1.T1", "E1.T1.r1"]):
            relation(d)["results"] = results
            self.assertEqual(validate(d).errors, [], results)

    def test_broken(self):
        for results in ([], "E1.T1.r1", ["E1.T1.r9"], ["E1.T2"], ["E9.T1.r1"], ["T1.r1"], [3], [None], {"a": 1}):
            d = related()
            relation(d)["results"] = results
            self.assertEqual(rules(validate(d)), ["104"], repr(results))

    def test_only_within_the_paper(self):
        d = related()
        d.setdefault("references", []).append({"id": "B9", "target": "10.1016/j.ijforecast.2006.03.001",
                                               "id_type": "doi"})
        claim(d, "C4")["relations"].append({"type": "supports", "reference": "B9", "results": ["E1.T1.r1"]})
        self.assertEqual(rules(validate(d)), ["104"])
        d = related()
        claim(d, "C4")["relations"].append({"type": "supports", "target": "10.1016/j.ijforecast.2006.03.001",
                                            "id_type": "doi", "results": ["E1.T1.r1"]})
        self.assertEqual(rules(validate(d)), ["104"])

    def test_evidence_of_another_claim(self):
        d = related()
        e2 = copy.deepcopy(next(x for x in d["evidence"] if x["id"] == "E1"))
        e2["id"] = "E2"
        d["evidence"].append(e2)
        relation(d)["results"] = ["E2.T1.r1"]          # exists, but no support entry of C4 points to E2
        self.assertEqual(rules(validate(d)), ["104"])


class TestWarning45(unittest.TestCase):
    def test_two_hundred_and_fifty_words(self):
        d = doc()
        d["paper"]["summary"] = " ".join(["word"] * 250)
        self.assertEqual(warned(validate(d), "W45"), [])
        d["paper"]["summary"] = " ".join(["word"] * 251)
        r = validate(d)
        self.assertEqual(r.errors, [])
        self.assertEqual(len(warned(r, "W45")), 1)

    @unittest.skipIf(V043 is None, "no v0.43 fixture")
    def test_an_earlier_version_keeps_its_limit(self):
        d = copy.deepcopy(V043)
        d["paper"]["summary"] = " ".join(["word"] * 151)
        self.assertEqual(len(warned(validate(d), "W45")), 1)


class TestReadingView(unittest.TestCase):
    def test_names_summaries_symbols_and_results(self):
        d = related()
        claim(d, "C2")["name"] = "Method M beats the seasonal naive method"
        claim(d, "C2")["summary"] = "The method forecasts retail sales better than repeating last year's value."
        definition(d, "D1")["symbol"] = "$k$"
        self.assertEqual(validate(d).errors, [])
        text = render(d)
        self.assertIn('C2 "Method M beats the seasonal naive method" [', text)
        self.assertIn("  in plain words: The method forecasts retail sales better than repeating last year's value.",
                      text)
        self.assertIn("D1 [variable] forecast skill ($k$): ", text)
        self.assertIn("  supports C2, by E1.T1.r1, E1.T1.r2: The improvement holds in both halves of the horizons.",
                      text)

    def test_a_file_without_them_reads_as_before(self):
        text = render(doc())
        self.assertNotIn("in plain words", text)
        self.assertIn("\nC2 [", text)


class TestWrongTypes(unittest.TestCase):
    def test_nothing_crashes(self):
        for bad in (None, 3, "x", [], {}, [[]], [{}]):
            d = related()
            claim(d, "C2")["name"] = bad
            claim(d, "C2")["summary"] = bad
            definition(d, "D1")["symbol"] = bad
            relation(d)["results"] = bad
            render(d)                                   # the reading view shows what it is given
            validate(d)
            claim(d, "C4")["support"] = bad             # and a claim whose support is no list names no evidence
            relation(d)["results"] = ["E1.T1.r1"]
            validate(d)


if __name__ == "__main__":
    unittest.main()

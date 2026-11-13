"""The review extension (spec/extensions/review-v0.1.md): its claimset rules and warnings, its lab events, flags,
verification and export."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.lab import sources  # noqa: E402
from claimset.lab.core import LabError, verify  # noqa: E402
from claimset.lab.export import export  # noqa: E402
from claimset.lab.review import parse_work  # noqa: E402
from claimset.validate import validate  # noqa: E402

from test_lab import LabCase  # noqa: E402

BASE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))


def target(d):
    """The claim the review blocks are on: the example's first claim that is not an assumption."""
    return next(c for c in d["claims"] if all(s.get("kind") != "assumption" for s in c["support"]))


def reviewed():
    """The native example as a review: a reference read in full, a cited claim with its extract, a protocol."""
    d = copy.deepcopy(BASE)
    d["extensions"] = dict(d.get("extensions") or {}, review="0.1")
    d.setdefault("references", []).append({"id": "B90", "target": "10.1198/jasa.2011.r10138", "id_type": "doi",
                                          "ext": {"review": {"read": "full_text", "version": "preprint",
                                                             "checked_on": "2026-11-13"}}})
    c = target(d)
    c["support"].append({"kind": "cited", "reference": "B90", "locator": "Section 5"})
    c["ext"] = {"review": {"kind": "summary", "extracts": [
        {"reference": "B90", "locator": "Section 5", "exact": "the squared error scoring function is consistent"}]}}
    d["paper"]["ext"] = {"review": {
        "protocol": {"sources": ["Google Scholar"], "include": ["methodological papers"]},
        "searches": [{"source": "Google Scholar", "query": "consistent scoring", "date": "2026-11-13", "results": 12}],
        "flow": {"identified": 12, "screened": 12, "excluded_screening": 10, "assessed": 2, "included": 1}}}
    return d


def rules(report):
    return sorted({e["rule"] for e in report.errors})


def warnings(report):
    return sorted({w["rule"] for w in report.warnings if w["rule"].startswith("review.")})


def ref(d):
    return next(r for r in d["references"] if r["id"] == "B90")


class TestClaimsetRules(unittest.TestCase):
    def test_a_review_is_valid_and_quiet(self):
        r = validate(reviewed())
        self.assertEqual(rules(r), [])
        self.assertEqual(warnings(r), [])

    def test_rule_1_blocks_and_fields(self):
        d = reviewed()
        d["paper"]["ext"]["review"]["notes"] = "x"
        self.assertIn("review.1", rules(validate(d)))
        d = reviewed()
        d["definitions"][0].setdefault("ext", {})["review"] = {"read": "full_text"}
        r = validate(d)
        self.assertTrue({"review.1", "R80"} & set(rules(r)) or rules(r), r.errors)

    def test_rule_2_how_a_reference_was_read(self):
        for field, value in (("read", "skimmed"), ("version", "draft"), ("checked_on", "13/11/2026"),
                             ("artefact", "A99"), ("via", "")):
            d = reviewed()
            ref(d)["ext"]["review"][field] = value
            self.assertIn("review.2", rules(validate(d)), field)
        d = reviewed()
        del ref(d)["ext"]["review"]["read"]
        self.assertIn("review.2", rules(validate(d)))

    def test_rule_3_extracts(self):
        d = reviewed()
        target(d)["ext"]["review"]["extracts"][0]["reference"] = "B1"       # not a cited support of the claim
        self.assertIn("review.3", rules(validate(d)))
        d = reviewed()
        del target(d)["ext"]["review"]["extracts"][0]["exact"]
        self.assertIn("review.3", rules(validate(d)))
        d = reviewed()
        target(d)["ext"]["review"]["extracts"][0].update(start=9, end=3)
        self.assertIn("review.3", rules(validate(d)))
        d = reviewed()
        target(d)["ext"]["review"]["extracts"] = []
        self.assertIn("review.3", rules(validate(d)))
        d = reviewed()
        target(d)["ext"]["review"]["extracts"][0] = {"reference": "B90", "text": "as read in the abstract"}
        self.assertEqual(rules(validate(d)), [])

    def test_rule_4_kind_and_contested_by(self):
        d = reviewed()
        target(d)["ext"]["review"]["kind"] = "opinion"
        self.assertIn("review.4", rules(validate(d)))
        d = reviewed()
        target(d)["ext"]["review"]["contested_by"] = [{"reference": "B99", "note": "Says the opposite."}]
        self.assertIn("review.4", rules(validate(d)))
        d = reviewed()
        target(d)["ext"]["review"]["contested_by"] = [{"reference": "B90", "note": "Qualifies it."}]
        self.assertEqual(rules(validate(d)), [])

    def test_rule_5_protocol_searches_flow_flags(self):
        d = reviewed()
        d["paper"]["ext"]["review"]["protocol"]["sources"] = []
        self.assertIn("review.5", rules(validate(d)))
        d = reviewed()
        d["paper"]["ext"]["review"]["searches"][0]["results"] = -1
        self.assertIn("review.5", rules(validate(d)))
        d = reviewed()
        d["paper"]["ext"]["review"]["flow"]["included"] = 5            # more included than assessed
        self.assertIn("review.5", rules(validate(d)))
        d = reviewed()
        d["paper"]["ext"]["review"]["flow"]["excluded_full_text"] = {"off topic": 1}
        self.assertEqual(rules(validate(d)), [])
        d = reviewed()
        d["paper"]["ext"]["review"]["flags"] = ["late"]
        self.assertIn("review.5", rules(validate(d)))

    def test_warning_1_only_abstracts(self):
        d = reviewed()
        ref(d)["ext"]["review"]["read"] = "abstract"
        r = validate(d)
        self.assertEqual(rules(r), [])
        self.assertIn("review.w1", warnings(r))

    def test_warning_2_no_extract(self):
        d = reviewed()
        del target(d)["ext"]
        self.assertIn("review.w2", warnings(validate(d)))

    def test_warning_3_no_searches(self):
        d = reviewed()
        del d["paper"]["ext"]["review"]["searches"]
        self.assertIn("review.w3", warnings(validate(d)))

    def test_no_warning_3_for_background_in_a_study(self):
        """A study that quotes the background its findings rest on is not a review: no searches are asked of it."""
        d = reviewed()
        del d["paper"]["ext"]["review"]["searches"]
        premise = target(d)
        principal = copy.deepcopy(premise)                # a finding of the study, resting on the quoted premise
        principal.pop("ext", None)
        principal.update(id="C90", support=[s for s in premise["support"] if s.get("kind") != "cited"],
                         depends_on=[premise["id"]])
        premise["role"] = "supporting"
        d["claims"].append(principal)
        self.assertNotIn("review.w3", warnings(validate(d)))

    def test_warning_4_read_not_said(self):
        d = reviewed()
        d["references"].append({"id": "B91", "target": "10.1/x", "id_type": "doi"})
        target(d)["support"].append({"kind": "cited", "reference": "B91"})
        self.assertIn("review.w4", warnings(validate(d)))


TEXT = ("Making and evaluating point forecasts. As regards the most commonly used scoring functions, "
        "the squared error scoring function is consistent for the mean, and the absolute error scoring "
        "function for the median.")


class TestLab(LabCase):
    def setUp(self):
        super().setUp()
        self.paper = Path(self.tmp.name) / "gneiting.txt"
        self.paper.write_text(TEXT, encoding="utf-8")
        self.h = self.hyp("Point forecasts of the mean should be evaluated with squared error.")

    def declare(self):
        if "review" not in self.lab.state().extensions:
            self.lab.append("extension", {"name": "review", "version": "0.1"}, by=self.agent)

    def protocol(self):
        self.declare()
        return self.lab.append("protocol", {"question": self.q, "sources": ["Google Scholar"],
                                            "include": ["methodological papers"]}, by=self.agent)["id"]

    def search(self, protocol=None):
        self.declare()
        return self.lab.append("search", {"source": "Google Scholar", "query": "consistent scoring", "results": 12,
                                          "protocol": protocol}, by=self.agent)["id"]

    def screen(self, work="doi:10.1198/jasa.2011.r10138", **kw):
        self.declare()
        body = dict({"work": parse_work(work), "stage": "full_text", "decision": "include", "read": "full_text"}, **kw)
        return self.lab.append("screening", {k: v for k, v in body.items() if v is not None}, by=self.agent)["id"]

    def test_events_need_the_extension_declared(self):
        self.assertRefused("L30", "search", {"source": "S", "query": "q", "results": 1})

    def test_L1_protocol(self):
        self.declare()
        self.assertRefused("review.L1", "protocol", {"sources": [], "include": ["x"]})
        self.assertRefused("review.L1", "protocol", {"sources": ["S"]})
        self.assertTrue(self.protocol().startswith("PT"))

    def test_L2_search(self):
        self.declare()
        self.assertRefused("review.L2", "search", {"source": "S", "query": "q", "results": -2})
        self.assertRefused("review.L2", "search", {"source": "S", "query": " ", "results": 2})
        self.assertRefused("review.L2", "search", {"source": "S", "query": "q", "results": 2, "at": "yesterday"})
        self.assertTrue(self.search().startswith("SE"))

    def test_L3_screening(self):
        self.declare()
        work = parse_work("doi:10.1/x")
        self.assertRefused("review.L3", "screening", {"work": work, "stage": "full_text", "decision": "exclude"})
        self.assertRefused("review.L3", "screening", {"work": work, "stage": "full_text", "decision": "include"})
        self.assertRefused("review.L3", "screening", {"work": {"target": "x", "id_type": "isbn13"},
                                                      "stage": "full_text", "decision": "exclude", "reason": "r"})
        self.assertRefused("review.L3", "screening", {"work": work, "stage": "skim", "decision": "exclude",
                                                      "reason": "r"})
        self.assertTrue(self.screen("doi:10.1/x", decision="exclude", read=None, reason="off topic").startswith("SC"))

    def test_parse_work(self):
        self.assertEqual(parse_work("doi:10.1/X"), {"target": "10.1/X", "id_type": "doi"})
        self.assertEqual(parse_work("https://a.org/p"), {"target": "https://a.org/p", "id_type": "url"})
        with self.assertRaises(LabError):
            parse_work("10.1/x")

    def test_L4_extract(self):
        sr = sources.capture(self.lab, self.agent, file=str(self.paper), url="https://arxiv.org/abs/0912.0902")["id"]
        self.declare()
        work = parse_work("doi:10.1198/jasa.2011.r10138")
        quote = sources.quote(self.lab, self.lab.state().latest(sr), "squared error scoring function is consistent")
        body = {"work": work, "for": [self.h], "source": sr, "locator": "Section 5",
                "quote": {k: quote[k] for k in ("exact", "prefix", "suffix", "start", "end")}}
        self.assertRefused("review.L4", "extract", body)            # not screened in yet
        self.screen(source=sr)
        self.assertRefused("review.L4", "extract", dict(body, text="also text"))
        self.assertRefused("review.L4", "extract", {"work": work, "for": [self.h]})
        xt = self.lab.append("extract", body, by=self.agent)["id"]
        self.assertTrue(xt.startswith("XT"))
        self.assertEqual(verify(self.lab)["errors"], [])
        self.screen(decision="exclude", read=None, reason="superseded by the published version")
        self.assertRefused("review.L4", "extract", body)            # excluded since

    def test_flags(self):
        from claimset.lab.review import flags
        self.search()
        self.assertEqual(flags(self.lab.state()), ["searched_before_protocol"])
        pt = self.protocol()
        self.lab.append("protocol", {"sources": ["Google Scholar", "Scopus"], "include": ["methodological papers"]},
                        by=self.agent, supersedes=pt)
        self.assertEqual(flags(self.lab.state()), ["searched_before_protocol", "protocol_changed_after_search"])

    def test_export(self):
        sr = sources.capture(self.lab, self.agent, file=str(self.paper), url="https://arxiv.org/abs/0912.0902")["id"]
        pt = self.protocol()
        se = self.search(pt)
        self.screen(source=sr, version="preprint", searches=[se])
        self.screen("doi:10.1/x", stage="title_abstract", decision="exclude", read=None, reason="off topic",
                    searches=[se])
        work = parse_work("doi:10.1198/jasa.2011.r10138")
        quote = sources.quote(self.lab, self.lab.state().latest(sr), "squared error scoring function is consistent")
        xt = self.lab.append("extract", {"work": work, "for": [self.h], "source": sr, "locator": "Section 5",
                                         "quote": {k: quote[k] for k in ("exact", "prefix", "suffix", "start", "end")}},
                             by=self.agent)["id"]
        self.lab.append("status", {"target": self.h, "to": "supported", "evidence": [xt],
                                   "rationale": "Gneiting (2011, Section 5)."}, by=self.agent)
        out = export(self.lab)
        d = out["draft"]
        self.assertEqual(d["extensions"].get("review"), "0.1")
        ref = next(r for r in d["references"] if r["target"] == "10.1198/jasa.2011.r10138")
        self.assertEqual(ref["ext"]["review"]["read"], "full_text")
        self.assertEqual(ref["ext"]["review"]["version"], "preprint")
        art = ref["ext"]["review"]["artefact"]
        self.assertEqual(next(a for a in d["artefacts"] if a["id"] == art)["reference"], ref["id"])
        self.assertFalse(any(r["id_type"] == "url" for r in d["references"]))   # the copy's page URL is not cited
        claim = d["claims"][0]
        self.assertIn({"kind": "cited", "reference": ref["id"], "locator": "Section 5"}, claim["support"])
        ex = claim["ext"]["review"]["extracts"][0]
        self.assertEqual(ex["exact"], "squared error scoring function is consistent")
        self.assertEqual((ex["artefact"], ex["lab_event"]), (art, xt))
        self.assertEqual(claim["ext"]["review"]["kind"], "recommendation")
        block = d["paper"]["ext"]["review"]
        self.assertEqual(block["protocol"]["sources"], ["Google Scholar"])
        self.assertEqual(block["searches"][0]["results"], 12)
        self.assertEqual(block["flow"], {"identified": 12, "screened": 1, "excluded_screening": 1, "assessed": 1,
                                         "included": 1})
        self.assertNotIn("flags", block)
        self.assertFalse(any(c["where"] == f"claims.{claim['id']}.support" for c in out["completion"]))
        report = validate(d)
        self.assertFalse([e for e in report.errors if e["rule"].startswith("review.")], report.errors)


    def test_flow_without_searches(self):
        self.screen()
        block = export(self.lab)["draft"]["paper"]["ext"]["review"]
        self.assertEqual(block["flow"], {"assessed": 1, "included": 1, "other_sources": 1})   # nothing identified by a search

if __name__ == "__main__":
    unittest.main()

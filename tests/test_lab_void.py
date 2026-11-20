"""Void plans (lab record v0.23 as amended on 2026-11-20: §5.7.4, §5.11, rule L37, §9, §10; claimset v0.44 §3.1.1,
rule 99): a planned analysis that a defect in its code made void, and that a later plan repeated on the same data,
gives no claim of its own; it is listed in the exploration summary with its runs, the defect and the claim its repeat
gives.

From a study whose counting scripts read the coding pass as a number where the record stores text: every planned
count came out 0, the supervisor approved a second plan, the same analysis on the same data with the scripts fixed,
and the paper had to carry the zeros as a claim of its own."""

import contextlib
import copy
import io
import json
import os
import unittest

from claimset import cli
from claimset.lab.core import LabError, final_repeat, verify, void_decisions
from claimset.lab.export import check as export_check
from claimset.lab.export import export
from claimset.render import render

from test_lab_export import ExportCase, rule, validate
from test_lab_v022 import ESTIMANDS

WHY = "The scripts read the coding pass as a number; every count came out 0, so the runs measured nothing."
DEFECT = "The script compared the pass, stored as text, with the number 1, and skipped every case."


class VoidCase(ExportCase):
    """A decided plan PL1, its defect DV1, and PL2, the same test planned after PL1's run and decided."""

    def setUp(self):
        super().setUp()
        self.pl1 = self.plan(design="Every monthly series.", analysis="Mean relative reduction.")
        self.rn1, _ = self.run_(-0.2, "monthly", plan=self.pl1)
        self.status(self.h, "not_supported", self.rn1, plan=self.pl1, why="PL1's rule on its run.")
        self.dv1 = self.add("deviation", {"plan": self.pl1, "run": self.rn1, "text": DEFECT,
                                          "reason": "A defect in the script, found after the run."})
        self.pl2 = self.plan(design="Every monthly series; the script fixed.", analysis="Mean relative reduction.")
        self.rn2, _ = self.run_(0.1, "monthly", plan=self.pl2)
        self.status(self.h, "supported", self.rn2, plan=self.pl2, why="PL2's rule on its run.")

    def void(self, plan=None, repeated_by=None, defects=None, by=None, **extra):
        body = {"text": WHY, "affects": [plan or self.pl1, repeated_by or self.pl2],
                "void": {"plan": plan or self.pl1, "repeated_by": repeated_by or self.pl2,
                         "defects": [self.dv1] if defects is None else defects}}
        body.update(extra)
        return self.add("decision", body, by=by or self.human)

    def refused(self, why, plan=None, repeated_by=None, defects=None, by=None, **extra):
        body = {"text": WHY, "void": {"plan": plan or self.pl1, "repeated_by": repeated_by or self.pl2,
                                      "defects": [self.dv1] if defects is None else defects}}
        body.update(extra)
        with self.assertRaises(LabError, msg=why) as cm:
            self.lab.append("decision", body, by=by or self.human)
        self.assertEqual(cm.exception.rule, "L37", msg=f"{why}: {cm.exception.message}")
        return cm.exception


class TestRule37(VoidCase):
    def test_a_void_plan_verifies(self):
        dc = self.void()
        rep = verify(self.lab)
        self.assertTrue(rep["ok"], rep["errors"])
        st = self.lab.state()
        self.assertEqual(set(void_decisions(st)), {self.pl1})
        self.assertEqual(void_decisions(st)[self.pl1]["id"], dc)
        self.assertEqual(final_repeat(st, self.pl1), self.pl2)

    def test_a_persons_word_recorded_by_an_agent(self):
        e = self.refused("an agent's own judgement", by=self.agent)
        self.assertIn("in your own words", e.ask)
        self.refused("no words", by=self.agent, on_behalf_of=self.human)
        self.refused("on behalf of an agent", by=self.agent, on_behalf_of=self.agent, words="Yes.")
        self.refused("a person writes as themselves", on_behalf_of=self.human, words="Yes.")
        self.void(by=self.agent, on_behalf_of=self.human, words="Yes, PL1 is void; report PL2.",
                  given_at="2026-11-20T10:00:00Z", channel="conversation")
        self.assertTrue(verify(self.lab)["ok"])

    def test_the_repeat_is_planned_after_the_void_runs(self):
        early = self.plan(design="Planned beside PL1.", analysis="Mean relative reduction.")
        pl = self.plan(design="Another plan.", analysis="Mean relative reduction.")
        rn, _ = self.run_(-0.2, "monthly", plan=pl)
        self.status(self.h, "not_supported", rn, plan=pl, why="r")
        dv = self.add("deviation", {"plan": pl, "run": rn, "text": DEFECT, "reason": "defect"})
        rn_e, _ = self.run_(0.1, "monthly", plan=early)
        self.status(self.h, "supported", rn_e, plan=early, why="r")
        e = self.refused("written before the first deciding run", plan=pl, repeated_by=early, defects=[dv])
        self.assertIn("planned after the void runs", e.message)

    def test_a_repeat_of_another_kind(self):
        est = self.add("plan", {"kind": "estimation", "question": self.q, "design": "d", "analysis": "a",
                                "estimands": ESTIMANDS})
        self.run_(0.1, "monthly", plan=est)
        self.refused("an estimation plan does not repeat a confirmatory one", repeated_by=est)

    def test_the_repeat_asks_the_same_question_in_the_same_way(self):
        two = rule()
        two["quantities"]["d"]["run"] = 1
        for field, extra in (("analysis", {"analysis": "Median relative reduction."}),
                             ("decision", {"decision": rule("weekly")}),
                             ("runs", {"runs": 2, "decision": two}),
                             ("data", {"data": [{"description": "other series"}]}),
                             ("exclusions", {"exclusions": [{"name": "short", "rule": "fewer than 24 points"}]}),
                             ("hypotheses", {"hypotheses": [self.hyp("Z helps.", independence="The brief.")]})):
            pl = self.plan(**dict({"design": "A changed repeat.", "analysis": "Mean relative reduction."}, **extra))
            for _ in range(extra.get("runs", 1)):
                self.run_(0.1, "monthly", plan=pl)
            e = self.refused(f"a different {field}", repeated_by=pl)
            self.assertIn(field, e.message)

    def test_the_defects(self):
        self.refused("no defect", defects=[])
        other = self.add("deviation", {"plan": self.pl2, "run": self.rn2, "text": "x", "reason": "y"})
        self.refused("a defect of another plan", defects=[other])
        late = self.add("deviation", {"plan": self.pl1, "run": self.rn1, "text": "late", "reason": "found later"})
        e = self.refused("a defect written after the repeat", defects=[late])
        self.assertIn("written after", e.message)

    def test_not_decided_or_not_planned(self):
        undecided = self.plan(design="Not yet run.", analysis="Mean relative reduction.")
        self.refused("an undecided repeat", repeated_by=undecided)
        self.refused("a plan repeats itself", repeated_by=self.pl1)

    def test_a_plan_is_made_void_once(self):
        self.void()
        e = self.refused("already void")
        self.assertIn("already void", e.message)

    def test_verify_checks_every_record(self):
        """L37 holds in the log, not only in the tool: a void decision written past the tool fails verify."""
        lines = self.lines()
        self.add("decision", {"text": "A plain decision.", "affects": [self.pl1]})
        ev = json.loads(self.lines()[-1])
        ev["body"] = {"text": WHY, "void": {"plan": self.pl1, "repeated_by": self.pl2, "defects": []}}
        from claimset.lab.core import content_hash
        ev["content_hash"] = content_hash(ev["body"])
        self.write_lines(lines + [json.dumps(ev)])
        rep = verify(self.lab)
        self.assertIn("L37", {e["rule"] for e in rep["errors"]}, rep["errors"])


class TestVoidExport(VoidCase):
    def setUp(self):
        super().setUp()
        self.dc = self.void()
        self.out = export(self.lab)
        self.draft = self.out["draft"]

    def test_the_void_plan_gives_no_claim(self):
        plans = [(c.get("test") or {}).get("lab_plan") for c in self.draft["claims"]]
        self.assertEqual(plans, [self.pl2])

    def test_it_is_listed_with_its_runs_and_the_repeats_claim(self):
        exp = self.draft["paper"]["exploration"]
        cid = self.claim(self.out, self.h)["id"]
        self.assertEqual(exp["not_claimed"], [{
            "lab_event": self.h, "lab_plan": self.pl1, "outcome": "not_supported", "because": "defective",
            "into": cid, "runs": [self.rn1], "why": f"{WHY} {DEFECT}", "statement": "X improves Y."}])
        self.assertEqual(exp["tests"], {"total": 2, "supported": 1, "not_supported": 1, "inconclusive": 0})
        self.assertEqual(exp["runs"]["confirmatory"], 2)

    def test_the_repeats_claim_has_the_limitation(self):
        c = self.claim(self.out, self.h)
        lim = next(x for x in self.draft["limitations"] if x["id"] in c.get("limitations", []))
        self.assertEqual((lim["category"], lim["impact"], lim["mitigation"], lim["affects"]),
                         ("deviation", "could_bias_magnitude", "partial", [c["id"]]))
        for part in (self.pl1, self.pl2, self.rn1, DEFECT, "planned after the void runs and before its own"):
            self.assertIn(part, lim["statement"])
        self.assertIn(f"what the void runs of {self.pl1}", " | ".join(t["what"] for t in self.out["completion"]))

    def test_the_draft_validates(self):
        rep = validate(self.draft)
        self.assertFalse([e for e in rep.errors if e["rule"] in ("11", "99")], rep.errors)
        self.assertFalse([w for w in rep.warnings if w["rule"] == "W59"])
        view = render(self.draft)
        self.assertIn(f"defective into {self.claim(self.out, self.h)['id']}; runs {self.rn1}", view)
        self.assertIn("not claimed (1 planned tests that give no claim):", view)

    def test_export_check_accepts_the_completed_file(self):
        doc = copy.deepcopy(self.draft)
        old = self.claim(self.out, self.h)["id"]
        for c in doc["claims"]:
            if c["id"] == old:
                c["id"] = "C9"
        doc["paper"]["exploration"]["not_claimed"][0].update(into="C9", statement="X improves Y")
        for li in doc["limitations"]:
            li["affects"] = ["C9" if a == old else a for a in li["affects"]]
        self.assertEqual(export_check(self.lab, doc), [])
        doc["paper"]["exploration"]["not_claimed"][0]["runs"] = []
        self.assertTrue([m for m in export_check(self.lab, doc) if "exploration" in m])

    def test_the_cli_check(self):
        path = os.path.join(self.tmp.name, "paper.claimset.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.draft, f)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["lab", "export", "--lab", str(self.dir), "--check", path])
        self.assertEqual(code, 0, out.getvalue())


class TestVoidChain(VoidCase):
    def test_into_follows_a_void_repeat(self):
        self.void()
        dv2 = self.add("deviation", {"plan": self.pl2, "run": self.rn2, "text": "Still wrong.", "reason": "defect"})
        pl3 = self.plan(design="Fixed again.", analysis="Mean relative reduction.")
        rn3, _ = self.run_(0.3, "monthly", plan=pl3)
        self.status(self.h, "supported", rn3, plan=pl3, why="PL3's rule on its run.")
        self.add("decision", {"text": "PL2 is void too.", "void": {"plan": self.pl2, "repeated_by": pl3,
                                                                     "defects": [dv2]}}, by=self.human)
        self.assertTrue(verify(self.lab)["ok"])
        self.assertEqual(final_repeat(self.lab.state(), self.pl1), pl3)
        out = export(self.lab)
        cid = self.claim(out, self.h)["id"]
        self.assertEqual([(c.get("test") or {}).get("lab_plan") for c in out["draft"]["claims"]], [pl3])
        nc = out["draft"]["paper"]["exploration"]["not_claimed"]
        self.assertEqual([(x["lab_plan"], x["into"], x["runs"]) for x in nc],
                         [(self.pl1, cid, [self.rn1]), (self.pl2, cid, [self.rn2])])
        lims = [x for x in out["draft"]["limitations"] if cid in x["affects"]]
        self.assertEqual(len(lims), 2)
        self.assertIn(f"through {self.pl2}, itself void", lims[0]["statement"])
        self.assertFalse([e for e in validate(out["draft"]).errors if e["rule"] in ("11", "99")])
        self.assertEqual(export_check(self.lab, copy.deepcopy(out["draft"])), [])


class TestVoidEstimation(ExportCase):
    def estimation(self, design):
        return self.add("plan", {"kind": "estimation", "question": self.q, "design": design,
                                 "analysis": "mean relative reduction", "estimands": ESTIMANDS})

    def test_a_void_estimation_plan_is_listed_once_without_an_outcome(self):
        pl1 = self.estimation("1,000 monthly series")
        rn1, _ = self.run_(0.0, "monthly", plan=pl1)
        dv = self.add("deviation", {"plan": pl1, "run": rn1, "text": DEFECT, "reason": "defect"})
        pl2 = self.estimation("1,000 monthly series; the script fixed")
        self.run_(0.08, "monthly", plan=pl2)
        self.add("decision", {"text": WHY, "affects": [pl1, pl2],
                              "void": {"plan": pl1, "repeated_by": pl2, "defects": [dv]}}, by=self.human)
        out = export(self.lab)
        claims = [c for c in out["draft"]["claims"] if c.get("estimate")]
        self.assertEqual([c["estimate"]["lab_plan"] for c in claims], [pl2])
        nc = out["draft"]["paper"]["exploration"]["not_claimed"]
        self.assertEqual(nc, [{"lab_event": self.q, "lab_plan": pl1, "because": "defective", "into": claims[0]["id"],
                               "runs": [rn1], "why": f"{WHY} {DEFECT}", "statement": "Does X help?"}])
        self.assertTrue(claims[0].get("limitations"))
        rep = validate(out["draft"])
        self.assertFalse([e for e in rep.errors if e["rule"] in ("11", "99")], rep.errors)
        self.assertEqual(export_check(self.lab, copy.deepcopy(out["draft"])), [])


class TestVoidCli(VoidCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue().strip(), err.getvalue()

    def test_claimset_lab_void(self):
        base = ("lab", "void", self.pl1, "--repeated-by", self.pl2, "--why", WHY, "--lab", str(self.dir))
        code, _, err = self.run_cli(*base, "--by", self.agent)
        self.assertEqual(code, 1)
        self.assertIn("L37", err)
        code, _, err = self.run_cli(*base, "--by", self.agent, "--on-behalf-of", self.human, "--words", "Agreed.")
        self.assertEqual(code, 1)
        self.assertIn("name the defects", err)
        code, out, err = self.run_cli(*base, "--defect", self.dv1, "--by", self.agent, "--on-behalf-of", self.human,
                                      "--words", "Agreed: PL1 is void.", "--given-at", "2026-11-20T10:00:00Z",
                                      "--channel", "conversation")
        self.assertEqual(code, 0, err)
        body = self.lab.state().get(out)["body"]
        self.assertEqual((body["affects"], body["void"], body["on_behalf_of"]),
                         ([self.pl1, self.pl2], {"plan": self.pl1, "repeated_by": self.pl2, "defects": [self.dv1]},
                          self.human))


if __name__ == "__main__":
    unittest.main()

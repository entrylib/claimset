"""Drafts (lab record §3.6, amended on 2026-11-17): what a study will test is agreed with its supervisor before it is
recorded; and formal tests give one claim, in their final wording, listing the other formal verdicts in the
exploration summary (lab record §5.7.4, §9; claimset §3.1.1, §3.3.3, rule 99).

From a study of proofs in which the agent recorded every hypothesis and plan as it proposed them: the supervisor's
corrections of the wording became new versions, a second plan decided the agreed wording, and export made a claim of
every version tested."""

import copy
import json
import os
import unittest
from pathlib import Path

from claimset.lab import draft as _draft
from claimset.lab import nextstep
from claimset.lab.core import LabError
from claimset.lab.export import check as export_check
from claimset.lab.export import export
from claimset.render import render
from claimset.validate import validate as _validate

from test_lab import LabCase, TestCli
from test_lab_export import ExportCase, validate

DECISION = {"framework": "deterministic", "quantities": {"q": {"variable": "q"}},
            "supported": "q > 0", "not_supported": "q < 0"}
FORMAL = {"framework": "formal", "supported": "The proof is complete and an independent checker confirms it.",
          "not_supported": "A counterexample that no correction of the proof removes."}


class TestDrafts(LabCase):
    def draft(self, etype, body, supersedes=None, name="plan"):
        return _draft.add(self.lab, name, etype, body, self.agent, supersedes)[0]["id"]

    def drafted(self, name="plan"):
        return _draft.simulate(self.lab, _draft.load(self.lab, name), self.agent)[2]

    def test_drafted_events_stay_out_of_the_record(self):
        before = len(self.lab.read())
        h = self.draft("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"})
        self.assertEqual(h, "H1")
        self.assertEqual(len(self.lab.read()), before)
        folder = Path(self.lab.root).parent
        self.assertTrue((folder / "drafts" / "plan.json").exists())
        self.assertIn("/drafts/", (folder / ".gitignore").read_text().splitlines())
        self.assertEqual(_draft.names(self.lab), ["plan"])

    def test_a_drafted_event_is_checked_as_if_recorded(self):
        with self.assertRaises(LabError):
            self.draft("hypothesis", {"statement": "X helps.", "question": "Q9", "origin": "a_priori"})
        with self.assertRaises(LabError) as cm:
            self.draft("plan", {"kind": "confirmatory", "hypotheses": ["H1"], "design": "d", "analysis": "a",
                                "decision": DECISION})
        self.assertEqual(cm.exception.rule, "L12")        # H1 exists in neither the record nor the draft
        with self.assertRaises(LabError):
            _draft.add(self.lab, "plan", "run", {"label": "exploratory"}, self.agent)

    def test_a_drafted_event_is_replaced_in_place(self):
        h = self.draft("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"})
        self.draft("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                            "decision": DECISION, "requires_approval": True})
        again = self.draft("hypothesis", {"statement": "X helps on monthly data.", "question": self.q,
                                          "origin": "a_priori"}, supersedes=h)
        self.assertEqual(again, h)
        events = self.drafted()
        self.assertEqual([e["type"] for e in events], ["hypothesis", "plan"])
        self.assertEqual(events[0]["body"]["statement"], "X helps on monthly data.")
        _draft.drop(self.lab, "plan", "PL1")
        self.assertEqual([e["type"] for e in self.drafted()], ["hypothesis"])

    def test_recording_writes_the_agreed_draft_with_the_records_ids_and_the_approval(self):
        t = self.draft("term", {"term": "MASE", "kind": "variable", "definition": "Mean absolute scaled error."})
        h = self.draft("hypothesis", {"statement": "X lowers [[TM1:MASE]].", "question": self.q,
                                      "origin": "a_priori"})
        self.draft("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                            "decision": DECISION, "requires_approval": True, "setup": {"lens": [t]}})
        # the record gains a term and a hypothesis meanwhile: the drafted ones move on
        self.add("term", {"term": "RMSE", "kind": "variable", "definition": "Root mean squared error."})
        self.hyp("Y helps.")
        before = len(self.lab.read())
        written, approvals = _draft.record(self.lab, "plan", self.agent,
                                           {"on_behalf_of": self.human, "words": "Agreed, record it.",
                                            "given_at": "2026-11-17T09:20:47Z", "channel": "conversation"},
                                           code=("abc123", False))
        self.assertEqual(written, [("TM1", "TM2"), ("H1", "H2"), ("PL1", "PL1")])
        st = self.lab.state()
        self.assertEqual(st.get("H2")["body"]["statement"], "X lowers [[TM2:MASE]].")
        plan = st.get("PL1")["body"]
        self.assertEqual((plan["hypotheses"], plan["setup"], plan["code_version"], plan["dirty"]),
                         (["H2"], {"lens": ["TM2"]}, "abc123", False))
        ap = st.get(approvals[0])["body"]
        self.assertEqual((ap["target"], ap["on_behalf_of"], ap["words"]), ("PL1", self.human, "Agreed, record it."))
        self.assertEqual(len(self.lab.read()), before + 4)
        self.assertEqual(_draft.names(self.lab), [])

    def test_recording_without_the_supervisors_words_writes_nothing(self):
        h = self.draft("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"})
        self.draft("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                            "decision": DECISION, "requires_approval": True})
        before = len(self.lab.read())
        with self.assertRaises(LabError) as cm:
            _draft.record(self.lab, "plan", self.agent, {})
        self.assertEqual(cm.exception.rule, "L22")
        self.assertIn("Do you approve the draft plan", cm.exception.ask)
        self.assertEqual(len(self.lab.read()), before)
        self.assertEqual(_draft.names(self.lab), ["plan"])

    def test_a_draft_that_no_longer_checks_is_not_recorded(self):
        h = self.hyp("X helps.")
        self.draft("hypothesis", {"statement": "X helps on monthly data.", "question": self.q,
                                  "origin": "a_priori"}, supersedes=h)
        self.add("hypothesis", {"statement": "X helps weekly.", "question": self.q, "origin": "a_priori"},
                 supersedes=h)                         # the record corrected it first: the draft's correction fails
        problems, _ = _draft.check(self.lab, "plan")
        self.assertEqual([p[1].rule for p in problems], ["L11"])
        before = len(self.lab.read())
        with self.assertRaises(LabError):
            _draft.record(self.lab, "plan", self.agent, {})
        self.assertEqual(len(self.lab.read()), before)

    def test_next_leads_through_the_draft(self):
        steps = nextstep.steps(self.lab.read(), self.agent)
        self.assertIn(f"state what you expect for {self.q}", steps[0][0])
        self.assertIn("--draft plan", steps[0][1])
        h = self.draft("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"})
        self.draft("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                            "decision": DECISION, "requires_approval": True})
        step, command = nextstep.steps(self.lab.read(), self.agent, drafts=[("plan", self.drafted())])[0]
        self.assertIn("show the draft plan (1 hypothesis, 1 plan)", step)
        self.assertIn("claimset lab draft record plan", command)
        self.assertIn(f"--on-behalf-of {self.human}", command)

    def test_the_draft_as_the_supervisor_reads_it(self):
        h = self.draft("hypothesis", {"statement": "X lowers the error.", "question": self.q, "origin": "a_priori"})
        self.draft("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "Proof of the statement.",
                            "analysis": "Checked by another model.", "decision": FORMAL, "requires_approval": True,
                            "choices": [{"what": "checker", "choice": "another model", "source": "agent"}]})
        text = _draft.render(self.lab, "plan", self.agent)
        for part in ("H1  Hypothesis (a priori", "X lowers the error.", "PL1  Plan (confirmatory), tests H1",
                     "Design: Proof of the statement.", "Framework: formal",
                     "supported if The proof is complete", "Approval: required",
                     "Chosen by the agent alone, to agree: PL1: checker"):
            self.assertIn(part, text)


class TestDraftCli(TestCli):
    def test_draft_commands(self):
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R")
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "A",
                     "--model", "Anthropic|Claude Opus|5.5|claude-opus-5-5", "--by", "AC1")
        os.environ["CLAIMSET_ACTOR"] = "AC2"
        code, out, err = self.run_cli("lab", "question", "Does X help?", "--draft", "plan")
        self.assertEqual((code, out), (0, "Q1 (draft plan; not recorded)"))
        self.run_cli("lab", "hypothesis", "X helps.", "--question", "Q1", "--draft", "plan")
        code, out, _ = self.run_cli("lab", "draft", "show", "plan")
        self.assertIn("Q1  Question: Does X help?", out)
        self.assertIn("H1  Hypothesis (a priori; question Q1): X helps.", out)
        self.assertEqual(self.run_cli("lab", "draft", "list")[1], "plan: 2 drafted events")
        self.assertEqual(self.run_cli("lab", "draft", "check", "plan")[0], 0)
        code, out, _ = self.run_cli("lab", "summary")
        self.assertIn("Drafts, not recorded (lab record §3.6): plan (2 events)", out)
        code, out, _ = self.run_cli("lab", "draft", "record", "plan")
        self.assertEqual((code, out.splitlines()), (0, ["Q1", "H1"]))
        self.assertEqual(self.run_cli("lab", "draft", "list")[1], "no drafts")


class TestFormalExport(ExportCase):
    """A hypothesis tested by proof gives one claim, in its final wording; its other formal verdicts, and those of
    hypotheses merged or dropped, are listed in `not_claimed`."""

    def setUp(self):
        super().setUp()
        self.merged = self.hyp("X helps for small errors.")
        self.dropped = self.hyp("X has a large-sample variance.")
        pl1 = self.plan(hypotheses=[self.h, self.merged, self.dropped], decision=FORMAL)
        rn1, _ = self.run_(0.1, "m", plan=pl1)
        for h, to, rule in ((self.h, "supported", "supported"), (self.merged, "inconclusive", "neither"),
                            (self.dropped, "inconclusive", "neither")):
            self.status(h, to, rn1, plan=pl1, rule=rule, why=f"PL1 on {h}.")
        self.status(self.merged, "revised", why="Merged into the main result as its part (b).",
                    revised_to=self.h)
        self.status(self.dropped, "abandoned", why="Reported from a simulation instead.")
        self.final = self.add("hypothesis", {"statement": "X improves Y, without the factor 200.",
                                             "question": self.q, "origin": "a_priori",
                                             "independence": "The supervisor's rewording; no run shaped it."},
                              supersedes=self.h)
        pl2 = self.plan(hypotheses=[self.final], decision=FORMAL)
        rn2, _ = self.run_(0.1, "m", plan=pl2)
        self.status(self.final, "supported", rn2, plan=pl2, rule="supported", why="PL2 on the final wording.")
        self.pl1, self.pl2 = pl1, pl2
        self.out = export(self.lab)

    def test_one_claim_in_the_final_wording(self):
        claims = [c for c in self.out["draft"]["claims"] if c.get("hypothesis")]
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual((c["statement"], c["hypothesis"]["lab_event"], c["test"]["lab_plan"]),
                         ("X improves Y, without the factor 200.", self.final, self.pl2))

    def test_the_other_formal_verdicts_are_listed_with_the_claim_they_went_into(self):
        exp = self.out["draft"]["paper"]["exploration"]
        cid = self.claim(self.out, self.final)["id"]
        got = [(x["lab_event"], x["lab_plan"], x["outcome"], x["because"], x.get("into")) for x in exp["not_claimed"]]
        self.assertEqual(got, [(self.h, self.pl1, "supported", "reworded", cid),
                               (self.merged, self.pl1, "inconclusive", "revised", cid),
                               (self.dropped, self.pl1, "inconclusive", "abandoned", None)])
        self.assertIn(f"decided again under {self.pl2}", exp["not_claimed"][0]["why"])
        self.assertEqual(exp["not_claimed"][1]["why"], "Merged into the main result as its part (b).")
        self.assertEqual(exp["tests"], {"total": 4, "supported": 2, "not_supported": 0, "inconclusive": 2})
        self.assertFalse([e for e in validate(self.out["draft"]).errors if e["rule"] in ("45", "46", "99")])

    def test_the_reading_view_names_them(self):
        d = copy.deepcopy(self.out["draft"])
        cid = self.claim(self.out, self.final)["id"]
        lines = render_lines(d)
        self.assertNotIn("not claimed", next(x for x in lines if x.startswith("exploration ")))
        start = lines.index("not claimed (3 formal verdicts that give no claim):")
        listed = lines[start + 1:start + 4]                  # one line each, its wording first (amended 2026-11-20)
        nc = d["paper"]["exploration"]["not_claimed"]
        self.assertTrue(all(isinstance(x.get("statement"), str) and x["statement"] for x in nc))
        self.assertEqual(listed, [
            f"  - {nc[0]['statement']} (supported; reworded into {cid}; lab {self.h} under {self.pl1})",
            f"  - {nc[1]['statement']} (inconclusive; revised into {cid}; lab {self.merged} under {self.pl1})",
            f"  - {nc[2]['statement']} (inconclusive; abandoned; lab {self.dropped} under {self.pl1})"])

    def test_renumbered_claims_still_match_the_record(self):
        doc = copy.deepcopy(self.out["draft"])
        old = self.claim(self.out, self.final)["id"]
        for c in doc["claims"]:
            if c["id"] == old:
                c["id"] = "C99"
        for x in doc["paper"]["exploration"]["not_claimed"]:
            if x.get("into") == old:
                x["into"] = "C99"
        self.assertFalse([m for m in export_check(self.lab, doc) if "exploration" in m])
        doc["paper"]["exploration"]["not_claimed"].pop()
        self.assertTrue([m for m in export_check(self.lab, doc) if "exploration" in m])

    def test_a_shortened_statement_still_matches_the_record(self):
        doc = copy.deepcopy(self.out["draft"])
        for x in doc["paper"]["exploration"]["not_claimed"]:
            x["statement"] = "In a few words"                  # completing the claimset shortens it (2026-11-20)
        self.assertFalse([m for m in export_check(self.lab, doc) if "exploration" in m])
        doc["paper"]["exploration"]["not_claimed"][0]["outcome"] = "not_supported"
        self.assertTrue([m for m in export_check(self.lab, doc) if "exploration" in m])

    def test_other_frameworks_keep_one_claim_per_test(self):
        h = self.hyp("Z helps.", independence="The brief.")
        for _ in range(2):
            pl = self.plan(hypotheses=[h])
            rn, rs = self.run_(0.1, "m", plan=pl)
            self.status(h, "supported", rs, plan=pl)
        claims = [c for c in export(self.lab)["draft"]["claims"] if (c.get("hypothesis") or {}).get("lab_event") == h]
        self.assertEqual(len(claims), 2)


def render_lines(doc):
    return render(doc).splitlines()


class TestRule99(unittest.TestCase):
    def base(self):
        here = Path(__file__).resolve().parent.parent / "examples"
        for p in sorted(here.glob("*.json")):
            d = json.loads(p.read_text())
            if (d.get("paper") or {}).get("exploration") and any(c.get("hypothesis") for c in d["claims"]):
                return d
        self.skipTest("no example with a lab record")

    def errors(self, entry):
        d = self.base()
        cid = next(c["id"] for c in d["claims"] if c.get("hypothesis"))
        entry = {k: (cid if v == "<claim>" else v) for k, v in entry.items()}
        d["paper"]["exploration"]["not_claimed"] = [entry]
        return [e for e in _validate(d).errors if e["rule"] == "99"]

    def test_a_well_formed_entry_passes(self):
        self.assertEqual(self.errors({"lab_event": "H1", "lab_plan": "PL1", "outcome": "supported",
                                      "because": "reworded", "into": "<claim>", "why": "Reworded."}), [])
        self.assertEqual(self.errors({"lab_event": "H2", "lab_plan": "PL1", "outcome": "inconclusive",
                                      "because": "abandoned", "why": "Dropped."}), [])

    def test_broken_entries_fail(self):
        for entry in ({"lab_event": "H1", "lab_plan": "PL1", "outcome": "supported", "because": "reworded",
                       "why": "No claim named."},
                      {"lab_event": "H1", "lab_plan": "PL1", "outcome": "supported", "because": "abandoned",
                       "into": "<claim>", "why": "x"},
                      {"lab_event": "H1", "lab_plan": "PL1", "outcome": "maybe", "because": "revised", "why": "x"},
                      {"lab_event": "H1", "lab_plan": "PL1", "outcome": "supported", "because": "merged",
                       "why": "x"},
                      {"lab_event": "H1", "lab_plan": "PL1", "outcome": "supported", "because": "revised",
                       "into": "C999", "why": "x"},
                      {"lab_event": "", "lab_plan": "PL1", "outcome": "supported", "because": "revised", "why": ""}):
            self.assertTrue(self.errors(entry), entry)

    def test_a_void_plan_is_listed_with_its_runs(self):
        """A plan a defect made void (v0.44 as amended on 2026-11-20): `because: defective`, the claim of the plan
        that repeated it, its runs; an estimation plan's has no verdict."""
        self.assertEqual(self.errors({"lab_event": "Q2", "lab_plan": "PL2", "because": "defective", "into": "<claim>",
                                      "runs": ["RN3", "RN4"], "why": "The scripts skipped every coding."}), [])
        self.assertEqual(self.errors({"lab_event": "H3", "lab_plan": "PL2", "outcome": "not_supported",
                                      "because": "defective", "into": "<claim>", "why": "Wrong data read."}), [])
        for entry in ({"lab_event": "Q2", "lab_plan": "PL2", "because": "defective", "why": "No repeat named."},
                      {"lab_event": "Q2", "lab_plan": "PL2", "because": "defective", "into": "<claim>",
                       "runs": "RN3", "why": "x"},
                      {"lab_event": "Q2", "lab_plan": "PL2", "because": "defective", "into": "<claim>",
                       "runs": [""], "why": "x"},
                      {"lab_event": "H1", "lab_plan": "PL1", "because": "reworded", "into": "<claim>", "why": "x"}):
            self.assertTrue(self.errors(entry), entry)          # the last: only a void plan may give no verdict

    def test_the_reading_view_gives_a_void_plans_runs(self):
        from claimset.render import not_claimed_line
        self.assertEqual(not_claimed_line({"lab_event": "Q2", "lab_plan": "PL2", "because": "defective",
                                           "into": "C3", "runs": ["RN3", "RN4"], "why": "x",
                                           "statement": "Coders agree on the codes"}),
                         "Coders agree on the codes (defective into C3; runs RN3, RN4; lab Q2 under PL2)")


if __name__ == "__main__":
    unittest.main()

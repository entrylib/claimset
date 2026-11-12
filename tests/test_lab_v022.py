"""Lab record v0.22: rule L31 (a hypothesis written after runs says where it comes from), estimation plans (§5.7.8,
L32) and their export as planned estimates, a plan's diagnostics (flag diagnostic_missing), and the notice on a
record's first exploratory run. From a pilot of agents of three sizes (entrylib:2026.000005)."""

import os
import sys

from claimset.lab import nextstep
from claimset.lab.core import (Lab, LabError, bind_estimands, first_run_notice, missing_diagnostics, plan_flags,
                               verify)
from claimset.lab.export import check, export
from claimset.lab.run import run_command

from test_lab import TestCli, ticking_clock
from test_lab_export import ExportCase, validate

ESTIMANDS = {"d": {"variable": "mean relative MASE reduction", "conditions": {"frequency": "monthly"}}}


def older(tmp, version):
    """A record begun under an earlier version of the specification."""
    lab = Lab(os.path.join(tmp, "old"), clock=ticking_clock())
    lab.root.mkdir(parents=True)
    (lab.root / "runs").mkdir()
    (lab.root / "agents").mkdir()
    lab.append("init", {"lab_spec_version": version, "working_title": "t"}, by=None)
    lab.append("actor", {"kind": "human", "name": "R"}, by="AC1")
    lab.append("question", {"text": "Q?"}, by="AC1")
    return lab


class TestL31(ExportCase):
    def test_a_hypothesis_after_a_run_says_where_it_comes_from(self):
        rn, rs = self.run_("0.1", "monthly")
        self.assertRefused("L31", "hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"})
        self.hyp("X helps monthly.", origin="from_exploration", prompted_by=[rs[0]])
        self.hyp("X helps weekly.", independence="Stated in the grant proposal before the study began.")

    def test_independence_is_text(self):
        self.run_("0.1", "monthly")
        self.assertRefused("schema", "hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori",
                                                    "independence": " "})

    def test_before_any_run_nothing_is_asked(self):
        self.hyp("X helps daily.")

    def test_correcting_a_hypothesis_written_before_the_runs(self):
        self.run_("0.1", "monthly")
        self.add("hypothesis", {"statement": "X improves Y, worded better.", "question": self.q,
                                "origin": "a_priori"}, supersedes=self.h)
        late = self.hyp("Z helps.", independence="From the literature.")
        self.assertRefused("L31", "hypothesis", {"statement": "Z helps more.", "question": self.q,
                                                 "origin": "a_priori"}, supersedes=late)

    def test_records_begun_earlier_are_read_as_written(self):
        lab = older(self.tmp.name, "0.21")
        lab.append("run", {"label": "exploratory", "command": ["x"], "exit_status": "success"}, by="AC1")
        lab.append("hypothesis", {"statement": "X helps.", "question": "Q1", "origin": "a_priori"}, by="AC1")
        self.assertTrue(verify(lab)["ok"])


class TestEstimationPlans(ExportCase):
    def estimation(self, **extra):
        body = {"kind": "estimation", "question": self.q, "design": "1,000 monthly series",
                "analysis": "mean relative reduction", "estimands": ESTIMANDS}
        body.update(extra)
        return self.add("plan", {k: v for k, v in body.items() if v is not None})

    def test_an_estimation_plan(self):
        pl = self.estimation()
        rn, rs = self.run_("0.08", "monthly", plan=pl)
        self.assertEqual(self.lab.state().get(rn)["body"]["label"], "confirmatory")
        st = self.lab.state()
        pv, runs = st.deciding_runs(pl)
        self.assertEqual({k: v[1] for k, v in bind_estimands(st, pv, runs).items()}, {"d": 0.08})
        with self.assertRaises(LabError) as cm:
            self.run_("0.09", "monthly", plan=pl)
        self.assertEqual(cm.exception.rule, "L16")

    def test_what_an_estimation_plan_has(self):
        q = self.q
        base = {"kind": "estimation", "question": q, "design": "d", "analysis": "a", "estimands": ESTIMANDS}
        for bad in ({"question": None}, {"estimands": None}, {"estimands": {"d": {"conditions": {}}}},
                    {"estimands": {"1d": {"variable": "v"}}}, {"estimands": {"d": {"variable": "v", "unit": "x"}}},
                    {"hypotheses": [self.h]}, {"decision": rule_text()}, {"runs": 2}):
            body = dict(base, **bad)
            self.assertRefused("L32", "plan", {k: v for k, v in body.items() if v is not None})

    def test_estimands_are_an_estimation_plans(self):
        self.assertRefused("schema", "plan", {"kind": "confirmatory", "hypotheses": [self.h], "design": "d",
                                              "analysis": "a", "decision": rule_text(), "estimands": ESTIMANDS})

    def test_records_begun_earlier_have_none(self):
        lab = older(self.tmp.name, "0.21")
        with self.assertRaises(LabError):
            lab.append("plan", {"kind": "estimation", "question": "Q1", "design": "d", "analysis": "a",
                                "estimands": ESTIMANDS}, by="AC1")

    def test_exported_as_a_planned_estimate(self):
        pl = self.estimation(estimands=dict(ESTIMANDS, gone={"variable": "coverage"}))
        self.run_("0.08", "monthly", plan=pl)
        out = export(self.lab)
        c = next(c for c in out["draft"]["claims"] if c.get("planning") == "planned_estimate")
        self.assertEqual(c["estimate"]["lab_plan"], pl)
        self.assertEqual(c["estimate"]["not_obtained"], ["gone"])
        self.assertNotIn("hypothesis", c)
        self.assertIn("was 0.08", c["statement"])
        self.assertIn("was not obtained", c["statement"])
        self.assertTrue(any(t["where"] == f"claims.{c['id']}.statement" and "planned estimate" in t["what"]
                            for t in out["completion"]))
        draft = out["draft"]
        draft["paper"]["licence"] = "CC-BY-4.0"
        next(x for x in draft["contributors"] if x["type"] == "human")["positions"] = ["supervisor", "guarantor"]
        c["role"] = "principal"
        c["about"] = {"subject": "X", "relation": "changes", "object": "Y", "comparator": None, "conditions": []}
        c["scope"] = {"conditions": ["monthly series"]}
        draft["paper"]["contributions"] = [c["id"]]
        self.assertEqual(validate(draft).errors, [])
        self.assertEqual(check(self.lab, draft), [])
        c["estimate"]["not_obtained"] = []
        self.assertTrue(any("not_obtained" in m for m in check(self.lab, draft)))


class TestDiagnostics(ExportCase):
    def test_a_run_without_a_required_diagnostic_is_flagged(self):
        pl = self.plan(hypotheses=[self.h], decision=rule_text(), diagnostics=["convergence failures"])
        self.run_("0.1", "monthly", plan=pl)
        st = self.lab.state()
        pv, runs = st.deciding_runs(pl)
        self.assertIn("diagnostic_missing", plan_flags(st, pv, runs))
        self.assertEqual(missing_diagnostics(st, pv, runs), [(runs[0]["id"], "convergence failures")])

    def test_a_run_that_reports_it_is_not(self):
        pl = self.plan(hypotheses=[self.h], decision=rule_text(), diagnostics=["mean relative MASE reduction"])
        self.run_("0.1", "monthly", plan=pl)
        st = self.lab.state()
        pv, runs = st.deciding_runs(pl)
        self.assertNotIn("diagnostic_missing", plan_flags(st, pv, runs))

    def test_what_diagnostics_are(self):
        for bad in ([], ["a", "a"], [""], "convergence"):
            self.assertRefused("schema", "plan", {"kind": "confirmatory", "hypotheses": [self.h], "design": "d",
                                                  "analysis": "a", "decision": rule_text(), "diagnostics": bad})
        self.assertRefused("schema", "plan", {"kind": "exploratory", "design": "d", "analysis": "a",
                                              "diagnostics": ["x"]})

    def test_exported_into_the_tests_flags(self):
        pl = self.plan(hypotheses=[self.h], decision=rule_text(), diagnostics=["convergence failures"])
        rn, rs = self.run_("0.1", "monthly", plan=pl)
        self.status(self.h, "supported", rs, plan=pl)
        c = self.claim(export(self.lab), self.h)
        self.assertEqual(c["test"]["flags"], ["diagnostic_missing"])


class TestFirstRunNotice(ExportCase):
    def test_the_first_exploratory_run_with_no_plan(self):
        rn, _ = self.run_("0.1", "monthly")
        st = self.lab.state()
        self.assertIn("exploratory", first_run_notice(st, st.get(rn)))
        rn2, _ = self.run_("0.2", "monthly")
        self.assertIsNone(first_run_notice(self.lab.state(), self.lab.state().get(rn2)))

    def test_not_once_a_test_is_planned(self):
        self.plan(hypotheses=[self.h], decision=rule_text())
        rn, _ = self.run_("0.1", "monthly")
        st = self.lab.state()
        self.assertIsNone(first_run_notice(st, st.get(rn)))


def rule_text():
    return {"framework": "deterministic", "quantities": {"d": {"variable": "mean relative MASE reduction"}},
            "supported": "d > 0", "not_supported": "d < 0"}


class TestCommandLine(TestCli):
    def test_the_path_of_an_estimate(self):
        script = os.path.join(self.tmp.name, "est.py")
        with open(script, "w") as f:
            f.write("import json, os\njson.dump([{'variable': 'accuracy', 'value': 0.9}], "
                    "open(os.environ['CLAIMSET_RESULTS'], 'w'))\n")
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model", "P|M|1|m")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R", "--words", "Yes.", "--by", "AC1")
        os.environ["CLAIMSET_ACTOR"] = "AC1"
        self.run_cli("lab", "question", "How accurate is it?")
        code, _, err = self.run_cli("lab", "run", "--", sys.executable, script)
        self.assertIn("claimset: notice: RN1 is exploratory", err)
        self.assertIn("rule L31", self.hint)
        code, _, err = self.run_cli("lab", "hypothesis", "It is accurate.", "--question", "Q1")
        self.assertEqual(code, 1)
        self.assertIn("[L31]", err)
        code, out, _ = self.run_cli("lab", "hypothesis", "It is accurate.", "--question", "Q1",
                                    "--independence", "The supervisor's question, asked before any run.")
        self.assertEqual(code, 0)
        code, out, err = self.run_cli("lab", "plan", "--kind", "estimation", "--question", "Q1", "--design", "d",
                                      "--analysis", "a", "--estimand", "acc=accuracy",
                                      "--diagnostic", "convergence failures")
        self.assertEqual((code, out), (0, "PL1"), err)
        self.run_cli("lab", "run", "--plan", "PL1", "--", sys.executable, script)
        code, out, _ = self.run_cli("lab", "verdict", "PL1")
        self.assertIn("acc = 0.9 (RS2)", out)
        self.assertIn("flag: diagnostic missing", out)
        code, out, _ = self.run_cli("lab", "summary")
        self.assertIn("PL1 [estimation] estimates acc for Q1", out)

    def test_estimands_belong_to_estimation_plans(self):
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R")
        os.environ["CLAIMSET_ACTOR"] = "AC1"
        self.run_cli("lab", "question", "Q?")
        self.run_cli("lab", "hypothesis", "H.", "--question", "Q1")
        code, _, err = self.run_cli("lab", "plan", "--kind", "confirmatory", "--hypotheses", "H1", "--design", "d",
                                    "--analysis", "a", "--estimand", "acc=accuracy")
        self.assertEqual(code, 1)
        self.assertIn("--estimand is for estimation plans", err)


class TestNext(TestCli):
    def test_a_question_answered_by_an_estimation_plan_needs_no_hypothesis(self):
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model", "P|M|1|m")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R", "--words", "Yes.", "--by", "AC1")
        os.environ["CLAIMSET_ACTOR"] = "AC1"
        self.run_cli("lab", "question", "How accurate?")
        self.run_cli("lab", "plan", "--kind", "estimation", "--question", "Q1", "--design", "d", "--analysis", "a",
                     "--estimand", "acc=accuracy")
        lab = Lab(os.environ["CLAIMSET_LAB"])
        whats = [w for w, _ in nextstep.steps(lab.read(), "AC1")]
        self.assertFalse(any("state what you expect" in w for w in whats), whats)
        self.assertTrue(any(w.startswith("run the test PL1") for w in whats), whats)

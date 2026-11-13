"""Where each choice of a plan came from (lab record v0.22 §5.7 `choices`, §5.7.6, as amended on 2026-11-13): an agent
evaluating forecasts took its error measures from a competition's precedent, without asking."""

from claimset.lab.core import plan_warnings

from test_lab import DECISION, PlanRunCase, TestCli

CHOICES = [{"what": "measure", "choice": "RMSSE", "source": "good-practice", "ref": "study-planning/prediction#mean-forecasts"},
           {"what": "significance level", "choice": "0.05", "source": "supervisor"}]


class TestChoices(PlanRunCase):
    def body(self, **extra):
        b = {"kind": "confirmatory", "hypotheses": [self.h], "design": "d", "analysis": "a", "decision": DECISION}
        b.update(extra)
        return b

    def test_choices_are_recorded(self):
        pl = self.add("plan", self.body(choices=CHOICES))
        assert self.lab.state().get(pl)["body"]["choices"] == CHOICES

    def test_what_a_choice_is(self):
        for bad in ([], [{"what": "measure", "choice": "MAE"}], [{"what": "measure", "choice": "MAE", "source": "M4"}],
                    [{"what": "measure", "choice": "MAE", "source": "agent", "why": "x"}],
                    [{"what": "measure", "choice": "MAE", "source": "agent"},
                     {"what": "Measure", "choice": "RMSE", "source": "agent"}]):
            self.assertRefused("schema", "plan", self.body(choices=bad))

    def test_warnings(self):
        st = self.lab.state()
        assert any("no choices recorded" in w for w in plan_warnings(st, self.body()))
        mine = plan_warnings(st, self.body(choices=CHOICES + [{"what": "test", "choice": "Wilcoxon", "source": "agent"}]))
        assert any("chosen by you alone, not yet agreed: test" in w for w in mine)
        assert not any("choices" in w or "chosen by you" in w for w in plan_warnings(st, self.body(choices=CHOICES)))
        assert not any("choices" in w for w in plan_warnings(st, {"kind": "exploratory", "design": "d",
                                                                   "analysis": "a"}))


class TestChoiceOption(TestCli):
    def test_from_the_command_line(self):
        import os
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R")
        os.environ["CLAIMSET_ACTOR"] = "AC1"
        self.run_cli("lab", "question", "Q?")
        self.run_cli("lab", "hypothesis", "H.", "--question", "Q1")
        code, out, err = self.run_cli("lab", "plan", "--kind", "confirmatory", "--hypotheses", "H1", "--design", "d",
                                      "--analysis", "a", "--framework", "deterministic", "--quantity", "q=q",
                                      "--supported", "q > 0", "--not-supported", "q < 0",
                                      "--choice", "measure|RMSSE|good-practice|study-planning/prediction#mean-forecasts",
                                      "--choice", "test|Wilcoxon|agent")
        assert (code, out) == (0, "PL1"), err
        assert "chosen by you alone, not yet agreed: test" in err
        code, _, err = self.run_cli("lab", "plan", "--kind", "confirmatory", "--hypotheses", "H1", "--design", "d",
                                    "--analysis", "a", "--choice", "measure only")
        assert code == 1 and "WHAT|CHOICE|SOURCE" in err

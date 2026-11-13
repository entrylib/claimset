"""What to do next (`claimset lab next`, and the hint after every writing command), and the harness guard: inside an
agent harness, a command written as a person is refused (lab record §4.6, as amended on 2026-11-12). From a pilot in
which smaller models stopped with work undone and recorded a run as the human (entrylib:2026.000005, C17, L6)."""

import os
import unittest
from unittest import mock

from claimset.lab import nextstep
from claimset.lab.core import Lab

from test_lab import DECISION, TestCli, run_body, ticking_clock


def first(events):
    todo = nextstep.steps(events)
    return todo[0][0] if todo else ""


class TestSteps(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab.create(Path(self.tmp.name) / "lab", "Study", clock=ticking_clock())

    def add(self, etype, body, by="AC1"):
        return self.lab.append(etype, body, by=by)["id"]

    def test_the_steps_in_order_to_the_end(self):
        self.assertIn("register yourself", first(self.lab.read()))
        self.add("actor", {"kind": "agent", "name": "A", "models": [{"provider": "P", "name": "M", "version": "1"}]})
        self.assertIn("register the person", first(self.lab.read()))
        self.add("actor", {"kind": "human", "name": "R", "words": "I am R.", "given_at": "2026-11-12T10:00:00Z"})
        self.assertIn("record the research question", first(self.lab.read()))
        q = self.add("question", {"text": "Does X help?"})
        self.assertIn(f"state what you expect for {q}", first(self.lab.read()))
        h = self.add("hypothesis", {"statement": "X helps.", "question": q, "origin": "a_priori"})
        step, command = nextstep.steps(self.lab.read())[0]
        self.assertIn(f"agree the design of the test of {h} with the supervisor", step)
        self.assertIn(f"--hypotheses {h}", command)
        pl = self.add("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                               "decision": DECISION, "requires_approval": True})
        step, command = nextstep.steps(self.lab.read())[0]
        self.assertIn(f"show {pl} to AC2", step)
        self.assertIn("--on-behalf-of AC2", command)
        self.add("approval", {"target": pl, "on_behalf_of": "AC2", "words": "Approved.",
                              "given_at": "2026-11-12T11:00:00Z", "channel": "conversation"})
        self.assertIn(f"run the test {pl} plans", first(self.lab.read()))
        rn = self.add("run", run_body(plan=pl, label="confirmatory"))
        self.add("result", {"run": rn, "variable": "q", "value": 1, "source": "results.json"})
        step, command = nextstep.steps(self.lab.read())[0]
        self.assertIn(f"read the verdict of {pl} and record it for {h}", step)
        self.assertIn(f"claimset lab verdict {pl}", command)
        self.assertIn(f"--plan {pl} --evidence {rn}", command)
        self.add("status", {"target": h, "to": "supported", "rationale": "the rule", "evidence": [rn], "plan": pl})
        self.assertEqual(nextstep.steps(self.lab.read()), [])
        self.assertIn("export the claimset", nextstep.line(self.lab.read()))

    def test_anchoring_when_set_up(self):
        self.assertIn(("anchor the record, so its time is attested", "claimset lab anchor"),
                      nextstep.steps(self.lab.read(), anchored=False))


HARNESS = {"CLAUDECODE": "1"}


class TestCommandLine(TestCli):
    def start(self):
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model", "P|M|1",
                     "--record-source", "self_reported")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R", "--words", "I am R.",
                     "--given-at", "2026-11-12T10:00:00Z", "--by", "AC1")

    def test_next_and_the_hint(self):
        self.start()
        code, out, _ = self.run_cli("lab", "question", "Does X help?", "--by", "AC1")
        self.assertEqual((code, out), (0, "Q1"))
        self.assertTrue(self.hint.startswith("claimset: next: state what you expect for Q1"))
        code, out, _ = self.run_cli("lab", "next")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("Next: state what you expect for Q1"))
        self.assertIn("claimset lab hypothesis", out)

    def test_inside_a_harness_an_agent_writes_as_itself(self):
        self.start()
        with mock.patch.dict(os.environ, HARNESS):
            code, out, err = self.run_cli("lab", "note", "a note", "--by", "AC2")
            self.assertEqual(code, 1)
            self.assertIn("[harness] AC2 is a person", err)
            self.assertIn("--on-behalf-of AC2", err)
            self.assertEqual(self.run_cli("lab", "note", "a note", "--by", "AC1")[:2], (0, "NT1"))
        self.assertEqual(self.run_cli("lab", "note", "theirs", "--by", "AC2")[:2], (0, "NT2"))   # their own terminal


if __name__ == "__main__":
    unittest.main()

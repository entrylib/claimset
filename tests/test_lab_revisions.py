"""Revision labels (lab record §4.3, as amended on 2026-11-15): a corrected event is named ROOT.Rk; every command
accepts the label, a correction is printed with it, and an approval of an outdated plan revision is refused."""

import unittest

from claimset.lab.core import Lab, LabError

from test_lab import DECISION, TestCli, ticking_clock


class TestLabels(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab.create(Path(self.tmp.name) / "lab", "Study", clock=ticking_clock())

    def test_labels_and_their_resolution(self):
        self.lab.append("actor", {"kind": "agent", "name": "A", "models": [{"provider": "P", "name": "M", "version": "1"}]},
                        by="AC1")
        n1 = self.lab.append("note", {"text": "first"}, by="AC1")["id"]
        n2 = self.lab.append("note", {"text": "second"}, by="AC1", supersedes=n1)["id"]
        n3 = self.lab.append("note", {"text": "third"}, by="AC1", supersedes=n2)["id"]
        other = self.lab.append("note", {"text": "alone"}, by="AC1")["id"]
        st = self.lab.view(None)
        self.assertEqual(st.chain(n2), [n1, n2, n3])
        self.assertEqual([st.label(x) for x in (n1, n2, n3)], [f"{n1}.R1", f"{n1}.R2", f"{n1}.R3"])
        self.assertEqual(st.label(other), other)                 # an uncorrected event keeps its plain ID
        self.assertEqual(st.resolve(f"{n1}.R2"), n2)
        self.assertEqual(st.resolve(n1), n1)                     # not a label: unchanged
        with self.assertRaises(LabError) as cm:
            st.resolve(f"{n1}.R4")
        self.assertIn(f"latest {n1}.R3", cm.exception.message)
        with self.assertRaises(LabError):
            st.resolve(f"{n2}.R1")                               # only a root starts a chain


class TestCommandLine(TestCli):
    def start(self):
        self.run_cli("lab", "init", "--title", "Study")
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model", "P|M|1",
                     "--record-source", "self_reported")
        self.run_cli("lab", "actor", "--kind", "human", "--name", "R", "--words", "I am R.",
                     "--given-at", "2026-11-12T10:00:00Z", "--by", "AC1")
        self.run_cli("lab", "question", "Does X help?", "--by", "AC1")
        self.run_cli("lab", "hypothesis", "X helps.", "--question", "Q1", "--by", "AC1")

    def plan(self, *extra):
        return self.run_cli("lab", "plan", "--kind", "confirmatory", "--hypotheses", "H1", "--design", "d",
                            "--analysis", "a", "--framework", "deterministic", "--quantity", "x=\"x\"",
                            "--supported", "H1: x > 0", "--not-supported", "H1: x <= 0", "--requires-approval",
                            *extra, "--by", "AC1")

    def test_a_revised_plan_is_one_plan_with_revisions(self):
        self.start()
        self.assertEqual(self.plan()[:2], (0, "PL1"))
        self.assertEqual(self.plan("--supersedes", "PL1")[:2], (0, "PL1.R2"))      # printed by its revision
        self.assertEqual(self.plan("--supersedes", "PL1.R2")[:2], (0, "PL1.R3"))   # and accepted as one
        code, out, _ = self.run_cli("lab", "summary")
        self.assertIn("PL1.R3 [confirmatory]", out)
        self.assertIn("show PL1.R3 to AC2", self.hint or self.run_cli("lab", "next")[1])
        code, _, err = self.run_cli("lab", "approve", "PL1.R2", "--by", "AC1", "--on-behalf-of", "AC2",
                                    "--words", "Yes.", "--given-at", "2026-11-12T11:00:00Z", "--channel", "chat")
        self.assertEqual(code, 1)
        self.assertIn("PL1.R3 is", err)                                              # an outdated revision
        code, out, _ = self.run_cli("lab", "approve", "PL1.R3", "--by", "AC1", "--on-behalf-of", "AC2",
                                    "--words", "Yes.", "--given-at", "2026-11-12T11:00:00Z", "--channel", "chat")
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("lab", "show", out, "--json")
        import json
        self.assertEqual(json.loads(out)["event"]["body"]["target"], "PL3")          # the log keeps event IDs
        code, out, _ = self.run_cli("lab", "show", "PL1.R2")
        self.assertEqual((json.loads(out)["event"]["id"], json.loads(out)["revision"]), ("PL2", "PL1.R2"))
        code, out, _ = self.run_cli("lab", "show", "PL1")
        self.assertEqual(json.loads(out)["revision"], "PL1.R3")                      # the root: the latest

    def test_an_unknown_revision_is_refused(self):
        self.start()
        self.plan()
        code, _, err = self.run_cli("lab", "show", "PL1.R2")
        self.assertEqual(code, 1)
        self.assertIn("PL1 has 1 revision", err)


if __name__ == "__main__":
    unittest.main()

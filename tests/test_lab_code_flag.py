"""`code_changed_after_plan` counts changes to the code, not to the record (lab record §5.7.5, erratum of
2026-11-11; issue #93). A record kept in the code checkout commits itself when the plan is written, so a run made
afterwards records a newer commit although no code changed. Only the record's own paths are left out of the
comparison: its folder now and the folders its relocations moved it from; the code moved with it is code."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from claimset.lab.core import Lab, plan_flags, verify

from test_lab import DECISION, run_body, ticking_clock

HAVE_GIT = shutil.which("git") is not None
FLAG = "code_changed_after_plan"


def git(*args, cwd):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.org"] + list(args), cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(HAVE_GIT, "git is not installed")
class TestCodeChangedAfterPlan(unittest.TestCase):
    """A record in the code checkout (the layout before study branches): repo/lab beside repo/analysis.py."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.top = Path(self.tmp.name) / "repo"
        self.top.mkdir()
        git("init", "-q", cwd=self.top)
        (self.top / "analysis.py").write_text("print(1)\n")
        (self.top / "old" / "lab").mkdir(parents=True)
        (self.top / "old" / "lab" / "notes.txt").write_text("the lab's former folder\n")
        (self.top / "old" / "code").mkdir()
        (self.top / "old" / "code" / "helper.py").write_text("x = 1\n")
        self.lab = Lab.create(self.top / "lab", "Study", clock=ticking_clock())
        human = self.lab.append("actor", {"kind": "human", "name": "R", "orcid": "0000-0000-0000-0000"}, by="AC1")["id"]
        self.agent = self.lab.append("actor", {"kind": "agent", "name": "A",
                                               "models": [{"provider": "P", "name": "M", "version": "1"}]},
                                     by=human)["id"]
        q = self.lab.append("question", {"text": "Q?"}, by=self.agent)["id"]
        self.h = self.lab.append("hypothesis", {"statement": "X helps.", "question": q, "origin": "a_priori"},
                                 by=self.agent)["id"]
        self.plan_commit = self.commit("code and record before the plan")
        self.pl = self.lab.append("plan", {"kind": "confirmatory", "hypotheses": [self.h], "design": "d",
                                           "analysis": "a", "decision": DECISION, "code_version": self.plan_commit,
                                           "dirty": False}, by=self.agent)["id"]

    def commit(self, message):
        git("add", "-A", cwd=self.top)
        git("commit", "-q", "--allow-empty", "-m", message, cwd=self.top)
        return git("rev-parse", "HEAD", cwd=self.top)

    def flags(self, run_commit, lab=True):
        self.lab.append("run", run_body(plan=self.pl, label="confirmatory", code_version=run_commit, dirty=False),
                        by=self.agent)
        st = self.lab.state()
        pv, runs = st.deciding_runs(self.pl)
        notes = []
        return plan_flags(st, pv, runs, lab=self.lab if lab else None, notes=notes), notes

    def test_only_the_record_changed(self):
        flags, notes = self.flags(self.commit("the plan, committed with the record"))     # lab/lab.jsonl only
        self.assertNotIn(FLAG, flags)
        self.assertEqual(notes, [])
        self.assertNotIn(f"plan {self.pl}: code changed after plan", verify(self.lab)["notes"])

    def test_the_code_changed_too(self):
        (self.top / "analysis.py").write_text("print(2)\n")
        flags, _ = self.flags(self.commit("the plan and a change of the analysis"))
        self.assertIn(FLAG, flags)

    def test_the_records_former_folder(self):
        self.lab.append("relocation", {"from": "old/lab", "to": "lab",
                                       "moved": [{"from": "old/code", "to": "code"}]}, by=self.agent)
        (self.top / "old" / "lab" / "notes.txt").write_text("changed\n")
        flags, _ = self.flags(self.commit("the record's former folder"))
        self.assertNotIn(FLAG, flags)

    def test_code_moved_with_the_record_is_code(self):
        self.lab.append("relocation", {"from": "old/lab", "to": "lab",
                                       "moved": [{"from": "old/code", "to": "code"}]}, by=self.agent)
        (self.top / "old" / "code" / "helper.py").write_text("x = 2\n")
        flags, _ = self.flags(self.commit("code that moved with the record"))
        self.assertIn(FLAG, flags)

    def test_commits_that_cannot_be_compared_keep_the_flag(self):
        flags, notes = self.flags("f" * 40)
        self.assertIn(FLAG, flags)
        self.assertIn("could not be compared", notes[0])

    def test_without_the_repository_the_commits_are_compared_as_before(self):
        flags, _ = self.flags(self.commit("the plan, committed with the record"), lab=False)
        self.assertIn(FLAG, flags)

    def test_uncommitted_changes_still_count(self):
        self.lab.append("run", run_body(plan=self.pl, label="confirmatory", code_version=self.plan_commit,
                                        dirty=True), by=self.agent)
        st = self.lab.state()
        self.assertIn(FLAG, plan_flags(st, *st.deciding_runs(self.pl), lab=self.lab))


if __name__ == "__main__":
    unittest.main()

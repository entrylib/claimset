"""EntryLib's good practice for planning a study: the copy the package carries, and `claimset guide study-planning`."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from claimset import bundle  # noqa: E402

_spec = importlib.util.spec_from_file_location("sync_study_planning", ROOT / "tools" / "sync_study_planning.py")
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


def run(*args, script=None):
    cmd = [sys.executable, str(script)] if script else [sys.executable, "-m", "claimset"]
    env = {"PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(cmd + list(args), capture_output=True, text=True, env=env)


class TestCopy(unittest.TestCase):
    def test_copy_matches_its_source_record(self):
        self.assertEqual(sync.check(), [], msg="edit the guides in entrylib/study-planning and copy them again with "
                                               "tools/sync_study_planning.py")

    def test_source_names_a_commit_and_the_licence_is_carried(self):
        source = json.loads((sync.DEST / "SOURCE.json").read_text(encoding="utf-8"))
        self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
        self.assertIn("LICENSE", source["files"])
        self.assertIn("README.md", source["files"])

    def test_a_changed_copy_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "study-planning"
            dest.mkdir()
            for f in sync.DEST.iterdir():
                (dest / f.name).write_bytes(f.read_bytes())
            (dest / "prediction.md").write_text("edited here", encoding="utf-8")
            (dest / "extra.md").write_text("not copied", encoding="utf-8")
            old, sync.DEST = sync.DEST, dest
            try:
                diff = sync.check()
            finally:
                sync.DEST = old
        self.assertTrue(any(d.startswith("prediction.md: changed") for d in diff), diff)
        self.assertTrue(any(d.startswith("extra.md: not listed") for d in diff), diff)

    def test_the_lab_skill_installs_the_guides(self):
        files = bundle.files("claimset-lab")
        self.assertIn("references/study-planning/prediction.md", files)
        self.assertIn("references/study-planning/SOURCE.json", files)
        self.assertNotIn("references/study-planning/prediction.md", bundle.files("claimset-submit"))


class TestReading(unittest.TestCase):
    def test_list(self):
        text = bundle.study_planning()
        self.assertIn("Good practice for planning a study", text)
        self.assertIn("commit", text.split("\n")[0])
        self.assertEqual(bundle.study_planning("study-planning"), text)
        self.assertIn("prediction", bundle.study_planning_guides())

    def test_one_guide(self):
        text = bundle.study_planning("study-planning/prediction")
        self.assertIn("## mean-forecasts", text)
        self.assertIn("## References", text)

    def test_one_entry_with_the_references_it_cites(self):
        text = bundle.study_planning("study-planning/prediction#prediction-intervals")
        self.assertIn("## prediction-intervals", text)
        self.assertNotIn("## mean-forecasts", text)
        self.assertIn("Version ", text)
        self.assertIn("doi:10.1198/016214506000001437", text)       # Gneiting and Raftery 2007, cited
        self.assertNotIn("doi:10.1111/j.1467-9868.2007.00587.x", text)  # Gneiting, Balabdaoui and Raftery 2007
        self.assertNotIn("doi:10.1198/jasa.2011.r10138", text)       # Gneiting 2011, not cited here

    def test_unknown_references_name_what_exists(self):
        with self.assertRaisesRegex(ValueError, "the guides are .*prediction"):
            bundle.study_planning("study-planning/nothing")
        with self.assertRaisesRegex(ValueError, "the entries are .*mean-forecasts"):
            bundle.study_planning("study-planning/prediction#nothing")
        with self.assertRaisesRegex(ValueError, "not a study-planning reference"):
            bundle.study_planning("methods/prediction")
        with self.assertRaisesRegex(ValueError, "name a guide"):
            bundle.study_planning("study-planning#mean-forecasts")

    def test_cited_forms(self):
        refs = ("## References\n\n"
                "- One, A. (2001). Title.\n"
                "- Two, B., and Three, C. (2002). Title\n  continued.\n"
                "- Four, D., Five, E., and Six, F. (2003). Title.\n"
                "- Seven, G., Eight, H., Nine, I., and Ten, J. (2004). Title.\n")
        names = lambda entry: [i.split(",")[0][2:] for i in bundle._cited(entry, refs)]  # noqa: E731
        self.assertEqual(names("One 2001"), ["One"])
        self.assertEqual(names("Two and Three 2002"), ["Two"])
        self.assertEqual(names("Four, Five and Six 2003; Four et al. 2003"), ["Four"])
        self.assertEqual(names("Seven et al. 2004"), ["Seven"])
        self.assertEqual(names("One 2002; Three 2002; Five et al. 2003"), [])


class TestCommand(unittest.TestCase):
    def test_guide_command(self):
        out = run("guide", "study-planning/qualitative#second-coder")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("## second-coder", out.stdout)
        out = run("guide", "study-planning/nothing")
        self.assertEqual(out.returncode, 1)
        self.assertIn("the guides are", out.stderr)

    def test_from_the_lab_skill(self):
        script = ROOT / "skills" / "claimset-lab" / "scripts" / "claimset"
        out = run("guide", "study-planning/prediction#same-target", script=script)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("## same-target", out.stdout)


if __name__ == "__main__":
    unittest.main()

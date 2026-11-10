"""`claimset migrate` reports what the new version requires: the file under the version it declared against the
migrated file under the current one (spec §2.6). Errors new to the current version must change, new warnings should
change, problems the file already had are listed as such, and judgement no rule checks is left to decide."""

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset.cli import main  # noqa: E402
from claimset.migrate import migrate, report  # noqa: E402
from claimset.validate import validate  # noqa: E402

COMPAT = ROOT / "tests" / "compat"


def load(version, name):
    return json.loads((COMPAT / version / name).read_text(encoding="utf-8"))


def rules(findings):
    return sorted({f["rule"] for f in findings})


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestReport(unittest.TestCase):
    def migrated(self, doc):
        out, done, todo = migrate(copy.deepcopy(doc))
        return report(doc, out, todo)

    def test_an_error_new_to_the_current_version_must_change(self):
        d = load("0.40", "submission-from-lab.json")
        c2 = next(c for c in d["claims"] if c["id"] == "C2")
        c2["test"]["quantities"]["lower"]["variable"] = "a result no evidence has"
        self.assertEqual(rules(validate(d).errors), [])                       # valid under v0.40, with a warning
        rep = self.migrated(d)
        self.assertEqual((rep["from"], rep["to"]), ("0.40", "0.41"))
        self.assertEqual(rules(rep["must_change"]), ["91"])
        self.assertTrue(rep["errors"])
        self.assertNotIn("W41", rules(rep["should_change"]))                  # what was a warning is now the error

    def test_a_warning_new_since_the_files_version_should_change(self):
        d = load("0.39", "submission-native.json")
        d["evidence"][0]["results"] = [{"id": f"R{i + 1}", "variable": "D1", "value": 0.1 * i,
                                        "conditions": {"series": i}} for i in range(9)]
        rep = self.migrated(d)
        self.assertIn("W40", rules(rep["should_change"]))                     # tables are the standard form from v0.40
        self.assertEqual(rep["must_change"], [])

    def test_what_the_file_already_had_is_listed_apart(self):
        d = load("0.40", "submission-native.json")
        d["evidence"][0]["results"] = [{"id": f"R{i + 1}", "variable": "D1", "value": 0.1 * i,
                                        "conditions": {"series": i}} for i in range(9)]
        rep = self.migrated(d)
        self.assertIn("W40", rules(rep["already"]["warnings"]))               # a v0.40 warning, not the migration's
        self.assertNotIn("W40", rules(rep["should_change"]))

    def test_judgement_no_rule_checks_is_left_to_decide(self):
        rep = report({"schema_version": "0.40"}, {"schema_version": "0.41"},
                     ["C3: no longer inherits D4, the assumptions of a method it is not about; add them",
                      "paper.declarations: ask the guarantor (warning 29)", "D2: give it a kind (rule 63)"])
        self.assertEqual(rep["to_decide"], ["C3: no longer inherits D4, the assumptions of a method it is not about; "
                                            "add them"])

    def test_every_finding_is_reported(self):
        files = [(v.name, f) for v in sorted(COMPAT.iterdir()) if v.is_dir() for f in sorted(v.glob("submission-*"))]
        files += [("examples", ROOT / "examples" / "submission-native.json"),
                  ("examples", ROOT / "examples" / "submission-from-lab.json")]
        self.assertGreater(len(files), 10)
        for version, path in files:
            doc = json.loads(path.read_text(encoding="utf-8"))
            out, _, todo = migrate(copy.deepcopy(doc))
            rep = report(doc, out, todo)
            after = validate(out)
            listed = rep["must_change"] + rep["should_change"] + rep["already"]["errors"] + rep["already"]["warnings"]
            key = lambda f: (f["rule"], f["where"], f["message"])          # noqa: E731
            self.assertEqual(sorted(map(key, listed)), sorted(map(key, after.errors + after.warnings)),
                             f"{version}/{path.name}")


class TestCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, doc):
        path = Path(self.tmp.name) / "paper.claimset.json"
        path.write_text(json.dumps(doc))
        return str(path)

    def test_errors_left_fail_the_command(self):
        d = load("0.40", "submission-from-lab.json")
        next(c for c in d["claims"] if c["id"] == "C2")["test"]["quantities"]["lower"]["variable"] = "gone"
        code, out, _ = run("migrate", self.write(d))
        self.assertEqual(code, 1)
        self.assertIn("specification 0.40 -> 0.41", out)
        self.assertIn("must change: 1 error(s) under v0.41 that the file did not have under v0.40", out)
        self.assertIn("The migrated file has errors", out)
        code, out, _ = run("migrate", self.write(d), "--json")
        rep = json.loads(out)
        self.assertEqual((code, rules(rep["must_change"]), rep["changed"]),
                         (1, ["91"], ["schema_version 0.40 -> 0.41"]))

    def test_a_clean_migration(self):
        code, out, _ = run("migrate", self.write(load("0.40", "submission-native.json")))
        self.assertEqual(code, 0, out)
        self.assertIn("changed: schema_version 0.40 -> 0.41", out)
        self.assertIn("The migrated file has no errors.", out)
        code, out, _ = run("migrate", self.write(json.loads((ROOT / "examples" / "submission-native.json").read_text())))
        self.assertEqual(code, 0)
        self.assertIn("nothing to migrate or change", out)


if __name__ == "__main__":
    unittest.main()

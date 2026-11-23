"""`claimset correct` and tables held in a file (spec §3.4, rule 106): a published file names each table's file by the
address the platform published it at, and a correction started from it failed rule 106 until the files were named
again by their path in the package. `claimset correct` now does that, and fetches each file, checked by its hash."""

import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import cli  # noqa: E402
from claimset.validate import validate  # noqa: E402

PUBLISHED = json.loads((ROOT / "examples" / "published-native.json").read_text(encoding="utf-8"))
ROWS = b"row,x,value\nr1,a,1\nr2,b,2\n"
URL = "https://platform.example/p/2026.000006/v3/files/files/rows.csv"


def published(rows=ROWS):
    d = copy.deepcopy(PUBLISHED)
    e = next(e for e in d["evidence"] if e.get("profile") != "formal")
    e.setdefault("tables", []).append({"id": "T9", "description": "two rows held in a file", "row_labels": ["x"],
                                       "columns": ["value"], "rows_file": "A90", "n_rows": 2})
    d["artefacts"].append({"id": "A90", "kind": "data", "uri": URL, "availability": {"level": "public"},
                           "version": "sha256:" + hashlib.sha256(rows).hexdigest(),
                           "description": "The rows of table T9."})
    d["artefacts"].append({"id": "A91", "kind": "data", "uri": "https://platform.example/other.csv",
                           "availability": {"level": "public"}, "description": "Not a table's file."})
    return d


def run(doc, fetched=ROWS, no_fetch=False):
    tmp = Path(tempfile.mkdtemp())
    src = tmp / "current.json"
    src.write_text(json.dumps(doc), encoding="utf-8")
    calls = []

    def fake(url, timeout=60):
        calls.append(url)
        return fetched
    real, cli.fetch_file = cli.fetch_file, fake
    try:
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli._cmd_correct(SimpleNamespace(file=str(src), output=str(tmp / "correction.json"),
                                                    no_fetch=no_fetch))
    finally:
        cli.fetch_file = real
    return code, tmp, json.loads((tmp / "correction.json").read_text(encoding="utf-8")), out.getvalue(), calls


class TestCorrectTableFiles(unittest.TestCase):
    def test_a_tables_file_is_named_by_its_path_in_the_package(self):
        d = published()
        moved = cli.table_files_to_package(d)
        self.assertEqual(moved, [("A90", URL, "files/rows.csv", d["artefacts"][-2]["version"])])
        arts = {a["id"]: a for a in d["artefacts"]}
        self.assertEqual(arts["A90"]["uri"], "files/rows.csv")
        self.assertEqual(arts["A91"]["uri"], "https://platform.example/other.csv")      # not a table's file

    def test_it_is_fetched_into_the_package_and_rule_106_holds(self):
        before = [x["rule"] for x in validate(cli.start_correction(published())[0]).errors]
        self.assertIn("106", before)                                    # the failure this fixes
        code, tmp, doc, out, calls = run(published())
        self.assertEqual(code, 0)
        self.assertEqual(calls, [URL])
        self.assertEqual((tmp / "files" / "rows.csv").read_bytes(), ROWS)
        self.assertNotIn("106", [x["rule"] for x in validate(doc).errors])
        self.assertIn("A90: files/rows.csv  fetched", out)

    def test_a_file_that_is_not_the_recorded_version_is_not_kept(self):
        code, tmp, _doc, out, _calls = run(published(), fetched=b"row,x,value\nr1,a,9\n")
        self.assertEqual(code, 1)
        self.assertFalse((tmp / "files" / "rows.csv").exists())
        self.assertIn("NOT KEPT", out)

    def test_without_fetching_it_says_where_each_file_is(self):
        code, tmp, doc, out, calls = run(published(), no_fetch=True)
        self.assertEqual((code, calls), (0, []))
        self.assertIn(f"A90: files/rows.csv  (fetch it from {URL})", out)
        self.assertEqual(next(a for a in doc["artefacts"] if a["id"] == "A90")["uri"], "files/rows.csv")


if __name__ == "__main__":
    unittest.main()

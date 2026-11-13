"""`claimset score`: the scores a claimset would have once published, computed on this machine by EntryLib's rubric
(rubric.assess, rubric.report), with the verifiability the platform sets at publication. Optional, before submitting.
The claimset package only prepares the file and supplies the claims to compare with; the scoring is the rubric's, so a
stub stands in for it here (the package does not depend on it), and the real one is used when it is installed."""

import contextlib
import copy
import io
import json
import sys
import tempfile
import threading
import types
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import package  # noqa: E402
from claimset import score as sc  # noqa: E402
from claimset.cli import main  # noqa: E402
from claimset.validate import validate, with_verifiability  # noqa: E402

EXAMPLE = json.loads((resources.files("claimset") / "data" / "examples" / "submission-from-lab.json")
                     .read_text(encoding="utf-8"))
try:
    import rubric as REAL_RUBRIC
    HAVE_RUBRIC = hasattr(REAL_RUBRIC, "assess")
except ImportError:
    HAVE_RUBRIC = False


def stub_rubric():
    """A rubric that records what it was given."""
    m = types.ModuleType("rubric")
    m.VERSION, m.seen = "9.9", {}

    def assess(doc, find=None):
        m.seen.update(doc=doc, find=find)
        if find:
            m.seen["found"] = find("Method [[D2:M]] beats the naive method $x < y$ on retail series.")
        return {"rubric": m.VERSION, "paper": {"score": 77, "band": "medium", "lowest": "C2"}, "claims": {},
                "problems": {}, "novelty": {}}
    m.assess = assess
    m.report = lambda scores, n=0: f"REPORT {scores['paper']['score']} top={n}\n"
    return m


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, doc, name="paper.claimset.json"):
        path = Path(self.tmp.name) / name
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path


class TestPreparation(Files):
    def test_with_verifiability_is_what_publication_sets(self):
        doc = copy.deepcopy(EXAMPLE)
        out = with_verifiability(doc)
        computed = validate(EXAMPLE).computed
        self.assertTrue(computed)
        for c in out["claims"]:
            if c["id"] in computed:
                self.assertEqual((c["verifiability"], c["verifiability_flags"]),
                                 (computed[c["id"]]["verifiability"], computed[c["id"]]["verifiability_flags"]))
        self.assertEqual(doc, EXAMPLE)                                       # the file itself is not changed
        self.assertEqual(with_verifiability(doc, {}), EXAMPLE)

    def test_the_rubric_scores_the_file_as_published(self):
        stub = stub_rubric()
        with mock.patch.dict(sys.modules, {"rubric": stub}):
            out = sc.score(self.write(EXAMPLE))
            text = sc.describe(out, 5)
        self.assertTrue(out["valid"])
        self.assertIsNone(stub.seen["find"])
        self.assertFalse(out["novelty_checked"])
        self.assertEqual(stub.seen["doc"], with_verifiability(EXAMPLE))
        self.assertIn("REPORT 77 top=5", text)
        self.assertIn("Novelty: not checked", text)
        self.assertIn("Scoring is optional. Submit the claimset as it is", text)
        self.assertIn("(computed on this machine; nothing was sent)", text)
        with mock.patch.dict(sys.modules, {"rubric": stub}):
            self.assertIn("(by EntryLib; nothing was kept)", sc.describe(out, by="by EntryLib; nothing was kept"))

    def test_a_site_may_name_the_score(self):
        stub = stub_rubric()
        with mock.patch.dict(sys.modules, {"rubric": stub}):
            out = sc.score(self.write(EXAMPLE))
            old = stub.report                                       # a rubric that takes no name: its own word
            self.assertIn("REPORT 77", sc.describe(out, name="Support"))
            stub.report = lambda scores, top=0, name="reliability": f"{name} REPORT"
            self.assertIn("Support REPORT", sc.describe(out, name="Support"))
            self.assertIn("reliability REPORT", sc.describe(out))
            stub.report = old

    def test_a_claimset_with_packaged_files_is_scored_alone_or_as_its_package(self):
        folder = Path(self.tmp.name) / "study"
        (folder / "files").mkdir(parents=True)
        doc = copy.deepcopy(EXAMPLE)
        doc["artefacts"].append({"id": "A9", "kind": "data", "title": "Results", "uri": "files/results.csv",
                                 "availability": {"level": "public"}})
        (folder / "files" / "results.csv").write_text("a,b\n1,2\n")
        path = folder / "paper.claimset.json"
        path.write_text(json.dumps(doc))
        zip_path = Path(self.tmp.name) / "paper.zip"
        package.build(path, zip_path)
        for source in (path, zip_path):
            stub = stub_rubric()
            with mock.patch.dict(sys.modules, {"rubric": stub}):
                self.assertTrue(sc.score(source)["valid"], source)
            self.assertIn("A9", {a["id"] for a in stub.seen["doc"]["artefacts"]})

    def test_the_validators_warnings_go_to_a_rubric_that_reads_them(self):
        stub = stub_rubric()
        plain = stub.assess

        def assess(doc, find=None, warnings=None):
            stub.seen["warnings"] = warnings
            return plain(doc, find)
        stub.assess = assess
        d = copy.deepcopy(EXAMPLE)
        c = next(c for c in d["claims"] if c.get("role") == "principal")
        c["statement"] = c["statement"] + " It reached 0.123456."
        with mock.patch.dict(sys.modules, {"rubric": stub}):
            self.assertTrue(sc.score(self.write(d))["valid"])
        self.assertIn(("W17", f"claims:{c['id']}.statement"), [(w["rule"], w["where"]) for w in stub.seen["warnings"]])

    def test_a_file_with_errors_is_not_scored(self):
        bad = copy.deepcopy(EXAMPLE)
        del bad["paper"]["title"]
        stub = stub_rubric()
        with mock.patch.dict(sys.modules, {"rubric": stub}):
            code, out, _ = run("score", str(self.write(bad)))
        self.assertEqual(code, 1)
        self.assertIn("Not scored: the claimset has", out)
        self.assertNotIn("doc", stub.seen)

    def test_without_the_rubric(self):
        with mock.patch.dict(sys.modules, {"rubric": None}):
            code, _, err = run("score", str(self.write(EXAMPLE)))
            with self.assertRaises(sc.ScoreError):
                sc.score(self.write(EXAMPLE))
        self.assertEqual(code, 2)
        self.assertIn("pip install entrylib-rubric", err)
        old = types.ModuleType("rubric")
        old.VERSION, old.score = "0.1", lambda d: {}
        with mock.patch.dict(sys.modules, {"rubric": old}):
            with self.assertRaisesRegex(sc.ScoreError, "too old.*pip install --upgrade entrylib-rubric"):
                sc.score(self.write(EXAMPLE))

    def test_json(self):
        with mock.patch.dict(sys.modules, {"rubric": stub_rubric()}):
            code, out, _ = run("score", str(self.write(EXAMPLE)), "--json")
        out = json.loads(out)
        self.assertEqual((code, out["valid"], out["scores"]["paper"]["score"]), (0, True, 77))


class FakeSearch(BaseHTTPRequestHandler):
    asked = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        FakeSearch.asked.append(self.path)
        body = json.dumps({"results": [{"id": "entrylib:2026.000003@v2#C4", "claim": "C4",
                                        "statement": "M beats the naive method."}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestNovelty(Files):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSearch)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.portal = f"http://127.0.0.1:{self.server.server_address[1]}"
        FakeSearch.asked.clear()

    def test_principal_claims_are_compared_with_the_public_search(self):
        stub = stub_rubric()
        with mock.patch.dict(sys.modules, {"rubric": stub}):
            code, out, _ = run("score", str(self.write(EXAMPLE)), "--novelty", "--portal", self.portal)
        self.assertEqual(code, 0, out)
        self.assertEqual(stub.seen["found"], [{"claim": "entrylib:2026.000003@v2#C4",
                                               "statement": "M beats the naive method."}])
        (path,) = FakeSearch.asked
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
        self.assertEqual(urllib.parse.urlsplit(path).path, "/api/search/claims")
        self.assertEqual(query["q"], ["method or beats or the or naive or retail or series"])
        self.assertIn("Novelty: principal claims compared", out)

    def test_an_unreachable_search_is_an_error_not_no_match(self):
        self.server.shutdown()
        self.server.server_close()
        with mock.patch.dict(sys.modules, {"rubric": stub_rubric()}):
            code, _, err = run("score", str(self.write(EXAMPLE)), "--novelty", "--portal", self.portal)
        self.assertEqual(code, 2)
        self.assertIn("the novelty check could not search EntryLib", err)

    def test_words(self):
        self.assertEqual(sc._words("[[D2:Method M]] is $a+b$ better at it; method again"),
                         ["method", "better", "again"])


@unittest.skipUnless(HAVE_RUBRIC, "the rubric package is not installed")
class TestWithTheRubric(Files):
    def test_the_report(self):
        code, out, _ = run("score", str(self.write(EXAMPLE)))
        self.assertEqual(code, 0, out)
        expected = REAL_RUBRIC.assess(with_verifiability(EXAMPLE))
        self.assertIn(f"PAPER: reliability {expected['paper']['score']} ({expected['paper']['band']})", out)
        self.assertIn("BIGGEST ISSUES", out)
        self.assertIn(REAL_RUBRIC.report(expected, 3), out)


if __name__ == "__main__":
    unittest.main()

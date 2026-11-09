"""`claimset submit` and `claimset status`, against a fake portal on localhost that answers as EntryLib does."""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import submit as sm  # noqa: E402
from claimset.cli import main  # noqa: E402

EXAMPLE = json.loads((resources.files("claimset") / "data" / "examples" / "submission-native.json")
                     .read_text(encoding="utf-8"))


class FakePortal(BaseHTTPRequestHandler):
    received = []

    def log_message(self, *args):
        pass

    def _answer(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        FakePortal.received.append((self.path, self.headers["Content-Type"], body))
        if self.path.startswith("/api/submissions/from-url"):
            url = json.loads(body)["url"]
            if "private" in url:
                return self._answer(422, {"error": "cannot fetch the URL: 10.0.0.1 is not a public address",
                                          "errors": [], "warnings": []})
        elif b"Duplicate" in body:
            return self._answer(409, {"error": "this looks like a claimset already on EntryLib: entrylib:2026.000001",
                                      "errors": [], "warnings": []})
        self._answer(201, {"id": "sub_abc", "state": "pending", "kind": "new", "expires": "2026-11-11T12:00:00+00:00",
                           "status_url": "http://127.0.0.1/api/submissions/sub_abc",
                           "guarantors": [{"orcid": "0000-0000-0000-0000", "confirmed": False}],
                           "consent": [{"orcid": "0000-0000-0000-0000", "name": "A. Researcher",
                                        "consent_url": "http://127.0.0.1/consent/token"}],
                           "report": {"valid": True, "errors": [],
                                      "warnings": [{"rule": "W21", "where": "artefacts[0]", "message": "a branch"}]}})

    def do_GET(self):
        FakePortal.received.append((self.path, None, b""))
        if self.path == "/api/submissions/sub_abc":
            return self._answer(200, {"id": "sub_abc", "state": "published", "kind": "new",
                                      "expires": "2026-11-11T12:00:00+00:00",
                                      "guarantors": [{"orcid": "0000-0000-0000-0000", "confirmed": True}],
                                      "published": "entrylib:2026.000001@v1"})
        self._answer(404, {"error": "no such submission (submissions are forgotten 14 days after they close)"})


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestSubmit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakePortal)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.portal = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakePortal.received.clear()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.file = self.tmp / "paper.claimset.json"
        self.file.write_text(json.dumps(EXAMPLE))

    def test_a_claimset_file(self):
        code, out, _ = run("submit", str(self.file), "--portal", self.portal)
        self.assertEqual(code, 0)
        self.assertIn("http://127.0.0.1/consent/token", out)
        self.assertIn("shown only now", out)
        self.assertIn("claimset status sub_abc", out)
        self.assertIn("W21 artefacts[0]", out)
        path, kind, body = FakePortal.received[0]
        self.assertEqual((path, kind), ("/api/submissions", "application/json"))
        self.assertEqual(json.loads(body), EXAMPLE)

    def test_a_package_folder_is_sent_as_a_zip(self):
        bag = self.tmp / "bag"
        self.assertEqual(run("package", str(self.file), "-o", str(bag))[0], 0)
        self.assertEqual(run("submit", str(bag), "--portal", self.portal, "--new-paper")[0], 0)
        path, kind, body = FakePortal.received[0]
        self.assertEqual((path, kind), ("/api/submissions?new_paper=true", "application/zip"))
        self.assertIn("data/paper.claimset.json", zipfile.ZipFile(io.BytesIO(body)).namelist())

    def test_by_url(self):
        url = "https://zenodo.org/records/1/files/paper.zip"
        code, out, _ = run("submit", url, "--portal", self.portal, "--json")
        self.assertEqual((code, json.loads(out)["id"]), (0, "sub_abc"))
        self.assertEqual(json.loads(FakePortal.received[0][2]), {"url": url})
        code, _, err = run("submit", "https://private.example/p.zip", "--portal", self.portal)
        self.assertEqual(code, 1)
        self.assertIn("not a public address", err)
        self.assertEqual(run("submit", "http://e.org/p.zip", "--portal", self.portal)[0], 1)

    def test_refusals(self):
        bad = dict(EXAMPLE, paper={k: v for k, v in EXAMPLE["paper"].items() if k != "title"})
        self.file.write_text(json.dumps(bad))
        code, _, err = run("submit", str(self.file), "--portal", self.portal)
        self.assertEqual(code, 1)
        self.assertIn("validation error", err)
        self.assertIn("rule", err)
        self.assertEqual(FakePortal.received, [])          # not sent
        dup = json.loads(json.dumps(EXAMPLE))
        dup["paper"]["title"] = "Duplicate " + dup["paper"]["title"]
        self.file.write_text(json.dumps(dup))
        code, _, err = run("submit", str(self.file), "--portal", self.portal)
        self.assertEqual(code, 1)
        self.assertIn("entrylib:2026.000001", err)
        self.assertEqual(run("submit", str(self.tmp / "missing.json"), "--portal", self.portal)[0], 1)

    def test_status(self):
        code, out, _ = run("status", "sub_abc", "--portal", self.portal)
        self.assertEqual(code, 0)
        self.assertIn("sub_abc: published", out)
        self.assertIn("published as entrylib:2026.000001@v1", out)
        code, _, err = run("status", "sub_nothing", "--portal", self.portal)
        self.assertEqual(code, 1)
        self.assertIn("no such submission", err)
        self.assertEqual(run("status", "../etc", "--portal", self.portal)[0], 1)

    def test_portal_address(self):
        with self.assertRaises(sm.SubmitError):
            sm.portal_url("http://entrylib.org")             # https only, except localhost
        self.assertEqual(sm.portal_url("https://entrylib.org/"), "https://entrylib.org")
        code, _, err = run("status", "sub_abc", "--portal", "https://127.0.0.1:1")
        self.assertEqual(code, 1)
        self.assertIn("cannot reach", err)


if __name__ == "__main__":
    unittest.main()

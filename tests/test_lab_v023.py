"""Lab record v0.23: results in run files (§5.10, L4, L36), contributors (§3.7, L34, L35), credit (§9),
`init.continues` (§5.1), signatures (§4.7) and the reading view (§11).

From a simulation study whose record was 9.3 MB, 97% of it result events, which neither its repository's host nor
assistants could read; and from the wish that a second person could take a record up and be credited."""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from claimset.lab.core import Lab, LabError, verify  # noqa: E402
from claimset.lab.export import export  # noqa: E402
from claimset.lab.run import run_command  # noqa: E402
from claimset.lab import view as lab_view  # noqa: E402
from claimset.validate import validate  # noqa: E402
from test_lab import ticking_clock  # noqa: E402

KEY = "0000-0002-1825-0097"
SCRIPT = ("import json, os, sys\n"
          "n = int(sys.argv[1]) if len(sys.argv) > 1 else 3\n"
          "json.dump([{'variable': 'error', 'value': 0.5 + i / 10, 'conditions': {'k': i}} for i in range(n)]\n"
          "          + [{'variable': 'bad', 'value': 'x'}], open(os.environ['CLAIMSET_RESULTS'], 'w'))\n")
MODEL = [{"provider": "P", "name": "M", "version": "1"}]
DECISION = {"framework": "formal", "parameters": {"checker": "independent"}, "supported": "proof checked",
            "not_supported": "counterexample"}


class Case(unittest.TestCase):
    version = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.lab = Lab.create(self.dir / "lab", "Study", clock=ticking_clock(), lab_spec_version=self.version)
        self.owner = self.lab.append("actor", {"kind": "human", "name": "Owner", "orcid": "0000-0001-7826-0281"},
                                     by="AC1")["id"]
        self.agent = self.lab.append("actor", {"kind": "agent", "name": "Agent", "models": MODEL},
                                     by=self.owner)["id"]
        self.q = self.lab.append("question", {"text": "Does X help?"}, by=self.agent)["id"]
        self.script = self.dir / "s.py"
        self.script.write_text(SCRIPT)

    def run_(self, by=None, n=3, **kw):
        return run_command(self.lab, by or self.agent, [sys.executable, str(self.script), str(n)], echo=False,
                           cwd=str(self.dir), **kw)

    def contribute(self):
        log, ev = self.lab.contribute(orcid=KEY, name="Josiah Carberry")
        agent = self.lab.append("actor", {"kind": "agent", "name": "Their agent", "models": MODEL},
                                by=f"{KEY}.AC2")["id"]
        return log, ev, agent


class TestResultsInFiles(Case):
    def test_a_run_writes_its_results_file_and_no_result_event(self):
        out = self.run_()
        run = out["run"]
        self.assertEqual(run["body"]["results"], {"path": "results.csv", "rows": 3})
        self.assertIn("results.csv", {o["path"] for o in run["body"]["outputs"]})
        self.assertEqual([r["id"] for r in out["results"]], ["RN1.1", "RN1.2", "RN1.3"])
        self.assertEqual(len(out["problems"]), 1)                               # the invalid entry is reported
        types = [e["type"] for e in self.lab.read()]
        self.assertNotIn("result", types)
        st = self.lab.state()
        self.assertEqual(st.get("RN1.2")["body"], {"variable": "error", "value": 0.6, "conditions": {"k": 1},
                                                   "run": "RN1", "source": "results.csv"})
        self.assertTrue(verify(self.lab)["ok"])

    def test_results_are_cited_by_their_rows(self):
        h = self.lab.append("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"},
                            by=self.agent)["id"]
        self.run_()
        self.lab.append("status", {"target": h, "to": "supported", "rationale": "r", "evidence": ["RN1.2"]},
                        by=self.agent)
        with self.assertRaises(LabError) as cm:
            self.lab.append("status", {"target": h, "to": "inconclusive", "rationale": "r",
                                       "evidence": ["RN1.9"]}, by=self.agent)
        self.assertEqual(cm.exception.rule, "L12")

    def test_l6_holds_for_rows(self):
        self.run_()
        h = self.lab.append("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "from_exploration",
                                           "prompted_by": ["RN1"]}, by=self.agent)["id"]
        with self.assertRaises(LabError) as cm:
            self.lab.append("status", {"target": h, "to": "supported", "rationale": "r", "evidence": ["RN1.3"]},
                            by=self.agent)
        self.assertEqual(cm.exception.rule, "L6")

    def test_a_log_without_its_run_folders_still_verifies(self):
        """A published log read alone (§5.10): its rows resolve, and checks that need their values are not made."""
        from claimset.lab.core import verify_events
        h = self.lab.append("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"},
                            by=self.agent)["id"]
        pl = self.lab.append("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                                      "decision": DECISION}, by=self.agent)["id"]
        run = self.run_(plan=pl)["run"]["id"]
        self.lab.append("status", {"target": h, "to": "supported", "rationale": "proof checked", "plan": pl,
                                   "evidence": [f"{run}.2"], "rule": "supported"}, by=self.agent)
        events = [json.loads(line) for line in (self.dir / "lab" / "lab.jsonl").read_text().splitlines()]
        report = verify_events(events)
        self.assertTrue(report["ok"], report["errors"])

    def test_l4_no_result_event(self):
        run = self.run_()["run"]["id"]
        with self.assertRaises(LabError) as cm:
            self.lab.append("result", {"run": run, "variable": "q", "value": 1.0, "source": "results.csv"},
                            by=self.agent)
        self.assertEqual(cm.exception.rule, "L4")

    def test_l36_the_file_must_hold_its_rows(self):
        self.run_()
        f = self.dir / "lab" / "runs" / "RN1" / "results.csv"
        os.chmod(f, 0o644)
        f.write_text(f.read_text().splitlines()[0] + "\n")                       # the rows removed
        rules = {e["rule"] for e in verify(self.lab)["errors"]}
        self.assertIn("L36", rules)
        self.assertIn("L13", rules)

    def test_a_large_results_file_is_compressed_and_read(self):
        out = self.run_(n=60000)                                               # over 1 MB of text
        self.assertEqual(out["run"]["body"]["results"], {"path": "results.csv.gz", "rows": 60000})
        self.assertEqual(self.lab.state().get("RN1.60000")["body"]["conditions"], {"k": 59999})
        self.assertTrue(verify(self.lab)["ok"])

    def test_the_run_schema(self):
        from claimset.lab.core import State
        st = self.lab.state()
        bad = {"label": "exploratory", "command": ["x"], "exit_status": "success",
               "outputs": [{"path": "results.csv", "hash": "sha256:" + "0" * 64}], "results": {"path": "results.csv"}}
        with self.assertRaises(LabError):
            st.check("run", st.next_id("run"), self.agent, bad, None)
        bad["results"] = {"path": "other.csv", "rows": 1}
        with self.assertRaises(LabError) as cm:
            st.check("run", st.next_id("run"), self.agent, bad, None)
        self.assertEqual(cm.exception.rule, "L36")
        self.assertIsInstance(State, type)


class TestEarlierRecords(Case):
    version = "0.22"

    def test_results_stay_events(self):
        out = self.run_()
        self.assertNotIn("results", out["run"]["body"])
        self.assertEqual([r["id"] for r in out["results"]], ["RS1", "RS2", "RS3"])
        self.assertNotIn("results.csv", {o["path"] for o in out["run"]["body"]["outputs"]})

    def test_no_contributors_or_results_files(self):
        with self.assertRaises(LabError) as cm:
            self.lab.contribute(orcid=KEY, name="J")
        self.assertEqual(cm.exception.rule, "L34")
        st = self.lab.state()
        body = {"label": "exploratory", "command": ["x"], "exit_status": "success", "outputs": [],
                "results": {"path": "results.csv", "rows": 1}}
        with self.assertRaises(LabError):
            st.check("run", st.next_id("run"), self.agent, body, None)


class TestContributors(Case):
    def test_a_contributor_writes_their_own_log_with_their_key(self):
        log, ev, agent = self.contribute()
        self.assertEqual(log, KEY)
        self.assertEqual((ev["id"], ev["by"], ev["body"]["orcid"]), (f"{KEY}.AC1", f"{KEY}.AC1", KEY))
        self.assertEqual(agent, f"{KEY}.AC2")
        h = self.lab.append("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"},
                            by=agent)
        self.assertEqual(h["id"], f"{KEY}.H1")
        run = self.run_(by=agent)
        self.assertEqual(run["run"]["id"], f"{KEY}.RN1")
        self.assertEqual(run["results"][0]["id"], f"{KEY}.RN1.1")
        main = [e["id"] for e in self.lab.read()]
        self.assertNotIn(f"{KEY}.H1", main)                                     # the main log is the owner's
        lines = (self.dir / "lab" / "contributors" / f"{KEY}.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 4)

    def test_merge_and_go_on(self):
        _, _, agent = self.contribute()
        self.lab.append("note", {"text": "first"}, by=agent)
        m = self.lab.merge(self.owner, [KEY])
        self.assertEqual(m["body"], {"agents": [], "events_merged": 3, "contributors": [f"contributors/{KEY}.jsonl"]})
        merged = [e for e in self.lab.read() if e["id"].startswith(KEY)]
        self.assertEqual(merged[0]["origin"]["log"], f"contributors/{KEY}.jsonl")
        with self.assertRaises(LabError) as cm:                                 # no open log: open the next
            self.lab.append("note", {"text": "more"}, by=agent)
        self.assertEqual(cm.exception.rule, "L35")
        log2, ev2 = self.lab.contribute(orcid=KEY)
        self.assertEqual((log2, ev2), (f"{KEY}.2", None))
        self.assertEqual(self.lab.append("note", {"text": "more"}, by=agent)["id"], f"{KEY}.NT2")   # continues
        self.lab.merge(self.owner)
        report = verify(self.lab)
        self.assertTrue(report["ok"], report["errors"])

    def test_l34_the_log_begins_with_the_contributor(self):
        path = self.dir / "lab" / "contributors" / f"{KEY}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        with self.assertRaises(LabError) as cm:                                 # an agent first: refused
            self.lab.append("actor", {"kind": "agent", "name": "A", "models": MODEL}, by=f"{KEY}.AC1")
        self.assertEqual(cm.exception.rule, "L34")
        with self.assertRaises(LabError) as cm:                                 # another person's ORCID iD
            self.lab.append("actor", {"kind": "human", "name": "X", "orcid": "0000-0001-7826-0281"},
                            by=f"{KEY}.AC1")
        self.assertEqual(cm.exception.rule, "L34")
        ok = self.lab.append("actor", {"kind": "human", "name": "J", "orcid": KEY}, by=f"{KEY}.AC1")
        self.assertEqual(ok["id"], f"{KEY}.AC1")

    def test_l35_only_the_contributors_actors_write_it(self):
        self.contribute()
        from claimset.lab.core import State
        st = self.lab.side_state(self.lab.read(), KEY)
        with self.assertRaises(LabError) as cm:                                 # the owner's agent, into their log
            st.check("note", st.next_id("note"), self.agent, {"text": "x"}, None)
        self.assertEqual(cm.exception.rule, "L35")
        with self.assertRaises(LabError) as cm:                                 # no papers in a contributor's log
            st.check("paper", st.next_id("paper"), f"{KEY}.AC2", {"name": "p", "questions": [self.q]}, None)
        self.assertEqual(cm.exception.rule, "L35")
        self.assertIsInstance(st, State)

    def test_a_github_account_without_orcid(self):
        log, ev = self.lab.contribute(github="Alice-Smith", name="Alice")
        self.assertEqual(log, "github-alice-smith")
        self.assertEqual((ev["id"], ev["body"]["github"]), ("github-alice-smith.AC1", "Alice-Smith"))

    def test_a_merged_log_changed_afterwards_is_reported(self):
        _, _, agent = self.contribute()
        self.lab.append("note", {"text": "first"}, by=agent)
        self.lab.merge(self.owner)
        path = self.dir / "lab" / "contributors" / f"{KEY}.jsonl"
        lines = path.read_text().splitlines()
        lines[-1] = lines[-1].replace("first", "altered")
        path.write_text("\n".join(lines) + "\n")
        self.assertFalse(verify(self.lab)["ok"])

    def test_export_credits_each_contributor(self):
        _, _, agent = self.contribute()
        h = self.lab.append("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"},
                            by=agent)["id"]
        pl = self.lab.append("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                                      "decision": DECISION, "requires_approval": True}, by=agent)["id"]
        self.lab.append("approval", {"target": pl, "on_behalf_of": f"{KEY}.AC1", "words": "Yes, go ahead.",
                                     "given_at": "2026-11-20T10:00:00Z", "channel": "chat"}, by=agent)
        run = self.run_(by=agent, plan=pl)["run"]["id"]
        self.lab.append("status", {"target": h, "to": "supported", "rationale": "proof checked", "plan": pl,
                                   "evidence": [run], "rule": "supported"}, by=agent)
        self.lab.merge(self.owner)
        out = export(self.lab)
        people = {c["name"]: c for c in out["draft"]["contributors"]}
        self.assertEqual(people["Josiah Carberry"]["orcid"], KEY)
        self.assertEqual(people["Josiah Carberry"]["credit_roles"], ["supervision"])        # their approval
        self.assertEqual(people["Their agent"]["credit_roles"], ["conceptualization", "methodology",
                                                                 "formal_analysis"])
        self.assertIn("credit roles", " ".join(t["what"] for t in out["completion"]))
        ev = out["draft"]["evidence"][0]
        self.assertEqual(ev["lab_runs"], [f"{KEY}.RN1"])
        self.assertNotIn("1", {e["rule"] for e in validate(out["draft"]).errors if "lab_runs" in e["where"]})


class TestContinuesAndSignatures(unittest.TestCase):
    def test_continues(self):
        with tempfile.TemporaryDirectory() as d:
            cont = {"record": "https://github.com/o/r/blob/abc/lab/lab.jsonl", "head": "sha256:" + "a" * 64,
                    "study": "earlier"}
            lab = Lab.create(Path(d) / "lab", "Next", clock=ticking_clock(), continues=cont)
            self.assertEqual(lab.read()[0]["body"]["continues"], cont)
            self.assertTrue(verify(lab)["ok"])
            self.assertIn("continues https://github.com/o/r", lab_view.render(lab.read()))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(LabError):
                Lab.create(Path(d) / "lab", "Next", continues={"record": "not a url", "head": "x"})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(LabError):
                Lab.create(Path(d) / "lab", "Old", lab_spec_version="0.22", continues=cont)

    def test_a_signature_is_kept_and_noted(self):
        with tempfile.TemporaryDirectory() as d:
            lab = Lab.create(Path(d) / "lab", "S", clock=ticking_clock())
            lab.append("actor", {"kind": "human", "name": "O"}, by="AC1")
            lines = lab.log_path.read_text().splitlines()
            e = json.loads(lines[1])
            e["signature"] = {"key": "0000-0001-7826-0281", "alg": "none", "value": "x"}
            lines[1] = json.dumps(e)
            lab.log_path.write_text("\n".join(lines) + "\n")
            report = verify(lab)
            self.assertTrue(report["ok"], report["errors"])
            self.assertTrue(any("signature" in n for n in report["notes"]))


class TestReadingView(Case):
    def test_the_view_counts_results_and_never_lists_them(self):
        self.run_(n=50)
        text = lab_view.render(self.lab.read())
        self.assertIn("50 results in runs/RN1/results.csv (RN1.1 to RN1.50)", text)
        self.assertNotIn("0.55", text)                                          # no value
        self.assertIn("WHO", text)
        self.assertIn("main log; credit: conceptualization, formal_analysis", text)

    def test_the_trail_of_a_hypothesis_and_of_its_claim(self):
        h = self.lab.append("hypothesis", {"statement": "X helps.", "question": self.q, "origin": "a_priori"},
                            by=self.agent)["id"]
        other = self.lab.append("hypothesis", {"statement": "Z.", "question": self.q, "origin": "a_priori"},
                                by=self.agent)["id"]
        pl = self.lab.append("plan", {"kind": "confirmatory", "hypotheses": [h], "design": "d", "analysis": "a",
                                      "decision": DECISION}, by=self.agent)["id"]
        run = self.run_(plan=pl)["run"]["id"]
        self.lab.append("check", {"target": run, "outcome": "confirmed", "extent": "full"}, by=self.owner)
        self.lab.append("status", {"target": h, "to": "supported", "rationale": "proof checked", "plan": pl,
                                   "evidence": [run], "rule": "supported"}, by=self.agent)
        ids = lab_view.trail_ids(self.lab.read(), h)
        self.assertEqual([i[:2] for i in ids], ["Q1", "H1", "PL", "RN", "CK", "ST"])
        self.assertNotIn(other, ids)
        text = lab_view.trail(self.lab.read(), h)
        self.assertIn("3 results in runs/RN1/results.csv", text)
        claimset = {"claims": [{"id": "C1", "hypothesis": {"lab_event": h, "outcome": "supported"}}]}
        self.assertIn("TRAIL OF H1 (claim C1)", lab_view.claim_trail(self.lab.read(), claimset, "C1"))
        self.assertIsNone(lab_view.claim_trail(self.lab.read(), {"claims": [{"id": "C2"}]}, "C2"))

    def test_the_trail_of_a_planned_estimate(self):
        estimands = {"d": {"variable": "mean difference"}}
        body = {"kind": "estimation", "question": self.q, "design": "d", "analysis": "a", "estimands": estimands}
        first = self.lab.append("plan", body, by=self.agent)["id"]
        pl = self.lab.append("plan", {**body, "design": "d, worded better"}, by=self.agent, supersedes=first)["id"]
        self.lab.append("hypothesis", {"statement": "Unrelated.", "question": self.q, "origin": "a_priori"},
                        by=self.agent)
        run = self.run_(plan=pl)["run"]["id"]
        self.lab.append("note", {"text": "Seed chosen at random.", "refers_to": [run]}, by=self.owner)
        ids = lab_view.plan_trail_ids(self.lab.read(), pl)
        self.assertEqual([i[:2] for i in ids], ["Q1", "PL", "PL", "RN", "NT"])
        claimset = {"claims": [{"id": "C1", "planning": "planned_estimate", "estimate": {"lab_plan": pl}}]}
        text = lab_view.claim_trail(self.lab.read(), claimset, "C1")
        self.assertIn(f"TRAIL OF {first} (claim C1; plan as revised in {pl})", text)
        self.assertIn("estimands: d", text)
        self.assertIn("3 results in runs/RN1/results.csv", text)

    def test_records_before_v023(self):
        with tempfile.TemporaryDirectory() as d:
            lab = Lab.create(Path(d) / "lab", "Old", clock=ticking_clock(), lab_spec_version="0.22")
            a = lab.append("actor", {"kind": "agent", "name": "A", "models": MODEL}, by="AC1")["id"]
            run_command(lab, a, [sys.executable, str(self.script), "4"], echo=False, cwd=d)
            text = lab_view.render(lab.read())
            self.assertIn("4 results in runs/RN1/results.json (RS1 to RS4)", text)
            self.assertNotIn("RS2 ", text)


class TestClaimsetLabIds(unittest.TestCase):
    def test_lab_runs_may_carry_a_contributors_key(self):
        from claimset.validate import LAB_EVENT_RE, LAB_RUN_RE
        for good in ("RN4", "AC2.RN4", f"{KEY}.RN4", "github-alice.RN2"):
            self.assertTrue(LAB_RUN_RE.match(good), good)
        for bad in ("XX.RN4", "RN4.1", "0000-0002.RN4", "github-.RN2"):
            self.assertFalse(LAB_RUN_RE.match(bad), bad)
        self.assertTrue(LAB_EVENT_RE.match(f"{KEY}.CD3"))
        doc = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text())
        ev = doc["evidence"][0]
        ev["lab_runs"] = [f"{KEY}.RN4"]
        self.assertNotIn("lab_runs", " ".join(e["where"] for e in validate(doc).errors))
        bad = copy.deepcopy(doc)
        bad["evidence"][0]["lab_runs"] = ["XX.RN4"]
        self.assertIn("1", {e["rule"] for e in validate(bad).errors if "lab_runs" in e["where"]})


if __name__ == "__main__":
    unittest.main()

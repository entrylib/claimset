"""Registering actors (lab record spec v0.19 §5.2; rule L28; verify notes)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from claimset.lab.core import Lab, LabError, verify

from test_lab import TestCli, ticking_clock

MODEL = [{"provider": "Anthropic", "name": "Claude Opus", "version": "5.5"}]
WORDS = "I'm Jane Doe, ORCID 0000-0002-1825-0097."


class ActorCase(unittest.TestCase):
    """A lab begun under v0.19 where the agent registers itself first."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = Lab.create(Path(self.tmp.name) / "lab", "Study", clock=ticking_clock())
        self.agent = self.lab.append("actor", {"kind": "agent", "name": "Agent", "models": MODEL}, by="AC1")["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def actor(self, body, by):
        return self.lab.append("actor", body, by=by)

    def refused(self, body, by, supersedes=None):
        with self.assertRaises(LabError) as cm:
            self.lab.append("actor", body, by=by, supersedes=supersedes)
        self.assertEqual(cm.exception.rule, "L28", cm.exception.message)
        return cm.exception.message

    def notes(self):
        rep = verify(self.lab)
        self.assertTrue(rep["ok"], rep["errors"])
        return " | ".join(rep["notes"])


class TestRegistration(ActorCase):
    def test_an_agent_registers_a_person_with_their_words(self):
        ev = self.actor({"kind": "human", "name": "Jane Doe", "orcid": "0000-0002-1825-0097", "words": WORDS,
                         "given_at": "2026-11-05T20:30:00Z", "channel": "chat"}, by=self.agent)
        self.assertEqual((ev["by"], ev["body"]["words"]), (self.agent, WORDS))
        self.assertTrue(verify(self.lab)["ok"], verify(self.lab)["errors"])

    def test_a_person_registers_themselves_and_others(self):
        jane = self.actor({"kind": "human", "name": "Jane Doe"}, by="AC2")["id"]
        self.actor({"kind": "human", "name": "John Roe"}, by=jane)
        self.actor({"kind": "agent", "name": "Second agent", "models": MODEL}, by=jane)
        self.actor({"kind": "organisation", "name": "A lab"}, by=self.agent)        # no one to quote
        self.assertTrue(verify(self.lab)["ok"], verify(self.lab)["errors"])

    def test_L28_an_agent_never_registers_a_person_without_their_words(self):
        msg = self.refused({"kind": "human", "name": "Jane Doe"}, by=self.agent)
        self.assertIn("--words", msg)
        self.refused({"kind": "human", "name": "Jane Doe", "words": WORDS}, by="AC2")   # self, with words
        jane = self.actor({"kind": "human", "name": "Jane Doe", "words": WORDS}, by=self.agent)["id"]
        self.refused({"kind": "human", "name": "John Roe", "words": "I'm John."}, by=jane)  # a person writes
        self.refused({"kind": "human", "name": "Jane A. Doe"}, by=self.agent, supersedes=jane)
        self.actor({"kind": "human", "name": "Jane A. Doe"}, by=jane)                    # their own correction
        with self.assertRaises(LabError):
            self.lab.append("actor", {"kind": "human", "name": "J", "words": WORDS, "given_at": "yesterday"},
                            by=self.agent)

    def test_a_person_registered_by_the_agent_approves_through_it(self):
        jane = self.actor({"kind": "human", "name": "Jane Doe", "words": WORDS}, by=self.agent)["id"]
        q = self.lab.append("question", {"text": "Q?"}, by=self.agent)["id"]
        h = self.lab.append("hypothesis", {"statement": "X improves Y.", "question": q, "origin": "a_priori"},
                            by=self.agent)["id"]
        pl = self.lab.append("plan", {"kind": "exploratory", "hypotheses": [h], "design": "d", "analysis": "a",
                                      "requires_approval": True}, by=self.agent)["id"]
        self.lab.append("approval", {"target": pl, "on_behalf_of": jane, "words": "Approved."}, by=self.agent)
        self.assertTrue(verify(self.lab)["ok"], verify(self.lab)["errors"])


class TestNotes(ActorCase):
    def test_an_agent_alone_is_noted_until_a_person_is_registered(self):
        self.assertIn("the record has no human actor", self.notes())
        self.actor({"kind": "human", "name": "Jane Doe", "words": WORDS}, by=self.agent)
        self.assertNotIn("no human actor", self.notes())

    def test_records_begun_before_v0_19_keep_their_registrations(self):
        old = Lab(Path(self.tmp.name) / "old", clock=ticking_clock())
        old.root.mkdir()
        old.append("init", {"lab_spec_version": "0.18", "working_title": "t"}, by=None)
        hum = old.append("actor", {"kind": "human", "name": "H"}, by="AC1")["id"]
        agent = old.append("actor", {"kind": "agent", "name": "A", "models": MODEL}, by=hum)["id"]
        old.append("actor", {"kind": "human", "name": "K"}, by=agent)                    # no words: allowed then
        rep = verify(old)
        self.assertTrue(rep["ok"], rep["errors"])
        self.assertIn("human actors AC1 registered themselves and then the agent", " | ".join(rep["notes"]))


class TestActorCli(TestCli):
    def test_the_agent_registers_itself_then_the_person(self):
        self.run_cli("lab", "init", "--title", "Study")
        code, out, err = self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model",
                                      "Anthropic|Claude Opus|5.5|claude-opus-5-5")
        self.assertEqual((code, out), (0, "AC1"), err)
        code, _, err = self.run_cli("lab", "actor", "--kind", "human", "--name", "Jane Doe", "--by", "AC1")
        self.assertNotEqual(code, 0)
        self.assertIn("--words", err)
        code, _, err = self.run_cli("lab", "actor", "--kind", "human", "--name", "Jane Doe", "--words", WORDS)
        self.assertNotEqual(code, 0)                                             # words, but no writer
        code, out, err = self.run_cli("lab", "actor", "--kind", "human", "--name", "Jane Doe", "--orcid",
                                      "0000-0002-1825-0097", "--words", WORDS, "--given-at", "2026-11-05T20:30:00Z",
                                      "--channel", "chat", "--by", "AC1")
        self.assertEqual((code, out), (0, "AC2"), err)
        ev = json.loads((Path(self.env["CLAIMSET_LAB"]) / "lab.jsonl").read_text().splitlines()[-1])
        self.assertEqual((ev["by"], ev["body"]["words"], ev["body"]["channel"]), ("AC1", WORDS, "chat"))


class TestHarness(TestCli):
    """Lab record v0.21 §5.2: the harness an agent runs in (`system`), and the model the human sets."""

    def setUp(self):
        super().setUp()
        self.saved = {k: os.environ.pop(k) for k in list(os.environ)
                      if k in ("CLAIMSET_MODEL", "AI_AGENT") or k.startswith(("CLAUDECODE", "CODEX_", "GEMINI_CLI",
                                                                              "OPENCODE", "KILO", "QWEN_CODE"))}
        self.addCleanup(os.environ.update, self.saved)

    def start(self):
        self.assertEqual(self.run_cli("lab", "init", "--title", "Study")[0], 0)

    def last(self):
        return json.loads((Path(self.env["CLAIMSET_LAB"]) / "lab.jsonl").read_text().splitlines()[-1])["body"]

    def test_the_harness_that_names_itself(self):
        self.start()
        os.environ["GEMINI_CLI"] = "1"
        self.addCleanup(os.environ.pop, "GEMINI_CLI", None)
        self.assertEqual(self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model",
                                      "Google|Gemini|3|gemini-3-pro")[0], 0)
        self.assertEqual(self.last()["system"], {"name": "Gemini CLI"})

    def test_given_and_absent(self):
        self.start()
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model", "DeepSeek|DeepSeek|V3.2",
                     "--system", "opencode|1.4.2")
        self.assertEqual(self.last()["system"], {"name": "opencode", "version": "1.4.2"})
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "B", "--model", "DeepSeek|DeepSeek|V3.2", "--by",
                     "AC1")
        self.assertNotIn("system", self.last())
        code, _, err = self.run_cli("lab", "actor", "--kind", "human", "--name", "Jane", "--system", "x",
                                    "--words", "I'm Jane.", "--by", "AC1")
        self.assertNotEqual(code, 0)
        self.assertIn("--system", err)

    def test_the_model_the_human_sets(self):
        self.start()
        os.environ["CLAIMSET_MODEL"] = "MiniMax|MiniMax|M2|MiniMax-M2"
        self.addCleanup(os.environ.pop, "CLAIMSET_MODEL", None)
        self.assertEqual(self.run_cli("lab", "actor", "--kind", "agent", "--name", "A")[0], 0)
        body = self.last()
        self.assertEqual((body["models"], body["record_source"]),
                         ([{"provider": "MiniMax", "name": "MiniMax", "version": "M2", "identifier": "MiniMax-M2"}],
                          "user_reported"))

    def test_export_carries_it(self):
        self.start()
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "A", "--model", "DeepSeek|DeepSeek|V3.2",
                     "--system", "opencode|1.4")
        self.run_cli("lab", "note", "--by", "AC1", "hello")
        out = Path(self.tmp.name) / "draft.json"
        self.run_cli("lab", "export", "-o", str(out))
        agent = next(c for c in json.loads(out.read_text())["contributors"] if c["type"] == "agent")
        self.assertEqual(agent["system"], {"name": "opencode", "version": "1.4"})

    def test_a_malformed_system_is_refused(self):
        self.start()
        lab = Lab(Path(self.env["CLAIMSET_LAB"]))
        for bad in ({"version": "1"}, {"name": ""}, {"name": "x", "colour": "red"}, "opencode"):
            with self.assertRaises(LabError):
                lab.append("actor", {"kind": "agent", "name": "A", "models": MODEL, "system": bad}, by="AC1")

    def test_an_agents_label(self):
        """An agent says what it does in a few words (claimset §3.11 v0.41, lab record §5.2); export carries it."""
        self.start()
        self.run_cli("lab", "actor", "--kind", "agent", "--name", "Claude Code", "--model", "Anthropic|Claude Opus|5.5",
                     "--label", "drafting")
        self.assertEqual(self.last()["label"], "drafting")
        self.run_cli("lab", "note", "--by", "AC1", "hello")
        out = Path(self.tmp.name) / "draft.json"
        self.run_cli("lab", "export", "-o", str(out))
        agent = next(c for c in json.loads(out.read_text())["contributors"] if c["type"] == "agent")
        self.assertEqual((agent["name"], agent["label"]), ("Claude Code", "drafting"))
        lab = Lab(Path(self.env["CLAIMSET_LAB"]))
        for body in ({"kind": "agent", "name": "A", "models": MODEL, "label": "x" * 61},
                     {"kind": "agent", "name": "A", "models": MODEL, "label": " "},
                     {"kind": "human", "name": "Jane", "label": "supervision", "words": WORDS}):
            with self.assertRaises(LabError):
                lab.append("actor", body, by="AC1")


if __name__ == "__main__":
    unittest.main()

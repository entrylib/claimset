"""An agent's label (claimset v0.41 §3.11, as amended on 2026-11-11): rule 93, warning 43, the page view, and a site's
own way of showing people (render_parts' person)."""

import copy
import json
import re
import sys
import unittest
from importlib import resources
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import html  # noqa: E402
from claimset import validate as V  # noqa: E402

NATIVE = json.loads((resources.files("claimset") / "data" / "examples" / "submission-native.json").read_text("utf-8"))


def with_people(**changes):
    """The native example with its agent (P1) and person (P2) changed."""
    d = copy.deepcopy(NATIVE)
    for c in d["contributors"]:
        c.update(changes.get(c["id"], {}))
    return d


def found(d, rule):
    rep = V.validate(d)
    return [x for x in (rep.errors if rule.isdigit() else rep.warnings) if x["rule"] == rule]


class TestLabel(unittest.TestCase):
    def test_rule_93_a_short_label_on_an_agent(self):
        self.assertEqual(found(with_people(P1={"label": "drafting"}), "93"), [])
        self.assertEqual(len(found(with_people(P1={"label": "x" * 61}), "93")), 1)
        self.assertEqual(len(found(with_people(P1={"label": "  "}), "93")), 1)
        self.assertEqual(len(found(with_people(P1={"label": 3}), "93")), 1)
        self.assertEqual(len(found(with_people(P2={"label": "supervision"}), "93")), 1)     # agents only

    def test_warning_43_a_role_in_a_name(self):
        self.assertEqual(found(with_people(P1={"name": "Claude Code", "label": "drafting"}), "W43"), [])
        self.assertEqual(len(found(with_people(P1={"name": "Claude Code (drafting agent)"}), "W43")), 1)
        self.assertEqual(found(with_people(P2={"name": "A. Researcher (Lancaster)"}), "W43"), [])   # people as written

    def test_the_page_view_gives_the_label(self):
        header = html.render_parts(with_people(P1={"name": "Claude Code", "label": "drafting"}))["header"]
        authors = re.search(r'<p class="cs-authors">.*?</p>', header, re.S).group(0)
        self.assertIn('Claude Code <span class="cs-label">· drafting</span> (AI agent)', authors)
        plain = html.render_parts(with_people(P1={"name": "Claude Code"}))["header"]
        self.assertNotIn("cs-label", plain)

    def test_a_site_shows_people_its_own_way(self):
        """render_parts(person=…): the site draws each person and agent in the header; None keeps the default."""
        seen = []

        def person(c, where):
            seen.append((c.get("id"), where))
            return f'<b class="who">{html.esc(c.get("name"))}</b>' if c.get("type") == "agent" else None
        header = html.render_parts(with_people(P1={"name": "Claude <x>"}), person=person)["header"]
        self.assertIn('Authors: <b class="who">Claude &lt;x&gt;</b>', header)
        self.assertIn('orcid-verified', header)                               # the guarantor: the default
        self.assertEqual(sorted(seen), [("P1", "author"), ("P2", "guarantor")])

if __name__ == "__main__":
    unittest.main()


LAB = json.loads((resources.files("claimset") / "data" / "examples" / "submission-from-lab.json").read_text("utf-8"))


class TestSiteChoices(unittest.TestCase):
    """What a site decides through render_parts: what marks a claim, a claim's own page, how sections are arranged."""

    def test_marker_and_claim_url(self):
        parts = html.render_parts(LAB, marker=lambda c, where: ("<b>S</b>", " · after") if where == "claim" else "<i>s</i>",
                                  claim_url=lambda cid: f"/p/x/{cid}" if cid == "C2" else "javascript:x")
        c2 = re.search(r'<div class="cs-item cs-claim[^"]*" id="C2"><p class="cs-claim-meta">(.*?)</p>', parts["body"])
        self.assertTrue(c2.group(1).startswith('<b>S</b><a class="cs-claim-page" href="/p/x/C2">C2</a>'))
        self.assertTrue(c2.group(1).endswith(" · after"))
        self.assertNotIn("javascript:", parts["body"])                       # only safe addresses are linked
        self.assertNotIn('class="light light-', re.search(r'<ul class="cs-brief">.*?</ul>', parts["body"], re.S).group(0))
        default = html.render_parts(LAB)["body"]
        self.assertIn('class="light light-', default)                        # without a marker: the lights

    def test_byline(self):
        seen = []

        def byline(role, people):
            seen.append((role, [c["id"] for c in people]))
            return "Responsible: X" if role == "guarantor" else None

        header = html.render_parts(NATIVE, byline=byline)["header"]
        self.assertIn('<p class="cs-guarantor">Responsible: X</p>', header)
        self.assertIn('<p class="cs-authors">Authors: ', header)              # None: the package's words
        self.assertEqual([r for r, _ in seen], ["guarantor", "authors"])
        self.assertEqual(html.render_parts(NATIVE)["header"],
                         html.render_parts(NATIVE, byline=lambda role, people: None)["header"])
        self.assertEqual(html.render_parts(NATIVE)["header"], html.render_parts(NATIVE, byline="x")["header"])

    def test_blocks(self):
        parts = html.render_parts(LAB)
        self.assertEqual(list(parts["blocks"]), [sid for sid, _, _ in parts["sections"]])
        self.assertEqual("\n".join(parts["blocks"].values()), parts["body"])

    def test_vocabularies_in_words(self):
        body = html.render_parts(LAB)["body"]
        self.assertNotRegex(body, r"\bdata_type:|Verdict:|code_changed_after_plan|planned \d{4}-\d\d-\d\dT")
        self.assertIn("Outcome:</span> computed from the recorded results", body)
        self.assertEqual(html._date("2026-11-05T11:37:01Z"), "5 November 2026")
        self.assertEqual(html._date("soon"), "soon")

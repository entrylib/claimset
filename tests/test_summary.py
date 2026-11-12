"""A paper's summary (claimset spec v0.41 §3.1, as amended on 2026-11-11): rule 94, warning 45, the reading view and
the page view, where it comes first, under Summary, before Highlights."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import html  # noqa: E402
from claimset.render import render  # noqa: E402
from claimset.validate import validate  # noqa: E402

NATIVE = json.loads((ROOT / "examples" / "submission-native.json").read_text(encoding="utf-8"))
TEXT = "Method M forecasts UK retail sales better than the seasonal naive benchmark, with error $e_t$ lower by a tenth."


def doc(**paper):
    d = copy.deepcopy(NATIVE)
    d["paper"].update(paper)
    return d


def found(report, rule):
    return [x for x in report.errors + report.warnings if x["rule"] == rule]


class TestSummary(unittest.TestCase):
    def test_rule_94(self):
        self.assertEqual(found(validate(doc(summary=TEXT)), "94"), [])
        self.assertEqual(found(validate(NATIVE), "94"), [])                        # optional
        for bad in ("", "   ", 3, ["a"]):
            self.assertEqual(len(found(validate(doc(summary=bad)), "94")), 1, bad)

    def test_warning_45(self):
        self.assertEqual(found(validate(doc(summary=TEXT)), "W45"), [])
        self.assertEqual(found(validate(doc(summary=" ".join(["word"] * 150))), "W45"), [])
        self.assertEqual(len(found(validate(doc(summary=" ".join(["word"] * 151))), "W45")), 1)

    def test_reading_view(self):
        lines = render(doc(summary="A  finding,\nin plain words.")).splitlines()
        self.assertEqual(lines[1], "summary A finding, in plain words.")
        self.assertFalse(any(x.startswith("summary ") for x in render(NATIVE).splitlines()))

    def test_page_view_puts_it_first_then_the_highlights(self):
        parts = html.render_parts(doc(summary=TEXT))
        page = parts["body"]
        self.assertIn('<p class="cs-summary">', page)
        self.assertIn("<math", page.split('<p class="cs-summary">')[1].split("</p>")[0])
        self.assertEqual([s[0] for s in parts["sections"]][:2], ["summary", "highlights"])
        self.assertLess(page.index('id="summary"'), page.index('id="highlights"'))
        self.assertIn('class="cs-brief"', page.split('id="highlights"')[1].split("</section>")[0])
        plain = html.render_parts(NATIVE)
        self.assertNotIn('id="summary"', plain["body"])                    # no summary: it starts with Highlights
        self.assertEqual(plain["sections"][0][:2], ("highlights", "Highlights"))
        self.assertNotIn("<b>", html.render_parts(doc(summary="<b>x</b>"))["body"].split('cs-summary">')[1][:20])


if __name__ == "__main__":
    unittest.main()


class TestSmallFixes(unittest.TestCase):
    def test_a_tooltip_shows_maths_as_characters(self):
        tip = html._first_sentence("The error $\\epsilon_t \\sim N(0, \\sigma^2)$ of [[D2:the model]]. More.")
        self.assertEqual(tip, "The error ϵt∼N(0,σ2) of the model.")

    def test_an_artefact_links_its_file_not_its_description(self):
        d = copy.deepcopy(NATIVE)
        d["artefacts"] = [{"id": "A9", "kind": "code", "description": "The code that runs every forecast",
                           "uri": "https://github.com/x/y/blob/main/model.R"}]
        body = html.render_parts(d)["body"]
        self.assertIn('The code that runs every forecast <a class="cs-open" '
                      'href="https://github.com/x/y/blob/main/model.R">model.R</a>', body)
        self.assertEqual(html._link_name("https://zenodo.org/"), "zenodo.org")

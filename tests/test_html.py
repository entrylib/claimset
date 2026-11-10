"""The page view (claimset.html): order, lights, In brief, terms, references, maths, images, escaping."""

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

from claimset import html as H  # noqa: E402
from claimset.cli import main  # noqa: E402

EXAMPLES = ROOT / "src" / "claimset" / "data" / "examples"
COMPAT = ROOT / "tests" / "compat"


def example(name="submission-native.json"):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def claim(cid, role="principal", typ="descriptive", kind="argument", statement=None, **extra):
    c = {"id": cid, "type": typ, "role": role, "statement": statement or f"Statement {cid} about forecasting.",
         "support": [{"kind": kind}]}
    c.update(extra)
    return c


class TestWholeFiles(unittest.TestCase):
    def test_every_example_and_compat_file_renders(self):
        files = sorted(EXAMPLES.glob("*.json")) + sorted(COMPAT.glob("*/*.json"))
        self.assertTrue(files)
        for f in files:
            with self.subTest(f.name):
                page = H.render_html(json.loads(f.read_text(encoding="utf-8")))
                self.assertTrue(page.startswith("<!doctype html>"))
                self.assertNotIn("<script", page)

    def test_section_order(self):
        doc = example()
        doc["references"] = [{"id": "B1", "target": "Smith, J. (2020). A paper. Journal.", "id_type": "reference"}]
        doc["claims"][2]["relations"] = [{"type": "extends", "reference": "B1", "note": "Earlier result."}]
        doc["limitations"][0]["affects"] = ["C2"]
        body = H.render_parts(doc)["body"]
        order = ["brief", "context", "definitions", "assumptions", "principal", "evidence", "limitations",
                 "references", "artefacts"]
        positions = [body.index(f'id="{s}"') for s in order]
        self.assertEqual(positions, sorted(positions))

    def test_cli_writes_the_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / "x.claimset.json", Path(tmp) / "x.html"
            src.write_text(json.dumps(example()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["render", str(src), "--html", "-o", str(out)]), 0)
            page = out.read_text(encoding="utf-8")
            self.assertIn('class="cs-page"', page)
            self.assertIn(".cs-toc", page)                  # the stylesheet is inline


class TestEscaping(unittest.TestCase):
    def test_submitted_text_is_never_markup(self):
        doc = example()
        doc["paper"]["title"] = "<script>alert(1)</script>"
        doc["claims"][2]["statement"] = 'Rises <img src=x onerror="alert(1)"> and [[D1:<b>term</b>]].'
        doc["definitions"][0]["definition"] = '"><script>bad()</script>'
        page = H.render_html(doc)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<img src=x", page)
        self.assertNotIn("<b>term</b>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_only_http_links_from_the_file(self):
        doc = example()
        doc["artefacts"][0]["uri"] = "javascript:alert(1)"
        page = H.render_html(doc)
        self.assertNotIn('href="javascript:', page)


class TestLights(unittest.TestCase):
    def setUp(self):
        self.doc = {"paper": {"title": "T"}, "claims": [
            claim("C1", kind="empirical_quant", verifiability="open"),
            claim("C2", kind="empirical_quant", verifiability="audit_only"),
            claim("C3", kind="argument", verifiability="open"),
            claim("C4", kind="unstated", verifiability="unverifiable"),
            {"id": "C5", "type": "descriptive", "role": "supporting", "statement": "Assumed.",
             "support": [{"kind": "assumption"}], "assumption_category": "statistical", "verifiability": "not_applicable"}]}

    def test_each_light(self):
        P = H._Paper(self.doc)
        self.assertEqual([P.light(c) for c in P.claims], ["green", "amber", "amber", "red", None])
        parts = H.render_parts(self.doc)
        self.assertEqual(parts["lights"], {"green": 1, "amber": 2, "red": 1})
        self.assertIn('aria-label="supported, not checkable"', parts["body"])


WORDS = ["Seasonal models reduce error on monthly retail series.", "The estimator is consistent under mixing.",
         "Damped trends forecast long horizons better than linear trends.", "Intervals are too narrow for short series.",
         "Combinations beat single methods on the tourism data.", "The smoothing parameter controls stationarity.",
         "Outliers inflate the mean scaled interval score.", "Selection by AICc picks seasonal models too often.",
         "Hourly data need multiple seasonal cycles."]


class TestBrief(unittest.TestCase):
    def doc(self, n, **paper):
        return {"paper": {"title": "T", "contributions": [f"C{i}" for i in range(1, n + 1)], **paper},
                "definitions": [{"id": "D1", "kind": "method", "term": "M", "definition": "A method."}],
                "claims": [claim(f"C{i}", typ=("formal" if i % 2 else "descriptive"), statement=WORDS[i - 1])
                           for i in range(1, n + 1)]}

    def test_highlights_first(self):
        ids, auto = H.brief(self.doc(8, highlights=["C3", "D1"]))
        self.assertEqual((ids, auto), (["C3", "D1"], False))
        body = H.render_parts(self.doc(8, highlights=["C3", "D1"]))["body"]
        self.assertIn("<strong>M</strong>: A method.", body)

    def test_five_or_fewer_all_shown(self):
        self.assertEqual(H.brief(self.doc(4)), (["C1", "C2", "C3", "C4"], False))

    def test_computed_choice(self):
        doc = self.doc(9)
        doc["claims"].append(claim("C10", role="supporting", depends_on=["C7"]))
        doc["claims"].append(claim("C11", role="supporting", depends_on=["C10"]))
        ids, auto = H.brief(doc)
        self.assertTrue(auto)
        self.assertEqual(len(ids), H.BRIEF_MAX)
        self.assertIn("C7", ids)                            # used, directly and through C10
        self.assertEqual(ids, sorted(ids, key=lambda x: int(x[1:])))
        self.assertIn("Selected automatically", H.render_parts(doc)["body"])

    def test_near_duplicates_skipped(self):
        doc = self.doc(7)
        doc["claims"][1]["statement"] = doc["claims"][0]["statement"]
        ids, _ = H.brief(doc)
        self.assertFalse({"C1", "C2"} <= set(ids))


class TestTermsReferencesMaths(unittest.TestCase):
    def test_terms_link_to_definitions(self):
        P = H._Paper({"paper": {}, "definitions": [{"id": "D1", "kind": "method", "term": "CES",
                                                     "definition": "Complex exponential smoothing. More."}]})
        self.assertEqual(P.text("[[D1:CES]] and [[D9:other]]"),
                         '<a class="term" href="#D1" title="CES: Complex exponential smoothing.">CES</a> and other')

    def test_author_year_labels(self):
        refs = [{"id": "B1", "id_type": "reference",
                 "target": "Hyndman, R. J., Koehler, A. B., Ord, J. K., & Snyder, R. D. (2008). Forecasting. Springer."},
                {"id": "B2", "id_type": "reference", "target": "Kolassa, S. (2011). Combining. IJF, 27(2)."},
                {"id": "B3", "id_type": "reference", "target": "Petropoulos, F., & Svetunkov, I. (2020). A simple combination."},
                {"id": "B4", "id_type": "reference", "target": "Kolassa, S. (2011). Another. IJF."},
                {"id": "B5", "id_type": "doi", "target": "10.1002/nav.22074"}]
        P = H._Paper({"paper": {}, "references": refs})
        self.assertEqual(P.labels, {"B1": "Hyndman et al. (2008)", "B2": "Kolassa (2011a)",
                                    "B3": "Petropoulos and Svetunkov (2020)", "B4": "Kolassa (2011b)",
                                    "B5": "doi:10.1002/nav.22074"})

    def test_references_link_back(self):
        doc = example()
        doc["references"] = [{"id": "B1", "target": "Smith, J. (2020). A paper.", "id_type": "reference"}]
        doc["definitions"][0]["source"] = "B1"
        body = H.render_parts(doc)["body"]
        self.assertIn('Source: <a class="ref" href="#B1">Smith (2020)</a>', body)
        self.assertIn('Used by: <a href="#D1">D1</a>', body)

    def test_latex(self):
        self.assertEqual(H.latex(r"\phi_1 = 2 - \alpha_0"), "ϕ<sub>1</sub> = 2 − α<sub>0</sub>")
        self.assertEqual(H.latex(r"\hat{y}_t"), "y\u0302<sub>t</sub>")
        self.assertEqual(H.latex(r"x^{h-1} \leq \infty"), "x<sup>h−1</sup> ≤ ∞")
        self.assertEqual(H.latex(r"\unknown<b>"), "\\unknown&lt;b&gt;")
        P = H._Paper({"paper": {}})
        self.assertEqual(P.text("when $\\alpha_1 < 1$ holds"),
                         'when <span class="math">α<sub>1</sub> &lt; 1</span> holds')


class TestImages(unittest.TestCase):
    def doc(self, uri):
        doc = example()
        doc["artefacts"].append({"id": "A9", "kind": "figure", "function": "data_plot", "uri": uri,
                                 "description": "Errors by horizon", "shows": ["E1"]})
        return doc

    def test_a_packaged_figure_is_shown_in_its_evidence(self):
        body = H.render_parts(self.doc("figures/errors.png"))["body"]
        ev = body[body.index('id="evidence"'):body.index('id="limitations"')]
        self.assertIn('<img src="figures/errors.png" alt="Errors by horizon" loading="lazy">', ev)

    def test_the_site_gives_the_address(self):
        body = H.render_parts(self.doc("figures/errors.png"), file_url=lambda a: f"/files/{a['id']}.png")["body"]
        self.assertIn('<img src="/files/A9.png"', body)
        doc = self.doc("https://entrylib.org/files/0a1b")          # published: no extension; the site knows the type
        body = H.render_parts(doc, file_url=lambda a: "/img/0a1b.png" if a["id"] == "A9" else None)["body"]
        self.assertIn('<img src="/img/0a1b.png"', body)
        self.assertEqual(body.count("<img"), 1)

    def test_images_elsewhere_are_linked_not_embedded(self):
        for uri in ("https://example.org/fig.png", "../outside.png", "/etc/x.png"):
            with self.subTest(uri):
                body = H.render_parts(self.doc(uri))["body"]
                self.assertNotIn("<img", body)
        self.assertIn('href="https://example.org/fig.png"', H.render_parts(self.doc("https://example.org/fig.png"))["body"])

    def test_observation_records(self):
        doc = self.doc("images/gel.jpg")
        del doc["artefacts"][-1]["shows"]
        doc["evidence"][0]["records"] = [{"kind": "image", "artefact": "A9", "description": "Gel"}]
        self.assertIn('<img src="images/gel.jpg"', H.render_parts(doc)["body"])


class TestOriginAndHeader(unittest.TestCase):
    def test_origins(self):
        self.assertEqual(H.render_parts(example())["origin"], "native")
        self.assertEqual(H.render_parts(example("submission-from-lab.json"))["origin"], "lab")
        conv = copy.deepcopy(example())
        conv["paper"]["converted_from"] = {"source_id": "10.1/x", "source_authors": [{"name": "A. B", "orcid": None}]}
        parts = H.render_parts(conv)
        self.assertEqual(parts["origin"], "converted")
        self.assertIn('href="https://doi.org/10.1/x"', parts["header"])

    def test_guarantor_orcid_is_the_verified_one(self):
        header = H.render_parts(example())["header"]
        self.assertIn('class="orcid orcid-verified"', header)


if __name__ == "__main__":
    unittest.main()

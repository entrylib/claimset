"""The reading view follows the paper's sections, a definition may hold a table, and the reading view gives an
artefact's version (claimset spec v0.44 as amended on 2026-11-23: §2.3, §3.2, rule 108, Appendix D)."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import render as render_module  # noqa: E402
from claimset.render import render  # noqa: E402
from claimset.validate import validate  # noqa: E402

# C1 and C3 are assumptions; C2 (principal) and C4 (secondary) are the paper's claims
LAB = json.loads((ROOT / "examples" / "submission-from-lab.json").read_text(encoding="utf-8"))

TABLE = {"description": "The blocks of the matrices of each restriction of the model.",
         "columns": ["Restriction", "$W$", "$F$", "$G$"],
         "rows": [["None", "$I_m$", "$I_m$", "$\\mathrm{diag}(\\alpha_1, \\dots, \\alpha_m)$"],
                  ["Common smoothing", "$I_m$", "$I_m$", "$\\alpha I_m$"]]}


def doc(sections=None, tables=None):
    d = copy.deepcopy(LAB)
    if sections is not None:
        d["paper"]["sections"] = sections
    if tables is not None:
        d["definitions"][1]["tables"] = tables
    return d


def rules(report):
    return sorted({e["rule"] for e in report.errors})


def claims_part(view):
    return view.split("\nCLAIMS\n", 1)[1].split("\n\n", 1)[0]


class TestClaimsBySection(unittest.TestCase):
    def test_sections_give_the_order(self):
        view = render(doc([{"title": "What else was found", "claims": ["C4"]},
                           {"title": "The comparison", "claims": ["C2"]}]))
        part = claims_part(view)
        heads = [x for x in part.splitlines() if not x.startswith(" ")]
        self.assertEqual([h.split(" [")[0] for h in heads],
                         ["== 1. What else was found", "C4", "== 2. The comparison", "C2"])
        self.assertNotIn("== Claims in no section", view)     # the assumptions C1 and C3 are listed apart
        self.assertLess(view.index("\nASSUMPTIONS\nC1 ["), view.index("\nCLAIMS\n"))
        self.assertLess(view.index("\nDEFINITIONS\n"), view.index("\nCLAIMS\n"))
        self.assertLess(view.index("\nCLAIMS\n"), view.index("\nEVIDENCE\n"))

    def test_every_claim_placed_gives_no_heading_for_the_rest(self):
        d = doc([{"title": "All", "claims": ["C4", "C2"]}])
        for c in d["claims"]:
            if c["id"] in ("C1", "C3"):
                c["support"] = [{"kind": "argument"}]         # not principal, no evidence: listed apart
        view = render(d)
        self.assertNotIn("== Claims in no section", view)
        self.assertIn("\nCLAIMS WITHOUT EVIDENCE\nC1", view)
        self.assertEqual([x.split(" [")[0] for x in claims_part(view).splitlines() if not x.startswith(" ")],
                         ["== 1. All", "C4", "C2"])

    def test_a_claim_without_evidence_stays_in_its_section(self):
        d = doc([{"title": "The comparison", "claims": ["C2"]}, {"title": "What else was found", "claims": ["C4"]}])
        next(c for c in d["claims"] if c["id"] == "C4")["support"] = [{"kind": "argument"}]
        view = render(d)
        self.assertIn("== 2. What else was found\nC4 [", view)
        self.assertNotIn("CLAIMS WITHOUT EVIDENCE", view)

    def test_without_sections_nothing_changes(self):
        view = render(doc())
        self.assertNotIn("== ", view)
        self.assertEqual([x.split(" [")[0] for x in claims_part(view).splitlines() if not x.startswith(" ")],
                         ["C2", "C4"])            # principal first, then by role; the assumptions are listed apart

    def test_odd_sections_do_not_break_the_view(self):
        d = doc([{"title": "First", "claims": ["C2", "C99", 7, ["C4"], "C2"]},
                 {"title": "Second", "claims": ["C2"]}, "not a section"])
        part = claims_part(render(d))
        self.assertEqual(part.count("\nC2 ["), 1)
        self.assertIn("== 2. Second\n== Claims in no section", part)


class TestAssumptionsListedApart(unittest.TestCase):
    def test_assumptions_come_after_the_definitions_one_line_each(self):
        view = render(doc([{"title": "The comparison", "claims": ["C2", "C4"]}]))
        part = view.split("\nASSUMPTIONS\n")[1].split("\n\n")[0].splitlines()
        self.assertEqual([x.split(" [")[0] for x in part], ["C1", "C3"])
        self.assertTrue(all(not x.startswith(" ") for x in part))
        self.assertLess(view.index("\nDEFINITIONS\n"), view.index("\nASSUMPTIONS\n"))
        self.assertLess(view.index("\nASSUMPTIONS\n"), view.index("\nCLAIMS\n"))
        self.assertNotIn("\nC1 [", view.split("\nCLAIMS\n")[1])

    def test_a_paper_without_assumptions_has_no_such_part(self):
        d = doc()
        d["claims"] = [c for c in d["claims"] if c["id"] in ("C2", "C4")]
        for c in d["claims"]:
            c.pop("assumptions", None)
        self.assertNotIn("ASSUMPTIONS", render(d))


class TestRule108DefinitionTables(unittest.TestCase):
    def test_a_table(self):
        rep = validate(doc(tables=[TABLE]))
        self.assertEqual(rep.errors, [])

    def test_empty_cells(self):
        t = dict(TABLE, rows=[["None", "", "$I_m$", ""]])
        self.assertEqual(validate(doc(tables=[t])).errors, [])

    def test_no_tables_is_as_before(self):
        self.assertEqual(validate(doc()).errors, [])

    def test_broken_tables(self):
        broken = {
            "not a list": TABLE,
            "empty": [],
            "an entry that is no object": ["a table"],
            "another field": [dict(TABLE, id="T1")],
            "no description": [{k: v for k, v in TABLE.items() if k != "description"}],
            "an empty description": [dict(TABLE, description=" ")],
            "a description that is no text": [dict(TABLE, description=["The blocks"])],
            "no columns": [{k: v for k, v in TABLE.items() if k != "columns"}],
            "no column": [dict(TABLE, columns=[])],
            "an empty heading": [dict(TABLE, columns=["Restriction", "", "$F$", "$G$"])],
            "a heading that is no text": [dict(TABLE, columns=["Restriction", 2, "$F$", "$G$"])],
            "no rows": [{k: v for k, v in TABLE.items() if k != "rows"}],
            "no row": [dict(TABLE, rows=[])],
            "a row that is no list": [dict(TABLE, rows=["None | I | I | G"])],
            "a cell that is no string": [dict(TABLE, rows=[["None", 1, "$I_m$", "$G$"]])],
            "a row too short": [dict(TABLE, rows=[["None", "$I_m$", "$I_m$"]])],
            "a row too long": [dict(TABLE, rows=[["None", "$I_m$", "$I_m$", "$G$", "extra"]])],
        }
        for what, tables in broken.items():
            with self.subTest(what):
                self.assertIn("108", rules(validate(doc(tables=tables))), what)

    def test_term_markers_in_a_table(self):
        t = dict(TABLE, rows=[["[[D3:seasonal naive method]]", "$I_m$", "$I_m$", "$G$"]])
        self.assertEqual(validate(doc(tables=[t])).errors, [])
        t = dict(TABLE, rows=[["[[D99:no such term]]", "$I_m$", "$I_m$", "$G$"]])
        self.assertIn("1", rules(validate(doc(tables=[t]))))

    def test_odd_types_are_reported_not_crashed_on(self):
        odd = [["E1"], {"x": 1}, 7, None, "", True, [], {}]
        paths = [(), ("description",), ("columns",), ("columns", 0), ("rows",), ("rows", 0), ("rows", 0, 1)]
        for p in paths:
            for v in odd:
                t = copy.deepcopy(TABLE)
                if p:
                    x = t
                    for k in p[:-1]:
                        x = x[k]
                    x[p[-1]] = v
                d = doc(tables=[t] if p else v)
                with self.subTest(path=p, value=v):
                    rep = validate(d)
                    self.assertNotIn("86", rules(rep))
                    render(d)

    def test_the_reading_view_prints_the_table(self):
        view = render(doc(tables=[TABLE]))
        self.assertIn("D2 [method] method M: The forecasting method studied in this paper, as implemented in version "
                      "1.0 of the code.\n"
                      "  table 1: The blocks of the matrices of each restriction of the model.\n"
                      "  | Restriction | $W$ | $F$ | $G$ |\n"
                      "  | None | $I_m$ | $I_m$ | $\\mathrm{diag}(\\alpha_1, \\dots, \\alpha_m)$ |\n"
                      "  | Common smoothing | $I_m$ | $I_m$ | $\\alpha I_m$ |\nD3 ", view)
        self.assertNotIn("table 1:", render(doc()))


class TestArtefactVersion(unittest.TestCase):
    def test_a_version_is_shown(self):
        d = doc()
        d["artefacts"].append({"id": "A9", "kind": "software", "version": "3.2.0", "licence": "LGPL-2.1",
                               "availability": {"level": "public"}, "uri": "https://cran.r-project.org/package=smooth",
                               "description": "The smooth R package, used for every estimate."})
        self.assertEqual(validate(d).errors, [])
        self.assertIn("\nA9 [software, version 3.2.0] The smooth R package, used for every estimate.\n", render(d))

    def test_a_content_hash_is_not(self):
        view = render(doc())
        self.assertIn("\nA2 [data] Every result", view)                # its version is sha256:0000
        self.assertNotIn("sha256", view)


class TestPublicHelpers(unittest.TestCase):
    def test_the_names_a_platform_uses_are_kept(self):
        for name in ("number", "interval", "uncertainty", "value", "statistic", "statistic_note", "DIGITS"):
            self.assertTrue(hasattr(render_module, name), name)


if __name__ == "__main__":
    unittest.main()

"""claimset.mathml: inline LaTeX as MathML, without a script."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from claimset.mathml import to_mathml  # noqa: E402


def body(tex):
    out = to_mathml(tex)
    assert out is not None, tex
    return out.split("<semantics>", 1)[1].split("<annotation", 1)[0]


class TestMathML(unittest.TestCase):
    def test_scripts_and_greek(self):
        self.assertEqual(body(r"y_t = \alpha^2"), "<mrow><msub><mi>y</mi><mi>t</mi></msub><mo>=</mo>"
                                                 "<msup><mi>α</mi><mn>2</mn></msup></mrow>")
        self.assertIn('<mi mathvariant="normal">Φ</mi>', body(r"\Phi^{-1}(\tau)"))
        self.assertIn("<msubsup><mi>e</mi><mi>t</mi><mn>2</mn></msubsup>", body("e_t^2"))
        self.assertIn('<msup><mi>y</mi><mo>′</mo></msup>', body("y'"))

    def test_fractions_roots_and_accents(self):
        self.assertIn("<mfrac><mi>T</mi><mrow><mi>T</mi><mo>−</mo><mi>k</mi></mrow></mfrac>", body(r"\frac{T}{T-k}"))
        self.assertIn("<msqrt><msub><mi>V</mi><mi>h</mi></msub></msqrt>", body(r"\sqrt{V_h}"))
        self.assertIn("<mroot><mi>x</mi><mn>3</mn></mroot>", body(r"\sqrt[3]{x}"))
        self.assertIn('<mover accent="true"><mi>σ</mi><mo stretchy="false">^</mo></mover>', body(r"\hat\sigma"))
        self.assertIn('linethickness="0"', body(r"\binom{n}{k}"))

    def test_big_operators_and_functions(self):
        out = body(r"\sum_{t=1}^{T} e_t")
        self.assertIn('<munderover><mo largeop="true" movablelimits="true">∑</mo>', out)
        self.assertIn("<msubsup><mo largeop=\"true\">∫</mo>", body(r"\int_0^1 f"))
        self.assertIn("<munder><mi>max</mi><mi>x</mi></munder><mo>\u2061</mo>", body(r"\max_x f(x)"))
        self.assertIn("<mi>log</mi><mo>\u2061</mo>", body(r"\log x"))

    def test_fonts_fences_and_matrices(self):
        self.assertIn("<mi>𝔼</mi>", body(r"\mathbb{E}[x]"))
        self.assertIn("<mi>𝐅</mi>", body(r"\mathbf{F}"))
        self.assertIn("<mi>ℝ</mi>", body(r"\mathbb{R}"))
        self.assertIn('<mo fence="true" stretchy="true">(</mo><mfrac>', body(r"\left(\frac{a}{b}\right)"))
        self.assertIn("<mtable><mtr><mtd><mn>1</mn></mtd><mtd><mn>2</mn></mtd></mtr>",
                      body(r"\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}"))
        self.assertIn('<mtable columnalign="left">', body(r"\begin{cases} 0 & x < 0 \\ 1 & \text{otherwise} \end{cases}"))
        self.assertIn("<mtext>otherwise</mtext>", body(r"\text{otherwise}"))
        out = body(r"\begin{aligned} y_t &= w v_{t-1} \\ v_t &= F v_{t-1} \end{aligned}")
        self.assertIn('<mtable columnalign="right left" columnspacing="0"><mtr><mtd><msub><mi>y</mi>', out)

    def test_what_it_cannot_read(self):
        for tex in (r"\foo{x}", "x^{2", r"\left( x", r"\begin{tikz} x \end{tikz}", "a & b", "", "x" * 3000,
                    "{" * 200 + "x" + "}" * 200):
            with self.subTest(tex[:20]):
                self.assertIsNone(to_mathml(tex))

    def test_escaped(self):
        out = to_mathml("<script>alert(1)</script> & \\text{<b>}")
        self.assertIsNone(out)                                  # a bare & is not maths
        out = to_mathml(r"\text{<b>x</b>} < y")
        self.assertNotIn("<b>", out)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", out)
        self.assertIn('<annotation encoding="application/x-tex">\\text{&lt;b&gt;x&lt;/b&gt;} &lt; y</annotation>', out)

    def test_display(self):
        self.assertTrue(to_mathml("x", display=True).startswith('<math display="block">'))


if __name__ == "__main__":
    unittest.main()


class TestLongInlineFormula(unittest.TestCase):
    """Warning 44 (v0.41 as amended on 2026-11-11, §8 rule 6): a formula too long for a sentence."""

    def warnings(self, statement):
        import copy
        import json
        from importlib import resources
        from claimset import validate as V
        d = json.loads((resources.files("claimset") / "data" / "examples" / "submission-native.json").read_text())
        d = copy.deepcopy(d)
        d["claims"][0]["statement"] = statement
        return [w for w in V.validate(d).warnings if w["rule"] == "W44"]

    def test_a_long_formula_in_a_sentence(self):
        long = r"$\sum_{O_t=1}\log f(z_t\mid Y_{t-1};\theta)+\sum_{O_t=1}\log p_t+\sum_{O_t=0}\log(1-p_t)$"
        self.assertEqual(len(self.warnings(f"The likelihood is {long}.")), 1)
        self.assertEqual(self.warnings(f"The likelihood is $${long[1:-1]}$$."), [])        # on a line of its own
        self.assertEqual(self.warnings(r"With $\epsilon_t \sim N(0, \sigma^2)$ the errors are normal."), [])

    def test_symbols_as_a_reader_sees_them(self):
        from claimset.validate import formula_symbols
        self.assertEqual(formula_symbols(r"\left(x_{t}\right)"), 4)              # ( x t )
        self.assertEqual(formula_symbols(r"\alpha + \beta"), 3)

"""The reading view's public helpers, for other views of a claimset to write values alike, and the page view's
removal: how a claimset looks to people is a platform's (spec v0.41, as amended on 2026-11-12)."""

import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from claimset import render  # noqa: E402
from claimset.cli import main  # noqa: E402


class TestPublicHelpers(unittest.TestCase):
    def test_the_names_are_the_reading_views_own(self):
        self.assertIs(render.number, render._num)
        self.assertIs(render.interval, render._interval)
        self.assertIs(render.uncertainty, render._uncertainty)
        self.assertIs(render.value, render._val)
        self.assertIs(render.statistic, render._statistic)
        self.assertIs(render.statistic_note, render._stat_note)

    def test_they_write_values(self):
        self.assertEqual(render.number(0.123456), "0.123456")
        token = render.DIGITS.set(("digits", 3))
        try:
            self.assertEqual(render.number(0.123456), "0.123")
        finally:
            render.DIGITS.reset(token)
        self.assertEqual(render.statistic("mean"), "mean")
        self.assertEqual(render.statistic_note({"statistic": "median", "approximate": True}), " (median, approximate)")


class TestNoPageView(unittest.TestCase):
    def test_render_html_says_where_it_went(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = main(["render", str(ROOT / "examples" / "submission-native.json"), "--html"])
        self.assertEqual(code, 2)
        self.assertIn("the HTML page view has left the claimset package", err.getvalue())
        self.assertIn("`claimset render` gives the reading view", err.getvalue())

    def test_the_modules_are_gone(self):
        for name in ("html", "html_css", "mathml"):
            self.assertFalse((ROOT / "src" / "claimset" / f"{name}.py").exists(), name)


if __name__ == "__main__":
    unittest.main()

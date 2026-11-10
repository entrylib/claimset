"""What a built distribution carries: every data file the package reads, and one version everywhere.

A file under src/claimset/data that no package-data pattern names is left out of the wheel, so an installed
package lacks it although the tests (run from the source tree) find it."""

import fnmatch
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "claimset"
sys.path.insert(0, str(ROOT / "src"))

from claimset import __version__  # noqa: E402


def pyproject():
    try:
        import tomllib
    except ModuleNotFoundError:                         # Python 3.10
        return None
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def package_data_patterns():
    data = pyproject()
    if data is not None:
        return data["tool"]["setuptools"]["package-data"]["claimset"]
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    line = re.search(r"^\[tool\.setuptools\.package-data\]\s*\nclaimset\s*=\s*\[(.*?)\]", text, re.M | re.S)
    return re.findall(r'"([^"]+)"', line.group(1))


class TestPackaging(unittest.TestCase):
    def test_every_data_file_is_packaged(self):
        patterns = package_data_patterns()
        files = [f.relative_to(PACKAGE).as_posix() for f in sorted((PACKAGE / "data").rglob("*"))
                 if f.is_file() and "__pycache__" not in f.parts]
        self.assertTrue(files)
        # setuptools globs do not cross directories with *, as fnmatch does; compare segment by segment
        missing = [f for f in files if not any(
            len(p.split("/")) == len(f.split("/")) and
            all(fnmatch.fnmatchcase(a, b) for a, b in zip(f.split("/"), p.split("/"))) for p in patterns)]
        self.assertEqual(missing, [], msg="add these to [tool.setuptools.package-data] in pyproject.toml")

    def test_one_version(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(re.search(r'^version = "([^"]+)"', text, re.M).group(1), __version__,
                         msg="pyproject.toml and src/claimset/__init__.py give different versions")


if __name__ == "__main__":
    unittest.main()

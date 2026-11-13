"""Large text outputs of a run are compressed when it ends, before they are hashed (lab record §5.9.1, step 4, as
amended on 2026-11-13): 40 MB of a run's CSV tables had been committed to a study branch and pushed."""

import gzip
import sys

from claimset.lab import run as run_mod
from claimset.lab.core import verify
from claimset.lab.run import run_command
from claimset.validate import package_file_problems

from test_lab import LabCase

SCRIPT = """
import json, os
d = os.environ["CLAIMSET_RUN_DIR"]
rows = "".join(f"{i},{i * 0.5}\\n" for i in range(200_000))
open(os.path.join(d, "big.csv"), "w").write("series,mase\\n" + rows)
open(os.path.join(d, "small.csv"), "w").write("series,mase\\n1,0.5\\n")
open(os.path.join(d, "figure.png"), "wb").write(b"\\x89PNG" + b"0" * 2_000_000)
json.dump([{"variable": "mean MASE", "value": 0.5}], open(os.environ["CLAIMSET_RESULTS"], "w"))
print("x" * 1_100_000)
"""


class TestCompression(LabCase):
    def setUp(self):
        super().setUp()
        self.script = self.dir.parent / "write.py"
        self.script.write_text(SCRIPT)

    def run_it(self):
        return run_command(self.lab, self.agent, [sys.executable, str(self.script)], echo=False,
                           cwd=str(self.dir.parent))

    def test_large_text_outputs_are_compressed_before_hashing(self):
        out = self.run_it()
        paths = {o["path"] for o in out["run"]["body"]["outputs"]}
        assert {"big.csv.gz", "stdout.txt.gz", "small.csv", "figure.png", "results.json"} <= paths, paths
        assert "big.csv" not in paths and sorted(out["compressed"]) == ["big.csv", "stdout.txt"]
        rdir = self.dir / "runs" / out["run"]["id"]
        with gzip.open(rdir / "big.csv.gz", "rt") as f:
            assert f.readline() == "series,mase\n" and sum(1 for _ in f) == 200_000
        assert (rdir / "big.csv.gz").stat().st_size < 1_000_000
        assert [r["body"]["variable"] for r in out["results"]] == ["mean MASE"]   # results.json stays readable
        assert verify(self.lab)["ok"]

    def test_the_same_content_gives_the_same_hash(self):
        a, b = self.run_it(), self.run_it()
        hashes = [{o["path"]: o["hash"] for o in r["run"]["body"]["outputs"]}["big.csv.gz"] for r in (a, b)]
        assert hashes[0] == hashes[1]

    def test_the_tools_own_files_and_small_ones_stay(self):
        rdir = self.dir.parent / "plain"
        rdir.mkdir()
        (rdir / "results.json").write_text("[" + "0," * 600_000 + "0]")
        (rdir / "codings.json").write_text("x" * 1_100_000)
        (rdir / "note.txt").write_text("short")
        assert run_mod.compress_outputs(rdir, keep={"results.json", "codings.json"}) == []

    def test_a_package_takes_a_compressed_table(self):
        assert package_file_problems("files/runs/RN1/big.csv.gz", 1000) == []
        assert package_file_problems("files/outputs.zip", 1000)                     # archives stay refused

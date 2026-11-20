"""A run's results file (lab record §5.10, from v0.23).

In records begun under v0.23 or later a run's results are not events: the tool writes the valid entries of the
script's `results.json` to `results.csv` in the run's folder, one row per entry in their order, and the result in
row k is named `<run ID>.k`. Text and numbers are written as they are, objects and lists as JSON, and a cell is
empty where the entry has none. A file larger than 1 MB is compressed to `results.csv.gz` like any text output
(§5.9.1, step 5); this module reads both.
"""

import csv
import gzip
import io
import json
import math

#: The columns of a results file, in order (§5.10).
COLUMNS = ("variable", "value", "unit", "interval", "uncertainty", "conditions")
#: The results file's name in a run's folder, before compression.
NAME = "results.csv"


def _cell(column, v):
    if v is None:
        return ""
    if column == "value":
        return json.dumps(v)                        # full precision, as JSON writes a number
    if column in ("variable", "unit") and isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def text(entries):
    """The results file's text for a list of valid entries ({variable, value, unit?, interval?, …})."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    for e in entries:
        w.writerow([_cell(c, e.get(c)) for c in COLUMNS])
    return buf.getvalue()


def write(path, entries):
    """Write the results file at `path`; returns the number of rows."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text(entries))
    return len(entries)


def _open(path):
    path = str(path)
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", newline="")
    return open(path, encoding="utf-8", newline="")


def parse_row(row):
    """An observation from one row of a results file, or raise ValueError saying what is wrong."""
    out = {}
    for c in COLUMNS:
        cell = row.get(c)
        if cell is None or cell == "":
            continue
        if c == "variable" or c == "unit":
            out[c] = cell
        else:
            try:
                out[c] = json.loads(cell)
            except json.JSONDecodeError:
                raise ValueError(f"column {c} is not JSON: {cell[:40]!r}") from None
    v = out.get("value")
    if not isinstance(out.get("variable"), str) or not out["variable"].strip():
        raise ValueError("needs a variable")
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        raise ValueError("value must be a finite number")
    return out


def read(path):
    """The observations of a results file, in row order. Raises OSError if the file cannot be read and ValueError
    (with the row number) if a row is not a valid observation or the columns are not those of §5.10."""
    with _open(path) as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"the columns are {', '.join(reader.fieldnames or [])}, not {', '.join(COLUMNS)}")
        rows = []
        for k, row in enumerate(reader, start=1):
            try:
                rows.append(parse_row(row))
            except ValueError as exc:
                raise ValueError(f"row {k}: {exc}") from None
    return rows


def result_id(run_id, k):
    """The name of the result in row k (from 1) of a run's results file: `RN4.12` (§4.2, §5.10)."""
    return f"{run_id}.{k}"

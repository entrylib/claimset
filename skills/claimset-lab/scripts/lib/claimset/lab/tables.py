"""Result tables from a lab record's results (lab record §9; claimset §3.4, *Tables are the standard form*).

    tabulate(results, eid, artefact) -> (tables, results, refs)

`results` are result events of the record (their bodies hold `variable` or `quantity`, `value`, `unit`, `statistic`,
`conditions` and the measures a cell cannot hold). They are grouped by the condition keys that identify the compared
units; each group of two or more observations becomes a table whose rows are the units and whose columns are the
variables, with the keys that set a variable apart (a nominal level, a subset, a statistic) as column conditions and
the keys every observation of the group shares as the table's conditions. What a cell cannot hold, and a group of
one, stays a result entry. `refs` maps each result event's ID to where it went: `E2.T1.r3` or `E2.R1`.
"""

import json
import math

from ..validate import ENUM

#: Condition keys that set a variable apart rather than identify a compared unit: they become column conditions
COLUMN_KEYS = {"level", "nominal level", "nominal", "confidence level", "coverage level", "alpha", "subset",
               "tercile", "quartile", "quantile", "probability", "statistic", "stat", "bound", "part"}
#: Measures a table cell cannot hold: an observation with any of them stays a result entry
RESULT_ONLY = ("interval", "uncertainty", "n", "approximate", "read_from", "ext")
SIGNIFICANT = 4


def _norm(key):
    return str(key).strip().lower().replace("_", " ").replace("-", " ")


def column_key(key):
    """Whether a condition key sets a variable apart (a column condition) rather than identifying a unit."""
    return _norm(key) in COLUMN_KEYS


def variable_of(body):
    return body.get("variable", body.get("quantity"))


def cell_value(value):
    """Whether a value fits a table cell here: a number, text or a boolean (excerpts, limits and ranges stay results)."""
    return isinstance(value, (bool, int, float, str)) and not (isinstance(value, float) and not math.isfinite(value))


def rounded(value, digits=SIGNIFICANT):
    """A float to `digits` significant digits; any other value as it is."""
    if isinstance(value, float) and math.isfinite(value) and value != 0:
        return float(f"{value:.{digits}g}")
    return value


def _key(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _column(variable, conds, statistic):
    if not conds and statistic is None:
        return variable
    col = {"variable": variable}
    if conds:
        col["conditions"] = dict(conds)
    if statistic is not None:
        col["statistic"] = statistic
    return col


def _table(group, keys, tid):
    """One table from a group of observations [(event, body, conditions)] whose rows are told apart by `keys`; None
    if two observations would fill the same cell."""
    shared = {}
    first = group[0][2]
    for k, v in first.items():
        if all(k in c and _key(c[k]) == _key(v) for _, _, c in group):
            shared[k] = v
    row_keys = [k for k in keys if k not in shared]
    rows, cols, cells, units = [], [], {}, {}
    for ev, body, conds in group:
        row = tuple(_key(conds.get(k)) for k in row_keys)
        colconds = {k: v for k, v in conds.items() if k not in shared and k not in row_keys}
        statistic = body.get("statistic")
        for k in list(colconds):
            if _norm(k) == "statistic" and statistic is None and colconds[k] in ENUM["statistic"]:
                statistic = colconds.pop(k)
        col = (_key(variable_of(body)), _key(colconds), _key(statistic), _key(body.get("unit")))
        if row not in rows:
            rows.append(row)
        if col not in cols:
            cols.append(col)
            units[col] = body.get("unit")
        if (row, col) in cells:
            return None
        cells[(row, col)] = (ev, body)
    table = {"id": tid, "description": "", "row_labels": row_keys}
    if shared:
        table = {"id": tid, "description": "", "conditions": shared, "row_labels": row_keys}
    table["columns"] = [_column(json.loads(c[0]), json.loads(c[1]), json.loads(c[2])) for c in cols]
    if any(units[c] is not None for c in cols):
        table["units"] = [units[c] for c in cols]
    table["rows"] = []
    where = {}
    for i, row in enumerate(rows):
        rid = f"r{i + 1}"
        values = []
        for col in cols:
            hit = cells.get((row, col))
            values.append(hit[1].get("value") if hit else None)
            if hit:
                where[hit[0]["id"]] = rid
        table["rows"].append({"id": rid, "label": [json.loads(x) for x in row], "values": values})
    return table, where


def describe(table, runs):
    """A first description of a table, for the writing agent to make self-contained."""
    names = []
    for c in table["columns"]:
        v = c if isinstance(c, str) else c.get("variable")
        if isinstance(v, str) and v not in names:
            names.append(v)
    by = f" by {', '.join(str(k) for k in table['row_labels'])}" if table["row_labels"] else ""
    on = "; " + ", ".join(f"{k}: {v}" for k, v in table.get("conditions", {}).items()) if table.get("conditions") else ""
    return f"{', '.join(names)}{by}{on} (lab runs {', '.join(runs)})"


def tabulate(results, eid, artefact=None):
    """(tables, result entries, refs) for the result events of one evidence object, in record order."""
    plain, kept = [], []
    for ev in results:
        body = ev["body"]
        if any(body.get(k) is not None for k in RESULT_ONLY) or not cell_value(body.get("value")) \
                or not isinstance(variable_of(body), str):
            kept.append(ev)
        else:
            conds = body.get("conditions") if isinstance(body.get("conditions"), dict) else {}
            plain.append((ev, body, conds))
    # Groups: observations told apart by the same unit keys (every condition key that does not set a variable apart)
    groups, order = {}, []
    for item in plain:
        sig = tuple(k for k in item[2] if not column_key(k))
        key = tuple(sorted(sig))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    tables, refs = [], {}
    for key in order:
        group = groups[key]
        if len(group) < 2:
            kept += [ev for ev, _, _ in group]
            continue
        keys = []
        for _, _, conds in group:
            keys += [k for k in conds if not column_key(k) and k not in keys]
        tid = f"T{len(tables) + 1}"
        made = _table(group, keys, tid)
        runs = sorted({ev["body"].get("run") for ev, _, _ in group if ev["body"].get("run")})
        if made is None and len(runs) > 1:     # several runs filled the same cell: each run its own rows
            group = [(ev, body, dict(conds, run=body.get("run"))) for ev, body, conds in group]
            made = _table(group, keys + ["run"], tid)
        if made is None:                        # the same observation recorded twice: kept as results
            kept += [ev for ev, _, _ in group]
            continue
        table, where = made
        table["description"] = describe(table, runs)
        if artefact:
            table["artefact"] = artefact
        tables.append(table)
        refs.update({rid: f"{eid}.{tid}.{row}" for rid, row in where.items()})
    entries = []
    for ev in sorted(kept, key=lambda e: e["seq"]):
        rid = f"R{len(entries) + 1}"
        refs[ev["id"]] = f"{eid}.{rid}"
        entry = {"id": rid}
        entry.update({("variable" if k == "quantity" else k): ev["body"][k]
                      for k in ("variable", "quantity", "value", "unit", "interval", "uncertainty", "n", "statistic",
                                "approximate", "conditions") if ev["body"].get(k) is not None})
        if isinstance(ev["body"].get("ext"), dict):
            entry["ext"] = dict(ev["body"]["ext"])          # an observation's extension blocks (§9)
        entries.append(entry)
    return tables, entries, refs


def binds(quantity, body):
    """Whether a test quantity (`{variable, conditions}`) binds a result: its variable, and every given condition."""
    if not isinstance(quantity, dict):
        return False
    var = quantity.get("variable", quantity.get("quantity"))
    conds = body.get("conditions") if isinstance(body.get("conditions"), dict) else {}
    want = quantity.get("conditions") if isinstance(quantity.get("conditions"), dict) else {}
    return var == variable_of(body) and all(k in conds and _key(conds[k]) == _key(v) for k, v in want.items())


def csv_text(events):
    """Every result of the record, at full precision: lab_result, run, quantity, conditions (JSON), value (JSON)."""
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["lab_result", "run", "quantity", "conditions", "value"])
    for ev in events:
        b = ev["body"]
        w.writerow([ev["id"], b.get("run") or "", variable_of(b) or "",
                    json.dumps(b.get("conditions") or {}, sort_keys=True, ensure_ascii=False),
                    json.dumps(b.get("value"), ensure_ascii=False)])
    return out.getvalue()


CSV_COLUMNS = [{"name": "lab_result", "dimension": "the result event of the lab record"},
               {"name": "run", "dimension": "the lab run that produced it"},
               {"name": "quantity", "dimension": "the quantity, as the run's script named it"},
               {"name": "conditions", "dimension": "the result's conditions, as JSON"},
               {"name": "value", "variable": "the value of the quantity, as JSON, at full precision"}]

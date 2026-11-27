"""The reading view: a plain-text rendering of a claimset for reading models (spec §2.3).

The view is derived mechanically from a valid claimset file. It keeps what a reader needs to
understand, use or challenge the paper's claims, and leaves out what serves tools, audit and
publication (provenance, source spans, availability, artefact locations and licences,
contributors, models, lab identifiers). It adds nothing: every line comes from a field of the file.

How the reading view writes values, for any other view of a claimset (a platform's pages) to write them alike:

    number(v), interval(iv), uncertainty(unc), value(v), statistic(st), statistic_note(obj)
    DIGITS     -> how numbers are written: None as the file gives them, ("digits", n) to n significant digits, or a
                  function given a number that returns its text (None for the default); set it for one view
"""

import contextvars
import decimal
import json

from .validate import inherited_assumptions


def _s(x):
    return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)


# How a view writes numbers: None writes them as the file gives them; ("digits", n) to n
# significant digits; a function is the site's own: given a number, it returns the text to show, or None for the
# default. The file keeps every digit: this only changes what a page prints.
DIGITS = contextvars.ContextVar("claimset_numbers", default=None)


def _num(v):
    if v is None:
        return ""
    r = DIGITS.get()
    if callable(r) and isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            shown = r(v)
        except Exception:                                   # a site's formatter must not break the page
            shown = None
        if isinstance(shown, str):
            return shown
    if isinstance(v, float) and v.is_integer():
        return str(int(v)) if abs(v) < 1e15 else repr(v)
    if isinstance(r, tuple) and isinstance(v, float) and v == v and abs(v) != float("inf"):
        return _rounded(v, r[1])
    return str(v)


def _rounded(v, d):
    """v to d significant digits, never in exponent form and never dropping a digit before the point:
    0.00068061 -> 0.0006806, 1.00193 -> 1.002, 12345.67 -> 12346."""
    if abs(v) >= 10 ** d:
        return str(round(v))
    text = format(decimal.Decimal(f"{v:.{d}g}"), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _join(items, sep="; "):
    return sep.join(i for i in items if i)


def _interval(iv):
    if not isinstance(iv, dict):
        return ""
    level = iv.get("level")
    lvl = f"{_num(level * 100 if isinstance(level, (int, float)) and level <= 1 else level)}% " if level is not None else ""
    kind = f"{iv['kind']} " if isinstance(iv.get("kind"), str) else ""
    return f"{lvl}{kind}interval {_num(iv.get('lower'))} to {_num(iv.get('upper'))}"


def _uncertainty(unc):
    """± 0.4 (stat) ± 0.4 (sys); +0.5/-0.3 (sys, luminosity); the level when not one standard deviation."""
    parts = []
    for u in unc if isinstance(unc, list) else []:
        if not isinstance(u, dict):
            continue
        size = f"± {_num(u['value'])}" if "value" in u else f"+{_num(u.get('plus'))}/-{_num(u.get('minus'))}"
        level = u.get("level")
        note = _join([u.get("kind"), u.get("label"),
                      f"{_num(level * 100)}%" if isinstance(level, (int, float)) else ""], ", ")
        parts.append(f"{size} ({note})")
    return " ".join(parts)


def _conditions(c):
    if not isinstance(c, dict) or not c:
        return ""
    return "{" + ", ".join(f"{k}: {_s(v)}" for k, v in c.items()) + "}"


def _val(v):
    """An observation's value: a number, a category, yes/no, or an excerpt with its locator and translation (and,
    in files before v0.38, its gloss; since then the gloss is in the linguistics extension)."""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return _num(v)
    if isinstance(v, dict) and "bound" in v:
        level = f", {_num(v['level'] * 100)}%" if isinstance(v.get("level"), (int, float)) else ""
        sign = "<" if v.get("bound") == "upper" else ">"
        return f"{sign} {_num(v.get('limit'))} ({v.get('bound')} limit{level})"
    if isinstance(v, dict) and ("min" in v or "max" in v):
        level = f", {_num(v['level'] * 100)}%" if isinstance(v.get("level"), (int, float)) else ""
        return f"{_num(v.get('min'))} to {_num(v.get('max'))} (range{level})"
    if isinstance(v, dict) and "text" in v:
        out = f"\"{v.get('text')}\""
        if v.get("language"):
            out += f" [{v['language']}]"
        if v.get("gloss"):
            out += f" (gloss: {v['gloss']})"
        if v.get("translation"):
            out += f" ('{v['translation']}')"
        loc = v.get("locator")
        if isinstance(loc, dict):
            where = f"{loc.get('artefact')}, characters {loc.get('start')}–{loc.get('end')}"
            out += f" ({where}{', ' + loc['lab_event'] if loc.get('lab_event') else ''})"
        elif loc:
            out += f" ({loc})"
        return out
    return "" if v is None else _s(v)


def _ext(x):
    """An object's extension blocks (spec §2.7), shown as data: ` [linguistics: gloss "…"; segmented "…"]`."""
    ext = x.get("ext") if isinstance(x, dict) else None
    if not isinstance(ext, dict):
        return ""
    out = ""
    for name, block in ext.items():
        if isinstance(block, dict) and block:
            out += f" [{name}: " + "; ".join(f"{k} {_s(v)}" for k, v in block.items()) + "]"
    return out


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _statistic(st):
    """A statistic in words: mean, geometric mean, trimmed mean (10% each tail), quantile 0.9, 3rd central moment,
    excess kurtosis, or the label of other; a label on a listed name follows it."""
    if isinstance(st, str):
        return "" if st == "other" else st
    if not isinstance(st, dict) or not isinstance(st.get("name"), str):
        return ""
    name, label = st["name"], st.get("label") if isinstance(st.get("label"), str) else ""
    if name == "other":
        return label
    text = name
    if name == "mean" and isinstance(st.get("kind"), str) and st["kind"] != "arithmetic":
        text = f"{st['kind']} mean"
        if isinstance(st.get("trim"), (int, float)) and not isinstance(st.get("trim"), bool):
            text += f" ({_num(round(st['trim'] * 100, 6))}% each tail)"
    elif name in ("quantile", "expectile") and st.get("probability") is not None:
        text = f"{name} {_num(st['probability'])}"
    elif name == "moment" and isinstance(st.get("order"), int):
        text = f"{_ordinal(st['order'])} {'central' if st.get('central') is True else 'raw'} moment"
    elif name == "kurtosis" and st.get("excess") is True:
        text = "excess kurtosis"
    return _join([text, label], ", ")


def _stat_note(obj):
    """' (mean)', ' (median, approximate)' or '' for a column or a row."""
    note = _join([_statistic(obj.get("statistic")), "approximate" if obj.get("approximate") is True else ""], ", ")
    return f" ({note})" if note else ""


def _column(c):
    """A column's header (spec §2.3, *Tables and results*, from v0.45): its variable, its conditions in words, each key
    and value separated by a space and the conditions by commas, then its statistic: `D11, DGP Normal (mean)`."""
    if isinstance(c, dict):
        conds = c.get("conditions")
        words = [f"{k} {_s(v)}" for k, v in conds.items()] if isinstance(conds, dict) else []
        return ", ".join([_s(c.get("variable"))] + words) + _stat_note(c)
    return _s(c)


def _unit(u):
    """A value's unit as the reading view writes it: none for a dimensionless value, whose unit is `1` (§2.3)."""
    return "" if u is None or (isinstance(u, str) and u.strip() in ("", "1")) else _s(u)


#: Fields of a table or a result that hold texts or bookkeeping, not the identifiers a key explains.
_NOT_KEYED = ("description", "note", "id", "read_from", "statistic", "label_text", "approximate", "uncertainty",
              "interval", "n", "unit", "units", "rows_file", "n_rows")


def _keyed(x, labels, found=None):
    """The definitions an object names by identifier (a key or a value that is a definition's ID, in its conditions,
    variables, row labels or cells), in order of first use; texts are skipped, whose term markers carry words."""
    found = [] if found is None else found
    if isinstance(x, dict):
        for k, v in x.items():
            if k in _NOT_KEYED:
                continue
            if isinstance(k, str) and k in labels and k not in found:
                found.append(k)
            _keyed(v, labels, found)
    elif isinstance(x, list):
        for v in x:
            _keyed(v, labels, found)
    elif isinstance(x, str) and x in labels and x not in found:
        found.append(x)
    return found


def key_labels(doc):
    """{definition ID: its brief label}: the `symbol` if it has one, else its `short` (from v0.45), else its term
    (spec §2.3 and §3.2)."""
    out = {}
    for d in doc.get("definitions") or [] if isinstance(doc.get("definitions"), list) else []:
        if not isinstance(d, dict) or not isinstance(d.get("id"), str):
            continue
        for f in ("symbol", "short", "term"):
            if isinstance(d.get(f), str) and d[f].strip():
                out.setdefault(d["id"], " ".join(d[f].split()))
                break
    return out


def _key(ids, labels):
    """The key under a table or results (spec §2.3): `  key: D7 method; D14 RMSSE`, or nothing."""
    return ["  key: " + "; ".join(f"{i} {labels[i]}" for i in ids)] if ids else []


def _declarations(d):
    if not isinstance(d, dict):
        return ""
    parts = []
    if "funding" in d:
        fund = [_join([f.get("funder"), f"({f['funder_id']})" if f.get("funder_id") else "",
                       f"award {f['award']}" if f.get("award") else "",
                       "in kind" if f.get("kind") == "in_kind" else "",
                       f"(role: {f['role']})" if f.get("role") else ""], " ")
                for f in d.get("funding") or [] if isinstance(f, dict)]
        parts.append("funding: " + ("; ".join(fund) if fund else "none"))
    if d.get("competing_interests"):
        parts.append(f"competing interests: {d['competing_interests']}")
    if "ethics" in d:
        eth = [_join([x.get("body"), x.get("reference"), x.get("decision")], ", ")
               for x in d.get("ethics") or [] if isinstance(x, dict)]
        parts.append("ethics: " + ("; ".join(eth) if eth else "not reviewed"))
    if d.get("consent"):
        parts.append(f"consent: {d['consent']}")
    return " | ".join(parts)


def _definition(d):
    tags = [("members", "members"), ("part_of", "part of"), ("broader", "a kind of"), ("assumptions", "assumes"),
            ("identifiers", "identifiers"), ("measures", "measures"), ("targets", "targets"), ("unit", "unit")]
    symbol = f" ({d['symbol'].strip()})" if isinstance(d.get("symbol"), str) and d["symbol"].strip() else ""
    line = (f"{d.get('id')} " + (f"[{d['kind']}] " if d.get("kind") else "")
            + f"{d.get('term')}{symbol}: {d.get('definition')}")
    for key, label in tags:
        if d.get(key):
            vals = d[key] if isinstance(d[key], list) else [d[key]]
            line += f" [{label} {', '.join(_s(x) for x in vals)}]"
    if isinstance(d.get("location"), list):
        pts = [_join([f"{_num(x.get('latitude'))}, {_num(x.get('longitude'))}", x.get("label")], " ")
               for x in d["location"] if isinstance(x, dict)]
        line += f" [location {'; '.join(pts)}]"
    if d.get("source"):
        line += f" [source {_s(d['source']) if not isinstance(d['source'], dict) else d['source'].get('target')}]"
    lines = [line + _ext(d)]
    tables = [t for t in d.get("tables") or [] if isinstance(t, dict)] if isinstance(d.get("tables"), list) else []
    for i, t in enumerate(tables, 1):                  # the tables the paper specifies the term by (§3.2, 2026-11-23)
        lines.append(f"  table {i}: {_cell(t.get('description'))}")
        if isinstance(t.get("columns"), list):
            lines.append("  | " + " | ".join(_cell(c) for c in t["columns"]) + " |")
        for row in t.get("rows") or [] if isinstance(t.get("rows"), list) else []:
            if isinstance(row, list):
                lines.append("  | " + " | ".join(_cell(x) for x in row) + " |")
    return lines


def _cell(x):
    """A cell of a definition's table on one line."""
    return " ".join(_s(x).split()) if x is not None else ""


def _support(s):
    k = s.get("kind", "")
    ptr = [s.get("evidence"), s.get("warrant"), s.get("reference"), s.get("holder")]
    if s.get("target"):
        ptr.append(f"{s.get('id_type', '')} {s['target']}".strip())
    out = " ".join([k] + [p for p in ptr if p])
    if s.get("results"):
        out += " (" + ", ".join(s["results"]) + ")"
    if s.get("artefacts"):
        out += " artefacts " + ", ".join(s["artefacts"])
    if s.get("locator"):
        out += f", at {s['locator']}"
    if s.get("self"):
        out += ", own earlier work"
    return out


def _scope(sc):
    if not isinstance(sc, dict):
        return ""
    parts = []
    for k, v in sc.items():
        if isinstance(v, list):
            if v:
                parts.append(f"{k}: " + "; ".join(_s(x) for x in v))
        elif v not in (None, ""):
            parts.append(f"{k}: {_s(v)}")
    return " | ".join(parts)


def _is_assumption(c):
    """An assumption claim: its sole support is of kind `assumption` (§3.8, rule 3)."""
    return any(isinstance(s, dict) and s.get("kind") == "assumption" for s in c.get("support") or [])


def _assumption(c):
    """An assumption in the ASSUMPTIONS part: one line, its name, category and check, then its statement (§2.3)."""
    name = f' "{" ".join(c["name"].split())}"' if isinstance(c.get("name"), str) and c["name"].strip() else ""
    head = _join([c.get("assumption_category"), c.get("check", "unchecked")])
    return [f"{c.get('id')}{name} [{head}] {' '.join(str(c.get('statement', '')).split())}{_ext(c)}"]


def _claim(c, inherited=()):
    head = [c.get("type"), c.get("role")]
    if c.get("novelty") and c.get("novelty") != "no_prior_found":
        head.append(c["novelty"])
    if c.get("assumption_category"):
        head.append(f"assumption ({c['assumption_category']}, {c.get('check', 'unchecked')})")
    sup = [_support(s) for s in c.get("support") or [] if isinstance(s, dict) and s.get("kind") != "assumption"]
    if sup:
        head.append("support: " + ", ".join(sup))
    for key, label in (("assumptions", "assumes"), ("depends_on", "uses"), ("limitations", "limitations")):
        if c.get(key):
            head.append(f"{label} " + ", ".join(c[key]))
    inherited = [a for a in inherited if a not in (c.get("assumptions") or [])]
    if inherited:
        head.append("inherits " + ", ".join(inherited))
    if c.get("warrant"):
        head.append(f"warrant {c['warrant']}")
    strengths = [f"{a.get('strength')} ({a.get('by')})" for a in c.get("assessments") or [] if isinstance(a, dict)]
    if strengths:
        head.append("strength " + ", ".join(strengths))
    for key in ("verification", "verifiability", "planning"):
        if c.get(key):
            head.append(f"{key} {c[key]}")
    if isinstance(c.get("hypothesis"), dict) and c["hypothesis"].get("outcome"):
        head.append(f"outcome {c['hypothesis']['outcome']}")
    name = f' "{" ".join(c["name"].split())}"' if isinstance(c.get("name"), str) and c["name"].strip() else ""
    lines = [f"{c.get('id')}{name} [{_join(head)}]{_ext(c)}", f"  {c.get('statement', '')}"]
    if isinstance(c.get("summary"), str) and c["summary"].strip():
        lines.append("  in plain words: " + " ".join(c["summary"].split()))
    if c.get("scope"):
        lines.append(f"  scope: {_scope(c['scope'])}")
    for rel in c.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        target = rel.get("reference") or (rel.get("target", "") if rel.get("id_type") == "local"
                                          else f"{rel.get('id_type', '')} {rel.get('target', '')}".strip())
        loc = f", at {rel['locator']}" if rel.get("locator") else ""
        note = f": {rel['note']}" if rel.get("note") else ""
        own = ", own earlier work" if rel.get("self") else ""
        by = (", by " + ", ".join(_s(x) for x in rel["results"])
              if isinstance(rel.get("results"), list) and rel["results"] else "")
        lines.append(f"  {rel.get('type')} {target}{loc}{own}{by}{note}")
    t = c.get("test")
    if isinstance(t, dict):
        params = "; ".join(f"{k} {_s(v)}" for k, v in (t.get("parameters") or {}).items())
        lines.append("  test: " + _join([t.get("framework"), params,
                                          f"supported if {t['supported']}" if t.get("supported") else "",
                                          f"not supported if {t['not_supported']}" if t.get("not_supported") else "",
                                          f"verdict {t['verdict']}" if t.get("verdict") else "",
                                          ("flags " + ", ".join(t["flags"])) if t.get("flags") else ""]))
        plan = [f"lab plan {t['lab_plan']}" if t.get("lab_plan") else "",
                f"registered {t['registration']}" if t.get("registration") else "",
                f"planned {c['planned_at']}" if c.get("planned_at") else "",
                f"anchor {c['planned_at_anchor']}" if c.get("planned_at_anchor") else ""]
        if any(plan):
            lines.append("  plan: " + _join(plan))
    e = c.get("estimate")
    if isinstance(e, dict):
        missing = set(e.get("not_obtained") or [])
        names = [f"{n} = {q.get('variable')}"
                 + (f" {_conditions(q.get('conditions'))}" if q.get("conditions") else "")
                 + (f" {q['field']}" if q.get("field") not in (None, "value") else "")
                 + (" (table: every value)" if q.get("table") is True else "")
                 + (" (not obtained)" if n in missing else "")
                 for n, q in (e.get("estimands") or {}).items() if isinstance(q, dict)]
        lines.append("  planned estimate: " + _join(["; ".join(names),
                                                     ("flags " + ", ".join(e["flags"])) if e.get("flags") else ""]))
        plan = [f"lab plan {e['lab_plan']}" if e.get("lab_plan") else "",
                f"registered {e['registration']}" if e.get("registration") else "",
                f"planned {c['planned_at']}" if c.get("planned_at") else "",
                f"anchor {c['planned_at_anchor']}" if c.get("planned_at_anchor") else ""]
        if any(plan):
            lines.append("  plan: " + _join(plan))
    return lines


def _table(eid, t, labels=None):
    lines = [f"  {eid}.{t.get('id')} {t.get('description', '')}"
             + (f" {_conditions(t.get('conditions'))}" if t.get("conditions") else "") + _ext(t)]
    cols = [_column(c) for c in t.get("columns") or []]
    units = t.get("units")
    if isinstance(units, list):
        cols = [f"{c} ({_unit(u)})" if _unit(u) else c for c, u in zip(cols, units)]
    lines.append("  | " + " | ".join(["row"] + list(t.get("row_labels") or []) + cols) + " |")
    if t.get("rows_file") and not t.get("rows"):
        n = t.get("n_rows")
        lines.append(f"  ({n} rows, held in the file of artefact {t['rows_file']})" if n is not None
                     else f"  (rows held in the file of artefact {t['rows_file']})")
    for r in t.get("rows") or []:
        if isinstance(r, dict):
            cells = ([f"{r.get('id', '')}{_stat_note(r)}"] + [_s(x) for x in r.get("label") or []]
                     + [_val(v) for v in r.get("values") or []])
            lines.append("  | " + " | ".join(cells) + " |")
    if labels:                       # in the order the table is read: its conditions, its header, its rows
        found = []
        for part in ("conditions", "row_labels", "columns", "rows"):
            _keyed(t.get(part), labels, found)
        lines += _key(found, labels)
    return lines


def _evidence(e, labels=None):
    head = [e.get("profile")]
    for key in ("design", "data_origin", "analytic_approach", "sampling", "foundation", "checker"):
        if e.get(key):
            head.append(f"{key} {_s(e[key])}")
    for key in ("n", "n_participants_or_cases", "runs"):
        if e.get(key) is not None:
            head.append(f"{key} {_num(e[key])}")
    if e.get("preregistered"):
        head.append("preregistered")
    lines = [f"{e.get('id')} [{_join(head)}] {e.get('description', '')}{_ext(e)}"]
    setup = e.get("setup") if isinstance(e.get("setup"), dict) else {}
    parts = [f"{role} {', '.join(str(d) for d in setup[role])}" for role in ("studied", "cases", "procedure", "lens", "context")
             if isinstance(setup.get(role), list) and setup[role]]
    if parts:
        lines.append(f"  setup: {'; '.join(parts)}")
    derived = [f"{x.get('evidence')} ({x.get('how')})" for x in e.get("derived_from") or [] if isinstance(x, dict)]
    if derived:
        lines.append("  derived from " + ", ".join(derived))
    for x in e.get("records") or []:
        if isinstance(x, dict):
            lines.append("  record: " + _join([x.get("kind"), f"in {x['artefact']}" if x.get("artefact") else "",
                                               x.get("description")], "; "))
    if e.get("estimate") is not None:
        lines.append(f"  estimate: {e.get('estimand', '')} = {_num(e['estimate'])}"
                     + (f" {_uncertainty(e.get('uncertainty'))}" if e.get("uncertainty") else "")
                     + (f" ({_interval(e.get('interval'))})" if e.get("interval") else ""))
    if e.get("assumptions"):
        lines.append("  assumes " + ", ".join(e["assumptions"]))
    for r in e.get("results") or []:
        if isinstance(r, dict):
            rf = r.get("read_from") if isinstance(r.get("read_from"), dict) else {}
            extra = _join([_uncertainty(r.get("uncertainty")), _unit(r.get("unit")), _interval(r.get("interval")),
                           f"n {_num(r['n'])}" if r.get("n") is not None else "", _conditions(r.get("conditions")),
                           f"read from {rf.get('artefact')}, precision {_s(rf.get('precision'))}" if rf else ""], " ")
            stat = f" ({_statistic(r.get('statistic'))})" if _statistic(r.get("statistic")) else ""
            approx = "about " if r.get("approximate") is True else ""
            lines.append(f"  {e.get('id')}.{r.get('id')} {_s(r.get('variable'))}{stat} = {approx}{_val(r.get('value'))}"
                         + (f" {extra}" if extra else "") + _ext(r))
    if labels and isinstance(e.get("results"), list):       # the key under the results (§2.3, from v0.45)
        found = []
        for r in e["results"]:
            if isinstance(r, dict):
                _keyed({"variable": r.get("variable"), "conditions": r.get("conditions"), "value": r.get("value")},
                       labels, found)
        lines += _key(found, labels)
    for t in e.get("tables") or []:
        if isinstance(t, dict):
            lines += _table(e.get("id"), t, labels)
    for s in e.get("steps") or []:
        if isinstance(s, dict):
            lines.append(f"  {s.get('id')} {s.get('statement')} (by {', '.join(s.get('by') or []) or 'none'}; {s.get('rule')})")
    if e.get("profile") == "formal" and not e.get("steps") and e.get("source_spans"):
        lines.append("  derivation: in the source")
    for key in ("reflexivity", "outputs", "parameters", "seeds"):
        if e.get(key):
            lines.append(f"  {key}: {_s(e[key])}")
    return lines


def _warrant(w):
    return [f"{w.get('id')} [{_join([w.get('reasoning'), ('premises ' + ', '.join(w['premises'])) if w.get('premises') else ''])}] {w.get('text', '')}"]


def _limitation(l):
    return [f"{l.get('id')} [{_join([l.get('category'), ('affects ' + ', '.join(l.get('affects') or [])), l.get('impact'), ('mitigation ' + l['mitigation']) if l.get('mitigation') else ''])}] {l.get('statement', '')}{_ext(l)}"]


def _open_question(q):
    return [f"{q.get('id')}" + (f" [from {', '.join(q['claims'])}]" if q.get("claims") else "") + f" {q.get('question', '')}"]


def _artefact(a):
    """An artefact's line: kind, function and version (not a content hash; §2.3, as amended on 2026-11-23)."""
    v = a.get("version")
    version = f"version {v.strip()}" if isinstance(v, str) and v.strip() and not v.strip().startswith("sha256:") \
        else ""
    return [f"{a.get('id')} [{_join([a.get('kind'), a.get('function'), version], ', ')}] {a.get('description')}"
            + (f" shows {', '.join(_s(x) for x in a['shows'])}" if a.get("shows") else "") + _ext(a)]


def _without_evidence(c):
    """True if the claim's only support is argument or none (spec §2.3)."""
    kinds = {s.get("kind") for s in c.get("support") or [] if isinstance(s, dict)}
    return bool(kinds) and kinds <= {"argument", "unstated"}


#: The counts of `exploration` (spec §3.1.1) in the order and words the reading view gives them.
_COUNTS = {"hypotheses": ("supported", "not_supported", "inconclusive", "revised", "abandoned", "open",
                          "from_exploration"),
           "tests": ("supported", "not_supported", "inconclusive"),
           "runs": ("confirmatory", "exploratory", "failed")}


def _counted(name, counts):
    """`hypotheses 11: 6 supported, 3 not supported` from the counts of one kind; zero counts are left out."""
    if not isinstance(counts, dict):
        return None
    parts = [f"{counts[k]} {k.replace('_', ' ')}" for k in _COUNTS[name]
             if isinstance(counts.get(k), int) and not isinstance(counts.get(k), bool) and counts[k]]
    total = counts.get("total")
    head = f"{name} {total}" if isinstance(total, int) and not isinstance(total, bool) else name
    return head + (": " + ", ".join(parts) if parts else "")


def not_claimed_line(x):
    """One formal verdict that gives no claim, in one line (spec §3.1.1): what it decided (its `statement`, when the
    file gives one), its verdict, why it gives no claim and the claim it went into; its lab IDs last."""
    verdict = str(x.get("outcome") or "").replace("_", " ")
    tail = (f"{verdict}; " if verdict else "") + f"{x.get('because')}" + (
        f" into {x['into']}" if x.get("into") else "") + (
        f"; runs {', '.join(str(v) for v in x['runs'])}" if isinstance(x.get("runs"), list) and x["runs"] else "")
    ids = f"{x.get('lab_event')} under {x.get('lab_plan')}"
    if isinstance(x.get("statement"), str) and x["statement"].strip():
        return f"{x['statement'].strip()} ({tail}; lab {ids})"
    return f"{ids} ({tail})"


def exploration_words(e, listed=False):
    """The reading view's exploration line, in words (spec §2.3): questions, hypotheses, tests and runs counted,
    the lab record, and what the paper covers of its lab. `listed`: leave out the verdicts that give no claim, which
    the reading view lists one per line after it."""
    out = []
    q = e.get("questions")
    if isinstance(q, int) and not isinstance(q, bool):
        out.append(f"{q} question{'s' if q != 1 else ''}")
    out += [x for x in (_counted(k, e.get(k)) for k in _COUNTS) if x]
    if e.get("lab_record"):
        out.append(f"lab record {e['lab_record']}")
    cov = e.get("covers")
    if isinstance(cov, dict):
        mine = ", ".join(str(x) for x in cov.get("questions") or [])
        lab = cov.get("lab") if isinstance(cov.get("lab"), dict) else {}
        whole = [f"{lab['questions']} questions"] if isinstance(lab.get("questions"), int) else []
        whole += [x for x in (_counted(k, lab.get(k)) for k in ("hypotheses", "tests")) if x]
        others = "; ".join(f"{o.get('name')} ({', '.join(str(x) for x in o.get('questions') or [])})"
                           for o in cov.get("other_papers") or [] if isinstance(o, dict))
        out.append("covers " + (mine or "part of its lab")
                   + (f" (the whole lab: {', '.join(whole)})" if whole else "")
                   + (f"; other papers from the lab: {others}" if others else ""))
    nc = [x for x in e.get("not_claimed") or [] if isinstance(x, dict)] if isinstance(e.get("not_claimed"), list) \
        else []
    if nc and not listed:      # the formal verdicts that give no claim (spec §3.1.1, as amended on 2026-11-17)
        out.append("not claimed: " + ", ".join(not_claimed_line(x) for x in nc))
    return "; ".join(out)


def _corrections(p):
    """The departures from the source that a claimset records (§3.1): those of a converted source, or of the published
    paper its authors converted, each with a string `field`; and how the view names what they correct."""
    if isinstance(p.get("converted_from"), dict):
        found, against = p["converted_from"].get("corrections"), "the source"
    elif isinstance(p.get("published_as"), dict):
        found, against = p["published_as"].get("corrections"), "the published paper"
    else:
        return [], ""
    return [c for c in found if isinstance(c, dict) and isinstance(c.get("field"), str) and c["field"]] \
        if isinstance(found, list) else [], against


def render(doc):
    """The reading view of a claimset, as a string."""
    p = doc.get("paper") or {}
    out = [f"CLAIMSET {p.get('title', '')}"]
    if isinstance(p.get("summary"), str) and p["summary"].strip():
        out.append("summary " + " ".join(p["summary"].split()))
    meta = [f"licence {p['licence']}" if p.get("licence") else ""]
    cf = p.get("converted_from")
    if isinstance(cf, dict):
        authors = ", ".join(a.get("name", "") for a in cf.get("source_authors") or [] if isinstance(a, dict))
        meta.append(f"converted from {cf.get('source_id')} {cf.get('source_version', '')}".strip()
                    + (f" by {authors}" if authors else ""))
    corrections, against = _corrections(p)
    if corrections:
        meta.append(f"corrects {against} in {len(corrections)} place{'s' if len(corrections) != 1 else ''} "
                    f"(CORRECTIONS)")
    if p.get("contributions"):
        meta.append("contributions " + ", ".join(p["contributions"]))
    if isinstance(p.get("highlights"), list) and p["highlights"]:
        meta.append("highlights " + ", ".join(str(x) for x in p["highlights"]))
    out.append(_join(meta))
    sections = [s for s in p.get("sections") or [] if isinstance(s, dict) and isinstance(s.get("title"), str)
                and isinstance(s.get("claims"), list)] if isinstance(p.get("sections"), list) else []
    if sections:                                       # the order the paper is read in (§3.1)
        out.append("sections")
        out += [f"  {i}. {' '.join(sec['title'].split())}: {', '.join(str(x) for x in sec['claims'])}"
                for i, sec in enumerate(sections, 1)]
    if p.get("declarations"):
        out.append("declarations " + _declarations(p["declarations"]))
    if isinstance(p.get("collaborations"), list):
        out.append("on behalf of " + "; ".join(
            _join([x.get("name"), ", ".join(x.get("identifiers") or [])], " ") for x in p["collaborations"]
            if isinstance(x, dict)))
    if isinstance(doc.get("extensions"), dict) and doc["extensions"]:
        out.append("extensions " + ", ".join(f"{k} {v}" for k, v in doc["extensions"].items()) + _ext(p))
    if isinstance(p.get("exploration"), dict):
        out.append("exploration " + exploration_words(p["exploration"], listed=True))
        nc = p["exploration"].get("not_claimed")
        nc = [x for x in nc if isinstance(x, dict)] if isinstance(nc, list) else []
        if nc:      # one line each (spec §2.3, as amended on 2026-11-20)
            what = "planned tests" if any(x.get("because") == "defective" for x in nc) else "formal verdicts"
            out.append(f"not claimed ({len(nc)} {what} that give no claim):")   # a void plan's too (2026-11-20)
            out += [f"  - {not_claimed_line(x)}" for x in nc]

    claims = [c for c in doc.get("claims") or [] if isinstance(c, dict)]
    defs = {d.get("id"): d for d in doc.get("definitions") or [] if isinstance(d, dict)}
    evid = {e.get("id"): e for e in doc.get("evidence") or [] if isinstance(e, dict)}

    def inherited(c):
        """Assumptions a claim inherits from the terms it rests on (§3.2)."""
        return inherited_assumptions(c, defs, evid)
    by_id = {}
    for c in claims:
        if isinstance(c.get("id"), str):
            by_id.setdefault(c["id"], c)
    in_section, placed = [], set()             # the claims section by section (§2.3, as amended on 2026-11-23)
    for i, sec in enumerate(sections, 1):
        mine = []
        for x in sec["claims"]:
            c = by_id.get(x) if isinstance(x, str) else None
            if c is not None and id(c) not in placed and not _is_assumption(c):   # read once, in its first section
                placed.add(id(c))
                mine.append(c)
        in_section.append((f"== {i}. {' '.join(sec['title'].split())}", mine))
    assumptions = [c for c in claims if _is_assumption(c)]   # listed before the claims (§2.3, as amended 2026-11-23)
    rest = [c for c in claims if id(c) not in placed and not _is_assumption(c)]
    unevidenced = [c for c in rest if c.get("role") != "principal" and _without_evidence(c)]
    order = {"principal": 0, "supporting": 1, "secondary": 2}
    main = sorted((c for c in rest if not any(c is u for u in unevidenced)),
                  key=lambda c: order.get(c.get("role"), 3))           # stable: file order within a role
    labels = key_labels(doc)         # a brief label for each term a table or result names (§2.3, from v0.45)
    corrected = {}
    for corr in corrections:
        corrected.setdefault(corr["field"].split(".")[0], []).append(corr)

    def marked(fn):
        """An object's lines, then a line for each correction of it (§3.1, Appendix D)."""
        def lines(x):
            out = fn(x)
            for corr in corrected.get(x.get("id"), []):
                out.append(f"  corrected from {against} ({_join([corr.get('kind'), corr.get('where')])}): "
                           f"printed {corr.get('printed')}")
            return out
        return lines
    claim_lines = marked(lambda c: _claim(c, inherited(c)))
    if in_section:
        listed = [x for head, mine in in_section for x in [head] + mine]
        listed += (["== Claims in no section"] + main) if main else []
    else:
        listed = main
    parts = [
        ("DEFINITIONS", doc.get("definitions"), marked(_definition)),
        ("ASSUMPTIONS", assumptions, marked(_assumption)),
        ("CLAIMS", listed, lambda x: [x] if isinstance(x, str) else claim_lines(x)),
        ("CLAIMS WITHOUT EVIDENCE", unevidenced, claim_lines),
        ("EVIDENCE", doc.get("evidence"), marked(lambda e: _evidence(e, labels))),
        ("WARRANTS", doc.get("warrants"),
         _warrant),
        ("LIMITATIONS", doc.get("limitations"),
         _limitation),
        ("OPEN QUESTIONS", doc.get("open_questions"),
         _open_question),
        ("ARTEFACTS", [a for a in doc.get("artefacts") or [] if isinstance(a, dict) and a.get("description")],
         _artefact),
        ("CORRECTIONS", corrections,
         lambda x: [f"{x.get('field')} [{_join([x.get('kind'), x.get('where'), ('found by ' + x['found_by']) if x.get('found_by') else ''])}] "
                    f"printed {x.get('printed')}; recorded {x.get('recorded')}; {x.get('reason')}"]),
        ("REFERENCES", doc.get("references"),
         lambda b: [f"{b.get('id')} {b.get('target')}" + (f" ({b['id_type']})" if b.get("id_type") not in (None, "reference") else "")]),
    ]
    for title, items, fn in parts:
        items = [x for x in items or [] if isinstance(x, dict) or (title == "CLAIMS" and isinstance(x, str))]
        if items:
            out += ["", title]
            for x in items:
                out += fn(x)
    return "\n".join(out) + "\n"


# The public names of how values are written (see the module's docstring): stable, for other views of a claimset.
number = _num
interval = _interval
uncertainty = _uncertainty
value = _val
statistic = _statistic
statistic_note = _stat_note

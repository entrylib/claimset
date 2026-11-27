"""Split views (spec §2.3, *Split views*): a claimset's reading view as a set of small plain-text files, so a reading
model takes what it needs: an overview of what is inside, one file per claim (assumptions too), per evidence object and
per definition, and the references. They are made mechanically from a valid file, as the reading view is, and keep its
links: every file names objects by their IDs, and its first line says which file holds each ID.

Links are written against a base address the publisher gives (`base`, the folder the files are served from, and
`whole`, the address of the whole reading view); without one, they are the files' names, which work beside each other
in a folder. The claimset itself holds no address.
"""

import re

from .render import (_artefact, _claim, _corrections, _declarations, _definition, _evidence, _key, _keyed,
                     _is_assumption, _join, _limitation, _open_question, _s, _warrant, inherited_assumptions, key_labels)

ID = re.compile(r"(?<![\w.])([A-Z]\d+)(?![\d])")
CITED = re.compile(r"^(E\d+)\.((?:T\d+|R\d+))(?:\.(r\d+))?$")
HANDOFF = ("If you cannot open links found in this text, give the person you are helping the addresses of the files "
           "that would answer their question, each on its own line, and let them choose which to paste back to you.")


def file_name(oid):
    """The file that holds an object of the claimset, by its ID; None for an ID no file holds on its own."""
    if re.fullmatch(r"[CED]\d+", oid or ""):
        return f"{oid}.txt"
    if re.fullmatch(r"B\d+", oid or ""):
        return "references.txt"
    return None


class _Paper:
    """The claimset, indexed for the views."""

    def __init__(self, doc, base="", whole=None):
        self.doc, self.base = doc, base or ""
        self.whole = whole or f"{self.base}claimset.txt"
        self.paper = doc.get("paper") if isinstance(doc.get("paper"), dict) else {}
        self.claims = {c["id"]: c for c in doc.get("claims") or [] if isinstance(c, dict) and isinstance(c.get("id"), str)}
        self.defs = {d["id"]: d for d in doc.get("definitions") or [] if isinstance(d, dict) and isinstance(d.get("id"), str)}
        self.evid = {e["id"]: e for e in doc.get("evidence") or [] if isinstance(e, dict) and isinstance(e.get("id"), str)}
        self.refs = {b["id"]: b for b in doc.get("references") or [] if isinstance(b, dict) and isinstance(b.get("id"), str)}
        self.lims = {x["id"]: x for x in doc.get("limitations") or [] if isinstance(x, dict) and isinstance(x.get("id"), str)}
        self.warrants = {x["id"]: x for x in doc.get("warrants") or [] if isinstance(x, dict) and isinstance(x.get("id"), str)}
        self.arts = {a["id"]: a for a in doc.get("artefacts") or [] if isinstance(a, dict) and isinstance(a.get("id"), str)}
        self.questions = {x["id"]: x for x in doc.get("open_questions") or [] if isinstance(x, dict)
                          and isinstance(x.get("id"), str)}
        self.corrections, self.against = _corrections(self.paper)
        self.labels = key_labels(doc)

    def url(self, oid):
        name = file_name(oid)
        return f"{self.base}{name}" if name else None

    def title_line(self, kind, oid=None):
        version = f"@v{self.paper['version']}" if self.paper.get("version") else ""
        what = f"{kind} {oid} of" if oid else kind
        return " ".join(x for x in (what, f"{self.paper.get('id', '')}{version}".strip(), self.paper.get("title")) if x)

    def files_line(self):
        b = self.base
        return (f"FILES{' at ' + b if b else ''}: claim or assumption Cn in Cn.txt, evidence En in En.txt, definition Dn in Dn.txt, "
                f"references Bn in references.txt, overview.txt; the whole paper: {self.whole}")

    def corrected(self, oid):
        return [f"  corrected from {self.against} ({_join([c.get('kind'), c.get('where')])}): printed {c.get('printed')}"
                for c in self.corrections if c["field"].split(".")[0] == oid]

    def ids_in_text(self, *texts):
        found = []
        for t in texts:
            for m in ID.finditer(t if isinstance(t, str) else ""):
                if m.group(1) not in found:
                    found.append(m.group(1))
        return found

    def name(self, oid):
        x = self.claims.get(oid) or {}
        if x.get("name"):
            return " ".join(x["name"].split())
        d = self.defs.get(oid)
        if d:
            return d.get("term", "")
        return ""


def _art(a):
    """An artefact's line, as the reading view gives it; an artefact without a description is named by its kind."""
    return [x.rstrip() for x in _artefact(a if a.get("description") else dict(a, description=""))]


def _label(P, oid):
    return f"{oid} {P.name(oid)}".strip()


def _finish(P, out):
    """The view's text, with every object it names that has no file of its own and is not shown in it (an artefact,
    limitation, warrant or open question) shown at its end, so that every ID in a view leads somewhere."""
    kinds = ((P.arts, _art), (P.lims, _limitation), (P.warrants, _warrant), (P.questions, _open_question))
    added = False
    while True:
        text = "\n".join(out)
        shown = set(re.findall(r"^\s*([A-Z]\d+)\b", text, re.MULTILINE))
        missing = [i for i in P.ids_in_text(text) if i not in shown and not file_name(i)
                   and any(i in objs for objs, _ in kinds)]
        if not missing:
            return text + "\n"
        if not added:
            out += ["", "ALSO NAMED ABOVE"]
            added = True
        for i in missing:
            objs, line = next((o, f) for o, f in kinds if i in o)
            out += line(objs[i])


def _text_of_claim(c):
    """The texts of a claim a reader reads: statement, summary, scope, relation notes."""
    out = [c.get("statement"), c.get("summary")]
    if isinstance(c.get("scope"), dict):
        out += [_s(v) for v in c["scope"].values()]
    out += [r.get("note") for r in c.get("relations") or [] if isinstance(r, dict)]
    return [x for x in out if isinstance(x, str)]


def overview(doc, base="", whole=None, score=None, claim_scores=None):
    """What a claimset contains, in a few lines: its title, summary and declarations, its claims section by section
    (one line each: ID and name; principal claims marked *), its assumptions, the terms it defines, how much else it
    holds, and how to read on. `score` is a line the publisher adds after the title, and `claim_scores` {claim ID:
    text} what it adds beside each claim's ID, in parentheses (scores are a publisher's, not in the file)."""
    P = _Paper(doc, base, whole)
    p = P.paper
    head = [P.title_line("OVERVIEW")]
    if score:
        head.append(score)
    if p.get("licence"):
        head.append(p["licence"])
    pub = p.get("published_as") if isinstance(p.get("published_as"), dict) else {}
    if pub.get("id"):
        head.append(f"published as {pub.get('id_type', '')}:{pub['id']}".replace(" :", ":"))
    cf = p.get("converted_from") if isinstance(p.get("converted_from"), dict) else {}
    if cf.get("source_id"):
        head.append(f"converted from {cf['source_id']}")
    out = [" · ".join(head), P.files_line()]
    if isinstance(p.get("summary"), str) and p["summary"].strip():
        out += ["", " ".join(p["summary"].split())]
    if p.get("declarations"):
        out.append("declarations " + _declarations(p["declarations"]))

    scored = claim_scores if isinstance(claim_scores, dict) else {}

    def line(cid):
        c = P.claims[cid]
        extra = f" ({scored[cid]})" if scored.get(cid) else ""
        return (f"  {cid}{'*' if c.get('role') == 'principal' else ''}{extra} "
                f"{P.name(cid) or _short(c.get('statement'))}")
    sections = [s for s in p.get("sections") or [] if isinstance(s, dict) and isinstance(s.get("claims"), list)] \
        if isinstance(p.get("sections"), list) else []
    assumptions = [k for k, c in P.claims.items() if _is_assumption(c)]
    listed = set()
    out += ["", "CLAIMS (* principal)"]
    for i, s in enumerate(sections, 1):
        ids = [x for x in s["claims"] if x in P.claims and x not in listed and x not in assumptions]
        listed |= set(ids)
        out.append(f"== {i}. {' '.join(_s(s.get('title')).split())}")
        out += [line(x) for x in ids]
    rest = [k for k in P.claims if k not in listed and k not in assumptions]
    if rest:
        if sections:
            out.append("== Claims in no section")
        order = {"principal": 0, "supporting": 1, "secondary": 2}
        out += [line(x) for x in sorted(rest, key=lambda k: order.get(P.claims[k].get("role"), 3))]
    if assumptions:
        out += ["", "ASSUMPTIONS"] + [line(x) for x in assumptions]
    principal = [k for k, c in P.claims.items() if c.get("role") == "principal" and k not in assumptions]
    hl = [x for x in p.get("highlights") or [] if isinstance(x, str)] if isinstance(p.get("highlights"), list) else []
    key = [x for x in hl if x in P.defs]
    for k in principal:
        key += [i for i in P.ids_in_text(*_text_of_claim(P.claims[k])) if i in P.defs and i not in key]
    if key:
        rest = len(P.defs) - len(key)
        out += ["", "KEY TERMS (highlighted, or named by a principal claim"
                + (f"; {rest} more in {P.base}D<n>.txt" if rest else "") + ")",
                "  " + "; ".join(f"{k} {P.defs[k].get('term', '')}" for k in key)]
    counts = [_count(len(P.evid), "evidence object") + f" ({', '.join(P.evid)})" if P.evid else "",
              _count(len(P.defs), "definition") if P.defs else "",
              _count(len(P.lims), "limitation") if P.lims else "",
              _count(len(P.refs), "reference") if P.refs else ""]
    nc = (p.get("exploration") or {}).get("not_claimed") if isinstance(p.get("exploration"), dict) else None
    if isinstance(nc, list) and nc:
        counts.append(_count(len(nc), "result") + " not claimed")
    if P.corrections:
        counts.append(_count(len(P.corrections), "correction") + f" of {P.against}")
    out += ["", "ALSO IN THE CLAIMSET: " + _join(counts)]
    out += ["", "READ ON (each file names the files of what it cites)"]
    out += [f"  {k}: {P.url(k)}" for k in principal]
    out += [f"  {k}: {P.url(k)}" for k in P.evid]
    out.append(f"  the whole paper: {P.whole}")
    out.append(HANDOFF)
    return re.sub(r"\n{3,}", "\n\n", _finish(P, out))


LINK = re.compile(r"\[\[[A-Z]+\d+(?:\.[A-Za-z0-9]+)*:([^\]]*)\]\]")


def _short(text, words=12):
    """A claim's statement as a name, for a claim without one: its first words, links written as their text."""
    w = LINK.sub(lambda m: m.group(1), _s(text)).split()
    return " ".join(w[:words]) + (" …" if len(w) > words else "")


def _count(n, noun):
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _range(ids):
    """C1, C2, C3, C5 as "C1–C3, C5"."""
    out, run = [], []
    for k in ids:
        if run and k[0] == run[-1][0] and int(k[1:]) == int(run[-1][1:]) + 1:
            run.append(k)
            continue
        if run:
            out.append(run[0] if len(run) < 3 else f"{run[0]}–{run[-1]}")
            out += run[1:2] if len(run) == 2 else []
        run = [k]
    if run:
        out.append(run[0] if len(run) < 3 else f"{run[0]}–{run[-1]}")
        out += run[1:2] if len(run) == 2 else []
    return ", ".join(out)


def _cited_parts(support):
    """{evidence ID: set of cited parts}: a part is ('T2', None) for a whole table, ('T2', 'r4') for a row, ('R1', None)
    for a result; an empty set means the evidence is cited as a whole."""
    out = {}
    for s in support:
        if not isinstance(s, dict) or not s.get("evidence"):
            continue
        parts = out.setdefault(s["evidence"], set())
        results = [r for r in s.get("results") or [] if isinstance(r, str)]
        if not results:
            parts.add(("*", None))
        for r in results:
            m = CITED.match(r)
            if m and m.group(1) == s["evidence"]:
                parts.add((m.group(2), m.group(3)))
            else:
                parts.add(("*", None))
    return out


def _first_sentence(text):
    """The first sentence of a text, as a short description of what it describes."""
    words = " ".join(_s(text).split())
    m = re.search(r"(?<=[.!?])\s+(?=[A-Z(\[$])", words)
    return words[:m.start()] if m else words


def _evidence_part(P, eid, parts):
    """What a claim cites of an evidence object, by reference (spec §2.3, split views): the object in one line (its
    profile and the first sentence of its description) with its file; each table it cites by title, with the rows it
    cites; the results it cites, one line each. The rows themselves are in the object's file."""
    e = P.evid[eid]
    head = _evidence(dict(e, description=_first_sentence(e.get("description"))))[0]
    lines = [f"{head} {P.url(eid)}"]
    if ("*", None) in parts:
        return lines + ["  cited as a whole"]
    tables = {t.get("id"): t for t in e.get("tables") or [] if isinstance(t, dict)}
    results = {r.get("id"): r for r in e.get("results") or [] if isinstance(r, dict)}
    for tid in sorted({p for p, _ in parts if p in tables}, key=lambda x: int(x[1:])):
        t = tables[tid]
        n = t.get("n_rows") if t.get("rows_file") and not t.get("rows") else len(t.get("rows") or [])
        rows = sorted({r for p, r in parts if p == tid and r}, key=lambda x: int(x[1:]))
        if not rows or (tid, None) in parts:
            which = "the whole table"
        elif isinstance(n, int) and len(rows) == n:
            which = f"every row ({n})"
        else:
            which = f"rows {_range(rows)}" + (f" of {n}" if isinstance(n, int) else "")
        lines.append(f"  {eid}.{tid} {' '.join(_s(t.get('description')).split())}: {which}")
    for rid in [p for p, _ in parts if p in results]:
        one = dict(e, results=[results[rid]], tables=[])
        lines += [x for x in _evidence(one)[1:] if x.lstrip().startswith(f"{eid}.{rid} ")]
    keyed = [r for p, _ in parts if p in results for r in [results[p]]]
    if keyed:                        # the key under the results it cites (§2.3, from v0.45)
        lines += _key(_keyed([{"variable": r.get("variable"), "conditions": r.get("conditions"),
                               "value": r.get("value")} for r in keyed], P.labels), P.labels)
    return lines


def claim_view(doc, claim_id, base="", whole=None):
    """One claim with what a reader needs to read it: the claim, its limitations, its warrant and the references it
    cites, in full; its assumptions, the definitions its texts name and the evidence it cites (each table by title with
    the rows cited, each result cited), by name, each in its own file. Raises KeyError for a claim the claimset does
    not have."""
    P = _Paper(doc, base, whole)
    c = P.claims[claim_id]
    inherited = inherited_assumptions(c, P.defs, P.evid)
    out = [P.title_line("ASSUMPTION" if _is_assumption(c) else "CLAIM", claim_id), P.files_line(), ""]
    # the support line names the evidence; what of it the claim cites is under EVIDENCE, by table and rows
    brief = dict(c, support=[{k: v for k, v in x.items() if k != "results"} if isinstance(x, dict) and x.get("evidence")
                             in P.evid else x for x in c.get("support") or []])
    out += _claim(brief, inherited) + P.corrected(claim_id)
    assumed = list(dict.fromkeys(a for a in list(c.get("assumptions") or []) + list(inherited) if a in P.claims))
    if assumed:                     # each in its own file: an assumption can be long, and many claims share one
        out += ["", "ASSUMPTIONS (each in its own file)"] + [f"  {_label(P, a)}: {P.url(a)}" for a in assumed]
    if _is_assumption(c):
        users = [k for k, x in P.claims.items() if k != claim_id and claim_id in
                 list(x.get("assumptions") or []) + list(inherited_assumptions(x, P.defs, P.evid))]
        if users:
            out += ["", "CLAIMS RESTING ON IT: " + " · ".join(_label(P, k) for k in users)]
    lims = [x for x in c.get("limitations") or [] if x in P.lims]
    lims += [k for k, x in P.lims.items() if claim_id in (x.get("affects") or []) and k not in lims]
    if lims:
        out += ["", "LIMITATIONS"]
        out += [line for k in lims for line in _limitation(P.lims[k])]
    named = [i for i in P.ids_in_text(*_text_of_claim(c)) if i in P.defs]
    about = c.get("about") if isinstance(c.get("about"), dict) else {}
    for v in about.values():
        for x in v if isinstance(v, list) else [v]:
            if isinstance(x, str) and x in P.defs and x not in named:
                named.append(x)
    if named:                       # each in its own file: a definition can be long, and many claims share one
        out += ["", "DEFINITIONS (the terms this claim names, each in its own file)"]
        out += [f"  {_label(P, d)}: {P.url(d)}" for d in named]
    cited = _cited_parts(c.get("support") or [])
    cited = {k: v for k, v in cited.items() if k in P.evid}
    if cited:                       # by reference: the rows are in the evidence's own file
        out += ["", "EVIDENCE (what this claim cites, each object in its own file)"]
        for eid, parts in cited.items():
            out += _evidence_part(P, eid, parts)
    arts = [a for x in c.get("support") or [] if isinstance(x, dict) for a in x.get("artefacts") or []]
    arts = [a for a in dict.fromkeys(arts + P.ids_in_text(*_text_of_claim(c))) if a in P.arts]
    if arts:
        out += ["", "ARTEFACTS"] + [line for a in arts for line in _art(P.arts[a])]
    w = c.get("warrant")
    if isinstance(w, str) and w in P.warrants:
        out += ["", "WARRANT"] + _warrant(P.warrants[w])
    refs = [s.get("reference") for s in c.get("support") or [] if isinstance(s, dict) and s.get("reference") in P.refs]
    refs += [r.get("reference") for r in c.get("relations") or [] if isinstance(r, dict) and r.get("reference") in P.refs]
    refs += [i for i in P.ids_in_text(*_text_of_claim(c)) if i in P.refs]
    refs = list(dict.fromkeys(refs))
    if refs:
        out += ["", "REFERENCES"] + [_reference(P.refs[b]) for b in refs]
    related = [i for i in list(c.get("depends_on") or []) + [r.get("target") for r in c.get("relations") or []
                                                              if isinstance(r, dict) and r.get("id_type") == "local"]
               if isinstance(i, str) and i in P.claims and i != claim_id]
    related = list(dict.fromkeys(related))
    if related:
        out += ["", "RELATED CLAIMS: " + " · ".join(f"{_label(P, k)} {P.url(k)}" for k in related)]
    return _finish(P, out)


def _reference(b):
    """A reference's line, as the reading view gives it."""
    return f"{b.get('id')} {b.get('target')}"


def evidence_view(doc, evidence_id, base="", whole=None):
    """One evidence object whole: its design, results and tables, the files it names, the terms it names (by name,
    each in its own file), the references it cites, and the claims that rest on it."""
    P = _Paper(doc, base, whole)
    e = P.evid[evidence_id]
    out = ([P.title_line("EVIDENCE", evidence_id), P.files_line(), ""] + _evidence(e, key_labels(doc))
           + P.corrected(evidence_id))
    named = [i for i in P.ids_in_text("\n".join(out)) if i in P.defs]
    if named:
        out += ["", "TERMS (each in its own file): " + " · ".join(_label(P, d) for d in named)]
    arts = [a for a in P.ids_in_text(str(e)) if a in P.arts]
    if arts:
        out += ["", "ARTEFACTS"] + [line for a in arts for line in _art(P.arts[a])]
    refs = [i for i in P.ids_in_text(str(e)) if i in P.refs]
    if refs:
        out += ["", "REFERENCES"] + [_reference(P.refs[b]) for b in refs]
    users = [k for k, c in P.claims.items()
             if any(isinstance(s, dict) and s.get("evidence") == evidence_id for s in c.get("support") or [])]
    if users:
        out += ["", "CLAIMS RESTING ON IT: " + " · ".join(_label(P, k) for k in users)]
    return _finish(P, out)


def definition_view(doc, definition_id, base="", whole=None):
    """One definition, with the reference it is taken from and the claims that name it."""
    P = _Paper(doc, base, whole)
    d = P.defs[definition_id]
    out = [P.title_line("DEFINITION", definition_id), P.files_line(), ""] + _definition(d) + P.corrected(definition_id)
    src = d.get("source")
    refs = [i for i in P.ids_in_text(_s(src) if not isinstance(src, dict) else _s(src.get("target")), d.get("definition"))
            if i in P.refs]
    if refs:
        out += ["", "REFERENCES"] + [_reference(P.refs[b]) for b in refs]
    users = [k for k, c in P.claims.items() if definition_id in P.ids_in_text(*_text_of_claim(c))]
    if users:
        out += ["", "CLAIMS NAMING IT: " + " · ".join(_label(P, k) for k in users)]
    return _finish(P, out)


def references_view(doc, base="", whole=None):
    """The references, each with the claims that cite it."""
    P = _Paper(doc, base, whole)
    out = [P.title_line("REFERENCES"), P.files_line(), ""]
    for b, ref in P.refs.items():
        citing = [k for k, c in P.claims.items()
                  if any(isinstance(s, dict) and s.get("reference") == b for s in list(c.get("support") or [])
                         + list(c.get("relations") or [])) or b in P.ids_in_text(*_text_of_claim(c))]
        out.append(_reference(ref) + (f" (cited by {', '.join(citing)})" if citing else ""))
    return _finish(P, out)


def files(doc, base="", whole=None, score=None, claim_scores=None):
    """Every split view of a claimset, as {file name: text}."""
    P = _Paper(doc, base, whole)
    out = {"overview.txt": overview(doc, base, whole, score, claim_scores)}
    for k in P.claims:
        out[f"{k}.txt"] = claim_view(doc, k, base, whole)
    for k in P.evid:
        out[f"{k}.txt"] = evidence_view(doc, k, base, whole)
    for k in P.defs:
        out[f"{k}.txt"] = definition_view(doc, k, base, whole)
    if P.refs:
        out["references.txt"] = references_view(doc, base, whole)
    return out

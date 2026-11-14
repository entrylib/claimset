"""The lab record part of the review extension (spec/extensions/review-v0.1.md §2): a review's protocol, the
searches it ran, its screening decisions and the passages of included works its hypotheses rest on; the flags of
the order of that work; and what export makes of them.

The lab core calls this module only for records that declare the extension.
"""

import re

from .. import validate as _claimset
from .core import LabError, State, _ref, _refs, _req, is_withheld
from .sources import HTML_FORMATS, TEXT_FORMATS, is_private, source_dir, text_of

NAME = "review"
STAGES = ("title_abstract", "full_text")
DECISIONS = ("include", "exclude")
READ = ("full_text", "abstract", "secondary")
VERSIONS = ("published", "preprint", "author_copy", "working_paper", "other")
SELECTOR_KEYS = ("exact", "prefix", "suffix", "start", "end")
#: Identifier types of a work, the claimset's (claimset §3.13), less those for claimsets of this repository.
ID_TYPES = sorted(_claimset.ENUM["id_type"] - {"claimset_local"})
UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def parse_work(text):
    """A work named on the command line: `doi:10.…`, `arxiv:…`, `isbn:…`, `pmid:…`, `handle:…`, `curie:…`, a URL, or
    `reference:<the reference as printed>`. Returns {target, id_type}."""
    text = str(text or "").strip()
    if re.match(r"^https?://", text):
        return {"target": text, "id_type": "url"}
    kind, sep, rest = text.partition(":")
    if not sep or kind.lower() not in ID_TYPES or not rest.strip():
        raise LabError("schema", f"a work is named by its identifier: doi:10.…, arxiv:…, isbn:…, pmid:…, handle:…, "
                                 f"curie:…, a URL, or reference:\"<as printed>\"; not '{text}'")
    return {"target": rest.strip(), "id_type": kind.lower()}


def work_key(work):
    """A work's identity, for comparing screenings and extracts: (id type, identifier), a DOI case-insensitively."""
    if not isinstance(work, dict):
        return None
    t = str(work.get("target") or "").strip()
    k = work.get("id_type")
    return (k, t.lower() if k == "doi" else t)


def _work(body, etype):
    w = _req(body, "work", etype)
    if not isinstance(w, dict) or w.get("id_type") not in ID_TYPES or not isinstance(w.get("target"), str) \
            or not w["target"].strip() or set(w) - {"target", "id_type"}:
        raise LabError("review.L3" if etype == "screening" else "review.L4",
                       f"{etype}: work is {{target, id_type}}, id_type one of {', '.join(ID_TYPES)}")
    return w


def _texts(body, field, etype, rule, required):
    v = body.get(field)
    if v is None and not required:
        return
    if not (isinstance(v, list) and v and all(isinstance(x, str) and x.strip() for x in v)):
        raise LabError(rule, f"{etype}: '{field}' is a non-empty list of texts")


def check_event(state, etype, body, by, eid):
    if etype == "protocol":
        _texts(body, "sources", "protocol", "review.L1", True)
        _texts(body, "include", "protocol", "review.L1", True)
        _texts(body, "exclude", "protocol", "review.L1", False)
        if body.get("question") is not None:
            _ref(state, body["question"], "protocol", "question", {"question"})
        for k in ("period", "guideline"):
            if body.get(k) is not None and not (isinstance(body[k], str) and body[k].strip()):
                raise LabError("review.L1", f"protocol: '{k}' is non-empty text")
    elif etype == "search":
        for k in ("source", "query"):
            if not (isinstance(body.get(k), str) and body[k].strip()):
                raise LabError("review.L2", f"search: '{k}' is required, non-empty text")
        n = body.get("results")
        if not (isinstance(n, int) and not isinstance(n, bool) and n >= 0):
            raise LabError("review.L2", "search: 'results' is the number of records it returned, an integer >= 0")
        if body.get("at") is not None and not (isinstance(body["at"], str) and UTC.match(body["at"])):
            raise LabError("review.L2", "search: 'at' is a UTC time YYYY-MM-DDTHH:MM:SSZ")
        if body.get("protocol") is not None:
            _ref(state, body["protocol"], "search", "protocol", {"protocol"})
    elif etype == "screening":
        _work(body, "screening")
        if body.get("stage") not in STAGES:
            raise LabError("review.L3", f"screening: 'stage' is one of {', '.join(STAGES)}")
        if body.get("decision") not in DECISIONS:
            raise LabError("review.L3", f"screening: 'decision' is one of {', '.join(DECISIONS)}")
        if body["decision"] == "exclude" and not (isinstance(body.get("reason"), str) and body["reason"].strip()):
            raise LabError("review.L3", "screening: a work excluded needs the reason (--reason)")
        if body["decision"] == "include" and body.get("read") not in READ:
            raise LabError("review.L3", f"screening: a work included says how far it was read (--read: "
                                        f"{', '.join(READ)})")
        if body.get("read") is not None and body["read"] not in READ:
            raise LabError("review.L3", f"screening: 'read' is one of {', '.join(READ)}")
        if body.get("version") is not None and body["version"] not in VERSIONS:
            raise LabError("review.L3", f"screening: 'version' is one of {', '.join(VERSIONS)}")
        if body.get("source") is not None:
            _ref(state, body["source"], "screening", "source", {"source"})
        _refs(state, body.get("searches"), "screening", "searches", {"search"})
        if body.get("title") is not None and not (isinstance(body["title"], str) and body["title"].strip()):
            raise LabError("review.L3", "screening: 'title' is non-empty text")
    elif etype == "extract":
        work = _work(body, "extract")
        _refs(state, _req(body, "for", "extract"), "extract", "for", {"hypothesis"})
        latest = latest_screenings(state).get(work_key(work), {})
        if not any(s["body"].get("decision") == "include" for s in latest.values()) or \
                any(s["body"].get("decision") == "exclude" for s in latest.values()):
            raise LabError("review.L4", f"extract: {work['id_type']}:{work['target']} is not a work the review "
                                        f"includes: screen it first (`claimset lab screen … --decision include`)")
        sel, text = body.get("quote"), body.get("text")
        if (sel is None) == (text is None):
            raise LabError("review.L4", "extract: the passage, as a quote from a captured copy (--source and --quote) "
                                        "or as text read where no copy was captured (--text); one of the two")
        if text is not None and not (isinstance(text, str) and text.strip()):
            raise LabError("review.L4", "extract: 'text' is the passage, non-empty")
        if sel is not None:
            sid = _ref(state, _req(body, "source", "extract"), "extract", "source", {"source"})
            if not isinstance(sel, dict) or not isinstance(sel.get("exact"), str) or not sel["exact"].strip() \
                    or not all(isinstance(sel.get(k), int) and not isinstance(sel.get(k), bool) for k in ("start", "end")) \
                    or not 0 <= sel["start"] < sel["end"] or set(sel) - set(SELECTOR_KEYS):
                raise LabError("review.L4", "extract: quote is {exact, prefix, suffix, start, end}, as `claimset lab "
                                            "quote` gives it")
            src = state.get(sid)
            if src is not None and not is_withheld(src) and not has_text(src["body"]):
                raise LabError("review.L4", f"extract: {sid} has no text to quote from (capture it with --text)")
        if body.get("locator") is not None and not (isinstance(body["locator"], str) and body["locator"].strip()):
            raise LabError("review.L4", "extract: 'locator' is non-empty text")


def has_text(body):
    """Whether a source has text to quote from: an extracted text, or an original that is text (sources.text_of)."""
    roles = {f.get("role") for f in body.get("files") or [] if isinstance(f, dict)}
    return "text" in roles or ("original" in roles and body.get("format") in (*TEXT_FORMATS, *HTML_FORMATS))


def check_block(state, etype, body, block, eid):
    raise LabError("L30", f"{etype}: the review extension has no block on lab events")


def latest_screenings(state):
    """{work key: {stage: the latest screening of that work at that stage}} (§2.3): the latest version of each,
    without withheld ones; a later screening of the same work at the same stage replaces an earlier one."""
    out = {}
    for e in state.events:
        if e.get("type") != "screening" or e["id"] in state.superseded_by or is_withheld(e) \
                or not isinstance(e.get("body"), dict):
            continue
        out.setdefault(work_key(e["body"].get("work")), {})[e["body"].get("stage")] = e
    return out


def current(state, etype):
    """The latest versions of the events of a type, in the order recorded, without withheld ones."""
    return [e for e in state.events if e.get("type") == etype and e["id"] not in state.superseded_by
            and not is_withheld(e) and isinstance(e.get("body"), dict)]


def flags(state):
    """The flags of §2.6, in the order of FLAGS."""
    searches = [e for e in state.events if e.get("type") == "search"]
    protocols = [e for e in state.events if e.get("type") == "protocol"]
    out = []
    if searches and (not protocols or state.pos.get(searches[0]["id"], 0) < state.pos.get(protocols[0]["id"], 0)):
        out.append("searched_before_protocol")
    if searches and any(p.get("supersedes") and state.pos.get(p["id"], 0) > state.pos.get(searches[0]["id"], 0)
                        for p in protocols):
        out.append("protocol_changed_after_search")
    return out


def included(state):
    """The works the review includes: {work key: the screening that includes it (full text if any, else title and
    abstract)}, works excluded at either stage left out."""
    out = {}
    for key, stages in latest_screenings(state).items():
        if any(s["body"].get("decision") == "exclude" for s in stages.values()):
            continue
        s = stages.get("full_text") or stages.get("title_abstract")
        if s is not None and s["body"].get("decision") == "include":
            out[key] = s
    return out


def flow(state):
    """The PRISMA counts of §2.7, from the latest screenings and the searches."""
    sc = latest_screenings(state)
    ta = [st["title_abstract"] for st in sc.values() if "title_abstract" in st]
    ft = [st["full_text"] for st in sc.values() if "full_text" in st]
    searches = current(state, "search")
    out = {"identified": sum(s["body"].get("results", 0) for s in searches) if searches else None,
           "screened": len(ta), "excluded_screening": sum(1 for s in ta if s["body"]["decision"] == "exclude"),
           "assessed": len(ft)}
    reasons = {}
    for s in ft:
        if s["body"]["decision"] == "exclude":
            reasons[s["body"]["reason"]] = reasons.get(s["body"]["reason"], 0) + 1
    if reasons:
        out["excluded_full_text"] = reasons
    inc = included(state)
    out["included"] = len(inc)
    other = sum(1 for s in inc.values() if not s["body"].get("searches")
                and not any(x["body"].get("searches") for x in sc[work_key(s["body"]["work"])].values()))
    if other:
        out["other_sources"] = other
    # identified counts what the searches found: with no search, nothing was identified by one, and the count is left out
    return {k: v for k, v in out.items() if v or (k == "included") or (k == "identified" and v is not None)}


def verify(lab, events):
    """review.L4: every extract's quote is in its source's text, at the recorded place."""
    st = State()
    for e in events:
        if isinstance(e, dict):
            st.apply(e)
    errors = []
    for e in events:
        if not isinstance(e, dict) or e.get("type") != "extract" or is_withheld(e) or not isinstance(e.get("body"), dict):
            continue
        sel = e["body"].get("quote")
        src = st.get(e["body"].get("source"))
        if not isinstance(sel, dict) or src is None or is_withheld(src):
            continue
        if is_private(src.get("body")) and not source_dir(lab, src).is_dir():
            continue                              # kept out of git; source_notes says so
        try:
            text = text_of(lab, src)
        except (LabError, OSError):
            errors.append({"seq": e["seq"], "id": e["id"], "rule": "review.L4",
                           "message": f"the text of {src['id']} cannot be read, so the quote cannot be checked"})
            continue
        start, end = sel.get("start"), sel.get("end")
        if not (isinstance(start, int) and isinstance(end, int) and text[start:end] == sel.get("exact")):
            errors.append({"seq": e["seq"], "id": e["id"], "rule": "review.L4",
                           "message": f"the quote is not in {src['id']}'s text at {start}-{end}"})
    return errors


RECOMMENDS = re.compile(r"\b(should|must|use|avoid|prefer|recommend\w*)\b", re.I)


def export(exp):
    """What export makes of the review's events (§2.7): the paper's protocol, searches, flow and flags; a reference
    for each included work, with how it was read; and, on the claim of each hypothesis an extract bears on, a cited
    support entry and the extract. Returns whether anything was exported."""
    st = exp.st
    block = {}
    protocols = current(st, "protocol")
    if protocols:
        p = protocols[-1]["body"]
        q = st.get(p["question"]) if p.get("question") else None
        prot = {"question": q["body"].get("text") if q is not None and not is_withheld(q) else None,
                "sources": p["sources"], "include": p["include"], "exclude": p.get("exclude"),
                "period": p.get("period"), "guideline": p.get("guideline"), "lab_event": protocols[-1]["id"]}
        block["protocol"] = {k: v for k, v in prot.items() if v}
    searches = current(st, "search")
    if searches:
        block["searches"] = [{"source": s["body"]["source"], "query": s["body"]["query"],
                              "date": str(s["body"].get("at") or s.get("at") or "")[:10],
                              "results": s["body"]["results"], "lab_event": s["id"]} for s in searches]
    if current(st, "screening"):
        block["flow"] = flow(st)
    fl = flags(st)
    if fl:
        block["flags"] = fl
    refs = {}
    for key, s in included(st).items():
        b = s["body"]
        rid = exp.reference_for(b["work"])
        ext = {"read": b["read"], "version": b.get("version"), "checked_on": str(s.get("at", ""))[:10] or None,
               "artefact": exp.mapping_back(b["source"]) if b.get("source") else None, "lab_event": s["id"]}
        exp.ext_block(exp.reference(rid), NAME).update({k: v for k, v in ext.items() if v})
        if ext["artefact"]:
            exp.retarget_artefact(ext["artefact"], rid)       # the copy that was read is a copy of this work
        refs[key] = rid
    by_hyp = {}
    for c in exp.claims:
        h = (c.get("hypothesis") or {}).get("lab_event")
        if h:
            by_hyp[st.root(h)] = c
    for x in current(st, "extract"):
        b = x["body"]
        rid = refs.get(work_key(b["work"])) or exp.reference_for(b["work"])
        for h in b["for"]:
            claim = by_hyp.get(st.root(h))
            if claim is None:
                continue
            support = {"kind": "cited", "reference": rid}
            if b.get("locator"):
                support["locator"] = b["locator"]
            if not any(s.get("kind") == "cited" and s.get("reference") == rid and s.get("locator") == b.get("locator")
                       for s in claim["support"]):
                claim["support"].append(support)
            ex = {"reference": rid, "locator": b.get("locator"), "lab_event": x["id"]}
            if b.get("quote"):
                ex.update({k: b["quote"][k] for k in SELECTOR_KEYS if b["quote"].get(k) is not None})
                ex["artefact"] = exp.mapping_back(b["source"])
            else:
                ex["text"] = b["text"]
            cb = exp.ext_block(claim, NAME)
            cb.setdefault("extracts", []).append({k: v for k, v in ex.items() if v is not None})
            cb.setdefault("kind", "recommendation" if RECOMMENDS.search(claim.get("statement") or "") else "summary")
            exp.done_support(claim)
            if hasattr(exp, "mark_synthesis") and not any(
                    s.get("kind") in ("empirical_quant", "empirical_qual") for s in claim["support"]):
                exp.mark_synthesis(claim, "it states what the works its extracts quote establish, which are its "
                                          "evidence; it extends them only if it goes beyond what they state")
    if block:
        exp.ext_block(exp.paper_object(), NAME).update(block)
    used = bool(block or refs or any(NAME in (c.get("ext") or {}) for c in exp.claims))
    if used:
        exp.todo("ext.review", "review: check each claim's ext.review.kind (summary or recommendation), and add "
                               "contested_by for works that disagree with a claim")
    return used

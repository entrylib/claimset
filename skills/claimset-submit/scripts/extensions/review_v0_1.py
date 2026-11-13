"""The review extension, version 0.1 (spec/extensions/review-v0.1.md): literature reviews, how they found and read
the works they cite, and the passages their claims rest on. Never edit once released: a new version of the extension
is a new module.

The claimset part (check) is here. The lab record part is implemented by the lab tool, in the module LAB names:
its event types (LAB_EVENTS).
"""

import re

NAME = "review"
VERSION = "0.1"
OBJECTS = {"paper", "reference", "claim"}

#: Lab record: event types this extension defines (type -> ID prefix), and the module that implements them.
LAB_EVENTS = {"protocol": "PT", "search": "SE", "screening": "SC", "extract": "XT"}
LAB_BLOCKS = set()
LAB = "claimset.lab.review"

READ = ("full_text", "abstract", "secondary")
VERSIONS = ("published", "preprint", "author_copy", "working_paper", "other")
KINDS = ("summary", "recommendation")
FLAGS = ("searched_before_protocol", "protocol_changed_after_search")
FIELDS = {"paper": {"protocol", "searches", "flow", "flags"},
          "reference": {"read", "version", "checked_on", "artefact", "via", "lab_event"},
          "claim": {"kind", "extracts", "contested_by"}}
EXTRACT_FIELDS = {"reference", "locator", "exact", "prefix", "suffix", "start", "end", "artefact", "text", "lab_event"}
FLOW_COUNTS = ("identified", "duplicates", "screened", "excluded_screening", "assessed", "included", "other_sources")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _text(x):
    return isinstance(x, str) and bool(x.strip())


def _texts(x):
    return isinstance(x, list) and bool(x) and all(_text(v) for v in x)


def _list(x):
    return x if isinstance(x, list) else []


def _dict(x):
    return x if isinstance(x, dict) else {}


def _count(x):
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def protocol_problems(p):
    """What makes a protocol invalid (§1.3, §2.1)."""
    if not isinstance(p, dict):
        return ["the protocol is an object"]
    out = []
    if not _texts(p.get("sources")):
        out.append("a protocol names the sources searched: a non-empty list of texts")
    if not _texts(p.get("include")):
        out.append("a protocol states what a work must meet to be included: a non-empty list of texts")
    if p.get("exclude") is not None and not _texts(p["exclude"]):
        out.append("a protocol's exclude is a list of texts")
    for k in ("question", "period", "guideline", "lab_event"):
        if p.get(k) is not None and not _text(p[k]):
            out.append(f"a protocol's {k} is non-empty text")
    return out


def flow_problems(f):
    """What makes a flow invalid (§1.3)."""
    if not isinstance(f, dict) or not f:
        return ["the flow is an object of counts"]
    out = []
    for k, v in f.items():
        if k == "excluded_full_text":
            if not (isinstance(v, dict) and all(_text(r) and _count(n) for r, n in v.items())):
                out.append("excluded_full_text is {reason: count}, each count a non-negative integer")
        elif k not in FLOW_COUNTS:
            out.append(f"the flow has no count {k}")
        elif not _count(v):
            out.append(f"{k} is a non-negative integer")
    chain = [f.get(k) for k in ("included", "assessed", "screened")]
    known = [v for v in chain if _count(v)]
    if any(a > b for a, b in zip(known, known[1:])):
        out.append("included <= assessed <= screened")
    return out


def check(blocks, doc, r):
    refs = {x.get("id"): x for x in _list(doc.get("references")) if isinstance(x, dict) and isinstance(x.get("id"), str)}
    arts = {x.get("id") for x in _list(doc.get("artefacts")) if isinstance(x, dict) and isinstance(x.get("id"), str)}
    claims_with_blocks = refs_with_blocks = False
    paper_searches = None
    for where, typ, obj, block in blocks:
        allowed = FIELDS.get(typ)
        if allowed is None:
            r.err("review.1", where, f"a review block is on the paper, a reference or a claim, not a {typ}")
            continue
        extra = set(block) - allowed
        if extra:
            r.err("review.1", where, f"on a {typ}: only {', '.join(sorted(allowed))}; not {', '.join(sorted(extra))}")
        if typ == "reference":
            refs_with_blocks = True
            if block.get("read") not in READ:
                r.err("review.2", f"{where}.read", f"how far the work was read: one of {', '.join(READ)}")
            if block.get("version") is not None and block["version"] not in VERSIONS:
                r.err("review.2", f"{where}.version", f"one of {', '.join(VERSIONS)}")
            if block.get("checked_on") is not None and not (isinstance(block["checked_on"], str)
                                                            and DATE.match(block["checked_on"])):
                r.err("review.2", f"{where}.checked_on", "a date YYYY-MM-DD")
            if block.get("artefact") is not None and (not isinstance(block["artefact"], str) or block["artefact"] not in arts):
                r.err("review.2", f"{where}.artefact", f"{block['artefact']} is not an artefact of the file")
            for k in ("via", "lab_event"):
                if block.get(k) is not None and not _text(block[k]):
                    r.err("review.2", f"{where}.{k}", "non-empty text")
        elif typ == "claim":
            claims_with_blocks = True
            cited = {s.get("reference") for s in _list(obj.get("support")) if isinstance(s, dict)
                     and s.get("kind") == "cited" and isinstance(s.get("reference"), str)}
            if "kind" in block and block["kind"] not in KINDS:
                r.err("review.4", f"{where}.kind", f"one of {', '.join(KINDS)}")
            if "extracts" in block:
                ex = block["extracts"]
                if not isinstance(ex, list) or not ex:
                    r.err("review.3", f"{where}.extracts", "a non-empty list of extracts")
                    ex = []
                for i, e in enumerate(ex):
                    w = f"{where}.extracts[{i}]"
                    if not isinstance(e, dict):
                        r.err("review.3", w, "an extract is an object")
                        continue
                    bad = set(e) - EXTRACT_FIELDS
                    if bad:
                        r.err("review.3", w, f"an extract has no {', '.join(sorted(bad))}")
                    if not isinstance(e.get("reference"), str) or e["reference"] not in cited:
                        r.err("review.3", f"{w}.reference", "the reference of one of the claim's cited support entries")
                    if not (_text(e.get("exact")) or _text(e.get("text"))):
                        r.err("review.3", w, "the passage: exact (from a captured copy) or text")
                    if e.get("artefact") is not None and (not isinstance(e["artefact"], str) or e["artefact"] not in arts):
                        r.err("review.3", f"{w}.artefact", f"{e['artefact']} is not an artefact of the file")
                    for k in ("locator", "lab_event"):
                        if e.get(k) is not None and not _text(e[k]):
                            r.err("review.3", f"{w}.{k}", "non-empty text")
                    s, t = e.get("start"), e.get("end")
                    if (s is not None or t is not None) and not (isinstance(s, int) and isinstance(t, int) and s < t):
                        r.err("review.3", w, "start and end are integers, start < end")
            if "contested_by" in block:
                cb = block["contested_by"]
                if not isinstance(cb, list) or not cb:
                    r.err("review.4", f"{where}.contested_by", "a non-empty list of {reference, note}")
                    cb = []
                for i, c in enumerate(cb):
                    if not (isinstance(c, dict) and isinstance(c.get("reference"), str) and c["reference"] in refs
                            and _text(c.get("note"))):
                        r.err("review.4", f"{where}.contested_by[{i}]", "{reference, note}: a reference of the file and a "
                                                                        "one-sentence note")
        elif typ == "paper":
            if "protocol" in block:
                for p in protocol_problems(block["protocol"]):
                    r.err("review.5", f"{where}.protocol", p)
            if "searches" in block:
                paper_searches = block["searches"]
                if not isinstance(paper_searches, list):
                    r.err("review.5", f"{where}.searches", "a list of searches")
                    paper_searches = []
                for i, s in enumerate(paper_searches):
                    ok = (isinstance(s, dict) and _text(s.get("source")) and _text(s.get("query"))
                          and isinstance(s.get("date"), str) and DATE.match(s["date"]) and _count(s.get("results")))
                    if not ok:
                        r.err("review.5", f"{where}.searches[{i}]", "{source, query, date YYYY-MM-DD, results}: non-empty "
                                                                   "source and query, a non-negative integer of results")
            if "flow" in block:
                for p in flow_problems(block["flow"]):
                    r.err("review.5", f"{where}.flow", p)
            if "flags" in block and not (isinstance(block["flags"], list) and all(f in FLAGS for f in block["flags"])):
                r.err("review.5", f"{where}.flags", f"a list of {', '.join(FLAGS)}")
    _warnings(doc, refs, claims_with_blocks or refs_with_blocks, paper_searches, r)


def _warnings(doc, refs, used, searches, r):
    if not used:
        return

    def read_of(rid):
        b = _dict(_dict(refs.get(rid)).get("ext")).get(NAME)
        return b.get("read") if isinstance(b, dict) else None

    any_read = any(read_of(rid) for rid in refs)
    unsaid = []
    for c in _list(doc.get("claims")):
        if not isinstance(c, dict):
            continue
        cited = [s.get("reference") for s in _list(c.get("support")) if isinstance(s, dict) and s.get("kind") == "cited"
                 and isinstance(s.get("reference"), str) and s["reference"] in refs]
        if not cited:
            continue
        cid = c.get("id")
        reads = [read_of(x) for x in cited]
        if all(x in ("abstract", "secondary") for x in reads):
            r.warn("review.w1", f"claims:{cid}", "rests only on works read in their abstracts or through others' "
                                                 "accounts: a full text could qualify what it states")
        block = _dict(c.get("ext")).get(NAME)
        if any_read and not (isinstance(block, dict) and block.get("extracts")):
            r.warn("review.w2", f"claims:{cid}", "no extract: the passage its cited support rests on is not shown")
        unsaid += [x for x, rd in zip(cited, reads) if rd is None and x not in unsaid]
    for x in unsaid:
        r.warn("review.w4", f"references:{x}", "how this cited work was read is not said (ext.review.read)")
    if not searches:
        r.warn("review.w3", "paper.ext.review.searches", "no searches recorded: the claims were confirmed against works "
                                                         "the authors knew, not searched for; say so in their "
                                                         "limitations")

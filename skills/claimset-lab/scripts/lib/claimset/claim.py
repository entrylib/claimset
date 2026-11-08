"""Claim bundles (spec §2.3): one claim with everything it rests on, for readers that want a single claim.

A bundle holds the claim, the claims it depends on, and the definitions, evidence, limitations, warrants, artefacts and
references they cite, found by following the IDs the claim cites and, in turn, those objects cite. Another claim is
pulled in only through `depends_on` and `assumptions` (of the claim, or of a definition or evidence it rests on); a
relation to another claim of the paper keeps its target's ID without pulling the claim in. The reading view of a bundle is the reading view (render) of it.
"""

import re

from .render import render

#: Lists of a claimset whose objects a bundle may hold, in reading order.
LISTS = ("claims", "definitions", "evidence", "warrants", "limitations", "artefacts", "references")
#: The fields through which an object rests on other claims.
CLAIM_LINKS = ("depends_on", "assumptions")
ID_IN_TEXT = re.compile(r"(?<![\w.])([A-Z]\d+)(?![\d])")


def _ids_in(x, known, skip_keys=()):
    """The known object IDs a value cites, wherever they appear: as a value, in `E1.R1`, in `[[D2:term]]`."""
    found = set()
    if isinstance(x, dict):
        for k, v in x.items():
            if k not in skip_keys:
                found |= _ids_in(v, known, skip_keys)
    elif isinstance(x, list):
        for v in x:
            found |= _ids_in(v, known, skip_keys)
    elif isinstance(x, str):
        found |= {m.group(1) for m in ID_IN_TEXT.finditer(x) if m.group(1) in known}
    return found


def claim_bundle(doc, claim_id):
    """The bundle of one claim: a dict with the paper's header, the claim's ID, and the objects it rests on. Raises
    KeyError if the claimset has no such claim."""
    where = {}
    for lst in LISTS:
        for x in doc.get(lst) or []:
            if isinstance(x, dict) and isinstance(x.get("id"), str):
                where[x["id"]] = (lst, x)
    if where.get(claim_id, ("",))[0] != "claims":
        raise KeyError(f"no claim {claim_id}")
    keep, queue = set(), [claim_id]
    while queue:
        oid = queue.pop()
        if oid in keep or oid not in where:
            continue
        keep.add(oid)
        lst, obj = where[oid]
        cited = {i for i in _ids_in(obj, where, skip_keys=("id", "relations")) if where[i][0] != "claims"}
        cited |= {i for k in CLAIM_LINKS for i in obj.get(k) or [] if isinstance(i, str) and i in where}
        queue += sorted(cited - keep)
    paper = doc.get("paper") or {}
    out = {"bundle_of": claim_id, "schema_version": doc.get("schema_version"),
           "paper": {k: paper[k] for k in ("id", "version", "title", "licence", "status", "date", "status_notice",
                                            "converted_from") if k in paper}}
    if doc.get("extensions"):
        out["extensions"] = doc["extensions"]
    for lst in LISTS:
        items = [x for x in doc.get(lst) or [] if isinstance(x, dict) and x.get("id") in keep]
        if lst == "claims":                              # the claim first, then those it depends on, in file order
            items.sort(key=lambda x: x.get("id") != claim_id)
        if items:
            out[lst] = items
    return out


def render_claim(doc, claim_id):
    """The reading view of one claim's bundle, as a string."""
    b = claim_bundle(doc, claim_id)
    view = dict(b)
    view["paper"] = dict(b["paper"], contributions=[claim_id])
    text = render(view)
    first, _, rest = text.partition("\n")
    head = " ".join(x for x in (f"CLAIM {claim_id} of", b["paper"].get("id"), b["paper"].get("title")) if x)
    return head + "\n" + rest

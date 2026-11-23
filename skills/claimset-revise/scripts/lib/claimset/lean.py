"""A leaner claimset: candidates for text a reader does not need, found mechanically, and the brief for the agent that
reviews them. Nothing here edits a claimset or decides: the candidates are where a reviewing agent should look, and the
guarantor decides what goes.

Usable on its own (standard library only): python3 lean.py claimset.json [--since published.json] [--prompt] [--json]

Candidates, by category:
- repeated: a sentence that nearly repeats one in another object (relation notes, definitions, statements, summaries,
  descriptions, limitations, proof steps, not-claimed entries).
- duplicate_relation: a claim relating twice to the same reference or claim, or relating to a reference it already
  cites as support.
- unused: a definition or reference that nothing in the claimset names.
- added: with --since, what a new version adds to objects the published version already had: a sentence, a relation,
  a limitation attached to a claim. A new version's own new objects are expected; additions to old ones are the ones
  to ask about.
"""
import argparse
import json
import re
import sys
from pathlib import Path

LINK = re.compile(r"\[\[([A-Z]+\d+(?:\.[A-Za-z0-9]+)*):([^\]]*)\]\]")
WORD = re.compile(r"[a-z0-9]+")
MIN_WORDS = 6          # shorter sentences ("It is 0.5.") repeat by nature
NEAR = 0.6             # Jaccard similarity of word triples above which two sentences count as near repeats


def _texts(doc):
    """(where, text) for every free-text field a reader reads."""
    out = []
    paper = doc.get("paper") or {}
    if isinstance(paper.get("summary"), str):
        out.append(("paper.summary", paper["summary"]))
    for c in doc.get("claims") or []:
        cid = c.get("id")
        for f in ("statement", "summary"):
            if isinstance(c.get(f), str):
                out.append((f"{cid}.{f}", c[f]))
        for i, r in enumerate(c.get("relations") or []):
            if isinstance(r, dict) and isinstance(r.get("note"), str):
                out.append((f"{cid}.relations[{i}]", r["note"]))
    for d in doc.get("definitions") or []:
        if isinstance(d.get("definition"), str):
            out.append((f"{d.get('id')}.definition", d["definition"]))
    for e in doc.get("evidence") or []:
        if isinstance(e.get("description"), str):
            out.append((f"{e.get('id')}.description", e["description"]))
        for s in e.get("steps") or []:
            if isinstance(s, dict) and isinstance(s.get("statement"), str):
                out.append((f"{e.get('id')}.{s.get('id')}", s["statement"]))
    for x in doc.get("limitations") or []:
        if isinstance(x.get("statement"), str):
            out.append((f"{x.get('id')}.statement", x["statement"]))
    for i, x in enumerate(((paper.get("exploration") or {}).get("not_claimed")) or []):
        if isinstance(x, dict) and isinstance(x.get("statement"), str):
            out.append((f"paper.exploration.not_claimed[{i}]", x["statement"]))
    return out


def sentences(text):
    """The sentences of a text, with displayed formulas kept whole."""
    text = re.sub(r"\$\$.*?\$\$", lambda m: m.group(0).replace(".", "․"), text, flags=re.S)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\[$])", text.strip())
    return [p.replace("․", ".").strip() for p in parts if p.strip()]


def _words(sentence):
    return WORD.findall(LINK.sub(lambda m: m.group(2), sentence).lower())


def _triples(words):
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


def _object(where):
    return re.split(r"[.\[]", where, maxsplit=1)[0]


def repeated(doc):
    """Pairs of sentences in different objects that nearly repeat each other."""
    items = []
    for where, text in _texts(doc):
        for s in sentences(text):
            w = _words(s)
            if len(w) >= MIN_WORDS:
                items.append((where, s, _triples(w)))
    index = {}
    for k, (_, _, t) in enumerate(items):
        for tri in t:
            index.setdefault(tri, []).append(k)
    seen, out = set(), []
    for k, (where, s, t) in enumerate(items):
        near = {j for tri in t for j in index[tri] if j > k}
        for j in sorted(near):
            w2, s2, t2 = items[j]
            if _object(where) == _object(w2) or (k, j) in seen:
                continue
            sim = len(t & t2) / len(t | t2)
            if sim >= NEAR:
                seen.add((k, j))
                out.append({"category": "repeated", "where": where, "text": s,
                            "detail": f"nearly repeats {w2}: \"{s2}\" (similarity {sim:.2f})"})
    return out


def duplicate_relations(doc):
    out = []
    for c in doc.get("claims") or []:
        cited = {s.get("reference") for s in c.get("support") or [] if isinstance(s, dict) and s.get("reference")}
        seen = {}
        for i, r in enumerate(c.get("relations") or []):
            if not isinstance(r, dict):
                continue
            key = r.get("reference") or r.get("target")
            where = f"{c.get('id')}.relations[{i}]"
            if key in seen:
                out.append({"category": "duplicate_relation", "where": where, "text": r.get("note") or "",
                            "detail": f"relates to {key} again, as {seen[key]} already does"})
            else:
                seen[key] = where
            if r.get("reference") in cited:
                out.append({"category": "duplicate_relation", "where": where, "text": r.get("note") or "",
                            "detail": f"{r['reference']} is already cited as support of {c.get('id')}"})
    return out


def unused(doc):
    """Definitions and references that nothing else in the claimset names."""
    out = []
    for key, prefix in (("definitions", "D"), ("references", "B")):
        for x in doc.get(key) or []:
            xid = x.get("id")
            if not isinstance(xid, str):
                continue
            rest = dict(doc)
            rest[key] = [y for y in doc.get(key) or [] if y is not x]
            if not re.search(rf"(?<![A-Za-z0-9]){re.escape(xid)}(?![0-9])", json.dumps(rest, ensure_ascii=False)):
                label = x.get("term") or x.get("target") or ""
                out.append({"category": "unused", "where": xid, "text": label,
                            "detail": "nothing in the claimset names it"})
    return out


def added(doc, published):
    """What a new version adds to the objects its published version already had."""
    old_text = {}                 # each object's words, as one string: a sentence kept but split or set differently
    for where, text in _texts(published):    # (a formula moved to its own line) is still found in it
        old_text[_object(where)] = old_text.get(_object(where), " ") + " ".join(_words(text)) + " "
    out = []
    old_objects = {x.get("id") for k in ("claims", "definitions", "evidence", "limitations")
                   for x in published.get(k) or []}
    for where, text in _texts(doc):
        obj = _object(where)
        if obj not in old_objects:
            continue
        ss = sentences(text)
        new = [s for s in ss if _words(s) and f" {' '.join(_words(s))} " not in old_text.get(obj, " ")]
        if ss and len(new) * 2 > len(ss):     # rewritten as a whole: one candidate, to compare with the published
            out.append({"category": "added", "where": where, "text": new[0] + (" …" if len(new) > 1 else ""),
                        "detail": f"rewritten: {len(new)} of its {len(ss)} sentences are new; compare it with the "
                                  f"published version of {obj}"})
            continue
        for s in new:
            out.append({"category": "added", "where": where, "text": s,
                        "detail": f"a sentence the published version of {obj} did not have"})
    old_claims = {c.get("id"): c for c in published.get("claims") or []}
    for c in doc.get("claims") or []:
        before = old_claims.get(c.get("id"))
        if not before:
            continue
        had = {json.dumps(r, sort_keys=True) for r in before.get("relations") or []}
        for i, r in enumerate(c.get("relations") or []):
            if json.dumps(r, sort_keys=True) not in had and (r.get("reference") or r.get("target")) not in {
                    (x.get("reference") or x.get("target")) for x in before.get("relations") or []}:
                out.append({"category": "added", "where": f"{c.get('id')}.relations[{i}]",
                            "text": r.get("note") or "", "detail": f"a relation the published {c.get('id')} did not have"})
        new_lims = [x for x in c.get("limitations") or [] if x not in (before.get("limitations") or [])]
        if new_lims:
            out.append({"category": "added", "where": f"{c.get('id')}.limitations", "text": ", ".join(new_lims),
                        "detail": f"limitations attached to {c.get('id')} that its published version did not have"})
    return out


def candidates(doc, published=None):
    out = repeated(doc) + duplicate_relations(doc) + unused(doc)
    if published is not None:
        new = added(doc, published)
        whole = {c["where"] for c in new if c["detail"].startswith("a relation ")}
        out += [c for c in new if c["where"] not in whole or c["detail"].startswith("a relation ")]
    return out


BRIEF = """\
You review a claimset before it is submitted, as a reader who did not write it. Your task is to make it leaner: find
text a reader does not need. Do not edit the file, and do not judge whether the claims are true.

Read its reading view (`claimset render {file}`) one object at a time: claims, relation notes, definitions, evidence
descriptions and proof steps, limitations, not-claimed entries. Ask of each sentence, and of each relation, definition
and limitation: if it were gone, would a reader conclude anything different, lose how a claim was established, or lose
where a claim stops holding? If not, flag it, in one of these categories:
- repeated: says what another place says. Name that place.
- aside: true, but no claim, definition or limitation needs it: background, commentary, a contrast nobody asked about.
- unrequested: added to what a published version already had, and not part of what the new version is said to change
  (the correction or revision reason, the record's decisions). Ask whether it was requested.
- retells: repeats values of a table instead of stating the conclusion the paper draws from them.
- unused: a definition, reference or relation that nothing needs.
Keep what a conclusion turns on: numbers a claim depends on, conditions, a limitation that bounds a claim, a definition
a claim uses. A recorded statement of a formal or planned claim is the wording the guarantor approved: flag a sentence
of it if it qualifies, but never propose new wording for it.

Start from the mechanical candidates below; they show where to look, and are neither complete nor all redundant.

Answer with a list, one item per flag: where (object ID and field), the sentence or item, its category, why (one
sentence), and a proposed action (delete, merge into <where>, shorten, or keep). End with the number of flags. The
guarantor decides; nothing is deleted without their agreement.

Mechanical candidates ({n}):
{candidates}
"""


def describe(found):
    if not found:
        return "  none"
    return "\n".join(f"  - [{c['category']}] {c['where']}: {c['text'][:200]}" + (f" ({c['detail']})" if c["detail"]
                                                                                 else "") for c in found)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="claimset lean", description=__doc__.split("\n\n")[0])
    add_arguments(ap)
    return run(ap.parse_args(argv))


def add_arguments(ap):
    ap.add_argument("file", help="the claimset JSON file to review")
    ap.add_argument("--since", help="the published version it was made from (a claimset JSON file): also list what "
                                    "the new version adds to the objects that version already had")
    ap.add_argument("--prompt", action="store_true",
                    help="print the brief for the reviewing agent, with the candidates, instead of the list")
    ap.add_argument("--json", action="store_true", help="the candidates as JSON")


def run(args):
    try:
        doc = json.loads(Path(args.file).read_text(encoding="utf-8"))
        published = json.loads(Path(args.since).read_text(encoding="utf-8")) if args.since else None
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    found = candidates(doc, published)
    if args.json:
        print(json.dumps(found, ensure_ascii=False, indent=1))
    elif args.prompt:
        print(BRIEF.format(file=args.file, n=len(found), candidates=describe(found)))
    else:
        print(f"{len(found)} candidates for a leaner claimset (where a reviewing agent should look; nothing is "
              f"redundant until the guarantor agrees):")
        print(describe(found))
        print("Next: give a different agent than the one that wrote the claimset the brief from "
              f"`claimset lean {args.file}{' --since ' + args.since if args.since else ''} --prompt`; show its flags "
              "to the guarantor; delete only what they accept, then validate again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Drafts (lab record §3.6): what a study will test, agreed with its supervisor before it is recorded.

A draft is the file `drafts/NAME.json` in the study folder, beside `lab/`, ignored by the study branch: not part of
the record. It holds question, term, hypothesis, assumption and plan events (and the extension declarations they
need) in the record's forms, each with the ID it would have if recorded now. Every drafted event is checked against
the record and the draft's earlier events by the rules that apply to it, as if recorded. `record` writes the agreed
draft to the record, then the supervisor's approval of each plan that requires one, and removes the file.

    names(lab) -> [name]
    load(lab, name) -> [event]                       the drafted events, in order
    simulate(lab, events, by) -> (state, problems, events)
                                                     the record's state with the draft applied, the problems found
                                                     ([(id, LabError)]) and the events with their IDs as the record
                                                     would give them now
    add(lab, name, etype, body, by, supersedes) -> event
    drop(lab, name, eid) -> [problems]
    record(lab, name, by, approval, code=(commit, dirty)) -> [(drafted id, recorded id)], [approval IDs]
    render(lab, name, by) -> text                    the draft for the supervisor
"""

import json
import re
from pathlib import Path

from .core import LabError, NAME_RE, REVISION_RE, TERM_MARK_RE, plan_warnings, utc_now

#: The event types a draft holds (§3.6): what is agreed before it is recorded. Runs, results, sources, notes,
#: decisions and statuses are recorded as they happen.
DRAFTABLE = ("question", "term", "hypothesis", "assumption", "plan", "extension")

MARK_RE = re.compile(r"\[\[[^:\]]+:([^\]]+)\]\]")


def folder(lab):
    return Path(lab.root).resolve().parent / "drafts"


def _path(lab, name):
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise LabError("schema", f"draft name '{name}': lower-case letters, digits and hyphens, starting with a letter")
    return folder(lab) / f"{name}.json"


def names(lab):
    d = folder(lab)
    return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []


def load(lab, name, must_exist=True):
    p = _path(lab, name)
    if not p.exists():
        if must_exist:
            known = names(lab)
            raise LabError("draft", f"no draft '{name}'" + (f"; the study's drafts: {', '.join(known)}" if known else
                                                              "; write one with --draft NAME on question, term, "
                                                              "hypothesis, assume or plan"))
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LabError("draft", f"draft '{name}' cannot be read: {exc}")
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        raise LabError("draft", f"draft '{name}' has no list of events")
    return events


def _ignore(lab):
    """The study branch ignores drafts (§3.6): `/drafts/` in the study folder's .gitignore."""
    gi = Path(lab.root).resolve().parent / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    if "/drafts/" not in lines:
        gi.write_text("\n".join(lines + ["/drafts/"]) + "\n", encoding="utf-8")


def save(lab, name, events):
    p = _path(lab, name)
    if not events:
        if p.exists():
            p.unlink()
        return
    _ignore(lab)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"draft": name, "events": events}, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")


def discard(lab, name):
    p = _path(lab, name)
    if not p.exists():
        load(lab, name)                 # the message naming the drafts there are
    p.unlink()


# -- IDs

def remap(value, mapping):
    """`value` with every reference to a key of `mapping` replaced: a string that is such an ID (or a revision label
    of one), a dict key that is one (a plan's per-hypothesis rules), and term marks in text."""
    if not mapping:
        return value
    if isinstance(value, dict):
        return {(mapping.get(k, k) if isinstance(k, str) else k): remap(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [remap(v, mapping) for v in value]
    if isinstance(value, str):
        if value in mapping:
            return mapping[value]
        m = REVISION_RE.match(value)
        if m and m.group(1) in mapping:
            return f"{mapping[m.group(1)]}.R{m.group(2)}"
        if "[[" in value:
            return TERM_MARK_RE.sub(lambda x: x.group(0).replace(x.group(1), mapping.get(x.group(1), x.group(1)), 1),
                                    value)
    return value


def _event(st, e, seq):
    return {"seq": seq, "id": e["id"], "type": e["type"], "at": e.get("at") or utc_now(), "by": e.get("by"),
            "prev": None, "content_hash": None, "supersedes": e.get("supersedes"), "origin": None,
            "body": e.get("body")}


def simulate(lab, events, by=None):
    """The record's state with the drafted events applied in order, each checked as if it were being recorded.
    Returns (state, problems, events): problems is [(id, LabError)]; events carry the IDs the record would give
    them now (they shift when the record has gained events of the same kind since they were drafted)."""
    st = lab.view(by)
    out, problems, mapping = [], [], {}
    for e in events:
        if not isinstance(e, dict) or e.get("type") not in DRAFTABLE:
            problems.append((str(e.get("id") if isinstance(e, dict) else e),
                             LabError("draft", "a draft holds only " + ", ".join(DRAFTABLE) + " events")))
            continue
        new = st.next_id(e["type"])
        if e.get("id") and e["id"] != new:
            mapping[e["id"]] = new
        e = dict(e, id=new, body=remap(e.get("body"), mapping), supersedes=remap(e.get("supersedes"), mapping))
        try:
            st.check(e["type"], e["id"], e.get("by"), e["body"], e.get("supersedes"))
        except LabError as exc:
            problems.append((e["id"], exc))
        st.apply(_event(st, e, len(st.events) + 1))
        out.append(e)
    return st, problems, out


def add(lab, name, etype, body, by, supersedes=None):
    """Add an event to the draft, or replace a drafted one (`supersedes` naming it). Raises LabError if the event
    breaks a rule. Returns (event, warnings): the warnings name later drafted events the change broke."""
    if etype not in DRAFTABLE:
        raise LabError("draft", f"{etype} events are recorded as they happen, never drafted (lab record §3.6)")
    events = load(lab, name, must_exist=False)
    _, earlier, events = simulate(lab, events, by)
    drafted = {e["id"]: i for i, e in enumerate(events)}
    if supersedes is not None and supersedes in drafted:
        i = drafted[supersedes]
        if events[i]["type"] != etype:
            raise LabError("L11", f"{supersedes} is a drafted {events[i]['type']}; replace it with the same command")
        events[i] = dict(events[i], body=body, by=by, at=utc_now())
        _, problems, events = simulate(lab, events, by)
        mine = [exc for eid, exc in problems if eid == supersedes]
        if mine:
            raise mine[0]
        event = events[i]
    else:
        st, _, events = simulate(lab, events, by)
        eid = st.next_id(etype)
        st.check(etype, eid, by, body, supersedes)
        event = {"id": eid, "type": etype, "by": by, "at": utc_now(), "supersedes": supersedes, "body": body}
        events.append(event)
        _, problems, events = simulate(lab, events, by)
    save(lab, name, events)
    before = {eid for eid, _ in earlier}
    return event, [f"{eid}: [{exc.rule}] {exc.message}" for eid, exc in problems
                   if eid != event["id"] and eid not in before]


def drop(lab, name, eid):
    events = load(lab, name)
    _, _, events = simulate(lab, events)
    if eid not in {e["id"] for e in events}:
        raise LabError("draft", f"draft '{name}' has no event {eid}")
    events = [e for e in events if e["id"] != eid]
    _, problems, events = simulate(lab, events)
    save(lab, name, events)
    return [f"{x}: [{exc.rule}] {exc.message}" for x, exc in problems]


def check(lab, name, by=None):
    """[(id, LabError)] for the whole draft against the record as it now is, and the plans' warnings."""
    events = load(lab, name)
    st, problems, events = simulate(lab, events, by)
    return problems, warnings(lab, events, by)


def warnings(lab, events, by=None):
    """The plans' warnings (lab record §5.7.6), each against the draft as far as that plan."""
    out = []
    for i, e in enumerate(events):
        if e["type"] == "plan":
            st, _, _ = simulate(lab, events[:i], by)
            out += [f"{e['id']}: {w}" for w in plan_warnings(st, e["body"])]
    return out


def needs_approval(events):
    return [e for e in events if e["type"] == "plan" and (e.get("body") or {}).get("requires_approval")]


def record(lab, name, by, approval=None, code=(None, None)):
    """Write the agreed draft to the record, then the approvals of its plans that require one. Returns
    ([(drafted id, recorded id)], [approval IDs])."""
    events = load(lab, name)
    drafted_as = [e.get("id") if isinstance(e, dict) else None for e in events]
    st, problems, events = simulate(lab, events, by)
    if problems:
        listed = "; ".join(f"{eid}: [{exc.rule}] {exc.message}" for eid, exc in problems)
        raise LabError("draft", f"draft '{name}' does not check against the record, so nothing of it is recorded: "
                                f"{listed}. Correct it with --draft {name} --supersedes ID, then show it again")
    plans = needs_approval(events)
    actor = st.latest(by) if by and st.get(by) is not None else None
    human = actor is not None and (actor.get("body") or {}).get("kind") == "human"
    approval = {k: v for k, v in (approval or {}).items() if v is not None}
    if plans and not human and not (approval.get("on_behalf_of") and approval.get("words")):
        raise LabError("L22", f"{', '.join(e['id'] for e in plans)}: the supervisor's approval is required; record the draft "
                              f"once they have agreed to it, with --on-behalf-of (their actor ID), --words (their "
                              f"reply, verbatim) and --given-at (when they gave it)",
                       ask=f"Do you approve the draft {name} as shown (claimset lab draft show {name})?")
    mapping, written = {}, []
    for e, old in zip(events, drafted_as):
        body = remap(e["body"], mapping)
        if e["type"] == "plan" and code[0] is not None:
            body = dict(body, code_version=code[0], dirty=code[1])
        new = lab.append(e["type"], body, by=e.get("by") or by, supersedes=remap(e.get("supersedes"), mapping))
        mapping[e["id"]] = new["id"]
        written.append((old or e["id"], new["id"]))
    approvals = []
    for e in plans:
        pid = mapping[e["id"]]
        body = {"target": pid,
                "comment": approval.get("comment") or f"Approves {pid} as drafted in {name} ({e['id']}) and shown "
                                                      f"before it was recorded (lab record §3.6).",
                "on_behalf_of": approval.get("on_behalf_of"), "words": approval.get("words"),
                "given_at": approval.get("given_at"), "channel": approval.get("channel")}
        approvals.append(lab.append("approval", {k: v for k, v in body.items() if v is not None}, by=by)["id"])
    save(lab, name, [])
    return written, approvals


# -- showing

def _plain(text):
    return MARK_RE.sub(r"\1", text) if isinstance(text, str) else text


def _rule(d):
    if not isinstance(d, dict):
        return []
    out = []
    params = d.get("parameters") or {}
    out.append(f"Framework: {d.get('framework')}" + (
        "; " + ", ".join(f"{k} = {v}" for k, v in params.items()) if params else ""))
    for name, q in (d.get("quantities") or {}).items():
        out.append(f"Quantity {name}: {json.dumps(q, ensure_ascii=False) if isinstance(q, dict) else q}")
    for key, rules in ([(None, d)] + [(h, r) for h, r in (d.get("rules") or {}).items() if isinstance(r, dict)]):
        prefix = f"{key}: " if key else ""
        if rules.get("supported") is not None:
            out.append(f"{prefix}supported if {_plain(rules['supported'])}")
        if rules.get("not_supported") is not None:
            out.append(f"{prefix}not supported if {_plain(rules['not_supported'])}")
    out.append("Otherwise: inconclusive.")
    return out


def render(lab, name, by=None):
    events = load(lab, name)
    st, problems, events = simulate(lab, events, by)
    lines = [f"Draft '{name}' of study {st.study or '(unnamed)'}: {len(events)} events, not recorded. The IDs are "
             f"those the record would give them now; recording may change them.", ""]
    agent = []
    for e in events:
        b, t, i = e.get("body") or {}, e["type"], e["id"]
        if t == "question":
            lines.append(f"{i}  Question: {b.get('text')}")
        elif t == "term":
            lines.append(f"{i}  Term ({b.get('kind')}) {b.get('term')}: {b.get('definition')}")
        elif t == "hypothesis":
            origin = "a priori" if b.get("origin") == "a_priori" else b.get("origin")
            if b.get("origin") == "from_exploration":
                origin = f"from exploration, prompted by {', '.join(b.get('prompted_by') or [])}"
            elif b.get("independence"):
                origin = f"a priori: {b['independence']}"
            lines.append(f"{i}  Hypothesis ({origin}; question {b.get('question')}"
                         + (f"; corrects {e['supersedes']}" if e.get("supersedes") else "") + f"): "
                         + _plain(b.get("statement")))
        elif t == "assumption":
            lines.append(f"{i}  Assumption ({b.get('category')}, {b.get('check')}): {_plain(b.get('statement'))}")
        elif t == "extension":
            lines.append(f"{i}  Extension declared: {b.get('name')} {b.get('version')}")
        elif t == "plan":
            what = f"tests {', '.join(b.get('hypotheses') or [])}" if b.get("hypotheses") else \
                f"estimates for {b.get('question')}"
            lines.append(f"{i}  Plan ({b.get('kind')}), {what}"
                         + (f"; corrects {e['supersedes']}" if e.get("supersedes") else ""))
            for label, key in (("Design", "design"), ("Analysis", "analysis"), ("New data", "new_data")):
                if b.get(key):
                    lines.append(f"    {label}: {_plain(b[key])}")
            for role, ids in (b.get("setup") or {}).items():
                lines.append(f"    Setup, {role}: {', '.join(ids)}")
            for x in b.get("exclusions") or []:
                lines.append(f"    Exclusion {x.get('name')}: {x.get('rule')}")
            lines += [f"    {x}" for x in _rule(b.get("decision"))] if b.get("decision") else []
            if b.get("criterion"):
                lines.append(f"    Criterion: {b['criterion']}")
            for k, q in (b.get("estimands") or {}).items():
                lines.append(f"    Estimand {k}: {json.dumps(q, ensure_ascii=False)}")
            for d in b.get("diagnostics") or []:
                lines.append(f"    Each run reports: {d}")
            if b.get("runs") and b["runs"] != 1:
                lines.append(f"    Deciding runs: {b['runs']}")
            for c in b.get("choices") or []:
                lines.append(f"    Choice, {c.get('what')}: {c.get('choice')} (from {c.get('source')}"
                             + (f", {c['ref']}" if c.get("ref") else "") + ")")
                if c.get("source") == "agent":
                    agent.append(f"{i}: {c.get('what')}")
            lines.append(f"    Approval: {'required' if b.get('requires_approval') else 'not required'}")
        lines.append("")
    if agent:
        lines.append("Chosen by the agent alone, to agree: " + "; ".join(agent))
    warns = warnings(lab, events, by)
    if warns:
        lines.append("Warnings: " + "; ".join(warns))
    if problems:
        lines.append("Problems (the draft cannot be recorded until they are fixed): "
                     + "; ".join(f"{x}: [{exc.rule}] {exc.message}" for x, exc in problems))
    return "\n".join(lines).rstrip() + "\n"

"""The reading view of a lab record, and the trail of one hypothesis (lab record §11).

Both are made from the log alone, the main log's events in order (merged events included), so that anyone who has
a published record can make them: no run folder is read. A run's results are given by number and file, never by
value: the results file of a record begun under v0.23 or later (`runs/RN4/results.csv`, `results.rows`), or, for
earlier records, the run's result events (counted, with their first and last IDs) and the file they were read from.
"""

import re

from .core import ID_RE, State, header_hash, is_withheld
from .export import CREDIT_ORDER, credit_role
from .summary import _text

#: Event types whose body refers to other events by these fields (what a trail follows, §11).
_REFS = ("target", "plan", "run", "refers_to", "prompted_by", "affects", "evidence", "hypotheses", "question",
         "revised_to", "plan_version", "on_behalf_of")


def _ids(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    return []


def _state(events):
    st = State()
    for e in events:
        st.apply(e)
    return st


def _who(st, actor):
    return actor or "-"


def _short(text, n=160):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def results_of_runs(st, events):
    """{run ID: (count, first ID, last ID, file)} for every run with results (§5.10)."""
    out = {}
    for e in events:
        if not isinstance(e, dict) or is_withheld(e):
            continue
        b = e.get("body") if isinstance(e.get("body"), dict) else {}
        if e.get("type") == "run" and isinstance(b.get("results"), dict):
            n = b["results"].get("rows") or 0
            out[e["id"]] = (n, f"{e['id']}.1", f"{e['id']}.{n}", f"runs/{e['id']}/{b['results'].get('path')}")
        elif e.get("type") == "result" and isinstance(b.get("run"), str):
            n, first, _, path = out.get(b["run"], (0, e["id"], None, f"runs/{b['run']}/{b.get('source')}"))
            out[b["run"]] = (n + 1, first, e["id"], path)
    return out


def _results_phrase(res):
    n, first, last, path = res
    ids = first if n == 1 else f"{first} to {last}"
    return f"{n:,} result{'' if n == 1 else 's'} in {path} ({ids})"


def describe(st, e, results):
    """One line for an event: what it records, in a few words (§11, Timeline)."""
    if is_withheld(e):
        b = e.get("body") if isinstance(e.get("body"), dict) else {}
        return f"withheld ({b.get('reason', 'no reason')})"
    b = e["body"]
    t = e["type"]
    if t == "init":
        cont = b.get("continues")
        extra = f"; continues {cont.get('record')}" if isinstance(cont, dict) else ""
        return f"began \"{_short(b.get('working_title'))}\" under lab record v{b.get('lab_spec_version')}{extra}"
    if t == "run":
        cmd = _short(" ".join(b.get("command") or []), 100)
        bits = [b.get("label"), b.get("exit_status")]
        if b.get("plan"):
            bits.append(f"under {b.get('plan_version') or b['plan']}")
        if b.get("code_version"):
            bits.append(f"commit {str(b['code_version'])[:7]}" + (" with uncommitted changes" if b.get("dirty") else ""))
        line = f"[{', '.join(str(x) for x in bits if x)}] {cmd}"
        if e["id"] in results:
            line += f"; {_results_phrase(results[e['id']])}"
        return line
    if t == "actor":
        kind = b.get("kind")
        ident = f", ORCID {b['orcid']}" if b.get("orcid") else (f", GitHub {b['github']}" if b.get("github") else "")
        return f"registers {b.get('name')} ({kind}{ident})"
    if t == "hypothesis":
        origin = b.get("origin")
        return f"{_short(b.get('statement'))}" + (f" [{origin}]" if origin else "")
    if t == "plan":
        hyps = ", ".join(_ids(b.get("hypotheses")))
        what = f" for {hyps}" if hyps else (f" for {b.get('question')}" if b.get("question") else "")
        approval = ", requires approval" if b.get("requires_approval") else ""
        return f"[{b.get('kind')}{approval}]{what}: {_short(b.get('design') or b.get('analysis'), 120)}"
    if t == "merge":
        logs = list(b.get("agents") or []) + list(b.get("contributors") or [])
        return f"merges {b.get('events_merged')} events from {', '.join(logs)}"
    if t == "status":
        ev = ", ".join(_ids(b.get("evidence")))
        return (f"{b.get('target')} -> {b.get('to')}" + (f" (plan {b['plan']})" if b.get("plan") else "")
                + (f", evidence {ev}" if ev else "") + f": {_short(b.get('rationale'), 120)}")
    if t == "decision":
        return _short(b.get("text"))
    return _short(_text(e))


def _timeline_line(st, e, results):
    at = str(e.get("at") or "")[:16].replace("T", " ")
    return f"{e.get('seq', ''):>6}  {at}  {e.get('id')}  {e.get('type')}  by {_who(st, e.get('by'))}: " \
           f"{describe(st, e, results)}"


def credit(events):
    """{actor ID: [CRediT roles]} drawn from the events each actor wrote, or that were written on a person's behalf
    (lab record §9, Credit)."""
    st = _state(events)
    got = {}
    for e in events:
        role = credit_role(e)
        if role is None:
            continue
        b = e.get("body") if isinstance(e.get("body"), dict) else {}
        who = st.root(b["on_behalf_of"]) if b.get("on_behalf_of") else (st.root(e.get("by")) if e.get("by") else None)
        if who:
            got.setdefault(who, set()).add(role)
    return {a: [r for r in CREDIT_ORDER if r in rs] for a, rs in got.items()}


def _log_of(e):
    o = e.get("origin")
    if isinstance(o, dict) and isinstance(o.get("log"), str):
        return o["log"].split("/", 1)[0][:-1] + " log " + o["log"].split("/")[-1][:-len(".jsonl")]
    m = ID_RE.match(str(e.get("id")))
    return "main log" if not (m and m.group(1)) else f"log of {m.group(1)}"


def render(events, title=None):
    """The reading view of a record (§11): `events`, the main log's events in order. Returns text."""
    events = [e for e in events if isinstance(e, dict) and isinstance(e.get("id"), str)]
    st = _state(events)
    results = results_of_runs(st, events)
    init = next((e for e in events if e.get("type") == "init"), None)
    ib = init["body"] if init and not is_withheld(init) else {}
    head = events[-1] if events else None
    runs = [e for e in events if e.get("type") == "run"]
    n_results = sum(r[0] for r in results.values())
    shown = [e for e in events if e.get("type") != "result"]
    out = [f"LAB RECORD: {title or ib.get('working_title') or '(untitled)'}"]
    meta = []
    if ib.get("study"):
        meta.append(f"Study: {ib['study']}")
    if ib.get("lab_spec_version"):
        meta.append(f"Lab record specification v{ib['lab_spec_version']}")
    if ib.get("started_at"):
        meta.append(f"Begun {str(ib['started_at'])[:10]}")
    if ib.get("repository"):
        meta.append(f"Repository: {ib['repository']}")
    out.append(" · ".join(meta))
    out.append(f"Events: {len(shown):,}; runs: {len(runs):,}; results: {n_results:,} (kept in files, never listed "
               f"here)" + (f"; head: seq {head.get('seq')}, {header_hash(head)}" if head else ""))
    cont = ib.get("continues")
    if isinstance(cont, dict):
        out.append(f"Continues: {cont.get('record')} (its last event {cont.get('head')})")
    out.append("This view is made from the log; the log is the record (lab record §11).")

    # Who
    out += ["", "WHO"]
    roles = credit(events)
    for a in (e for e in events if e.get("type") == "actor" and st.root(e["id"]) == e["id"]):
        cur = st.latest(a["id"])
        if is_withheld(cur):
            out.append(f"- {a['id']}: withheld")
            continue
        b = cur["body"]
        bits = [b.get("kind")]
        if b.get("orcid"):
            bits.append(f"ORCID {b['orcid']}")
        if b.get("github"):
            bits.append(f"GitHub {b['github']}")
        for m in b.get("models") or []:
            bits.append(" ".join(str(m.get(k)) for k in ("provider", "name", "version") if m.get(k)))
        if isinstance(b.get("system"), dict) and b["system"].get("name"):
            bits.append(f"in {b['system']['name']}")
        if b.get("label"):
            bits.append(b["label"])
        line = f"- {a['id']} {b.get('name')} ({'; '.join(str(x) for x in bits if x)}), {_log_of(a)}"
        if roles.get(a["id"]):
            line += f"; credit: {', '.join(roles[a['id']])}"
        out.append(line)

    # Questions and hypotheses
    out += ["", "QUESTIONS AND HYPOTHESES"]
    hyps = [e for e in events if e.get("type") == "hypothesis" and st.root(e["id"]) == e["id"]]
    for q in (e for e in events if e.get("type") == "question" and st.root(e["id"]) == e["id"]):
        cur = st.latest(q["id"])
        out.append(f"{q['id']} {describe(st, cur, results)}")
        for h in hyps:
            hb = st.latest(h["id"])
            if is_withheld(hb) or st.root(str(hb["body"].get("question"))) != q["id"]:
                continue
            out.append(f"  {h['id']} [{_status(st, events, h['id'])}] {_short(hb['body'].get('statement'), 300)}")
            out += ["    " + line for line in trail_lines(events, h["id"], st=st, results=results)]
    loose = [h for h in hyps if is_withheld(st.latest(h["id"])) or not st.get(str(st.latest(h["id"])["body"].get(
        "question")))]
    for h in loose:
        out.append(f"  {h['id']} [{_status(st, events, h['id'])}]")

    # Timeline
    out += ["", "TIMELINE (every event but results, in log order: seq, time, ID, type, writer)"]
    out += [_timeline_line(st, e, results) for e in shown]
    return "\n".join(out) + "\n"


def _status(st, events, hid):
    root = st.root(hid)
    last = None
    for e in events:
        if e.get("type") == "status" and not is_withheld(e) and isinstance(e["body"].get("target"), str) \
                and st.root(e["body"]["target"]) == root and st.latest(e["id"])["id"] == e["id"]:
            last = e["body"].get("to")
    return last or "open"


def trail_ids(events, hid, st=None):
    """The IDs of the events the trail of hypothesis `hid` holds (§11), in log order."""
    st = st or _state(events)
    if st.get(hid) is None:
        raise KeyError(hid)
    root = st.root(hid)
    keep = set(st.chain(root))
    hyp_versions = set(keep)
    latest = st.latest(root)
    hb = latest["body"] if not is_withheld(latest) else {}
    for f in ("question",):
        keep |= {st.root(x) for x in _ids(hb.get(f)) if st.get(x)}
    keep |= {x for x in _ids(hb.get("prompted_by")) if st.get(x)}
    about = hb.get("about") if isinstance(hb.get("about"), dict) else {}
    for v in about.values():
        keep |= {st.root(x) for x in _ids(v) if st.get(x)}
    keep |= {st.root(m) for m in re.findall(r"\[\[([^:\]]+):", str(hb.get("statement") or "")) if st.get(m)}
    keep |= {st.root(x) for x in _ids(hb.get("assumptions")) if st.get(x)}
    plans = set()
    for e in events:
        if e.get("type") == "plan" and not is_withheld(e) and any(
                st.get(x) and st.root(x) == root for x in _ids(e["body"].get("hypotheses"))):
            plans.add(st.root(e["id"]))
    for p in plans:
        keep |= set(st.chain(p))
    runs = set()
    for e in events:
        if is_withheld(e) or not isinstance(e.get("body"), dict):
            continue
        b = e["body"]
        t = e.get("type")
        if t == "run" and isinstance(b.get("plan"), str) and st.get(b["plan"]) and st.root(b["plan"]) in plans:
            runs.add(e["id"])
        if t == "status" and isinstance(b.get("target"), str) and st.get(b["target"]) \
                and st.root(b["target"]) == root:
            keep.add(e["id"])
            for x in _ids(b.get("evidence")):
                ev = st.get(x)
                if ev is None:
                    continue
                if ev.get("type") == "run":
                    runs.add(ev["id"])
                elif ev.get("type") == "result" and isinstance(ev["body"].get("run"), str):
                    runs.add(ev["body"]["run"])
                elif ev.get("type") == "hypothesis":
                    keep.add(st.root(ev["id"]))          # a premise (§5.5)
    keep |= runs
    return _with_links(events, st, keep, plans, runs, hyp_versions)


def _with_links(events, st, keep, plans, runs, linked):
    """`keep` with the runs of its results and what refers to any of it: approvals, deviations, checks, decisions and
    notes (§11). Returns the IDs in log order, results left out (they are given by number and file)."""
    keep = set(keep)
    for x in list(keep):
        ev = st.get(x)
        if ev is not None and ev.get("type") == "result" and isinstance(ev["body"].get("run"), str):
            keep.add(ev["body"]["run"])
    changed = True
    linked = set(keep) | plans | runs | set(linked)
    while changed:
        changed = False
        for e in events:
            if e["id"] in keep or e.get("type") in ("result", "merge", "actor", "init"):
                continue
            b = e.get("body") if isinstance(e.get("body"), dict) else {}
            refs = set()
            for f in _REFS:
                refs |= set(_ids(b.get(f)))
            refs = {st.root(r) if st.get(r) else r for r in refs}
            res_runs = {st.get(r)["body"].get("run") for r in refs if st.get(r) and st.get(r).get("type") == "result"}
            if e.get("type") in ("approval", "deviation", "check", "decision", "note") and (
                    refs & {st.root(x) for x in linked} or res_runs & runs):
                keep.add(e["id"])
                linked.add(e["id"])
                changed = True
    order = {e["id"]: i for i, e in enumerate(events)}
    out = []
    for x in keep:
        ev = st.get(x)
        if ev is None or ev.get("type") == "result":
            continue
        out.append(x)
    return sorted(out, key=lambda x: order.get(x, 0))


def plan_trail_ids(events, pid, st=None):
    """The IDs of the events the trail of plan `pid` holds (§11: a planned estimate's trail), in log order."""
    st = st or _state(events)
    if st.get(pid) is None or st.get(pid).get("type") != "plan":
        raise KeyError(pid)
    root = st.root(pid)
    keep = set(st.chain(root))
    latest = st.latest(root)
    pb = latest["body"] if not is_withheld(latest) else {}
    keep |= {st.root(x) for x in _ids(pb.get("question")) if st.get(x)}
    keep |= {st.root(x) for x in _ids(pb.get("assumptions")) if st.get(x)}
    keep |= {st.root(m) for m in re.findall(r"\[\[([^:\]]+):", " ".join(
        str(pb.get(f) or "") for f in ("design", "analysis"))) if st.get(m)}
    runs = {e["id"] for e in events if e.get("type") == "run" and not is_withheld(e)
            and isinstance(e["body"].get("plan"), str) and st.get(e["body"]["plan"])
            and st.root(e["body"]["plan"]) == root}
    keep |= runs
    return _with_links(events, st, keep, {root}, runs, set())


def trail_lines(events, hid, st=None, results=None, ids=None):
    st = st or _state(events)
    results = results if results is not None else results_of_runs(st, events)
    out = []
    for x in (ids if ids is not None else trail_ids(events, hid, st=st)):
        e = st.get(x)
        at = str(e.get("at") or "")[:16].replace("T", " ")
        out.append(f"{at}  {e['id']} {e['type']} by {_who(st, e.get('by'))}: {describe(st, e, results)}")
    return out


def trail(events, hid, title=None):
    """The trail of hypothesis `hid` (§11): what it rests on, in log order. Returns text."""
    events = [e for e in events if isinstance(e, dict) and isinstance(e.get("id"), str)]
    st = _state(events)
    h = st.latest(hid)
    statement = "" if is_withheld(h) else h["body"].get("statement")
    lines = [f"TRAIL OF {st.root(hid)}" + (f" ({title})" if title else ""),
             f"Statement: {statement}", f"Status: {_status(st, events, hid)}",
             "In log order: the question, each version of the hypothesis, the plans that name it with their "
             "approvals, deviations and runs, its statuses, and the checks, decisions and notes that refer to them. "
             "Results are given by number and file.", ""]
    lines += trail_lines(events, hid, st=st)
    return "\n".join(lines) + "\n"


def plan_trail(events, pid, title=None):
    """The trail of plan `pid` (§11), the trail of a planned estimate. Returns text."""
    events = [e for e in events if isinstance(e, dict) and isinstance(e.get("id"), str)]
    st = _state(events)
    ids = plan_trail_ids(events, pid, st=st)
    p = st.latest(pid)
    pb = {} if is_withheld(p) else p["body"]
    estimands = pb.get("estimands") if isinstance(pb.get("estimands"), dict) else {}
    named = [title] if title else []
    if p["id"] != st.root(pid):
        named.append(f"plan as revised in {p['id']}")
    lines = [f"TRAIL OF {st.root(pid)}" + (f" ({'; '.join(named)})" if named else ""),
             f"Plan: {pb.get('kind') or 'plan'}" + (f"; estimands: {', '.join(map(str, estimands))}" if estimands
                                                   else ""),
             "In log order: the question, each version of the plan with its approvals and deviations, its runs, and "
             "the checks, decisions and notes that refer to them. Results are given by number and file.", ""]
    lines += trail_lines(events, pid, st=st, ids=ids)
    return "\n".join(lines) + "\n"


def claim_trail(events, claimset, claim_id):
    """The trail of an exported claim (§11): of its `hypothesis.lab_event`, or of its `estimate.lab_plan` for a planned
    estimate; None if it has neither."""
    claim = next((c for c in claimset.get("claims") or [] if isinstance(c, dict) and c.get("id") == claim_id), None)
    claim = claim or {}
    hyp = claim.get("hypothesis") if isinstance(claim.get("hypothesis"), dict) else {}
    if isinstance(hyp.get("lab_event"), str):
        return trail(events, hyp["lab_event"], title=f"claim {claim_id}")
    est = claim.get("estimate") if isinstance(claim.get("estimate"), dict) else {}
    if isinstance(est.get("lab_plan"), str):
        return plan_trail(events, est["lab_plan"], title=f"claim {claim_id}")
    return None

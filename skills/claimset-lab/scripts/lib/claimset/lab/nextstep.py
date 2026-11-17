"""What to do next in a lab record (lab record §2, principle 8): the steps still open, in order, each with the command
that does it. For an agent picking up the work, and printed after every writing command, so that a record is carried
through to its end without the agent holding the whole skill in mind.

    steps(events, actor=None, anchored=True, drafts=None) -> [(what, command)], the first being the next step; []
                                                 when the record has nothing left but export. `drafts` is
                                                 [(name, drafted events)] (lab record §3.6)
"""

from .summary import build

FINAL = ("supported", "not_supported", "inconclusive", "revised", "abandoned")


def steps(events, actor=None, anchored=True, drafts=None):
    s = build(events)
    drafts = [(n, d) for n, d in (drafts or []) if d]
    drafted = [e for _, d in drafts for e in d]
    dname = drafts[0][0] if drafts else "plan"
    you = actor or next((a["id"] for a in s["actors"] if a["kind"] == "agent"), None) or "<your actor ID>"
    by = f"--by {you}"
    humans = [a["id"] for a in s["actors"] if a["kind"] == "human"]
    human = humans[0] if humans else "<their actor ID>"
    out = []
    if not any(a["kind"] == "agent" for a in s["actors"]):
        out.append(("register yourself as the agent doing the work, with the model your system prompt names",
                    'claimset lab actor --kind agent --name "<your system, e.g. Claude Code>" --label "research" '
                    '--model "<provider>|<model name>|<version>|<identifier>" --record-source self_reported'))
    if not humans:
        out.append(("register the person who supervises the study, with their own words",
                    f'claimset lab actor --kind human --name "<their name>" --orcid <iD> --words "<their reply, '
                    f'verbatim>" --given-at <when> --channel chat {by}'))
    if not s["questions"] and not any(e["type"] == "question" for e in drafted):
        out.append(("agree the research question with the supervisor, with what you expect and how each expectation "
                    "will be tested, in a draft that is recorded only once they agree (lab record §3.6): draft the "
                    "question, its terms, the hypotheses and their plans with --draft, show the draft, and revise it "
                    "until they agree",
                    f'claimset lab question "<the question>" --draft {dname} {by}'))
    for name, d in drafts:
        kinds = {}
        for e in d:
            kinds[e["type"]] = kinds.get(e["type"], 0) + 1
        held = ", ".join(f"{n} {t}{'s' if n > 1 else ''}" for t, n in kinds.items())
        out.append((f"show the draft {name} ({held}) to {human}, one topic at a time, and revise it with them (--draft "
                    f"{name} --supersedes ID) until they agree; then record it with their words. Do not run its "
                    f"plans before",
                    f"claimset lab draft show {name}; once they agree: claimset lab draft record {name} {by} "
                    f'--on-behalf-of {human} --words "<their reply>" --given-at <when> --channel conversation'))
    asked = {h["question"] for h in s["hypotheses"]} | {p["question"] for p in s["plans"] if p["kind"] == "estimation"}
    asked |= {(e.get("body") or {}).get("question") for e in drafted if e["type"] in ("hypothesis", "plan")}
    ran = bool(s["runs"]["total"])
    for q in s["questions"]:
        if q["id"] not in asked:
            out.append((f"state what you expect for {q['id']}" + (
                            ": runs were made already, so say whether one suggested it (rule L31)" if ran else
                            ", before any run informs it; or, to report a value rather than decide a hypothesis, "
                            "plan its estimate (claimset lab plan --kind estimation)"),
                        f'claimset lab hypothesis "<the statement>" --question {q["id"]} --draft {dname} '
                        + ('--from-exploration --prompted-by <the run or result that suggested it> (or '
                           '--independence "<what it rests on instead>") ' if ran else "") + by))
    planned = {h for p in s["plans"] if p["kind"] != "exploratory" for h in p["hypotheses"]}
    planned |= {h for e in drafted if e["type"] == "plan" for h in (e.get("body") or {}).get("hypotheses") or []}
    loose = [h["id"] for h in s["hypotheses"] if h["status"] in ("proposed", "testing") and h["id"] not in planned]
    if loose:
        out.append((f"agree the design of the test of {', '.join(loose)} with the supervisor, one topic at a time "
                    f"(what is compared, the data, the measures, the test and its level, what counts as supported), "
                    f"in a draft of its plan, recorded once they agree, with where each choice came from; record "
                    f"the earlier work it "
                    f"relies on as premises (a hypothesis stating each, supported by the passage of the work: "
                    f"claimset lab screen <work>, claimset lab extract <work> --for <premise>), and cite them in its "
                    f"status",
                    f'claimset lab plan --kind confirmatory --hypotheses {" ".join(loose)} --draft {dname} --design "…" '
                    f'--analysis "…" --framework … --quantity NAME=… --supported "…" --not-supported "…" '
                    f'--choice "measure|…|supervisor" --requires-approval {by}'))
    for p in s["plans"]:
        if p["awaiting_approval"]:
            shown = p.get("label") or p["id"]           # the revision shown is the revision approved (§4.3)
            out.append((f"show {shown} to {human} and ask whether they approve it as written; do not run it before "
                        f"they answer",
                        f'claimset lab approve {shown} {by} --on-behalf-of {human} --words "<their reply>" '
                        f'--given-at <when> --channel conversation'))
    for p in s["plans"]:
        if p["kind"] != "exploratory" and not p["awaiting_approval"] and not p["done"]:
            out.append((f"run the test {p['id']} plans, exactly as planned",
                        f"claimset lab run --plan {p['id']} {by} -- <the command>"))
    status = {h["id"]: h["status"] for h in s["hypotheses"]}
    for p in s["plans"]:
        open_ = [h for h in p["hypotheses"] if status.get(h) in ("proposed", "testing")]
        if p["kind"] != "exploratory" and p["done"] and open_:
            out.append((f"read the verdict of {p['id']} and record it for {', '.join(open_)}",
                        f"claimset lab verdict {p['id']}; then claimset lab status {open_[0]} <the verdict> "
                        f'--plan {p["id"]} --evidence {" ".join(p["runs"]) or "<its runs>"} --why "…" {by}'))
    if not anchored:
        out.append(("anchor the record, so its time is attested", "claimset lab anchor"))
    return out


def line(events, actor=None, anchored=True, drafts=None):
    """The next step in one line, or what is left when nothing is."""
    todo = steps(events, actor, anchored, drafts)
    if not todo:
        return ("nothing left to record: export the claimset (claimset lab export) and complete it with the "
                "claimset-submit skill")
    what, command = todo[0]
    return f"{what}: {command}"

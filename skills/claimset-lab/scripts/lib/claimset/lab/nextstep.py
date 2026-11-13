"""What to do next in a lab record (lab record §2, principle 8): the steps still open, in order, each with the command
that does it. For an agent picking up the work, and printed after every writing command, so that a record is carried
through to its end without the agent holding the whole skill in mind.

    steps(events, actor=None, anchored=True) -> [(what, command)], the first being the next step; [] when the record
                                                 has nothing left but export
"""

from .summary import build

FINAL = ("supported", "not_supported", "inconclusive", "revised", "abandoned")


def steps(events, actor=None, anchored=True):
    s = build(events)
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
    if not s["questions"]:
        out.append(("record the research question", f'claimset lab question "<the question>" {by}'))
    asked = {h["question"] for h in s["hypotheses"]} | {p["question"] for p in s["plans"] if p["kind"] == "estimation"}
    ran = bool(s["runs"]["total"])
    for q in s["questions"]:
        if q["id"] not in asked:
            out.append((f"state what you expect for {q['id']}" + (
                            ": runs were made already, so say whether one suggested it (rule L31)" if ran else
                            ", before any run informs it; or, to report a value rather than decide a hypothesis, "
                            "plan its estimate (claimset lab plan --kind estimation)"),
                        f'claimset lab hypothesis "<the statement>" --question {q["id"]} '
                        + ('--from-exploration --prompted-by <the run or result that suggested it> (or '
                           '--independence "<what it rests on instead>") ' if ran else "") + by))
    planned = {h for p in s["plans"] if p["kind"] != "exploratory" for h in p["hypotheses"]}
    loose = [h["id"] for h in s["hypotheses"] if h["status"] in ("proposed", "testing") and h["id"] not in planned]
    if loose:
        out.append((f"agree the design of the test of {', '.join(loose)} with the supervisor, one topic at a time "
                    f"(what is compared, the data, the measures, the test and its level, what counts as supported), "
                    f"then plan it before running it, with where each choice came from",
                    f'claimset lab plan --kind confirmatory --hypotheses {" ".join(loose)} --design "…" '
                    f'--analysis "…" --framework … --quantity NAME=… --supported "…" --not-supported "…" '
                    f'--choice "measure|…|supervisor" --requires-approval {by}'))
    for p in s["plans"]:
        if p["awaiting_approval"]:
            out.append((f"show {p['id']} to {human} and ask whether they approve it as written; do not run it before "
                        f"they answer",
                        f'claimset lab approve {p["id"]} {by} --on-behalf-of {human} --words "<their reply>" '
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


def line(events, actor=None, anchored=True):
    """The next step in one line, or what is left when nothing is."""
    todo = steps(events, actor, anchored)
    if not todo:
        return ("nothing left to record: export the claimset (claimset lab export) and complete it with the "
                "claimset-submit skill")
    what, command = todo[0]
    return f"{what}: {command}"

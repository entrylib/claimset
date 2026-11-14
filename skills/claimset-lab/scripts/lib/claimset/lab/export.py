"""Export a lab record to a draft claimset submission (lab record spec §9).

The draft holds only what the record states. Decisions the record cannot make
(licence, guarantor, principal claims, claim types, wording of negative
results...) are left at neutral defaults or left out, and listed in a separate
completion list: a claimset never contains instructions.
"""

import json
import re
import subprocess
from pathlib import Path

from .. import LAB_SPEC_VERSION, SPEC_VERSION, __version__
from .. import validate as _claimset
from .anchor import covers, read_anchors
from . import decision as _decision
from . import tables as _tables
from . import record as _record
from .core import (FLAGS, RENAMED_KINDS, SETUP_ROLES, TERM_ID_RE, TERM_MARK_RE, LabError, State, agent_base,
                   bind_estimands, file_hash, final_statuses, is_withheld, plan_flags, verify)

FINAL = {"supported", "not_supported", "inconclusive", "revised", "abandoned"}
OUTCOMES = ("supported", "not_supported", "inconclusive")
ARTEFACT_KINDS = _claimset.ENUM["artefact_kind"]


BLOB_PATTERNS = (
    (("github.com",), "{repo}/blob/{commit}/{path}"),
    (("gitlab.com",), "{repo}/-/blob/{commit}/{path}"),
    (("codeberg.org", "gitea.com"), "{repo}/src/commit/{commit}/{path}"),
    (("bitbucket.org",), "{repo}/src/{commit}/{path}"),
)


def _blob_pattern(repo):
    """The URL pattern of a file at a commit on a repository's host, or None if the host is not known. Hosts are
    matched by name: a self-hosted GitLab whose name contains "gitlab", or a Gitea or Forgejo whose name contains
    "gitea" or "forgejo", are recognised too."""
    if not isinstance(repo, str) or not repo.startswith("https://"):
        return None
    host = repo[len("https://"):].split("/", 1)[0].lower()
    for hosts, pattern in BLOB_PATTERNS:
        if host in hosts:
            return pattern
    if "gitlab" in host:
        return "{repo}/-/blob/{commit}/{path}"
    if "gitea" in host or "forgejo" in host:
        return "{repo}/src/commit/{commit}/{path}"
    return None


def _repo_path(path):
    """`path` relative to the top of its git repository, or None."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=Path(path).parent,
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if top.returncode != 0:
        return None
    try:
        return Path(path).resolve().relative_to(Path(top.stdout.strip()).resolve()).as_posix()
    except ValueError:
        return None


def select_paper(lab, name=None):
    """The body of the paper to export: the named one, the only one, or None (the whole record)."""
    st = lab.state()
    papers = {(e.get("body") or {}).get("name"): e for e in st.papers.values()}
    if name:
        if name not in papers:
            known = ", ".join(sorted(n for n in papers if n)) or "none recorded"
            raise LabError("export", f"no paper '{name}' in the record (papers: {known}); record it with "
                                     f"`claimset lab paper {name} --questions …`")
        return dict(papers[name]["body"], _id=st.root(papers[name]["id"]))
    if len(papers) == 1:
        e = next(iter(papers.values()))
        return dict(e["body"], _id=st.root(e["id"]))
    if len(papers) > 1:
        raise LabError("export", f"the record names several papers ({', '.join(sorted(papers))}): choose one "
                                 f"with --paper NAME")
    return None


#: Stands for the artefact of the results CSV until the artefacts are numbered
RESULTS_CSV = "__results_csv__"


class _Exporter:
    def __init__(self, lab, paper=None, results_path=None):
        self.lab = lab
        self.results_path = results_path or "files/results.csv"
        self.files = {}
        rep = verify(lab)
        if not rep["ok"]:
            first = rep["errors"][0]
            raise LabError("export", f"the record does not verify ({len(rep['errors'])} error(s); first: "
                                     f"[{first['rule']}] {first['message']}); run `claimset lab verify`")
        self.events = lab.read()
        st = self.st = State()
        for e in self.events:
            st.apply(e)
        unmerged = [a for a in lab.agent_logs() if a not in st.merged and lab.read_agent(a)]
        if unmerged:
            raise LabError("export", f"agent logs of {', '.join(unmerged)} are not merged; run `claimset lab merge`")
        self.roots = [e for e in st.events if e["id"] == st.root(e["id"])]
        self.all_hyps = [e for e in self.roots if e["type"] == "hypothesis"]
        self.paper = paper
        if paper:
            self.questions = [st.root(q) for q in paper.get("questions") or []]
            self.hyps = [h for h in self.all_hyps if st.root(str((st.latest(h["id"]) or h).get("body", {})
                                                                 .get("question"))) in self.questions]
        else:
            self.questions = None
            self.hyps = self.all_hyps
        self.statuses = final_statuses(st)
        # Verdicts: the latest status naming each (hypothesis, plan), corrections in their original's place.
        self.verdicts = {}
        for e in st.events:
            b = e.get("body") if isinstance(e.get("body"), dict) else {}
            if e["type"] != "status" or is_withheld(e) or e["id"] in st.superseded_by \
                    or not isinstance(b.get("plan"), str) or not isinstance(b.get("target"), str):
                continue
            key = (st.root(b["target"]), st.root(b["plan"]))
            place = st.pos[st.root(e["id"])]
            if key not in self.verdicts or place > self.verdicts[key][0]:
                self.verdicts[key] = (place, e)
        self.verdicts = {k: v[1] for k, v in self.verdicts.items()}
        missing = [(h["id"], root) for h in (self.hyps if st.strict else [])
                   for root in st.decided_plans_for(h["id"]) if (h["id"], root) not in self.verdicts]
        if missing and not st.has_withheld:
            h, root = missing[0]
            raise LabError("export", f"the planned test of {h} under {root} has run but its verdict is not recorded; "
                                     f"see `claimset lab verdict {root}` and record it with "
                                     f"`claimset lab status {h} … --plan {root}`. Every planned test that ran is "
                                     f"reported")
        self.anchors = read_anchors(lab)
        # Where each merged agent log started in the main log (§3.5), to know what its agent saw.
        self.bases = {}
        for a in st.merged:
            try:
                agent = lab.read_agent(a)
            except LabError:
                continue
            if agent:
                self.bases[a] = agent_base(self.events, agent)
        self.completion, self.mapping = [], {}
        self.contributors, self.models, self.claims, self.evidence = [], [], [], []
        self.warrants = []
        self.limitations, self.artefacts, self.references = [], [], []
        self.person, self.evidence_of_run = {}, {}
        self.results_of = {}
        for e in st.events:
            if e["type"] == "result" and not is_withheld(e):
                self.results_of.setdefault(e["body"].get("run"), []).append(e)

    # -- helpers
    def todo(self, where, what):
        self.completion.append({"where": where, "what": what})

    def versions(self, eid):
        st = self.st
        cur = st.root(eid)
        out = [cur]
        while cur in st.superseded_by:
            cur = st.superseded_by[cur]
            out.append(cur)
        return out

    def body(self, eid):
        e = self.st.latest(eid)
        return {} if e is None or is_withheld(e) else e["body"]

    def actor_of(self, by):
        return self.st.root(by) if by else None

    def visible(self, v, run):
        """Whether event v was visible to whoever wrote `run` when it was written."""
        o = run.get("origin")
        if not isinstance(o, dict):
            return v["seq"] < run["seq"]
        agent = run["id"].split(".")[0]
        base = self.bases.get(agent)
        if base is not None and v["seq"] <= base:
            return True
        vo = v.get("origin")
        return isinstance(vo, dict) and v["id"].startswith(agent + ".") and vo.get("seq", 0) < o.get("seq", 0)

    def version_before(self, eid, run):
        """The latest version of eid's chain that the run's writer could see (not withheld), or None."""
        named = run["body"].get("plan_version") if isinstance(run.get("body"), dict) else None
        if isinstance(named, str) and self.st.get(named) is not None \
                and self.st.root(named) == self.st.root(eid):
            e = self.st.get(named)
            return None if is_withheld(e) else e
        found = None
        for v in self.versions(eid):
            e = self.st.get(v)
            if self.visible(e, run) and not is_withheld(e):
                found = e
        return found

    # -- parts of the draft
    def export_contributors(self):
        st = self.st
        writes, active = {}, {}
        for e in st.events:
            a = self.actor_of(e["by"])
            if a:
                writes.setdefault(a, set()).add(e["type"])
                first, last = active.get(a, (e["at"], e["at"]))
                active[a] = (min(first, e["at"]), max(last, e["at"]))
        self.writes = writes
        model_ids = {}
        self.withheld_actors = []
        for a in (e for e in self.roots if e["type"] == "actor"):
            cur = st.latest(a["id"])
            if is_withheld(cur):
                self.withheld_actors.append(a["id"])
                self.todo("contributors", f"actor {a['id']} is withheld in the record and is not exported; add it as "
                                          f"a contributor if it should be listed")
                continue
            b = cur["body"]
            pid = f"P{len(self.contributors) + 1}"
            self.person[a["id"]] = pid
            self.mapping[pid] = cur["id"]
            kind = b.get("kind")
            c = {"id": pid, "type": kind, "name": b.get("name")}
            if kind == "agent":
                authored = writes.get(a["id"], set()) - {"check", "actor"}
                c["positions"] = ["author"] if authored else ["contributor"]
                c["models"] = []
                period = active.get(a["id"])
                for m in b.get("models") or []:
                    key = (m.get("provider"), m.get("name"), m.get("version"), m.get("identifier"))
                    if key not in model_ids:
                        model_ids[key] = f"M{len(self.models) + 1}"
                        self.models.append({k: v for k, v in (("id", model_ids[key]), ("provider", key[0]),
                                                              ("name", key[1]), ("version", key[2]),
                                                              ("identifier", key[3])) if v})
                    mdef = next(x for x in self.models if x["id"] == model_ids[key])
                    if period and (mdef.get("accessed") is None or period[0][:10] < mdef["accessed"]):
                        mdef["accessed"] = period[0][:10]
                    c["models"].append({"model": model_ids[key]})
                if len(c["models"]) == 1:
                    c["models"][0]["role"] = "sole"
                if period:
                    c["run_period"] = {"start": period[0][:10], "end": period[1][:10]}
                if "run" in writes.get(a["id"], set()):
                    c["tools"] = ["code_execution"]
                if not authored and "check" in writes.get(a["id"], set()):
                    c["ai_tasks"] = [{"task": "review", "extent": "full"}]
                if b.get("system"):
                    c["system"] = dict(b["system"])
                if b.get("label"):
                    c["label"] = b["label"]
                if b.get("record_source"):
                    c["record_source"] = b["record_source"]
            else:
                c["positions"] = ["contributor"]
                if b.get("orcid"):
                    c["orcid"] = b["orcid"]
                self.todo(f"contributors.{pid}", f"{c['name']} ({a['id']}) is exported as a contributor; ask whether "
                                                 f"they supervised the work and whether they are the guarantor")
            self.contributors.append(c)

    def make_evidence(self, run_ids, keep=None, quantities=None):
        """One evidence object for the given runs. Its results are grouped into tables (§9; claimset §3.4, *Tables
        are the standard form*). `keep`: the result events a status names, with those the test's `quantities` bind;
        None for every result of the runs. Returns (evidence ID, {result event ID: "E<n>.T<m>.r<k>" or "E<n>.R<m>"},
        the references of the whole evidence: its tables and its result entries)."""
        st = self.st
        runs = sorted((st.get(r) for r in set(run_ids)), key=lambda e: e["seq"])
        eid = f"E{len(self.evidence) + 1}"
        self.mapping[eid] = [r["id"] for r in runs]
        events = []
        for r in runs:
            self.evidence_of_run.setdefault(r["id"], eid)
            for res in self.results_of.get(r["id"], []):
                if keep is None or res["id"] in keep or any(
                        _tables.binds(q, res["body"]) for q in (quantities or {}).values()):
                    events.append(res)
        tables, results, refs = _tables.tabulate(events, eid, RESULTS_CSV if events else None)
        whole = [f"{eid}.{t['id']}" for t in tables] + [f"{eid}.{x['id']}" for x in results]
        visible = [r for r in runs if not is_withheld(r)]
        plans = []
        for r in visible:
            pv = self.version_before(r["body"]["plan"], r) if r["body"].get("plan") else None
            if pv and pv["id"] not in [p["id"] for p in plans]:
                plans.append(pv)
        parts = [f"Lab runs {', '.join(r['id'] for r in runs)}"
                 + (f" under plan {', '.join(p['id'] for p in plans)}." if plans else ".")]
        parts += [f"Design: {p['body'].get('design')} Analysis: {p['body'].get('analysis')}" for p in plans]
        if not plans:
            parts += [f"Command: {' '.join(r['body'].get('command') or [])}" for r in visible]
        ev = {"id": eid, "profile": "quant", "design": "other", "description": " ".join(parts),
              "availability": {"level": "public"}, "lab_runs": [r["id"] for r in runs]}
        if results:
            ev["results"] = results
        if tables:
            ev["tables"] = tables
            self.todo(f"evidence.{eid}.tables", f"check the tables of {eid}: a self-contained description of each, "
                                                f"rows the compared units and columns the variables (name each "
                                                f"column by a variable term where the study defines one), and the "
                                                f"conditions that set columns apart (claimset §3.4, Tables are the "
                                                f"standard form)")
        if events:
            ev["artefacts"] = [RESULTS_CSV]
        setup = {}
        for p in plans:
            for role, ids in (p["body"].get("setup") or {}).items():
                for i in ids:
                    if i not in setup.setdefault(role, []):
                        setup[role].append(i)
        if setup:
            ev["setup"] = {role: setup[role] for role in SETUP_ROLES if setup.get(role)}
        execution = {}
        commits = {r["body"].get("code_version") for r in visible}
        if len(commits) == 1 and None not in commits and len(visible) == len(runs):
            execution["code_version"] = commits.pop()
        software = [(r["body"].get("environment") or {}).get("software") for r in visible]
        if software and software[0] and all(s == software[0] for s in software) and len(visible) == len(runs):
            execution["software"] = software[0]
        dirty = [r["id"] for r in visible if r["body"].get("dirty")]
        if dirty:
            execution["notes"] = (f"Runs {', '.join(dirty)} ran with uncommitted changes in the working tree, "
                                  f"so their code version is not exactly the recorded commit.")
        if execution:
            ev["execution"] = execution
        coded = self.coded_sources(visible)
        if coded is not None:                   # runs that read the codings: a content analysis of documents
            ev["profile"] = "qual"
            ev.pop("design", None)
            ev.update(data_sources=["document"], analytic_approach="content_analysis",
                      n_participants_or_cases=len(coded))
            ev["_sources"] = coded
            self.todo(f"evidence.{eid}", f"{eid} counts coded sources (exported as qual, content_analysis, documents): "
                                         f"confirm, give its sampling, and make its description self-contained")
        else:
            self.todo(f"evidence.{eid}", f"choose the profile and design of {eid} (exported as quant, design other) "
                                         f"and make its description self-contained")
        self.evidence.append(ev)
        return eid, refs, whole

    def coded_sources(self, runs):
        """The sources whose codings the runs read (from their codings.json), or None if none read codings."""
        out, any_coded = [], False
        from .qualitative import run_codings
        for r in runs:
            codings = run_codings(r["body"])
            if not isinstance(codings, dict):
                continue
            any_coded = True
            path = self.lab.root / "runs" / r["id"] / str(codings.get("path"))
            try:
                snap = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for c in snap.get("codings") or []:
                if c.get("source") not in out:
                    out.append(c.get("source"))
        return out if any_coded else None

    def hypothesis_at(self, hypothesis_id, pos):
        """The latest version of a hypothesis written before position `pos` (not withheld), or None."""
        found = None
        for v in self.versions(hypothesis_id):
            e = self.st.get(v)
            if self.st.pos[v] < pos and not is_withheld(e):
                found = e
        return found

    def claim_from(self, version, status, outcome, extra_runs=(), quantities=None):
        """A claim for a hypothesis version, with the evidence its status cites. Returns (claim, cited runs)."""
        st = self.st
        cid = f"C{len(self.claims) + 1}"
        self.mapping[cid] = version["id"]
        claim = {"id": cid, "type": "descriptive", "role": "supporting", "novelty": "no_prior_found", "support": [],
                 "provenance": "author_stated", "hypothesis": {"lab_event": version["id"], "outcome": outcome}}
        if is_withheld(version):
            self.todo(f"claims.{cid}.statement", f"hypothesis {version['id']} is withheld; write the statement of {cid}")
        else:
            claim = dict({"id": cid, "statement": version["body"].get("statement")}, **{k: v for k, v in claim.items()
                                                                                       if k != "id"})
            if isinstance(version["body"].get("about"), dict):
                claim = dict({k: claim[k] for k in ("id", "statement")}, about=dict(version["body"]["about"]),
                             **{k: v for k, v in claim.items() if k not in ("id", "statement")})
        cited_runs, cited_results, other, premises = [], [], [], []
        for ref in list(status["body"].get("evidence") or []):
            ev = st.get(ref)
            if ev is not None and ev["type"] == "hypothesis":     # a premise: linked once every claim exists (§9)
                if st.root(ev["id"]) not in premises:
                    premises.append(st.root(ev["id"]))
            elif ev is not None and ev["type"] == "run":
                if ev["id"] not in cited_runs:
                    cited_runs.append(ev["id"])
            elif ev is not None and ev["type"] == "result" and not is_withheld(ev):
                cited_results.append(ev["id"])
                if ev["body"].get("run") not in cited_runs:
                    cited_runs.append(ev["body"]["run"])
            else:
                other.append(ref + (" (withheld)" if ev is not None and is_withheld(ev) else ""))
        for r in extra_runs:
            if r not in cited_runs:
                cited_runs.append(r)
        if other:
            self.todo(f"claims.{cid}.support", f"status {status['id']} also cites {', '.join(other)}, which are not "
                                               f"exported as evidence")
        if cited_runs:
            # A status that names results is the record of what the claim rests on: the other results of its runs
            # are left to the CSV of every result (§9), with those the test reads
            eid, refs, whole = self.make_evidence(cited_runs, keep=set(cited_results) if cited_results else None,
                                                  quantities=quantities)
            profile = next((e.get("profile") for e in self.evidence if e["id"] == eid), "quant")
            support = {"kind": "empirical_qual" if profile == "qual" else "empirical_quant", "evidence": eid}
            # the rows of the results the status names, and of those the test reads, so a reader can check its rule
            read = [res["id"] for r in cited_runs for res in self.results_of.get(r, [])
                    if any(_tables.binds(q, res["body"]) for q in (quantities or {}).values())]
            cited = list(dict.fromkeys(refs[x] for x in list(cited_results) + (read if cited_results else [])
                                       if x in refs))
            if cited or whole:
                support["results"] = cited or whole
            claim["support"].append(support)
        elif not premises:
            self.todo(f"claims.{cid}.support", f"no run lies behind status {status['id']}; give {cid} its support")
        if premises:
            claim["_premises"] = (premises, status)
        claim["_targets"] = set(self.versions(version["id"])) | set(self.versions(status["id"])) | set(cited_runs) | {
            x["id"] for r in cited_runs for x in self.results_of.get(r, [])}
        if outcome == "not_supported":
            self.todo(f"claims.{cid}.statement", f"{cid} is a negative result: rewrite the statement of "
                                                 f"{version['id']} to say plainly what was not found, and under what "
                                                 f"conditions")
        self.todo(f"claims.{cid}", f"confirm the type (exported as descriptive) and role of {cid}, and give its "
                                   f"scope; its novelty is exported as no_prior_found: look for the closest earlier "
                                   f"result and cite it (a relation with a note on the difference), or relabel the "
                                   f"claim a replication or extension of it")
        return claim, cited_runs

    def mark_synthesis(self, claim, why):
        """The claim states what earlier work establishes (claimset v0.43 §3.7): its novelty is `synthesis`, and the
        completion item on its novelty says why."""
        if claim.get("novelty") == "synthesis":
            return
        claim["novelty"] = "synthesis"
        cid = claim["id"]
        self.completion = [c for c in self.completion
                           if not (c["where"] == f"claims.{cid}" and "novelty is exported as" in c["what"])]
        self.todo(f"claims.{cid}", f"confirm the type (exported as {claim.get('type')}) and role of {cid}, and give its "
                                   f"scope; its novelty is exported as synthesis: {why}")

    def synthesis_from_premises(self):
        """A claim whose only support is an argument from claims that are syntheses is one too (§9), unless the rule
        it draws goes beyond them, which the completion list asks about."""
        by_id = {c["id"]: c for c in self.claims}
        changed = True
        while changed:
            changed = False
            for c in self.claims:
                deps = c.get("depends_on") or []
                if (c.get("novelty") == "synthesis" or not deps or not c["support"]
                        or any(s.get("kind") != "argument" for s in c["support"])):
                    continue
                if all((by_id.get(d) or {}).get("novelty") == "synthesis" for d in deps):
                    self.mark_synthesis(c, "it rests, by an argument, on claims that state what earlier work "
                                           "establishes. If the rule it draws goes beyond what those works state, "
                                           "label it extension, with an extends relation to the work it carries "
                                           "further")
                    changed = True

    def ask_background(self):
        """A claim resting on runs and on no premise: ask what earlier work it relies on (§9)."""
        for c in self.claims:
            if c.pop("_linked", False) or c.get("depends_on"):
                continue
            if any(s.get("kind") in ("empirical_quant", "empirical_qual") for s in c["support"]):
                self.todo(f"claims.{c['id']}.depends_on",
                          f"say what earlier work {c['id']} relies on (a method's conditions, an instrument's "
                          f"calibration, a result it builds on): state each premise as a hypothesis supported by the "
                          f"passage of the work (claimset lab screen, extract, status), "
                          + (f"cite the hypotheses in the status of {c['hypothesis']['lab_event']}, and export again"
                             if c.get("hypothesis") else f"and name their claims in the depends_on of {c['id']}")
                          + "; or leave it if it relies on none")

    def link_premises(self):
        """A status whose evidence names hypotheses (§9): the claim depends on their claims; with no run behind it,
        its support is an argument from them, the status's rationale its warrant."""
        by_root = {self.st.root(c["hypothesis"]["lab_event"]): c["id"] for c in self.claims if c.get("hypothesis")}
        for c in self.claims:
            premises, status = c.get("_premises") or ((), None)
            if not premises:
                continue
            ids = [by_root[h] for h in premises if h in by_root and by_root[h] != c["id"]]
            missing = [h for h in premises if h not in by_root]
            if missing:
                self.todo(f"claims.{c['id']}.depends_on", f"status {status['id']} cites {', '.join(missing)}, "
                                                          f"which have no claim (no final status); give them one or "
                                                          f"drop them")
            if not ids:
                continue
            c["depends_on"] = list(dict.fromkeys(list(c.get("depends_on") or []) + ids))
            c["_linked"] = True
            if not any(s.get("kind") != "argument" for s in c["support"]):
                wid = f"W{len(self.warrants) + 1}"
                self.warrants.append({"id": wid, "reasoning": "deductive", "premises": ids,
                                      "text": status["body"].get("rationale") or ""})
                c["support"].append({"kind": "argument", "warrant": wid})
                self.todo(f"warrants.{wid}", f"check the reasoning of {wid} ({c['id']} from {', '.join(ids)}): "
                                             f"exported as deductive, with the rationale of {status['id']} as its text")
                self.done_support(c)

    # -- for the lab parts of extensions (their `export(exporter)`, called once the paper is drafted)
    def paper_object(self):
        """The draft's paper object."""
        return self._paper

    def reference(self, rid):
        """The references entry with ID `rid`."""
        return next(r for r in self.references if r["id"] == rid)

    def reference_for(self, work):
        """The ID of the references entry for a work {target, id_type}, added if the draft has none (a DOI is
        compared case-insensitively)."""
        def key(t, k):
            return (k, str(t).strip().lower() if k == "doi" else str(t).strip())
        want = key(work["target"], work["id_type"])
        for r in self.references:
            if key(r.get("target"), r.get("id_type")) == want:
                return r["id"]
        rid = f"B{max([int(r['id'][1:]) for r in self.references if r['id'][1:].isdigit()] + [0]) + 1}"
        self.references.append({"id": rid, "target": work["target"], "id_type": work["id_type"]})
        return rid

    def mapping_back(self, eid):
        """The ID of the claimset object exported from lab event `eid` (any version of it), or None."""
        root = self.st.root(eid) if self.st.get(eid) else eid
        for oid, ev in self.mapping.items():
            if isinstance(ev, str) and self.st.get(ev) is not None and self.st.root(ev) == root:
                return oid
        return None

    def retarget_artefact(self, aid, rid):
        """Point artefact `aid` at the cited work `rid`; a reference only it pointed to (a captured page's URL)
        is dropped, with what the completion list asked about it."""
        art = next((a for a in self.artefacts if a["id"] == aid), None)
        if art is None or art.get("reference") == rid:
            return
        old, art["reference"] = art.get("reference"), rid
        if old and not any(a.get("reference") == old for a in self.artefacts) and \
                old not in json.dumps([self.claims, self.evidence]):
            self.references = [r for r in self.references if r["id"] != old]
            self.completion = [c for c in self.completion if not c["where"].startswith(f"references.{old}.")]

    def done_support(self, claim):
        """An extension gave the claim its support: what the completion list asked about its support is done."""
        where = f"claims.{claim['id']}.support"
        self.completion = [c for c in self.completion if c["where"] != where]

    def ext_block(self, obj, name):
        """The block of extension `name` on a claimset object, created if needed."""
        return obj.setdefault("ext", {}).setdefault(name, {})

    def flag_owner(self, flag):
        """The declared extension whose test flag this is."""
        for name, _impl, mod in self.st.declared():
            if mod is not None and flag in getattr(mod, "TEST_FLAGS", ()):
                return name
        raise LabError("schema", f"export: no declared extension has the test flag {flag}")

    def test_quantities(self, claim, pv):
        """A claim's test quantities bind results by `variable` (claimset §3.3.3); counts of coded material go to
        the qualitative block of the claim (qualitative §2.7), their codes renamed with the definitions."""
        quantities = claim["test"].get("quantities")
        if not isinstance(quantities, dict):
            return
        from ..extensions.qualitative_count import result_variable
        from .qualitative import count_specs
        counts = count_specs(pv["body"])
        out = {}
        for name, q in quantities.items():
            if not isinstance(q, dict):
                out[name] = q
                continue
            q = {("variable" if k == "quantity" else k): v for k, v in q.items() if k != "count"}
            if name in counts:
                q["variable"] = result_variable(name)
                self.ext_block(claim, "qualitative").setdefault("counts", {})[name] = json.loads(
                    json.dumps(counts[name]))
            out[name] = q
        claim["test"]["quantities"] = out

    def add_deviation_limitation(self, claim, run, plan_version, dv):
        lid = f"L{len(self.limitations) + 1}"
        self.limitations.append({
            "id": lid, "category": "analytic_flexibility",
            "statement": f"Lab run {run['id']} deviated from plan {plan_version['id']}: {dv['body'].get('text')} "
                         f"Reason: {dv['body'].get('reason')}",
            "affects": [claim["id"]], "impact": "could_bias_magnitude", "mitigation": "none"})
        claim.setdefault("limitations", []).append(lid)
        self.todo(f"limitations.{lid}", f"review the category, impact and wording of {lid}, exported from "
                                        f"deviation {dv['id']}")

    def export_hypotheses(self):
        st = self.st
        deviations, self.withheld_deviations = {}, []
        for e in self.roots:
            if e["type"] != "deviation":
                continue
            cur = st.latest(e["id"])
            if is_withheld(cur):
                self.withheld_deviations.append(cur["id"])
            elif cur["body"].get("plan") and cur["body"].get("run"):
                deviations[(st.root(cur["body"]["plan"]), cur["body"]["run"])] = cur
        self.test_counts = {o: 0 for o in OUTCOMES}
        for h in self.hyps:
            decided = st.decided_plans_for(h["id"]) if st.strict else {}
            for root, (pv, runs) in sorted(decided.items(), key=lambda kv: st.pos[kv[1][1][0]["id"]]):
                verdict = self.verdicts.get((h["id"], root))
                if verdict is None:
                    self.todo("claims", f"the verdict of {root} on {h['id']} is not readable (withheld); add its claim")
                    continue
                outcome = verdict["body"]["to"]
                self.test_counts[outcome] += 1
                version = self.hypothesis_at(h["id"], st.pos[pv["id"]]) or st.latest(h["id"])
                whole = pv["body"].get("decision") or {}
                rule = _decision.effective(whole, h["id"], st.same_hypothesis)
                bound = {k: ({("variable" if a == "quantity" else a): b for a, b in q.items()}
                             if isinstance(q, dict) else q) for k, q in (rule.get("quantities") or {}).items()}
                claim, _ = self.claim_from(version, verdict, outcome, [r["id"] for r in runs], quantities=bound)
                devs = [(r, deviations[(root, r["id"])]) for r in runs if (root, r["id"]) in deviations]
                claim["planning"] = "confirmatory_with_deviations" if devs else "confirmatory"
                claim["planned_at"] = pv["at"]
                claim["planned_at_anchor"] = self.anchor_before(pv, runs[0])
                claim["test"] = {k: rule[k] for k in ("framework", "parameters", "quantities", "supported",
                                                      "not_supported") if rule.get(k) is not None}
                if _decision.per_hypothesis(whole) and isinstance(claim["test"].get("quantities"), dict):
                    used = _decision.names_used(rule)   # this hypothesis's quantities, not its neighbours'
                    claim["test"]["quantities"] = {k: v for k, v in claim["test"]["quantities"].items()
                                                   if k in used}
                claim["test"].update({"verdict": "computed" if _decision.computed(rule) else "judged",
                                      "runs": pv["body"].get("runs", 1), "lab_plan": pv["id"]})
                self.test_quantities(claim, pv)
                self.flags_onto(claim, claim["test"], pv, runs, "test")
                if pv["body"].get("addresses"):
                    claim["test"]["addresses"] = list(pv["body"]["addresses"])
                for r, dv in devs:
                    self.add_deviation_limitation(claim, r, pv, dv)
                self.claims.append(claim)
            if decided:
                continue
            status = self.statuses.get(h["id"])
            if status is None or status["body"].get("to") not in OUTCOMES:
                continue
            claim, cited_runs = self.claim_from(st.latest(h["id"]), status, status["body"]["to"])
            claim["planning"] = "exploratory"
            if not st.strict:
                self.legacy_planning(claim, h, cited_runs, deviations)
            self.claims.append(claim)
        if self.withheld_deviations:
            self.todo("claims[].planning", f"deviations {', '.join(self.withheld_deviations)} are withheld, so the "
                                           f"planning labels do not take them into account; check them")

    def anchor_before(self, pv, first_run):
        """The service of the earliest anchor that covers plan version `pv` and was made before the first deciding
        run started, or none (§9)."""
        started = first_run["body"].get("started_at") or first_run["at"]
        usable = sorted((a for a in self.anchors if isinstance(a, dict) and covers(a, pv)
                         and isinstance(a.get("at"), str) and a["at"] <= started), key=lambda a: a["at"])
        return usable[0].get("service", "none") if usable else "none"

    def flags_onto(self, claim, block, pv, runs, field):
        """The flags of a decided plan (§5.7.5): the core's into `block` (the claim's test or estimate), an
        extension's into its block on the claim."""
        unclear = []
        flags = plan_flags(self.st, pv, runs, lab=self.lab, notes=unclear)
        for note in unclear:
            self.todo(f"claims.{claim['id']}.{field}.flags", note)
        core = [f for f in flags if f in FLAGS]
        if core:
            block["flags"] = core
        for f in flags:
            if f not in core:                 # an extension's flag goes into its block on the claim
                self.ext_block(claim, self.flag_owner(f)).setdefault("test_flags", []).append(f)

    def export_estimates(self):
        """A claim for each decided estimation plan of the paper's questions (§5.7.8, §9): planning planned_estimate,
        the plan's estimands, the evidence of its deciding runs, and a statement drafted from the values."""
        st = self.st
        deviations = {}
        for e in self.roots:
            cur = st.latest(e["id"]) if e["type"] == "deviation" else None
            if cur is not None and not is_withheld(cur) and cur["body"].get("plan") and cur["body"].get("run"):
                deviations[(st.root(cur["body"]["plan"]), cur["body"]["run"])] = cur
        decided = []
        for root in st.plan_roots:
            d = st.deciding_runs(root)
            if not d or d[0]["body"].get("kind") != "estimation":
                continue
            q = d[0]["body"].get("question")
            if self.questions is not None and st.root(str(q)) not in self.questions:
                continue
            decided.append((root, d))
        for root, (pv, runs) in sorted(decided, key=lambda x: st.pos[x[1][1][0]["id"]]):
            cid = f"C{len(self.claims) + 1}"
            self.mapping[cid] = pv["id"]
            estimands = json.loads(json.dumps(pv["body"].get("estimands") or {}))
            bound = bind_estimands(st, pv, runs)
            missing = [n for n, (res, value) in bound.items() if res is None or value is None]
            parts = []
            for n, q in estimands.items():
                res, value = bound.get(n, (None, None))
                cond = q.get("conditions") or {}
                where = f" ({', '.join(f'{k} {v}' for k, v in cond.items())})" if cond else ""
                field = f" {q['field']}" if q.get("field") not in (None, "value") else ""
                parts.append(f"{q.get('variable')}{field}{where} " + (f"was {value:g}" if value is not None
                                                                      else "was not obtained"))
            statement = "Under plan " + pv["id"] + ", " + "; ".join(parts) + "."
            claim = {"id": cid, "statement": statement, "type": "descriptive", "role": "supporting",
                     "novelty": "no_prior_found", "support": [], "provenance": "author_stated",
                     "planning": "planned_estimate", "planned_at": pv["at"],
                     "planned_at_anchor": self.anchor_before(pv, runs[0])}
            estimate = {"estimands": estimands, "runs": pv["body"].get("runs", 1), "lab_plan": pv["id"]}
            if missing:
                estimate["not_obtained"] = missing
            self.flags_onto(claim, estimate, pv, runs, "estimate")
            claim["estimate"] = estimate
            run_ids = [r["id"] for r in runs]
            eid, refs, whole = self.make_evidence(run_ids, quantities=estimands)
            read = [res["id"] for res, _v in bound.values() if res is not None]
            cited = list(dict.fromkeys(refs[x] for x in read if x in refs))
            support = {"kind": "empirical_quant", "evidence": eid}
            if cited or whole:
                support["results"] = cited or whole
            claim["support"].append(support)
            claim["_targets"] = set(self.versions(pv["id"])) | set(run_ids) | {
                x["id"] for r in run_ids for x in self.results_of.get(r, [])}
            for r in runs:
                dv = deviations.get((root, r["id"]))
                if dv is not None:
                    self.add_deviation_limitation(claim, r, pv, dv)
            self.todo(f"claims.{cid}.statement",
                      f"{cid} reports the planned estimate of {pv['id']}: rewrite its statement as a sentence a "
                      f"reader understands alone, with each value, its uncertainty and the scope the plan fixed; it "
                      f"reports values, so it calls them large or small only by a standard the paper states and "
                      f"cites" + (f"; say that {', '.join(missing)} was not obtained, and why" if missing else ""))
            self.todo(f"claims.{cid}", f"confirm the type (exported as descriptive) and role of {cid}, and give its "
                                       f"scope; its novelty is exported as no_prior_found: look for the closest "
                                       f"earlier estimate and cite it")
            self.claims.append(claim)

    def legacy_planning(self, claim, h, cited_runs, deviations):
        """Planning labels for records begun under v0.4: a confirmatory run in the status's evidence under a plan
        naming the hypothesis."""
        st = self.st
        hyp_ids = set(self.versions(h["id"]))
        tests = []
        for r in sorted((st.get(x) for x in cited_runs), key=lambda e: e["seq"]):
            if is_withheld(r) or r["body"].get("label") != "confirmatory" or not r["body"].get("plan"):
                continue
            pv = self.version_before(r["body"]["plan"], r)
            if pv and hyp_ids & set(pv["body"].get("hypotheses") or []):
                tests.append((r, pv, deviations.get((st.root(pv["id"]), r["id"]))))
        clean = [t for t in tests if t[2] is None]
        chosen = clean[0] if clean else (tests[0] if tests else None)
        if not chosen:
            return
        claim["planning"] = "confirmatory" if clean else "confirmatory_with_deviations"
        r, pv, _ = chosen
        claim["planned_at"] = pv["at"]
        self.todo(f"claims.{claim['id']}.test", f"plan {pv['id']} has no decision rule (it was written under lab "
                                                f"record v0.4 with the criterion: {pv['body'].get('criterion')}); "
                                                f"state the rule in {claim['id']}.test as it was fixed before the run")
        started = r["body"].get("started_at") or r["at"]
        usable = sorted((a for a in self.anchors if isinstance(a, dict) and covers(a, pv)
                         and isinstance(a.get("at"), str) and a["at"] <= started), key=lambda a: a["at"])
        claim["planned_at_anchor"] = usable[0].get("service", "none") if usable else "none"
        for r, pv, dv in tests:
            if dv is not None:
                self.add_deviation_limitation(claim, r, pv, dv)

    def pinned_lab_uri(self, repo, rel):
        """A URI of exactly this version of the log: the git anchor commit of its last event, on the repository's
        host (GitHub, GitLab, Codeberg and other Gitea or Forgejo hosts, Bitbucket). None if the last event is not
        anchored by a git commit, or the host is not known."""
        pattern = _blob_pattern(repo)
        if pattern is None:
            return None
        lines = [l for l in self.lab.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return None
        head = json.loads(lines[-1]).get("seq")
        for a in reversed(read_anchors(self.lab)):
            commit = (a.get("receipt") or {}).get("commit") if isinstance(a, dict) else None
            if a.get("service") == "git_remote" and a.get("seq") == head and isinstance(commit, str) and commit:
                return pattern.format(repo=repo.rstrip("/").removesuffix(".git"), commit=commit, path=rel)
        return None

    def export_checks(self):
        st = self.st
        for e in self.roots:
            if e["type"] != "check":
                continue
            cur = st.latest(e["id"])
            if is_withheld(cur):
                self.todo("claims[].checks", f"check {cur['id']} is withheld and is not exported")
                continue
            b = cur["body"]
            target = b.get("target")
            matched = [c for c in self.claims if target in c.get("_targets", set())]
            if not matched:
                self.todo("claims[].checks", f"check {cur['id']} targets {target}, which no exported claim rests on; "
                                             f"it is not exported")
                continue
            by = self.person.get(self.actor_of(cur["by"]))
            checker = next((x for x in self.contributors if x["id"] == by), None)
            if checker is None or "author" in checker["positions"]:
                self.todo("claims[].checks", f"check {cur['id']} was made by {cur['by']}, who is an author or not "
                                             f"exported; a claimset check comes from a non-author, so it is not "
                                             f"exported")
                continue
            for c in matched:
                entry = {"by": by, "outcome": b.get("outcome"), "extent": b.get("extent")}
                entry.update({k: b[k] for k in ("notes", "resolution") if b.get(k)})
                c.setdefault("checks", []).append(entry)

    def export_assumptions(self):
        st = self.st
        if self.paper and any(a["type"] == "assumption" for a in self.roots):
            self.todo("claims[] (assumptions)", "assumptions are exported from the whole record; remove those that "
                                                "no claim of this paper rests on")
        for a in self.roots:
            if a["type"] != "assumption":
                continue
            cid = f"C{len(self.claims) + 1}"
            cur = st.latest(a["id"])
            self.mapping[cid] = cur["id"]
            if is_withheld(cur):
                self.claims.append({"id": cid, "type": "descriptive", "role": "supporting",
                                    "support": [{"kind": "assumption"}], "provenance": "author_stated"})
                self.todo(f"claims.{cid}", f"assumption {cur['id']} is withheld; write the statement, category and "
                                           f"check of {cid}")
                continue
            b = cur["body"]
            claim = {"id": cid, "statement": b.get("statement"), "type": "descriptive", "role": "supporting",
                     "support": [{"kind": "assumption"}],
                     "assumption_category": b.get("category"), "check": b.get("check"),
                     "provenance": "author_stated"}
            ce = b.get("check_evidence")
            if ce:
                ce_event = st.get(ce)
                run_id = None
                if ce_event is not None and ce_event["type"] == "run":
                    run_id = ce
                elif ce_event is not None and ce_event["type"] == "result" and not is_withheld(ce_event):
                    run_id = ce_event["body"].get("run")
                if run_id is None:
                    self.todo(f"claims.{cid}.check_evidence", f"assumption {cur['id']} was checked by {ce}, which is "
                                                              f"not a run or result; give {cid} its check_evidence")
                else:
                    if run_id not in self.evidence_of_run:
                        self.make_evidence([run_id])
                    claim["check_evidence"] = self.evidence_of_run[run_id]
            self.claims.append(claim)
        if any("assumption_category" in c for c in self.claims) or any(
                self.mapping.get(c["id"], "").startswith("AS") for c in self.claims):
            self.todo("claims[].assumptions", "link each claim to the assumption claims it relies on")

    def export_artefacts(self):
        st = self.st
        for a in self.roots:
            if a["type"] != "artefact":
                continue
            cur = st.latest(a["id"])
            if is_withheld(cur):
                self.todo("artefacts", f"artefact {cur['id']} is withheld and is not exported; add it if it should be "
                                       f"listed")
                continue
            b = cur["body"]
            aid = f"A{len(self.artefacts) + 1}"
            self.mapping[aid] = cur["id"]
            art = {"id": aid, "kind": b.get("kind") if b.get("kind") in ARTEFACT_KINDS else "other",
                   "uri": b.get("path_or_uri"), "availability": {"level": "public"}}
            art.update({k: v for k, v in (("version", b.get("hash")), ("licence", b.get("licence")),
                                          ("description", b.get("description"))) if v})
            if art["kind"] in ("figure", "table") and "description" not in art:
                self.todo(f"artefacts.{aid}.description", f"describe what {aid} shows, self-contained")
            if isinstance(cur["body"].get("ext"), dict):
                art["ext"] = json.loads(json.dumps(cur["body"]["ext"]))   # an event's blocks are its artefact's (§9)
            self.artefacts.append(art)
        self.export_sources()
        self.export_results_csv()
        lab_aid = f"A{len(self.artefacts) + 1}"
        init = self.body("INIT")
        rel = _repo_path(self.lab.log_path) or f"{self.lab.root.name}/{self.lab.log_path.name}"
        repo = init.get("repository")
        pinned = self.pinned_lab_uri(repo, rel)
        art = {"id": lab_aid, "kind": "lab_record",
               "uri": pinned or (f"{repo.rstrip('/')}/{rel}" if repo else rel),
               "version": file_hash(self.lab.log_path), "availability": {"level": "public"},
               "description": "Lab record of the study: questions, hypotheses, plans, runs, results and decisions, "
                              "as an append-only, hash-chained event log (Claimset lab record specification "
                              f"v{init.get('lab_spec_version') or LAB_SPEC_VERSION}, begun "
                              f"{str(init.get('started_at') or '')[:10]}; exported with claimset {__version__})."
                              + (" Kept in desk mode, without a remote: the hash chain fixes the order of events, "
                                 "their times are the recording tool's clock, and nothing is anchored."
                                 if _record.desk(self.lab) else "")}
        withheld = [{"event": e["id"], "reason": e["body"].get("reason"), "comment": e["body"].get("comment")}
                    for e in self.st.events if is_withheld(e)]
        if withheld:
            art["withheld_events"] = [{k: v for k, v in w.items() if v is not None} for w in withheld]
        self.artefacts.append(art)
        self.mapping[lab_aid] = "lab.jsonl"
        if not repo:
            self.todo(f"artefacts.{lab_aid}.uri", "give the public URI of the lab record (the record names no "
                                                  "repository)")
        elif not pinned:
            self.todo(f"artefacts.{lab_aid}.uri",
                      f"the URI names no fixed version of the lab record, and the file there changes as the record "
                      f"grows, so it will not match the version hash: anchor the record (`claimset lab anchor`) "
                      f"and export again, or give a URI of this version ({art['version']})")
        for x in self.artefacts:
            if "licence" not in x and not (x.get("reference") and x["availability"]["level"] != "public"):
                self.todo(f"artefacts.{x['id']}.licence",
                          f"give the licence of {x['id']} itself, which is not necessarily the paper's: the study's "
                          f"own code and data take the licence their owners choose; content written by others "
                          f"(downloaded issues, posts, pages) keeps its authors' terms and cannot take the paper's "
                          f"licence; say whose it is and under what terms it is shared, or leave it out of the "
                          f"package")
        return lab_aid

    def export_sources(self):
        """Captured sources (§5.20) as artefacts: content written by others is a cited work (`reference`), never
        under the paper's licence; a private source is listed with its hash and left out of the package."""
        st = self.st
        for e in self.roots:
            if e["type"] != "source":
                continue
            cur = st.latest(e["id"])
            if is_withheld(cur):
                self.todo("artefacts", f"source {cur['id']} is withheld and is not exported")
                continue
            b = cur["body"]
            files = {f.get("role"): f for f in b.get("files") or [] if isinstance(f, dict)}
            original = files.get("original") or {}
            rights = b.get("rights") if isinstance(b.get("rights"), dict) else {}
            third = rights.get("holder") == "third_party"
            aid = f"A{len(self.artefacts) + 1}"
            self.mapping[aid] = cur["id"]
            how = {"saved": "saved by hand", "browser": "captured from a browser",
                   "fetched": "fetched by the lab tool"}.get(b.get("method"), b.get("method"))
            when = f" on {str(b['retrieved_at'])[:10]}" if b.get("retrieved_at") else ""
            text = (f"{b.get('title') or 'Captured source'} ({b.get('format')}), {how}{when}; recorded in the lab "
                    f"record as {cur['id']} on {str(cur.get('at', ''))[:10]}.")
            facts = [f"{k}: {b[k]}" for k, label in (("venue", "venue"), ("published_at", "published"),
                                                    ("author", "author")) if b.get(k)]
            if facts:                           # what counts distinct by venue, year or author read
                text += " " + "; ".join(f.replace("published_at:", "published:") for f in facts) + "."
            if third:
                text += " Written by others" + (f"; shared under: {rights['terms']}." if rights.get("terms") else ".")
            if b.get("description"):
                text += " " + b["description"]
            art = {"id": aid, "kind": "data", "version": original.get("hash"), "description": text}
            if b.get("visibility") == "public":
                from .sources import source_dir
                path = source_dir(self.lab, cur) / str(original.get("path"))
                art["uri"] = _repo_path(path) or f"{self.lab.root.name}/sources/{cur['id']}/{original.get('path')}"
                art["availability"] = {"level": "public"}
            else:
                if b.get("uri"):
                    art["uri"] = b["uri"]
                art["availability"] = {"level": "author_only", "reason": "legal", "content_hash": original.get("hash")}
                self.todo(f"artefacts.{aid}.availability",
                          f"{cur['id']} is private: it is listed with its hash and not packaged; check the level "
                          f"(author_only, audit, platform) and the reason (legal for others' copyright, personal_data)")
            if rights.get("licence"):
                art["licence"] = rights["licence"]
            if third and b.get("uri"):
                bid = f"B{len(self.references) + 1}"
                ref = {"id": bid, "target": b["uri"], "id_type": "url"}
                if b.get("archive_uri"):
                    ref["archive_uri"] = b["archive_uri"]
                else:
                    self.todo(f"references.{bid}.archive_uri",
                              f"{cur['id']} ({b['uri']}) has no archived copy; give one (a web archive snapshot), "
                              f"since a page at a URL can change or disappear")
                self.references.append(ref)
                art["reference"] = bid
            if isinstance(cur["body"].get("ext"), dict):
                art["ext"] = json.loads(json.dumps(cur["body"]["ext"]))   # an event's blocks are its artefact's (§9)
            self.artefacts.append(art)
        art_of = {sr: aid for aid, sr in self.mapping.items() if isinstance(sr, str) and sr.startswith("SR")}
        self.exported_quotes = set()
        for ev in self.evidence:
            srcs = ev.pop("_sources", None)
            if srcs is None:
                continue
            arts = [art_of[s] for s in srcs if s in art_of]
            if arts:
                ev["artefacts"] = list(dict.fromkeys(list(ev.get("artefacts") or []) + arts))
            self.coded_evidence(ev, srcs, art_of)
        self.excerpt_todo()

    def coded_evidence(self, ev, srcs, art_of):
        """Evidence from runs that read codings: the quoted passages of its sources as excerpts, how the coding
        was done as a limitation, and what did the counting (§9)."""
        from .qualitative import current_codings
        dmap = getattr(self, "dmap", {})
        codings = [c for c in current_codings(self.st) if c["body"].get("source") in srcs]
        results = ev.setdefault("results", [])
        for c in codings:
            q = c["body"].get("quote")
            if not isinstance(q, dict) or c["body"]["source"] not in art_of:
                continue
            code = self.st.root(c["body"]["codes"][0])
            results.append({"id": f"R{len(results) + 1}", "variable": dmap.get(code, code),
                            "value": {"text": q.get("exact"),
                                      "locator": {"artefact": art_of[c["body"]["source"]], "start": q.get("start"),
                                                  "end": q.get("end"), "lab_event": c["id"]}}})
            self.exported_quotes.add(c["id"])
        if not results:
            ev.pop("results", None)
        coders = {c.get("by") for c in codings}
        passes = {str(c["body"].get("pass")) for c in codings if c["body"].get("pass") is not None}
        if codings and len(coders) == 1 and len(passes) <= 1:
            lid = f"L{len(self.limitations) + 1}"
            affects = [cl["id"] for cl in self.claims
                       if any(s.get("evidence") == ev["id"] for s in cl.get("support") or [])]
            self.limitations.append({
                "id": lid, "category": "measurement", "affects": affects, "impact": "could_bias_magnitude",
                "mitigation": "none",
                "statement": f"The {len(srcs)} sources of {ev['id']} were coded by one coder in one pass; agreement "
                             f"between coders was not assessed."})
            for cl in self.claims:
                if cl["id"] in affects:
                    cl.setdefault("limitations", []).append(lid)
            self.todo(f"limitations.{lid}", f"review {lid}: exported because one coder coded the sources in one pass")
        counters = [self.st.get(r) for r in ev.get("lab_runs") or []]
        versions = sorted({(r["body"].get("parameters") or {}).get("counter") for r in counters
                           if r and (r["body"].get("parameters") or {}).get("counter")})
        if versions:
            ex = ev.setdefault("execution", {})
            note = (f"Counted by the counter of the lab record tool ({', '.join(versions)}, claimset/lab/count.py) "
                    f"from the codings in force, recorded with the run (codings.json); the code version is the "
                    f"study's code checkout, not the counter's.")
            ex["notes"] = f"{ex['notes']} {note}" if ex.get("notes") else note

    def excerpt_todo(self):
        """Codings with a quote, as the excerpts a claim can give (claimset §3.4, rule 78)."""
        from .qualitative import current_codings
        art_of = {sr: aid for aid, sr in self.mapping.items() if isinstance(sr, str) and sr.startswith("SR")}
        quoted = [c for c in current_codings(self.st) if isinstance(c["body"].get("quote"), dict)
                  and c["id"] not in getattr(self, "exported_quotes", set())]
        if getattr(self, "exported_quotes", None):
            self.todo("evidence", f"{len(self.exported_quotes)} quoted codings are exported as excerpts of the evidence "
                                  f"whose runs read them; keep those the claims rely on and remove the rest")
        if not quoted:
            return
        lines = []
        for c in quoted[:10]:
            q = c["body"]["quote"]
            loc = {"artefact": art_of.get(c["body"]["source"]), "start": q.get("start"), "end": q.get("end"),
                   "lab_event": c["id"]}
            lines.append(json.dumps({"text": q.get("exact"), "locator": loc}, ensure_ascii=False))
        more = f" (and {len(quoted) - 10} more)" if len(quoted) > 10 else ""
        self.todo("evidence", f"the record has {len(quoted)} quoted codings{more}: counts from codings come from the "
                              f"runs that read them; an excerpt a claim gives is a result of a qual evidence object "
                              f"whose value is the coding's quote with a structured locator, e.g. "
                              + "; ".join(lines))

    def hypothesis_counts(self, hyps):
        counts = {k: 0 for k in ("supported", "not_supported", "inconclusive", "revised", "abandoned", "open")}
        for h in hyps:
            final = self.statuses.get(h["id"])
            to = final["body"].get("to") if final else None
            counts[to if to in FINAL else "open"] += 1
        out = dict({"total": sum(counts.values())}, **counts)
        latest = [self.st.latest(h["id"]) or h for h in hyps]
        out["from_exploration"] = sum(1 for h in latest if not is_withheld(h)
                                      and (h.get("body") or {}).get("origin") == "from_exploration")
        return out

    def test_counts_of(self, hyps):
        st, counts = self.st, {o: 0 for o in OUTCOMES}
        for h in hyps:
            for root in (st.decided_plans_for(h["id"]) if st.strict else {}):
                v = self.verdicts.get((h["id"], root))
                if v is not None and v["body"].get("to") in counts:
                    counts[v["body"]["to"]] += 1
        return dict({"total": sum(counts.values())}, **counts)

    def export_paper(self, lab_aid):
        runs = [e for e in self.st.events if e["type"] == "run"]
        visible = [r for r in runs if not is_withheld(r)]
        confirmatory = sum(r["body"].get("label") == "confirmatory" for r in visible)
        if len(visible) < len(runs):
            self.todo("paper.exploration.runs", f"{len(runs) - len(visible)} runs are withheld; they are counted as "
                                                f"exploratory and not failed; correct the counts if needed")
        all_questions = sum(1 for e in self.roots if e["type"] == "question")
        exploration = {
            "lab_record": lab_aid,
            "questions": len(self.questions) if self.questions is not None else all_questions,
            "hypotheses": self.hypothesis_counts(self.hyps),
            "tests": dict({"total": sum(self.test_counts.values())}, **self.test_counts),
            "runs": {"total": len(runs), "confirmatory": confirmatory, "exploratory": len(runs) - confirmatory,
                     "failed": sum(r["body"].get("exit_status") != "success" for r in visible)},
        }
        if self.paper:
            others = [{"name": (e.get("body") or {}).get("name"),
                       "questions": [self.st.root(q) for q in (e.get("body") or {}).get("questions") or []]}
                      for root, e in self.st.papers.items() if root != self.paper.get("_id")]
            exploration["covers"] = {
                "questions": self.questions,
                "lab": {"questions": all_questions, "hypotheses": self.hypothesis_counts(self.all_hyps),
                        "tests": self.test_counts_of(self.all_hyps)},
            }
            if others:
                exploration["covers"]["other_papers"] = sorted(others, key=lambda x: x["name"] or "")
        paper = {"contributions": [], "autonomy": "unknown",
                 "contribution_record": "partial" if self.withheld_actors else "complete",
                 "origin": "native", "exploration": exploration}
        if self.st.study:
            paper["study"] = self.st.study
        title = (self.paper or {}).get("title") or self.body("INIT").get("working_title")
        if title:
            paper = dict({"title": title}, **paper)
        else:
            self.todo("paper.title", "give the title (the record's working title is withheld)")
        self.completion[:0] = [
            {"where": "paper.licence", "what": "ask the supervisor or guarantor which licence applies "
                                               "(SPDX identifier)"},
            {"where": "contributors", "what": "ask who the guarantor is: one person, with an ORCID iD, who submits "
                                              "the claimset; give them the guarantor position"},
            {"where": "paper.contributions", "what": "choose the principal claims, set their role to principal and "
                                                     "list them in priority order"},
            {"where": "paper.highlights", "what": "propose up to five principal claims and terms the paper "
                                                 "introduces, in priority order, with a line on why each; ask the "
                                                 "guarantor to choose and record what they decide, or leave the "
                                                 "field out if they prefer none (claimset §3.1, W39)"},
            {"where": "paper.autonomy", "what": "set autonomy (exported as unknown): autonomous, human_supervised or "
                                                "human_assisted"},
            {"where": "paper.classification.keywords", "what": "propose keywords"},
            {"where": "definitions", "what": "check the definitions exported from the record's terms, and add any "
                                             "the claims need that the record lacks, each with its kind; each method "
                                             "or model of the study's own that a planned test compares gives every "
                                             "equation that defines it as the code of the runs implements it (a "
                                             "variant with its own equations in full), checked against that code "
                                             "(claimset §3.2, W26); remove definitions this paper does not use; the "
                                             "supervisor's approval covers the definitions too"},
            {"where": "paper.contribution_record", "what": "confirm that every contributor is listed (exported from "
                                                           "everyone who wrote to the lab record)"},
        ]
        return paper

    def export_terms(self):
        """Definitions from the record's terms (§5.19), in record order, and the term IDs in statements, abouts
        and setups replaced by definition IDs."""
        st = self.st
        dmap, definitions = {}, []
        for e in self.roots:
            if e["type"] != "term":
                continue
            cur = st.latest(e["id"])
            if is_withheld(cur):
                self.todo("definitions", f"term {cur['id']} is withheld; define it if a claim needs it")
                continue
            did = f"D{len(definitions) + 1}"
            for v in self.versions(e["id"]):
                dmap[v] = did
            kind = cur["body"].get("kind")
            d = {"id": did, "term": cur["body"].get("term"), "kind": RENAMED_KINDS.get(kind, kind),
                 "definition": cur["body"].get("definition")}
            from .qualitative import code_of
            if isinstance(cur["body"].get("ext"), dict):
                d["ext"] = json.loads(json.dumps(cur["body"]["ext"]))   # a term's blocks are its definition's (§9)
            code = code_of(cur["body"])
            if isinstance(code, dict):          # a code of the codebook (records before v0.20 had it on the term)
                self.ext_block(d, "qualitative")["code"] = code
            if cur["body"].get("broader"):
                d["_broader"] = list(cur["body"]["broader"])
            if cur["body"].get("source"):
                d["source"] = cur["body"]["source"]
                self.todo(f"definitions.{did}.source", f"{did} ({d['term']}) is borrowed: list its source "
                                                        f"({cur['body']['source']}) in references and point source "
                                                        f"at that entry (B1, …)")
            definitions.append(d)
            self.mapping[did] = cur["id"]

        def swap(v):
            return dmap.get(v.strip(), v) if isinstance(v, str) and TERM_ID_RE.match(v.strip()) else v
        self.dmap = dmap

        for d in definitions:
            if "_broader" in d:
                d["broader"] = [dmap[b] for b in d.pop("_broader") if b in dmap]
                if not d["broader"]:
                    del d["broader"]

        def marks(text):
            return TERM_MARK_RE.sub(lambda m: m.group(0).replace(m.group(1), dmap.get(m.group(1), m.group(1)), 1),
                                    text) if isinstance(text, str) else text

        for c in self.claims:
            c["statement"] = marks(c.get("statement"))
            for spec in (((c.get("ext") or {}).get("qualitative") or {}).get("counts") or {}).values():
                if isinstance(spec, dict):
                    spec["codes"] = [swap(x) for x in spec.get("codes") or []]
            ab = c.get("about")
            if isinstance(ab, dict):
                c["about"] = {"subject": swap(ab.get("subject")), "relation": ab.get("relation"),
                              "object": [swap(x) for x in ab["object"]] if isinstance(ab.get("object"), list)
                              else swap(ab.get("object")),
                              "comparator": swap(ab.get("comparator")),
                              "conditions": [swap(x) for x in ab.get("conditions") or []]}
            elif "assumption" not in {s.get("kind") for s in c.get("support") or []}:
                self.todo(f"claims.{c['id']}.about", f"give the about of {c['id']}: its atom as subject, relation, "
                                                     f"object, comparator and conditions (required if it is "
                                                     f"principal; record it on the hypothesis next time)")
        by_name = {d["term"].strip().lower(): d["id"] for d in definitions
                   if isinstance(d.get("term"), str) and d.get("kind") == "variable"}

        def named(var):
            """A variable by its term's definition ID, when a term of kind variable has its name."""
            return by_name.get(var.strip().lower(), var) if isinstance(var, str) else var
        for c in self.claims:          # a test's quantities and an estimate's estimands bind by the same names
            for q in list(((c.get("test") or {}).get("quantities") or {}).values()) + list(
                    ((c.get("estimate") or {}).get("estimands") or {}).values()):
                if isinstance(q, dict) and isinstance(q.get("variable"), str) and not q["variable"].startswith("count:"):
                    q["variable"] = named(q["variable"])
                    if isinstance(q.get("conditions"), dict):
                        q["conditions"] = {swap(k): swap(v) for k, v in q["conditions"].items()}
        for ev in self.evidence:
            if isinstance(ev.get("description"), str):     # term IDs written in a plan's design or analysis
                ev["description"] = re.sub(r"\b(?:AC\d+\.)?TM\d+\b", lambda m: dmap.get(m.group(0), m.group(0)),
                                           TERM_MARK_RE.sub(lambda m: m.group(0).replace(
                                               m.group(1), dmap.get(m.group(1), m.group(1)), 1), ev["description"]))
            for res in ev.get("results") or []:
                res["variable"] = named(res.get("variable"))
                if isinstance(res.get("conditions"), dict):
                    res["conditions"] = {swap(k): swap(v) for k, v in res["conditions"].items()}
            for tb in ev.get("tables") or []:
                if isinstance(tb.get("conditions"), dict):
                    tb["conditions"] = {swap(k): swap(v) for k, v in tb["conditions"].items()}
                tb["row_labels"] = [swap(k) for k in tb.get("row_labels") or []]
                tb["columns"] = [named(c) if isinstance(c, str) else dict(
                    c, variable=named(c.get("variable")),
                    **({"conditions": {swap(k): swap(v) for k, v in c["conditions"].items()}}
                       if isinstance(c.get("conditions"), dict) else {})) for c in tb.get("columns") or []]
                for row in tb.get("rows") or []:
                    row["label"] = [swap(x) for x in row.get("label") or []]
            if isinstance(ev.get("setup"), dict):
                ev["setup"] = {role: [swap(i) for i in ids] for role, ids in ev["setup"].items()}
            elif ev.get("profile") != "formal":
                self.todo(f"evidence.{ev['id']}.setup", f"give the setup of {ev['id']}: the definitions of what it "
                                                        f"studied, on what cases, by what procedure, through what "
                                                        f"lens (record it on the plan next time)")
        return definitions

    def run(self):
        self.export_contributors()
        self.export_hypotheses()
        self.export_estimates()
        self.export_checks()
        self.export_assumptions()
        self.link_premises()
        self.ask_background()
        definitions = self.export_terms()
        for c in self.claims:
            c.pop("_targets", None)
            c.pop("_premises", None)
            c.pop("_linked", None)
        lab_aid = self.export_artefacts()
        self.round_values()
        paper = self.export_paper(lab_aid)
        self._paper = paper
        for _name, impl, _mod in self.st.declared():       # the lab parts of extensions (§2.1)
            if impl is not None and hasattr(impl, "export"):
                impl.export(self)
        self.synthesis_from_premises()
        draft = {"schema_version": SPEC_VERSION, "paper": paper, "contributors": self.contributors,
                 "models": self.models, "definitions": definitions, "claims": self.claims, "evidence": self.evidence,
                 "warrants": self.warrants, "limitations": self.limitations, "artefacts": self.artefacts}
        if self.references:
            draft["references"] = self.references
        used = self.extensions_used(draft)
        if used:
            draft["extensions"] = used
        return {"draft": draft, "completion": self.completion, "mapping": self.mapping, "files": self.files}

    def export_results_csv(self):
        """Every result of the record, at full precision, as a CSV beside the claimset (§9), named by the evidence
        objects and tables that hold results; or nothing, when no evidence holds a result."""
        import hashlib
        events = [e for e in self.st.events if e["type"] == "result" and not is_withheld(e)]
        users = [ev for ev in self.evidence if RESULTS_CSV in (ev.get("artefacts") or [])]
        aid = None
        if events and users:
            text = _tables.csv_text(events)
            self.files[self.results_path] = text
            aid = f"A{len(self.artefacts) + 1}"
            runs = {e["body"].get("run") for e in events}
            self.artefacts.append({
                "id": aid, "kind": "data", "uri": self.results_path,
                "version": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "availability": {"level": "public"},
                "description": f"Every result of the lab record ({len(events)} results of {len(runs)} runs) at full "
                               f"precision: the lab result's ID, its run, the quantity as the run's script named it, "
                               f"its conditions and its value (both as JSON). The evidence's tables give the values "
                               f"to four significant digits.",
                "columns": json.loads(json.dumps(_tables.CSV_COLUMNS))})
            self.mapping[aid] = self.results_path
        for ev in self.evidence:
            if RESULTS_CSV in (ev.get("artefacts") or []):
                ev["artefacts"] = [x for x in (aid if x == RESULTS_CSV else x for x in ev["artefacts"]) if x]
                if not ev["artefacts"]:
                    del ev["artefacts"]
            for tb in ev.get("tables") or []:
                if tb.get("artefact") == RESULTS_CSV:
                    if aid:
                        tb["artefact"] = aid
                    else:
                        del tb["artefact"]

    def round_values(self):
        """Table values and results to four significant digits, except those a test's quantity binds, which keep the
        precision the verdict was computed at (claimset §3.4, *Tables are the standard form*)."""
        evidence = {ev["id"]: ev for ev in self.evidence}
        exact = set()
        for c in self.claims:
            quantities = list(((c.get("test") or {}).get("quantities") or {}).values()) + list(
                ((c.get("estimate") or {}).get("estimands") or {}).values())
            for s in c.get("support") or []:
                ev = evidence.get(s.get("evidence"))
                if not ev or not quantities:
                    continue
                for where, var, conds, _value, _unit in _claimset.observations(ev):
                    if any(isinstance(q, dict) and q.get("variable") == var and all(
                            k in conds and conds[k] == v for k, v in (q.get("conditions") or {}).items())
                           for q in quantities):
                        exact.add((ev["id"], where))
        for ev in self.evidence:
            for i, res in enumerate(ev.get("results") or []):
                if (ev["id"], f"results[{i}]") not in exact:
                    res["value"] = _tables.rounded(res.get("value"))
            for i, tb in enumerate(ev.get("tables") or []):
                for j, row in enumerate(tb.get("rows") or []):
                    row["values"] = [v if (ev["id"], f"tables[{i}].rows[{j}].values[{k}]") in exact
                                     else _tables.rounded(v) for k, v in enumerate(row.get("values") or [])]

    def extensions_used(self, draft):
        """{name: version} of the extensions whose blocks the draft has, at the versions the record declared."""
        names = set()

        def walk(x):
            if isinstance(x, dict):
                if isinstance(x.get("ext"), dict):
                    names.update(x["ext"])
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(draft)
        from .. import extensions as _ext
        return {n: self.st.extensions.get(n) or _ext.latest(n) for n in sorted(names)}


def export(lab, paper=None, results_path=None):
    """Return {"draft", "completion", "mapping", "files"}. Raises LabError if a precondition of §9 fails.
    `paper`: the body of a paper event (see select_paper): only its questions are exported. `files`: {path relative
    to the claimset: text} of the files to write beside it (the CSV of every result, at `results_path`, by default
    files/results.csv)."""
    return _Exporter(lab, paper, results_path).run()


#: What a completed claimset keeps exactly as export wrote it from the record (lab record §9): the record decides
#: them, and completing the claimset never changes them.
RECORD_FIELDS = ("hypothesis", "planning", "planned_at", "planned_at_anchor")
TEST_FIELDS = ("framework", "parameters", "supported", "not_supported", "flags", "verdict", "registration")
ESTIMATE_FIELDS = ("runs", "lab_plan", "flags", "not_obtained")


def _model_keys(doc, kind="agent"):
    """{(provider, name, version)} of the models the claimset's agent contributors name."""
    models = {m.get("id"): m for m in doc.get("models") or [] if isinstance(m, dict)}
    out = set()
    for c in doc.get("contributors") or []:
        if isinstance(c, dict) and c.get("type") == kind:
            for ref in c.get("models") or []:
                m = models.get(ref.get("model") if isinstance(ref, dict) else ref) or {}
                out.add((m.get("provider"), m.get("name"), m.get("version")))
    return out


def check(lab, doc, paper=None):
    """What a completed claimset changed of what export takes from the record (lab record §9): the claims of the
    record's planned tests, hypotheses and planned estimates, their outcome, planning, test and estimate, the
    exploration counts, and the models of the agents that did the work. [message]; empty when it keeps them all."""
    fresh = export(lab, paper)["draft"]
    out = []

    def key(c):
        if isinstance(c.get("hypothesis"), dict):
            return ("hypothesis", c["hypothesis"].get("lab_event"), (c.get("test") or {}).get("lab_plan"))
        if isinstance(c.get("estimate"), dict):
            return ("estimate", c["estimate"].get("lab_plan"), None)
        return None
    mine = {key(c): c for c in doc.get("claims") or [] if isinstance(c, dict) and key(c)}
    for c in fresh["claims"]:
        k = key(c)
        if not k or not k[1]:
            continue
        got = mine.get(k)
        if got is None:
            what = (f"hypothesis {k[1]}" + (f" under {k[2]}" if k[2] else "") if k[0] == "hypothesis"
                    else f"the planned estimate of {k[1]}")
            out.append(f"the claim of {what} ({c['id']} in the export) is gone: a result of the record stays in the "
                       f"claimset, whatever its outcome")
            continue
        for f in RECORD_FIELDS:
            if got.get(f) != c.get(f):
                out.append(f"{got.get('id')}.{f} is {json.dumps(got.get(f))}, but the record gives "
                           f"{json.dumps(c.get(f))}")
        for block, fields in (("test", TEST_FIELDS), ("estimate", ESTIMATE_FIELDS)):
            for f in fields:
                a, b = (got.get(block) or {}).get(f), (c.get(block) or {}).get(f)
                if a != b:
                    out.append(f"{got.get('id')}.{block}.{f} is {json.dumps(a)}, but the record gives "
                               f"{json.dumps(b)}")
    a, b = (doc.get("paper") or {}).get("exploration"), (fresh.get("paper") or {}).get("exploration")
    if a != b:
        out.append(f"paper.exploration is {json.dumps(a)}, but the record gives {json.dumps(b)}")
    for provider, name, version in sorted(_model_keys(fresh) - _model_keys(doc), key=str):
        out.append(f"the model {provider} {name} {version} of an agent that did the work is gone from the "
                   f"contributors: keep the models the record names; add your own as another agent contributor")
    return out

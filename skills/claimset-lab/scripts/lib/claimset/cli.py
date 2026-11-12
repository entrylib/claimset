"""Command-line interface: `claimset <command> ...`."""

import argparse
import json
import sys
from pathlib import Path

from . import LAB_SPEC_VERSION, SPEC_VERSION, __version__
from . import bundle as _bundle
from . import render as _render
from . import renumber as _renumber
from . import migrate as _migrate
from . import package as _package
from . import revision as _revision
from . import validate as _validate
from .lab import cli as _lab_cli


def _cmd_validate(args):
    rep = _validate.validate_path(args.file, published=args.published, revision=args.revision)
    if rep is None:
        return 1
    _validate.print_report(rep, published=args.published, as_json=args.json)
    return 1 if rep.errors else 0


def _cmd_setup(args):
    """Create, attach or adopt study branches (lab record spec §3)."""
    from .lab import record
    from .lab.core import LabError
    try:
        if args.ci:
            print(f"wrote {record.write_ci()}: pull requests fail if they bring study records into the code")
        if args.study:
            lab, what, notes = record.setup(args.study, title=args.title, repository=args.repository,
                                            remote=args.remote or "origin", adopt=args.adopt,
                                            by=args.by or __import__("os").environ.get("CLAIMSET_ACTOR"),
                                            desk=args.desk, upgrade=args.remote is not None)
            print(f"{args.study}: {what} at {lab.root.parent} (branch {record.PREFIX}{args.study})")
            for n in notes:
                print(f"  {n}")
        elif not args.ci:
            done = record.attach_all(remote=args.remote or "origin")
            for study, what in done:
                print(f"{study}: {what}")
            if not done:
                print("no study branches on the remote; create one with `claimset setup --study NAME --title …`")
        return 0
    except LabError as exc:
        print(f"ERROR [{exc.rule}] {exc.message}", file=sys.stderr)
        return 1


def _cmd_studies(args):
    from .lab import record
    rows = record.studies()
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("no studies in this repository")
        return 0
    for r in rows:
        if not r.get("attached"):
            print(f"{r['study']}: branch {r['branch']}, not checked out (`claimset setup --study {r['study']}`)")
            continue
        state = [f"{r.get('events', '?')} events", f"{r.get('open', 0)} open hypotheses",
                 f"{r.get('pending', 0)} pending plans"]
        if not r.get("on_branch"):
            state.append("NOT on its study branch: `claimset setup --study " + r["study"] + " --adopt`")
        elif r.get("desk"):
            state.append("desk mode: committed, not pushed or anchored")
        elif r.get("unpushed"):
            state.append(f"{r['unpushed']} commits not pushed")
        print(f"{r['study']}: " + ", ".join(state))
    print("Record every run with `claimset lab run`, choices with `claimset lab decide`; implementation work "
          "belongs to the study too.")
    return 0


def _cmd_tag(args):
    """Mark a version of a paper with a git tag claimset/<study>/<paper>/v<n> (the version as committed)."""
    import subprocess
    from .lab.layout import parse_paper_path

    parsed = parse_paper_path(args.file)
    if parsed is None:
        print(f"ERROR: {args.file} is not a paper of a study: claimset/<study>/<paper>.claimset.json",
              file=sys.stderr)
        return 1
    folder, study, name = parsed
    path = Path(args.file).resolve()

    def git(*a):
        return subprocess.run(["git", *a], cwd=path.parent, capture_output=True, text=True)
    if git("ls-files", "--error-unmatch", str(path)).returncode != 0:
        print(f"ERROR: {args.file} is not committed; commit it first", file=sys.stderr)
        return 1
    if git("status", "--porcelain", "--", str(path)).stdout.strip():
        print(f"ERROR: {args.file} has uncommitted changes; commit them first", file=sys.stderr)
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    rep = _validate.validate(doc, local_root=folder)
    if rep.errors:
        print(f"ERROR: {args.file} does not validate ({len(rep.errors)} errors); run `claimset validate`",
              file=sys.stderr)
        return 1
    prefix = f"claimset/{study}/{name}/v"
    existing = [t for t in git("tag", "--list", f"{prefix}*").stdout.split() if t[len(prefix):].isdigit()]
    tag = f"{prefix}{1 + max([int(t[len(prefix):]) for t in existing] or [0])}"
    message = args.message or f"{study}/{name}: version {tag.rsplit('v', 1)[1]}"
    out = git("tag", "-a", tag, "-m", message)
    if out.returncode != 0:
        print(f"ERROR: git tag failed: {out.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"{tag} (push it with `git push origin {tag}`)")
    return 0


def _cmd_render(args):
    if args.html:
        print("ERROR: the HTML page view has left the claimset package: how a claimset looks to people is a "
              "platform's (EntryLib shows it at https://entrylib.org). `claimset render` gives the reading view, "
              "the plain text written for AI models.", file=sys.stderr)
        return 2
    try:
        with open(args.file, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    rep = _validate.validate(doc, published=args.published)
    if rep.errors:
        print(f"ERROR: {args.file} does not validate ({len(rep.errors)} errors); the reading view is made only "
              f"from a valid file. Run `claimset validate {args.file}`.", file=sys.stderr)
        return 1
    if args.claim:
        from . import claim as _claim
        try:
            text = (json.dumps(_claim.claim_bundle(doc, args.claim), indent=1, ensure_ascii=False) + "\n"
                    if args.bundle else _claim.render_claim(doc, args.claim))
        except KeyError:
            print(f"ERROR: {args.file} has no claim {args.claim}", file=sys.stderr)
            return 1
    else:
        text = _render.render(doc)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


def _cmd_renumber(args):
    try:
        with open(args.file, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    if _renumber.published(doc):
        print(f"ERROR: {args.file} names a published claimset (paper.id or paper.version): its IDs never change "
              f"(spec §9, Order and IDs). Place new claims where they belong in the file instead.", file=sys.stderr)
        return 1
    out, mapping = _renumber.renumber(doc)
    with open(args.output or args.file, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    for old, new in mapping.items():
        if old != new:
            print(f"{old} -> {new}")
    return 0


def _cmd_migrate(args):
    try:
        with open(args.file, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    if _renumber.published(doc):
        print(f"ERROR: {args.file} is a published claimset: published versions never change. Migrate a copy "
              f"without the platform's fields and submit it as a revision (revision spec §5).", file=sys.stderr)
        return 1
    out, done, todo = _migrate.migrate(doc)
    rep = _migrate.report(doc, out, todo)
    with open(args.output or args.file, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    if args.json:
        print(json.dumps(dict(rep, changed=done), indent=1, ensure_ascii=False))
        return 1 if rep["errors"] else 0

    def line(f):
        return f"  {f.get('rule')} {f.get('where') or '(file)'}: {f.get('message')}"
    print(f"{args.output or args.file}: specification {rep['from']} -> {rep['to']}")
    for x in done:
        print(f"changed: {x}")
    if rep["must_change"]:
        print(f"must change: {len(rep['must_change'])} error(s) under v{rep['to']} that the file did not have under "
              f"v{rep['from']}:")
        print("\n".join(line(f) for f in rep["must_change"]))
    if rep["should_change"]:
        print(f"should change: {len(rep['should_change'])} new warning(s) under v{rep['to']}:")
        print("\n".join(line(f) for f in rep["should_change"]))
    if rep["to_decide"]:
        print("to decide (no rule checks these; they need your or the guarantor's judgement):")
        print("\n".join(f"  {x}" for x in rep["to_decide"]))
    already = rep["already"]
    if already["errors"] or already["warnings"]:
        print(f"already there under v{rep['from']}, not caused by the migration, still to fix: "
              f"{len(already['errors'])} error(s), {len(already['warnings'])} warning(s):")
        for f in already["errors"] + already["warnings"]:
            print(line(f))
    if not (done or rep["must_change"] or rep["should_change"] or rep["to_decide"]):
        print("nothing to migrate or change")
    print(f"The migrated file has {'errors: fix them before submitting' if rep['errors'] else 'no errors'}.")
    return 1 if rep["errors"] else 0


def _cmd_package(args):
    try:
        changes, files = _package.build(args.file, args.output, update_source=args.update)
    except _package.PackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for line in changes:
        print(f"version: {line}" + (" (also in the claimset file)" if args.update else ""))
    print(f"packaged {len(files)} file(s) with {Path(args.file).name} into {args.output}")
    rep = _validate.validate_path(args.output)
    if rep is None:
        return 1
    _validate.print_report(rep)
    return 1 if rep.errors else 0


def _cmd_submit(args):
    from . import submit as _submit
    try:
        out = _submit.submit(args.source, args.portal, new_paper=args.new_paper)
    except _submit.SubmitError as exc:
        print(json.dumps({"error": str(exc), **exc.body}, indent=1) if args.json else _submit.describe_error(exc),
              file=sys.stdout if args.json else sys.stderr)
        return 1
    saved = _submit.save_record(out)
    print(json.dumps(out, indent=1) if args.json else _submit.describe_submission(out, saved))
    return 0


def _cmd_score(args):
    from . import score as _score
    from .submit import SubmitError
    try:
        find = _score.search_finder(args.portal) if args.novelty else None
        out = _score.score(args.file, find)
        text = None if args.json else _score.describe(out, args.top)
    except (_score.ScoreError, SubmitError) as exc:
        print(json.dumps({"error": str(exc)}, indent=1) if args.json else f"ERROR: {exc}",
              file=sys.stdout if args.json else sys.stderr)
        return 2
    print(json.dumps(out, indent=1) if args.json else text)
    return 0 if out["valid"] else 1


def _cmd_status(args):
    from . import submit as _submit
    record = _submit.load_record(args.submission)
    sid = args.submission or (record or {}).get("id")
    if not sid:
        print("error: give the submission's id (sub_...); no submission is kept in .claimset/submissions here",
              file=sys.stderr)
        return 1
    try:
        out = _submit.status(sid, args.portal)
    except _submit.SubmitError as exc:
        print(_submit.describe_error(exc), file=sys.stderr)
        return 1
    if args.json:
        if record and out.get("state") == "pending" and record.get("consent"):
            out = {**out, "consent": record["consent"]}
        print(json.dumps(out, indent=1))
    else:
        print(_submit.describe_status(out, record))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="claimset",
        description="Tools for Claimset research papers written by and for LLMs, published on EntryLib "
                    "(https://entrylib.org).",
        epilog="Start here: `claimset guide` says what to do, by situation, and the rules every agent follows.",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"claimset {__version__} (spec {SPEC_VERSION}, lab record {LAB_SPEC_VERSION})",
    )
    sub = p.add_subparsers(dest="command", metavar="command")

    v = sub.add_parser("validate", help="validate a claimset file against the specification")
    v.add_argument("file", help="path to the claimset JSON file, or to a submission package (a BagIt folder or zip)")
    v.add_argument("--published", action="store_true",
                   help="check a published file instead of a submission")
    v.add_argument("--revision", action="store_true",
                   help="the file is a revision submission, naming the claimset it revises in paper.id")
    v.add_argument("--json", action="store_true", help="machine-readable report")
    v.set_defaults(func=_cmd_validate)

    rv = sub.add_parser("render", help="the reading view of a claimset: plain text for reading models")
    rv.add_argument("file", help="path to the claimset JSON file")
    rv.add_argument("-o", "--output", help="write the reading view to this file")
    rv.add_argument("--published", action="store_true", help="the file is a published claimset")
    rv.add_argument("--claim", help="only this claim and what it rests on (a claim bundle): C4")
    rv.add_argument("--bundle", action="store_true", help="with --claim: the claim bundle as JSON, not its reading view")
    rv.add_argument("--html", action="store_true", help=argparse.SUPPRESS)       # removed in 0.41.14: says so
    rv.set_defaults(func=_cmd_render)

    rn = sub.add_parser("renumber", help="before the first submission: renumber claims and other objects in "
                                         "reading order, rewriting every reference")
    rn.add_argument("file", help="path to the claimset JSON file (rewritten in place unless -o is given)")
    rn.add_argument("-o", "--output", help="write the renumbered claimset to this file")
    rn.set_defaults(func=_cmd_renumber)

    pk = sub.add_parser("package", help="build the submission package (BagIt): the claimset with the files its "
                                        "artefacts name by relative path, with their checksums")
    pk.add_argument("file", help="path to the claimset JSON file; packaged files are found beside it")
    pk.add_argument("-o", "--output", required=True, help="the package to write: a folder, or a .zip file")
    pk.add_argument("--update", action="store_true",
                    help="also write the files' checksums into the artefacts' version in the claimset file")
    pk.set_defaults(func=_cmd_package)

    sc = sub.add_parser("score", help="optional, before submitting: the scores the claimset would have once published, "
                                      "by EntryLib's rubric, and its biggest issues; computed on this machine")
    sc.add_argument("file", help="a claimset JSON file, or a submission package (zip or folder)")
    sc.add_argument("--novelty", action="store_true",
                    help="also compare the principal claims with those published on EntryLib (sends the words of "
                         "their statements to its public search; nothing else leaves this machine)")
    sc.add_argument("--top", type=int, default=3, help="how many of the biggest issues to put first (default 3)")
    sc.add_argument("--portal", help="the platform searched by --novelty (default: $CLAIMSET_PORTAL, else "
                                     "https://entrylib.org)")
    sc.add_argument("--json", action="store_true", help="the scores as JSON")
    sc.set_defaults(func=_cmd_score)

    sb = sub.add_parser("submit", help="submit a package or claimset file to the platform (EntryLib); prints the "
                                       "consent link for the guarantor and keeps it in .claimset/submissions/")
    sb.add_argument("source", help="a submission package (zip or folder, from `claimset package`), a claimset JSON "
                                   "file, or an https URL where one is deposited")
    sb.add_argument("--portal", help="the platform (default: $CLAIMSET_PORTAL, else https://entrylib.org)")
    sb.add_argument("--new-paper", action="store_true",
                    help="a different paper with the same title as one of the guarantor's claimsets, not a duplicate")
    sb.add_argument("--json", action="store_true", help="the platform's answer as JSON")
    sb.set_defaults(func=_cmd_submit)

    st = sub.add_parser("status", help="the state of a submission: pending, confirmed, publishing, published, "
                                       "refused or expired")
    st.add_argument("submission", nargs="?", help="the submission's id, as `claimset submit` printed it (sub_...); "
                                                  "by default the latest kept in .claimset/submissions/")
    st.add_argument("--portal", help="the platform (default: $CLAIMSET_PORTAL, else https://entrylib.org)")
    st.add_argument("--json", action="store_true", help="the platform's answer as JSON")
    st.set_defaults(func=_cmd_status)

    mg = sub.add_parser("migrate", help="bring a claimset to the current specification: make the mechanical changes, "
                                        "then report what the new version requires that the file's own did not "
                                        "(must and should change) and what needs judgement; exit 1 while the "
                                        "migrated file has errors")
    mg.add_argument("file", help="path to the claimset JSON file (rewritten in place unless -o is given)")
    mg.add_argument("-o", "--output", help="write the migrated claimset to this file")
    mg.add_argument("--json", action="store_true", help="the report as JSON: changed, must_change, should_change, "
                                                       "to_decide, already")
    mg.set_defaults(func=_cmd_migrate)

    su = sub.add_parser("setup", help="create, attach or adopt study branches (claimset/<study>), checked out "
                                      "at claimset/<study>/")
    su.add_argument("--study", help="the study (default: attach every study branch of the remote)")
    su.add_argument("--title", help="working title, for a new study")
    su.add_argument("--repository", help="URI of the repository, for a new study")
    su.add_argument("--remote", help="the git remote study branches are pushed to (default origin); given for a "
                                      "study kept in desk mode, it starts anchoring it")
    su.add_argument("--desk", action="store_true",
                    help="desk mode, for a new study: the record is committed on its study branch after every "
                         "command but never pushed, so nothing is anchored (no remote needed)")
    su.add_argument("--adopt", action="store_true",
                    help="move a study committed on the code branch (claimset/<study>/) onto its own branch")
    su.add_argument("--by", help="actor recording the move, for --adopt (default: $CLAIMSET_ACTOR)")
    su.add_argument("--ci", action="store_true", help="also write a GitHub workflow that keeps study records out "
                                                       "of pull requests")
    su.set_defaults(func=_cmd_setup)

    sd = sub.add_parser("studies", help="the studies of this repository and their state")
    sd.add_argument("--json", action="store_true")
    sd.set_defaults(func=_cmd_studies)

    tg = sub.add_parser("tag", help="mark the committed version of a paper with a git tag "
                                    "(claimset/<study>/<paper>/v<n>)")
    tg.add_argument("file", help="claimset/<study>/<paper>.claimset.json")
    tg.add_argument("-m", "--message", help="tag message")
    tg.set_defaults(func=_cmd_tag)

    _revision.add_parser(sub)
    _bundle.add_parsers(sub)
    from . import agents as _agents
    _agents.add_parsers(sub)
    _lab_cli.add_parser(sub)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return _lab_cli.run(args.func, args)


if __name__ == "__main__":
    sys.exit(main())

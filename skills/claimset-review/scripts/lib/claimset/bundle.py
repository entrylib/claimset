"""The specifications and agent skills that match this package (`claimset spec`, `claimset skill ...`).

The package carries the texts of its specifications, the examples and the skills' instructions, so an
installed package can always print the specification it validates against and install skills that use
it. A skill copied into a project once does not follow later versions; `claimset skill check` finds such
copies and `claimset skill install` replaces them.
"""

import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

from . import LAB_SPEC_VERSION, REVISION_SPEC_VERSION, SPEC_VERSION, __version__

PACKAGE = Path(__file__).resolve().parent
DATA = PACKAGE / "data"
SKILLS = ("claimset-submit", "claimset-from-paper", "claimset-lab", "claimset-revise", "claimset-review")
DEFAULT_DIR = ".claude/skills"


def spec_path(lab=False, revision=False):
    name = f"claimset-revision-v{REVISION_SPEC_VERSION}.md" if revision else \
        f"lab-record-v{LAB_SPEC_VERSION}.md" if lab else f"claimset-v{SPEC_VERSION}.md"
    path = DATA / "spec" / name
    if not path.exists():
        raise FileNotFoundError(f"this copy of claimset ({__version__}) carries no specification texts; install "
                                f"the package (pip install claimset)")
    return path


def _extension_specs():
    """{path inside a skill: source} for the specifications of the extensions (spec §2.7)."""
    return {f"references/extensions/{f.name}": f for f in sorted((DATA / "spec" / "extensions").glob("*.md"))}


def _package_modules():
    """The package's Python files, relative to the package directory."""
    return [f.relative_to(PACKAGE) for f in sorted(PACKAGE.rglob("*.py")) if "__pycache__" not in f.parts]


def files(name):
    """{path inside the skill: source file} for one skill, as this package would install it."""
    spec, lab, rev = spec_path(), spec_path(lab=True), spec_path(revision=True)
    rev_name = f"references/{rev.name.replace('claimset-revision-v', 'revision-v')}"
    if name == "claimset-submit":
        out = {"SKILL.md": DATA / "skills" / name / "SKILL.md",
               "scripts/validate.py": PACKAGE / "validate.py",
               f"references/{spec.name.replace('claimset-v', 'spec-v')}": spec,
               f"references/{lab.name}": lab}
        for ex in sorted((DATA / "examples").glob("*.json")):
            out[f"examples/{ex.name}"] = ex
        for sub in ("extensions", "versions"):            # imported by the validator beside it
            for f in sorted((PACKAGE / sub).glob("*.py")):
                out[f"scripts/{sub}/{f.name}"] = f
        out.update(_extension_specs())
        return out
    if name == "claimset-from-paper":                    # adds to claimset-submit, installed with it
        return {"SKILL.md": DATA / "skills" / name / "SKILL.md",
                f"references/{spec.name.replace('claimset-v', 'spec-v')}": spec,
                "examples/submission-native.json": DATA / "examples" / "submission-native.json"}
    if name in ("claimset-lab", "claimset-revise", "claimset-review"):
        out = {"SKILL.md": DATA / "skills" / name / "SKILL.md",
               "scripts/claimset": DATA / "skills" / "claimset-lab" / "claimset",
               f"references/{lab.name}": lab,
               rev_name: rev}
        if name in ("claimset-revise", "claimset-review"):
            out[f"references/{spec.name.replace('claimset-v', 'spec-v')}"] = spec
        out.update(_extension_specs())
        if name == "claimset-lab" and (DATA / PLANNING / "SOURCE.json").is_file():
            for f in sorted((DATA / PLANNING).iterdir()):
                if f.is_file():
                    out[f"references/{PLANNING}/{f.name}"] = f
        for rel in _package_modules():
            out[f"scripts/lib/claimset/{rel.as_posix()}"] = PACKAGE / rel
        return out
    raise ValueError(f"unknown skill '{name}': the skills are {', '.join(SKILLS)}")


def _is_claimset_skill(directory, name):
    md = directory / "SKILL.md"
    return md.exists() and f"name: {name}" in md.read_text(encoding="utf-8", errors="replace")[:500]


def check(directory, name):
    """Differences between an installed skill and this package's: [(path, what)]; empty when current."""
    target = Path(directory) / name
    if not target.exists():
        return [(name, "not installed")]
    want = files(name)
    out = []
    for rel, src in want.items():
        dst = target / rel
        if not dst.exists():
            out.append((rel, "missing"))
        elif not filecmp.cmp(src, dst, shallow=False):
            out.append((rel, "differs"))
    for f in sorted(target.rglob("*")):
        rel = f.relative_to(target).as_posix()
        if f.is_file() and "__pycache__" not in f.parts and rel not in want:
            out.append((rel, "not part of this version"))
    return out


def install(directory, name, force=False):
    """Install one skill into directory/name, replacing an earlier copy of the same skill. Returns
    "installed", "replaced" or "current"."""
    target = Path(directory) / name
    if target.exists():
        if not check(directory, name):
            return "current"
        if not (force or _is_claimset_skill(target, name)):
            raise FileExistsError(f"{target} exists and is not the {name} skill; use --force to replace it")
    Path(directory).mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=str(Path(directory).resolve())))
    try:
        for rel, src in files(name).items():
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        if name in ("claimset-lab", "claimset-revise", "claimset-review"):
            (staging / "scripts" / "claimset").chmod(0o755)
        existed = target.exists()
        if existed:
            shutil.rmtree(target)
        staging.rename(target)
        return "replaced" if existed else "installed"
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def cmd_spec(args):
    try:
        path = spec_path(lab=args.lab, revision=args.revision)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"{path.name} written to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


def installed_dirs(root="."):
    """The skills folders of the agents (claimset.agents) that hold a claimset skill."""
    from .agents import HARNESSES
    dirs = dict.fromkeys(d for h in HARNESSES for d in h.skills)
    return [d for d in dirs if any(_is_claimset_skill(Path(root) / d / n, n) for n in SKILLS)]


def cmd_skill(args):
    names = args.names or list(SKILLS)
    if args.dir is None:
        found = installed_dirs()
        if args.action == "check" and len(found) > 1:
            return max(cmd_skill(argparse_copy(args, dir=d)) for d in found)
        args = argparse_copy(args, dir=found[0] if found else DEFAULT_DIR)
    try:
        if args.action == "check":
            stale = 0
            for name in names:
                diff = check(args.dir, name)
                if not diff:
                    print(f"{name}: current (claimset {__version__}, spec {SPEC_VERSION})")
                    continue
                stale += 1
                print(f"{name}: out of date with claimset {__version__} (spec {SPEC_VERSION}); "
                      f"run `claimset skill install --dir {args.dir}`")
                for rel, what in diff[:20]:
                    print(f"  {rel}: {what}")
            return 1 if stale else 0
        for name in names:
            print(f"{name}: {install(args.dir, name, force=args.force)} in {Path(args.dir) / name} "
                  f"(claimset {__version__}, spec {SPEC_VERSION})")
        return 0
    except (FileNotFoundError, FileExistsError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def guide(name=None):
    """What `claimset guide` prints: where to start and the rules, or one skill's instructions."""
    from .agents import rules
    if name is None:
        text = (DATA / "agents" / "GUIDE.md").read_text(encoding="utf-8")
        return text.replace("{version}", __version__).replace("{spec}", SPEC_VERSION).replace("{rules}", rules())
    if name not in SKILLS:
        raise ValueError(f"unknown skill '{name}': the skills are {', '.join(SKILLS)}")
    note = (f"<!-- The {name} skill of claimset {__version__}. It names files kept beside it (references/, scripts/, "
            f"examples/): `claimset init`, or `claimset skill install {name} --dir DIR`, writes them. Without them, "
            f"`claimset spec` (--lab, --revision) prints the specifications and `claimset validate` checks a file. -->\n\n")
    return note + (DATA / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


PLANNING = "study-planning"
PLANNING_URL = "https://github.com/entrylib/study-planning"


def _planning_dir():
    """The copy of the study-planning guides: in the package's data, or beside an installed lab skill's scripts."""
    for d in (DATA / PLANNING, PACKAGE.parents[2] / "references" / PLANNING):
        if (d / "SOURCE.json").is_file():
            return d
    raise FileNotFoundError(f"this installation carries no copy of the study-planning guides; read them at "
                            f"{PLANNING_URL}")


def study_planning_guides():
    """The names of the guides this package carries (prediction, experiments, …)."""
    return [f.stem for f in sorted(_planning_dir().glob("*.md")) if f.name != "README.md"]


def study_planning(ref=None):
    """EntryLib's good practice for planning a study (https://github.com/entrylib/study-planning), from the copy
    this package carries, as text: the list of guides (`ref` None or 'study-planning'), one guide
    ('study-planning/prediction'), or one entry ('study-planning/prediction#mean-forecasts'): the references a plan
    cites with source good-practice. ValueError names the guides or entries when `ref` matches none."""
    import json
    folder = _planning_dir()
    source = json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
    rest = (ref or PLANNING).strip()
    if rest != PLANNING and not rest.startswith((PLANNING + "/", PLANNING + "#")):
        raise ValueError(f"'{ref}' is not a study-planning reference: write study-planning, "
                         f"study-planning/GUIDE or study-planning/GUIDE#ENTRY")
    rest = rest[len(PLANNING):].lstrip("/")
    name, _, entry = rest.partition("#")
    where = f"{PLANNING_URL}/blob/main/{name + '.md' if name else 'README.md'}"
    note = (f"<!-- EntryLib's good practice for planning a study, as {PLANNING_URL} was at commit "
            f"{source['commit'][:7]} ({source['date']}), carried by claimset {__version__}. The newest: {where} -->\n\n")
    if not name:
        if entry:
            raise ValueError(f"'{ref}': name a guide before an entry, e.g. study-planning/prediction#{entry}")
        return note + (folder / "README.md").read_text(encoding="utf-8")
    guides = study_planning_guides()
    if name not in guides:
        raise ValueError(f"no guide '{name}' in study-planning: the guides are {', '.join(guides)}")
    text = (folder / f"{name}.md").read_text(encoding="utf-8")
    if not entry:
        return note + text
    sections = _sections(text)
    if entry not in sections:
        raise ValueError(f"no entry '{entry}' in study-planning/{name}: the entries are "
                         f"{', '.join(k for k in sections if k not in ('Principle', 'References', 'Versions'))}")
    head = [line for line in text.split("\n")[:4] if line.startswith(("# ", "Version "))]
    cited = _cited(sections[entry], sections.get("References", ""))
    refs = ["## References\n\n" + "\n".join(cited)] if cited else []
    return note + "\n\n".join(head + [sections[entry].rstrip()] + refs) + "\n"


def _cited(entry, references):
    """The items of a guide's reference list that an entry cites as the guides do: "Gneiting 2011", "Gneiting and
    Raftery 2007", "Morris, White and Crowther 2019", "Nosek et al. 2018"."""
    import re
    items, out = [], []
    for line in references.split("\n")[1:]:
        if line.startswith("- "):
            items.append(line)
        elif line.startswith("  ") and items:
            items[-1] += "\n" + line
    text = " ".join(entry.split())
    for item in items:
        flat = " ".join(item[2:].split())
        year = re.search(r"\((\d{4})\)", flat)
        if not year:
            continue
        names = flat[:year.start()].replace(", and ", ", ").replace(" and ", ", ").split(", ")[0::2]
        if len(names) == 1:
            forms = [names[0]]
        elif len(names) == 2:
            forms = [f"{names[0]} and {names[1]}"]
        else:
            forms = [f"{names[0]} et al.", ", ".join(names[:-1]) + f" and {names[-1]}"]
        if any(re.search(rf"(?<![\w,] ){re.escape(f)} {year[1]}\b", text) for f in forms):
            out.append(item)
    return out


def _sections(text):
    """{heading: the section's text from its `## ` heading to the next one} of a guide."""
    out, current = {}, None
    for line in text.split("\n"):
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        if current is not None:
            out[current].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def cmd_guide(args):
    try:
        if args.skill and args.skill.split("/")[0].split("#")[0] == PLANNING:
            text = study_planning(args.skill)
        else:
            text = guide(args.skill)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


def argparse_copy(args, **changes):
    import argparse
    return argparse.Namespace(**dict(vars(args), **changes))


def add_parsers(sub):
    g = sub.add_parser("guide", help="start here: what to do, by situation, and the rules; or one skill's "
                                     "instructions (claimset guide claimset-submit)")
    g.add_argument("skill", nargs="?", help=f"print this skill's instructions: {', '.join(SKILLS)}; or "
                   f"study-planning, study-planning/GUIDE or study-planning/GUIDE#ENTRY: EntryLib's good practice "
                   f"for planning a study, the list, one guide or one entry")
    g.set_defaults(func=cmd_guide)

    s = sub.add_parser("spec", help="print the specification this package validates against")
    s.add_argument("--lab", action="store_true", help="the lab record specification instead")
    s.add_argument("--revision", action="store_true",
                   help="the revision specification (reviews, responses, revised versions, scores) instead")
    s.add_argument("-o", "--output", help="write it to this file")
    s.set_defaults(func=cmd_spec)

    k = sub.add_parser("skill", help="install or check the agent skills that match this package")
    k.add_argument("action", choices=["install", "check"])
    k.add_argument("names", nargs="*", metavar="skill", help=f"{', '.join(SKILLS)} (default: all)")
    k.add_argument("--dir", default=None,
                   help=f"the skills directory (default: every agent's skills folder that holds them, else "
                        f"{DEFAULT_DIR}; `claimset init` installs them for other agents)")
    k.add_argument("--force", action="store_true", help="replace a directory that is not a claimset skill")
    k.set_defaults(func=cmd_skill)

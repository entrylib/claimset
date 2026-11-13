#!/usr/bin/env python3
"""Copy EntryLib's good practice for planning a study into the package, from a checkout of its repository.

The guides are edited only in https://github.com/entrylib/study-planning. The package carries a copy, so that an
agent reads them with `claimset guide study-planning` where it cannot reach GitHub, and the lab skill carries them
in references/study-planning/. The copy records the commit it was taken from (SOURCE.json).

    git clone https://github.com/entrylib/study-planning ../study-planning
    python3 tools/sync_study_planning.py ../study-planning    # copy from the checkout's commit
    python3 tools/sync_study_planning.py --check              # the copy matches SOURCE.json; exit 1 if not

Copy from a commit on the repository's main branch, with nothing uncommitted; then run
`python3 tools/sync_skills.py`, which copies the guides into the lab skill.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src" / "claimset" / "data" / "study-planning"
REPOSITORY = "https://github.com/entrylib/study-planning"
NOT_COPIED = {"AGENTS.md", "CLAUDE.md"}          # instructions for working on that repository, not guides


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(checkout, *args):
    return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True, check=True).stdout.strip()


def wanted(checkout):
    """The files to copy: the README, the licence and every guide."""
    files = [f for f in sorted(Path(checkout).glob("*.md")) if f.name not in NOT_COPIED]
    return files + [Path(checkout) / "LICENSE"]


def check():
    """Differences between the copy and its SOURCE.json: a list of messages, empty when they match."""
    source = DEST / "SOURCE.json"
    if not source.exists():
        return [f"{source.relative_to(ROOT)} is missing: run tools/sync_study_planning.py with a checkout"]
    recorded = json.loads(source.read_text(encoding="utf-8"))["files"]
    present = {f.name for f in DEST.iterdir() if f.is_file() and f.name != "SOURCE.json"}
    out = [f"{name}: listed in SOURCE.json but missing" for name in sorted(set(recorded) - present)]
    out += [f"{name}: not listed in SOURCE.json" for name in sorted(present - set(recorded))]
    out += [f"{name}: changed since it was copied (edit it in {REPOSITORY}, then copy again)"
            for name in sorted(present & set(recorded)) if _sha256(DEST / name) != recorded[name]]
    return out


def copy(checkout):
    checkout = Path(checkout).resolve()
    if _git(checkout, "status", "--porcelain"):
        raise SystemExit(f"{checkout} has uncommitted changes: copy only from a commit")
    commit = _git(checkout, "rev-parse", "HEAD")
    date = _git(checkout, "show", "-s", "--format=%cs", "HEAD")
    try:
        _git(checkout, "merge-base", "--is-ancestor", "HEAD", "origin/main")
    except subprocess.CalledProcessError:
        print(f"warning: {commit[:7]} is not on origin/main of the checkout; copy a merged commit before release",
              file=sys.stderr)
    files = wanted(checkout)
    DEST.mkdir(parents=True, exist_ok=True)
    for old in DEST.iterdir():
        if old.is_file():
            old.unlink()
    for f in files:
        shutil.copyfile(f, DEST / f.name)
        print(f"copied {f.name}")
    record = {"repository": REPOSITORY, "commit": commit, "date": date,
              "files": {f.name: _sha256(DEST / f.name) for f in files}}
    (DEST / "SOURCE.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"study-planning at {commit[:7]} ({date}) -> {DEST.relative_to(ROOT)}; now run tools/sync_skills.py")


def main(argv):
    if argv == ["--check"]:
        diff = check()
        for line in diff:
            print(line)
        return 1 if diff else 0
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    copy(argv[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

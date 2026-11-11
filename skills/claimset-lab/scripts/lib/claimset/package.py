"""Building a submission package (spec §2.5): a BagIt bag (RFC 8493) holding the claimset and the files its
artefacts name by relative path.

    claimset package claimset/<study>/<paper>.claimset.json -o <paper>.zip

    build(claimset_path, out)        -> the bag of a claimset file and the files beside it
    build_from(doc, files, out)      -> the bag of a claimset and the contents of its files, sent without a folder
                                        (the platform's MCP server, `files`)

Each artefact whose `uri` is a relative path (`files/fig3.png`) is taken from beside the claimset file, copied to
`data/<uri>` in the bag, and its `version` set to `sha256:` followed by the file's checksum. The claimset is written
to `data/<name>`, and `bagit.txt` and `manifest-sha256.txt` list every file of the payload with its checksum.
A package that would break the limits of §2.5 (rule 77: file count, sizes, paths, file types) is not written.
"""

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .validate import folder_package_problems, is_relative_uri

BAGIT_TXT = "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n"


class PackageError(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe(uri):
    """A relative path that stays inside the payload."""
    p = PurePosixPath(uri)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise PackageError(f"'{uri}': a packaged file's uri is a relative path inside the claimset's folder")
    return p


def build(claimset_path, out, update_source=False, strict=False):
    """Build the bag at `out` (a folder, or a .zip file). Returns (changes, files): the artefacts whose `version`
    was set or corrected, and the packaged files. With `update_source`, the versions are also written back to the
    claimset file. With `strict`, a file whose checksum differs from the `sha256:` version its artefact records is
    an error instead of a correction."""
    src = Path(claimset_path)
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot read {src}: {exc}")
    base = src.parent
    out = Path(out)
    as_zip = out.suffix == ".zip"
    work = Path(tempfile.mkdtemp()) / (out.stem if as_zip else out.name)
    changes, files = [], []
    try:
        payload = work / "data"
        payload.mkdir(parents=True)
        for a in doc.get("artefacts") or []:
            if not isinstance(a, dict) or not is_relative_uri(a.get("uri")):
                continue
            rel = _safe(a["uri"])
            f = base.joinpath(*rel.parts)
            if not f.is_file():
                raise PackageError(f"artefact {a.get('id')}: {a['uri']} is not a file beside {src.name}")
            dest = payload.joinpath(*rel.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
            version = f"sha256:{sha256(dest)}"
            recorded = a.get("version")
            if strict and isinstance(recorded, str) and recorded.startswith("sha256:") and recorded != version:
                raise PackageError(f"artefact {a.get('id')}: {a['uri']} has checksum {version}, not the {recorded} "
                                   f"the claimset records: it is not the file the claimset describes; send it again")
            if recorded != version:
                changes.append(f"{a.get('id')}: version {a.get('version') or '(none)'} -> {version}")
                a["version"] = version
            files.append(str(rel))
        text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
        if str(src.name) in files:
            raise PackageError(f"an artefact uses the claimset's own name, {src.name}")
        (payload / src.name).write_text(text, encoding="utf-8")
        (work / "bagit.txt").write_text(BAGIT_TXT, encoding="utf-8")
        lines = [f"{sha256(p)}  {p.relative_to(work).as_posix()}"
                 for p in sorted(payload.rglob("*")) if p.is_file()]
        (work / "manifest-sha256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        problems = folder_package_problems(work)
        if problems:
            raise PackageError("the package would be refused (rule 77):\n" +
                               "\n".join(f"  {where}: {msg}" for where, msg in problems))
        if out.exists():
            raise PackageError(f"{out} exists; choose another output")
        if as_zip:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                for p in sorted(work.rglob("*")):
                    if p.is_file():
                        z.write(p, (PurePosixPath(work.name) / p.relative_to(work).as_posix()).as_posix())
        else:
            shutil.copytree(work, out)
        if update_source and changes:
            src.write_text(text, encoding="utf-8")
    finally:
        shutil.rmtree(work.parent, ignore_errors=True)
    return changes, files


def build_from(doc, files, out, name="paper.claimset.json"):
    """Build the bag at `out` from a claimset (a dict) and the contents of the files its artefacts name by relative
    path, sent without a folder: `files` maps each artefact's `uri` to the file's bytes. Every such file must be
    given, and only those; a file whose checksum differs from the `sha256:` version its artefact records is refused
    (strict). Returns what build() returns."""
    if not isinstance(doc, dict):
        raise PackageError("the claimset is not a JSON object")
    named = {a.get("uri") for a in doc.get("artefacts") or [] if isinstance(a, dict) and is_relative_uri(a.get("uri"))}
    extra = sorted(set(files) - named)
    if extra:
        raise PackageError(f"no artefact names {', '.join(extra)} by its uri; send only the files the artefacts name")
    missing = sorted(named - set(files))
    if missing:
        raise PackageError(f"the files of {', '.join(missing)} were not sent; send every file the artefacts name by "
                           f"a relative path")
    if not name.endswith(".json") or "/" in name or name in files:
        raise PackageError(f"{name}: the claimset's file name is a .json name of its own")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for uri, data in files.items():
            rel = _safe(uri)
            f = base.joinpath(*rel.parts)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        src = base / name
        src.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return build(src, out, strict=True)

"""Submitting to a Claimset platform (EntryLib) and following the submission.

    submit(source, portal, new_paper=False) -> the portal's response (a dict), or SubmitError
    status(submission_id, portal)           -> the submission's state, or SubmitError
    save_record(out, folder)                -> the response kept in .claimset/submissions/<id>.json
    load_record(submission_id, folder)      -> a kept response, or None; the latest with no id

`source` is a submission package (a zip or a BagIt folder, made by `claimset package`), a claimset JSON file, or an
https URL where one of them is deposited (the portal fetches it). A local file is validated first and not sent if it
has errors. The portal answers with a consent link for the guarantor, who signs in with ORCID within 48 hours and
confirms; the link is shown only in that answer, so `claimset submit` keeps the answer in
`.claimset/submissions/<id>.json` (a folder git ignores) and `claimset status` shows the link again from there. A
guarantor without the link confirms on the platform itself, signing in with ORCID (`confirm_url` in the status).

Only the standard library: urllib.
"""

import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import __version__

DEFAULT_PORTAL = "https://entrylib.org"
TIMEOUT = 300
USER_AGENT = f"claimset/{__version__}"


class SubmitError(Exception):
    """The portal could not be reached, or refused the request: `body` is its answer, when it gave one."""

    def __init__(self, message, body=None, status=None):
        super().__init__(message)
        self.body, self.status = body or {}, status


def portal_url(portal=None):
    """The portal to talk to: given, else $CLAIMSET_PORTAL, else EntryLib."""
    url = (portal or os.environ.get("CLAIMSET_PORTAL") or DEFAULT_PORTAL).rstrip("/")
    parts = urllib.parse.urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if parts.scheme != "https" and not (parts.scheme == "http" and local):
        raise SubmitError(f"the portal must be an https URL (http only for localhost): {url}")
    return url


def _request(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8") or "{}")
        except ValueError:
            body = {}
        raise SubmitError(body.get("error") or f"the portal answered {exc.code} {exc.reason}", body,
                          exc.code) from None
    except (urllib.error.URLError, OSError) as exc:
        from .agents import network_hint
        reason = f"{getattr(exc, 'reason', exc)}"
        raise SubmitError(f"cannot reach {urllib.parse.urlsplit(url).netloc}: {reason}."
                          f"{network_hint('network is unreachable')}") from None
    except ValueError:
        raise SubmitError("the portal's answer is not JSON") from None


def _zip_folder(folder):
    """A BagIt folder as a zip, in a temporary file the caller deletes."""
    fh = tempfile.NamedTemporaryFile(prefix="claimset-", suffix=".zip", delete=False)
    with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(Path(folder).rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(folder).as_posix())
    fh.close()
    return Path(fh.name)


def _package_file(path):
    """A claimset file whose artefacts name files by relative path, as a package of it and those files (spec §2.5),
    in a temporary zip the caller deletes; None when it names none. Raises SubmitError when a file is missing."""
    from .package import PackageError, build
    from .validate import standalone_problems
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not standalone_problems(doc):
        return None
    fh = tempfile.NamedTemporaryFile(prefix="claimset-", suffix=".zip", delete=False)
    fh.close()
    out = Path(fh.name)
    out.unlink()
    try:
        build(str(path), str(out))
    except PackageError as exc:
        raise SubmitError(f"{path} names files by relative path, which go in its package, and the package cannot be "
                          f"built: {exc}") from None
    from .validate import validate_path
    rep = validate_path(str(out))
    if rep is None or rep.errors:
        out.unlink(missing_ok=True)
        raise SubmitError(f"the package of {path} has {len(rep.errors) if rep else 'unreadable'} error(s): "
                          f"check it with `claimset package {path} -o paper.zip`",
                          {"errors": rep.errors if rep else []})
    return out


def check(path):
    """Validate a local submission before it is sent. Returns the report; raises SubmitError on errors."""
    from .validate import validate_path
    rep = validate_path(str(path))
    if rep is None:
        raise SubmitError(f"{path} is not a claimset file (JSON) or a submission package")
    if rep.errors:
        raise SubmitError(f"{path} has {len(rep.errors)} validation error(s): fix them first "
                          f"(claimset validate {path})", {"errors": rep.errors, "warnings": rep.warnings})
    return rep


def submit(source, portal=None, new_paper=False):
    """Submit `source` (a path, or an https URL of a deposited package or claimset file). Returns the portal's
    answer: the submission's id, state, status_url and `consent` links."""
    base = portal_url(portal)
    query = "?new_paper=true" if new_paper else ""
    if isinstance(source, str) and source.startswith(("https://", "http://")):
        if not source.startswith("https://"):
            raise SubmitError("the portal fetches https URLs only")
        return _request("POST", f"{base}/api/submissions/from-url{query}",
                        json.dumps({"url": source}).encode("utf-8"), {"Content-Type": "application/json"})
    path = Path(source)
    if not path.exists():
        raise SubmitError(f"no such file: {path}")
    check(path)
    packaged = None if path.is_dir() or zipfile.is_zipfile(path) else _package_file(path)
    tmp = _zip_folder(path) if path.is_dir() else packaged
    send = tmp or path
    try:
        headers = {"Content-Type": "application/zip" if zipfile.is_zipfile(send) else "application/json",
                   "Content-Length": str(send.stat().st_size)}
        with open(send, "rb") as fh:                        # streamed: a package may be 200 MB
            out = _request("POST", f"{base}/api/submissions{query}", fh, headers)
        if packaged is not None:                            # the files the claimset names went with it (§2.5)
            with zipfile.ZipFile(packaged) as z:
                out["packaged"] = sorted(n.split("/data/", 1)[-1] for n in z.namelist()
                                         if "/data/" in n and not n.endswith("/")
                                         and n.split("/data/", 1)[-1] != path.name)
        return out
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def status(submission_id, portal=None):
    """The state of a submission, by the id `submit` returned."""
    sid = (submission_id or "").strip()
    if not sid or "/" in sid or "?" in sid or "#" in sid:
        raise SubmitError("give the submission's id, as `submit` printed it (sub_...)")
    return _request("GET", f"{portal_url(portal)}/api/submissions/{urllib.parse.quote(sid)}")


RECORDS = Path(".claimset") / "submissions"


def save_record(out, folder="."):
    """Keep the platform's answer to a submission, consent link included, where `claimset status` finds it again:
    .claimset/submissions/<id>.json, in a folder with a .gitignore so that it is never committed. Returns the path,
    or None if it cannot be written (a read-only sandbox): the answer was printed anyway."""
    sid = out.get("id")
    if not isinstance(sid, str) or not sid or "/" in sid or "\\" in sid or sid.startswith("."):
        return None
    d = Path(folder) / RECORDS
    try:
        d.mkdir(parents=True, exist_ok=True)
        ignore = d.parent / ".gitignore"
        if not ignore.exists():
            ignore.write_text("# claimset's local records: never committed\n*\n", encoding="utf-8")
        path = d / f"{sid}.json"
        path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
    except OSError:
        return None


def load_record(submission_id=None, folder="."):
    """A kept answer by submission id, or the latest one with no id; None if there is none."""
    d = Path(folder) / RECORDS
    if submission_id:
        files = [d / f"{submission_id}.json"] if "/" not in submission_id and "\\" not in submission_id else []
    else:
        files = sorted(d.glob("sub_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:1] if d.is_dir() else []
    for f in files:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return None


def _consent_lines(out, expires):
    lines = []
    for c in out.get("consent") or []:
        who = f"{c.get('name')} ({c.get('orcid')})" if c.get("name") else c.get("orcid")
        lines += [f"Consent link for {who}:", f"  {c.get('consent_url')}",
                  "Give it to the guarantor: they open it, sign in with ORCID and confirm, by "
                  f"{expires or 'the deadline'} (48 hours). Then the claimset is published."]
    return lines


def describe_submission(out, saved=None):
    """What `claimset submit` prints: the consent link first, since it is shown only once."""
    lines = [f"Submitted: {out.get('id')} ({out.get('kind', 'new')}), waiting for the guarantor's consent.", ""]
    if out.get("packaged"):
        lines[1:1] = [f"Sent as a package with the {len(out['packaged'])} file(s) its artefacts name: "
                      f"{', '.join(out['packaged'])}."]
    consent = _consent_lines(out, out.get("expires"))
    if consent:
        lines += consent + [""]
    warnings = (out.get("report") or {}).get("warnings") or []
    if warnings:
        lines.append(f"{len(warnings)} warning(s) (accepted; worth fixing in a later version):")
        lines += [f"  {w.get('rule')} {w.get('where', '')}: {w.get('message', '')}" for w in warnings]
        lines.append("")
    lines.append(f"Follow it: claimset status {out.get('id')}   ({out.get('status_url')})")
    lines.append(f"Kept in {saved}: `claimset status` shows the consent link again." if saved else
                 "Not kept on disk: keep this output, the platform shows the consent link only now.")
    for c in out.get("consent") or []:                  # again at the end, for readers of the last lines
        lines.append(f"Consent link (again): {c.get('consent_url')}")
    if out.get("confirm_url"):
        lines.append(f"Without the link, the guarantor confirms at {out['confirm_url']}, signing in with ORCID.")
    return "\n".join(lines)


def describe_status(out, record=None):
    """What `claimset status` prints; while pending, the consent link again when `record` (the kept answer) has it."""
    lines = [f"{out.get('id')}: {out.get('state')}"]
    if out.get("corrects"):
        lines.append(f"  a new version of {out['corrects']}")
    for g in out.get("guarantors") or []:
        lines.append(f"  guarantor {g.get('orcid')}: {'confirmed' if g.get('confirmed') else 'not yet confirmed'}")
    if out.get("state") == "pending":
        lines.append(f"  waiting for consent until {out.get('expires')}")
        lines += ["  " + line for line in _consent_lines(record or {}, out.get("expires"))]
        if out.get("confirm_url"):
            lines.append(f"  without the link, the guarantor confirms at {out['confirm_url']}, signing in with ORCID")
    if out.get("registry_pull_request"):
        lines.append(f"  registry checks: {out['registry_pull_request']}")
    if out.get("published"):
        lines.append(f"  published as {out['published']}: cite claims as {out['published']}#C1")
    if out.get("detail"):
        lines.append(f"  {out['detail']}")
    return "\n".join(lines)


def describe_error(exc):
    """A refusal, with the portal's itemised errors."""
    lines = [f"error: {exc}"]
    for e in exc.body.get("errors") or []:
        lines.append(f"  rule {e.get('rule')} at {e.get('where') or '(file)'}: {e.get('message')}")
    return "\n".join(lines)

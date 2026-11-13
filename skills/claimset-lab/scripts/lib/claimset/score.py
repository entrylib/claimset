"""Scoring a claimset before it is submitted, on this machine, by EntryLib's rubric (https://github.com/entrylib/rubric):
the scores it would have once published and its biggest issues, so the human can decide whether to submit it as it is
or amend it first. Optional: nothing requires it.

    score(path, find=None, cited=None)
                           -> {valid, errors, warnings, scores, novelty_checked, cited_checked}: the file validated,
                              given the verifiability the platform sets at publication, and scored by rubric.assess()
    search_finder(portal)  -> find(statement): the published claims EntryLib's public search returns for a statement,
                              for the novelty check (`claimset score --novelty`)
    cited_claims(doc)      -> the global IDs of the published claims the file's `cited` support names
    published_scores(portal) or published_scores(folder=…)
                           -> score_of(global claim ID): that claim's score on EntryLib, from the score file EntryLib
                              publishes for its version (`claimset score --cited`; the portal reads its own folder)
    describe(out, top=3, by=None)
                           -> what `claimset score` prints: rubric.report() between what was scored and the choice

The scoring is the rubric's (rubric.assess, rubric.report); this module only prepares the file and supplies the
claims to compare with. EntryLib's portal calls the same functions for its MCP tool `score`, with its own search.
Standard library only: the `rubric` package is used when installed, never required by `claimset`.
"""

import json
import re
import urllib.parse
import zipfile
from pathlib import Path

from .submit import SubmitError, _request, portal_url

INSTALL = "pip install entrylib-rubric"
UPGRADE = "pip install --upgrade entrylib-rubric"
RUBRIC_URL = "https://github.com/entrylib/rubric/blob/main/RUBRIC.md"


class ScoreError(Exception):
    """The claimset could not be scored: the rubric is not installed, the file cannot be read, or the novelty check
    could not reach EntryLib."""


def _rubric():
    try:
        import rubric
    except ImportError:
        raise ScoreError(f"scoring needs EntryLib's rubric, which is not installed: {INSTALL}") from None
    if not hasattr(rubric, "assess") or not hasattr(rubric, "report"):
        raise ScoreError(f"the installed rubric ({getattr(rubric, 'VERSION', '?')}) is too old to score here; "
                         f"update it: {UPGRADE}")
    return rubric


def _assess(rubric, doc, find, warnings, cited=None):
    """rubric.assess, given the validator's warnings when the installed rubric reads them (rubric 0.3: the numbers a
    statement gives that match no recorded result, warning 17; a limitation that restates the declared competing
    interest, warning 46), and the scores of the cited published claims when it reads those (rubric 0.5)."""
    import inspect
    params = inspect.signature(rubric.assess).parameters
    kw = {}
    if "warnings" in params:
        kw["warnings"] = warnings
    if "cited" in params and cited is not None:
        kw["cited"] = cited
    return rubric.assess(doc, find, **kw)


def _load(path):
    """(validation report, claimset) of a claimset file or a submission package (zip or folder)."""
    from .validate import validate, validate_package
    p = Path(path)
    if not p.exists():
        raise ScoreError(f"no such file: {p}")
    try:
        if p.is_dir() or zipfile.is_zipfile(p):
            prep, doc = validate_package(p)
            if doc is None:
                return prep, None
            rep = validate(doc)
            rep.errors[:0] = prep.errors
            return rep, doc
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise ScoreError(f"cannot read {p}: {exc}") from None
    return validate(doc), doc


def score(path, find=None, cited=None):
    """The scores the claimset at `path` would have once published. A file with errors is not scored (`scores` is
    absent); its packaged files are not needed, so a claimset file is scored without its package. `find` supplies
    the published claims to compare principal claims with (rubric.assess); without it novelty is not checked.
    `cited` is score_of(global claim ID), the scores on EntryLib of the published claims the file cites (rubric 0.5);
    without it they cost as any cited work."""
    from .validate import with_verifiability
    rubric = _rubric()
    rep, doc = _load(path)
    out = {"valid": not rep.errors, "errors": rep.errors, "warnings": rep.warnings, "novelty_checked": find is not None,
           "cited_checked": cited is not None}
    if doc is not None and not rep.errors:
        known = None
        if cited is not None:
            known = {t: v for t in cited_claims(doc) for v in [cited(t)] if v is not None}
        out["scores"] = _assess(rubric, with_verifiability(doc, rep.computed), find, rep.warnings, known)
    return out


_CLAIM_ID = re.compile(r"^(?P<concept>(?:entrylib:|doi:10\.\d{4,9}/claimset\.)(?P<key>\d{4}\.\d{6,}))"
                       r"(?:@v(?P<v>[1-9]\d*))?#(?P<claim>C\d+)$")


def cited_claims(doc):
    """The global IDs of the published claims the file's `cited` support names (`id_type: claimset`, with a claim),
    directly or through its references, as the file writes them."""
    refs = {r.get("id"): r for r in doc.get("references") or [] if isinstance(r, dict)}
    out = []
    for c in doc.get("claims") or []:
        for s in (c.get("support") or []) if isinstance(c, dict) else []:
            if not isinstance(s, dict) or s.get("kind") != "cited":
                continue
            src = refs.get(s.get("reference")) if isinstance(s.get("reference"), str) else s
            src = src if isinstance(src, dict) else {}
            t = src.get("target")
            if src.get("id_type") == "claimset" and isinstance(t, str) and _CLAIM_ID.match(t) and t not in out:
                out.append(t)
    return out


def published_scores(portal=None, folder=None):
    """score_of(global claim ID) -> that claim's score on EntryLib, or None: read from the score file EntryLib
    publishes for the version (`/p/<year>.<number>@v<n>.score.json`, the current version's without @v), over HTTPS
    from `portal`, or from `folder`, the portal's own published folder. Only the claimsets' identifiers are sent."""
    base = None if folder is not None else portal_url(portal)
    cache = {}

    def score_of(target):
        m = _CLAIM_ID.match(target or "")
        if not m:
            return None
        name = f"{m['key']}@v{m['v']}.score.json" if m["v"] else f"{m['key']}.score.json"
        if name not in cache:
            try:
                if folder is not None:
                    p = Path(folder) / "p" / name
                    cache[name] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
                else:
                    cache[name] = _request("GET", f"{base}/p/{name}")
            except (OSError, ValueError, SubmitError):
                cache[name] = None                   # not published, or not reachable: cited as any work
        item = ((cache[name] or {}).get("claims") or {}).get(m["claim"])
        value = item.get("score") if isinstance(item, dict) else None
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    return score_of


def _words(statement):
    """The words of a statement to search for: term references by their text, mathematics left out."""
    text = re.sub(r"\[\[[^\]:]+:([^\]]*)\]\]", r"\1", str(statement or ""))
    text = re.sub(r"\$[^$]*\$", " ", text)
    seen = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text):
        if w.lower() not in seen:
            seen.append(w.lower())
    return seen[:30]


def search_finder(portal=None, limit=20):
    """find(statement) for rubric.assess: the claims of EntryLib's current versions that its public search
    (GET /api/search/claims) finds for any of the statement's words, as [{"claim", "statement"}]. Only the words of
    each principal claim's statement are sent; nothing is kept."""
    base = portal_url(portal)

    def find(statement):
        words = _words(statement)
        if not words:
            return []
        query = urllib.parse.urlencode({"q": " or ".join(words), "limit": limit})
        try:
            found = _request("GET", f"{base}/api/search/claims?{query}")
        except SubmitError as exc:
            raise ScoreError(f"the novelty check could not search EntryLib ({base}): {exc}; score without "
                             f"--novelty") from None
        return [{"claim": r["id"], "statement": r.get("statement")} for r in found.get("results") or []
                if isinstance(r, dict) and isinstance(r.get("id"), str)]
    return find


def describe(out, top=3, by=None, name=None):
    """The scores as `claimset score` prints them. `by` says where they were computed (default: on this machine;
    the portal's MCP tool says it scored the file sent to it). `name`: what the score is called, for a site that shows
    it under another name; the rubric's own word when None, or when the installed rubric cannot take a name."""
    if not out.get("valid"):
        errors = out.get("errors") or []
        lines = [f"Not scored: the claimset has {len(errors)} error(s). Fix them (`claimset validate`) and score it "
                 f"again."]
        lines += [f"  rule {e.get('rule')} at {e.get('where') or '(file)'}: {e.get('message')}" for e in errors[:20]]
        return "\n".join(lines)
    rubric = _rubric()
    sc = out["scores"]
    novelty = ("Novelty: principal claims compared with the claims published on EntryLib now." if out.get(
        "novelty_checked") else "Novelty: not checked (`--novelty` compares the principal claims with those "
                                "published on EntryLib, sending their statements' words to its search).")
    if out.get("cited_checked"):
        novelty += "\nCited claims published on EntryLib: scored by their scores there."
    if by is None:
        sent = [w for w, on in (("the search words", out.get("novelty_checked")),
                                 ("the identifiers of the cited claims", out.get("cited_checked"))) if on]
        by = "computed on this machine; nothing was sent" + (" but " + " and ".join(sent) if sent else "")
    head = [f"Scores by the EntryLib rubric {sc['rubric']}, as EntryLib would score this claimset once published "
            f"({by}). They check the record, not the science: {RUBRIC_URL}", novelty, ""]
    tail = ["Scoring is optional. Submit the claimset as it is (`claimset submit`), or amend it and score it again; "
            "EntryLib scores it again when it is published, by the rubric current then."]
    try:
        body = rubric.report(sc, top, name=name) if name else rubric.report(sc, top)
    except TypeError:                                   # a rubric older than its `name` (rubric PR 10)
        body = rubric.report(sc, top)
    return "\n".join(head) + "\n" + body + "\n" + "\n".join(tail)

"""Bound review validation for one real project root and task.

This is the portable runtime port of the hardened review grammar: the
four required headings must each occur exactly once as standalone
headings, each pass carries one canonical verdict plus a bound
``validation-review-proof/1`` record whose artifact exists under the
project with the exact stored-byte SHA-256 and a reviewer-owned origin,
Findings accepts only canonical declarations or ``- NONE``, every
material finding carries an anchored durable-correction disposition,
FULL accepting reviews are convergence-bound to the frozen requirement
IDs, and HIGH-risk reviews must bind a distinct reviewer-owned
adversarial challenge. The durable lessons path is configurable per
task; the reference snapshot's stricter lessons binding stays available
through the optional reference-guard composition.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .errors import UALError
from .paths import resolve_inside

TWO_PASS_HEADINGS = ("## Contract compliance", "## Adversarial validity")
REQUIRED_HEADINGS = TWO_PASS_HEADINGS + ("## Findings",
                                         "## Durable correction")
FINDINGS_HEADING = "## Findings"
CORRECTION_HEADING = "## Durable correction"
CONVERGENCE_HEADING = "## Convergence disposition"
PROOF_SCHEMA = "validation-review-proof/1"
PROOF_ORIGINS = ("REVIEWER_RECOMPUTED", "REVIEWER_REEXECUTED")
CHALLENGE_TYPES = ("NEGATIVE_COUNTEREXAMPLE", "INVARIANT_PROPERTY_CASE",
                   "DIFFERENTIAL_ORACLE", "BOUNDED_MUTATION",
                   "BOUNDARY_TRACE")
CORRECTION_OUTCOMES = ("NONE_REQUIRED", "LESSON_RECORDED", "RULE_PROMOTED")

_SECTION_RES = {h: re.compile(r"(?m)^" + re.escape(h) + r"\s*$")
                for h in REQUIRED_HEADINGS}
_VERDICT_FIELD_RE = re.compile(
    r"(?:[-*+>#]+|\d+[.)])?[ \t]*verdict[ \t]*:", re.IGNORECASE)
_CANONICAL_VERDICT_RE = re.compile(r"(?m)^- Verdict: `(PASS|FAIL)`\s*$")
_FINDING_LINE_RE = re.compile(r"^- ([A-Z]{1,8}\d+): (\S.*?)\s*$")
_NONE_FINDING_RE = re.compile(r"^- NONE\s*$")
_PROOF_RE = re.compile(
    r"^`validation-review-proof/(\d+)` artifact `([^`]*)`"
    r" sha256 `([^`]*)` origin `([^`]*)` action `([^`]*)`"
    r" candidate `([^`]*)`$")
_CORRECTION_LINE_RE = re.compile(
    r"(?m)^- ([A-Za-z][A-Za-z0-9._-]*): "
    r"`(NONE_REQUIRED|LESSON_RECORDED|RULE_PROMOTED)`"
    r" — rationale: (.+?) — evidence: (.+?)\s*$")
_CORRECTION_ANY_OUTCOME_RE = re.compile(
    r"(?m)^- ([A-Za-z][A-Za-z0-9._-]*): `([A-Z][A-Z_]*)` — rationale: ")
_MANDATED_CHANGE_RE = re.compile(r"(?m)^- Mandated change: `([^`]*)`")
_MANDATED_ID_RE = re.compile(r"([A-Za-z][A-Za-z0-9._-]*):\s")
_MATERIAL_FINDING_RE = re.compile(r"(?m)^- ([A-Z]{1,8}\d+): ")
_EVIDENCE_REF_RE = re.compile(r"`([^`]+)`")
_RULE_ANCHOR_RE = re.compile(r"^R\d+")
_TEST_REF_RE = re.compile(r"(?:^tests/|#test)")
_CHALLENGE_FIELD_RES = {
    "type": re.compile(r"(?m)^- Challenge type: `([A-Za-z0-9_.-]+)`\s*$"),
    "target": re.compile(r"(?m)^- Challenge target: `([^`]*)`\s*$"),
    "artifact": re.compile(r"(?m)^- Challenge artifact: `([^`]*)`\s*$"),
    "bytes": re.compile(r"(?m)^- Challenge artifact bytes: `([0-9]+)`\s*$"),
    "sha256": re.compile(
        r"(?m)^- Challenge artifact sha256: `([0-9a-fA-F]{64})`\s*$"),
    "result": re.compile(r"(?m)^- Challenge result: `([^`]*)`\s*$"),
}
_CONVERGENCE_FIELD_RES = {
    "disposition": re.compile(r"(?m)^- Disposition: `([^`]*)`\s*$"),
    "covered": re.compile(
        r"(?m)^- Covered requirement IDs: `([^`]*)`\s*$"),
    "remaining": re.compile(
        r"(?m)^- Remaining material requirement IDs: `([^`]*)`\s*$"),
}


_SECTION_RES_CACHE: dict = {}


def _section_res(heading: str):
    compiled = _SECTION_RES_CACHE.get(heading)
    if compiled is None:
        compiled = re.compile(r"(?m)^" + re.escape(heading) + r"\s*$")
        _SECTION_RES_CACHE[heading] = compiled
    return compiled


def _section(text: str, heading: str) -> str:
    match = _section_res(heading).search(text)
    if match is None:
        return ""
    start = match.end()
    nxt = text.find("\n## ", start)
    return text[start:nxt if nxt >= 0 else len(text)]


def _verdict_errors(section: str, heading: str) -> list:
    declarations = [line for line in section.splitlines()
                    if _VERDICT_FIELD_RE.match(line.strip())]
    if len(declarations) > 1:
        return [f"REVIEW_DUPLICATE_VERDICT:{heading}"]
    if not declarations:
        return [f"REVIEW_VERDICT_MISSING:{heading}"]
    if _CANONICAL_VERDICT_RE.fullmatch(declarations[0]) is None:
        return [f"REVIEW_VERDICT_MALFORMED:{heading}"]
    return []


def _findings_errors(section: str) -> list:
    errors = []
    ids = []
    none_markers = 0
    for raw in section.splitlines():
        if not raw.strip():
            continue
        if raw == "- NONE":
            none_markers += 1
            continue
        match = _FINDING_LINE_RE.match(raw)
        if match is None:
            errors.append("REVIEW_FINDING_MALFORMED:" + raw.strip()[:64])
            continue
        ids.append(match.group(1))
    for fid in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"REVIEW_FINDING_DUPLICATE:{fid}")
    if none_markers > 1:
        errors.append("REVIEW_FINDING_MALFORMED:duplicate NONE marker")
    if none_markers and ids:
        errors.append(
            "REVIEW_FINDING_MALFORMED:NONE marker with declared findings")
    return errors


def _grammar_errors(text: str) -> list:
    errors = []
    for heading in REQUIRED_HEADINGS:
        if text.count(heading) > 1:
            errors.append(f"REVIEW_HEADING_AMBIGUOUS:{heading}")
    for heading, heading_re in _SECTION_RES.items():
        count = len(heading_re.findall(text))
        if count > 1:
            errors.append(f"REVIEW_DUPLICATE_SECTION:{heading}")
        elif count == 0:
            errors.append(f"REVIEW_SECTION_MISSING:{heading}")
    for heading in TWO_PASS_HEADINGS:
        section = _section(text, heading)
        if section:
            errors.extend(_verdict_errors(section, heading))
    findings = _section(text, FINDINGS_HEADING)
    if findings:
        errors.extend(_findings_errors(findings))
    return errors


def _two_pass_errors(text: str, project: Path, task_id: str) -> list:
    errors = []
    for heading in TWO_PASS_HEADINGS:
        section = _section(text, heading)
        if not section:
            continue
        evidence = None
        for line in section.splitlines():
            if line.startswith("- Evidence: "):
                evidence = line[len("- Evidence: "):].strip()
                break
        if not evidence:
            errors.append(f"REVIEW_TWO_PASS_EVIDENCE_EMPTY:{heading}")
            continue
        match = _PROOF_RE.match(evidence)
        if match is None:
            errors.append(f"REVIEW_TWO_PASS_EVIDENCE_INVALID:{heading}")
            continue
        version, artifact_rel, claimed_sha, origin, action, candidate = (
            match.groups())
        if f"validation-review-proof/{version}" != PROOF_SCHEMA:
            errors.append(f"REVIEW_TWO_PASS_EVIDENCE_INVALID:{heading}")
            continue
        if origin not in PROOF_ORIGINS:
            errors.append(f"REVIEW_PROOF_ORIGIN_UNPROVEN:{heading}")
        if not action.strip():
            errors.append(f"REVIEW_PROOF_ACTION_EMPTY:{heading}")
        try:
            artifact = resolve_inside(project, artifact_rel,
                                      label="PROOF_ARTIFACT")
        except UALError as exc:
            errors.append(f"REVIEW_PROOF_ARTIFACT_MISSING:{heading}")
            continue
        if not artifact.is_file():
            errors.append(f"REVIEW_PROOF_ARTIFACT_MISSING:{heading}")
            continue
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual != claimed_sha.strip().lower():
            errors.append(f"REVIEW_PROOF_HASH_MISMATCH:{heading}")
        if candidate.strip() != task_id:
            errors.append(f"REVIEW_PROOF_TASK_MISMATCH:{heading}")
    return errors


def _contract_evidence_sha(text: str):
    section = _section(text, "## Contract compliance")
    for line in section.splitlines():
        if line.startswith("- Evidence: "):
            match = _PROOF_RE.match(line[len("- Evidence: "):].strip())
            if match:
                return match.group(3).strip().lower()
    return None


def review_verdicts(text: str) -> list:
    """The canonical verdicts of the two pass sections, in order."""
    verdicts = []
    for heading in TWO_PASS_HEADINGS:
        section = _section(text, heading)
        verdict = _CANONICAL_VERDICT_RE.search(section) if section else None
        verdicts.append(verdict.group(1) if verdict else None)
    return verdicts


_ENVELOPE_BINDING_RE = re.compile(
    r"(?m)^- Frozen envelope sha256: `([0-9a-fA-F]{64})`\s*$")


def envelope_binding(text: str):
    """The digest an accepting review binds to the current frozen
    envelope, or None when the binding is absent."""
    match = _ENVELOPE_BINDING_RE.search(text)
    return match.group(1).lower() if match else None


def _correction_errors(text: str, project: Path, lessons_path: str) -> list:
    errors = []
    findings_section = _section(text, FINDINGS_HEADING)
    material = set(_MATERIAL_FINDING_RE.findall(findings_section))
    section = _section(text, CORRECTION_HEADING)
    invalid_outcomes = {}
    for match in _CORRECTION_ANY_OUTCOME_RE.finditer(section):
        fid, outcome = match.group(1), match.group(2)
        if outcome not in CORRECTION_OUTCOMES:
            invalid_outcomes[fid] = True
            errors.append(f"CORRECTION_DISPOSITION_INVALID_OUTCOME:{fid}")
    dispositions = {}
    for match in _CORRECTION_LINE_RE.finditer(section):
        fid, outcome, rationale, evidence = match.groups()
        if fid in dispositions:
            errors.append(f"CORRECTION_DISPOSITION_DUPLICATE:{fid}")
            continue
        dispositions[fid] = (outcome, rationale.strip(), evidence.strip())
    for fid in sorted(material):
        if fid not in dispositions and fid not in invalid_outcomes:
            errors.append(f"CORRECTION_DISPOSITION_MISSING:{fid}")
    mandated = _MANDATED_CHANGE_RE.findall(section)
    if len(mandated) > 1:
        errors.append("CORRECTION_MANDATED_CHANGE_DUPLICATE")
    mandated_ids = set()
    for value in mandated:
        if value.strip().upper() != "NONE":
            mandated_ids.update(_MANDATED_ID_RE.findall(value))
    for fid, (outcome, rationale, evidence) in dispositions.items():
        if fid not in material:
            errors.append(f"CORRECTION_DISPOSITION_UNKNOWN_FINDING:{fid}")
        if not rationale:
            errors.append(f"CORRECTION_RATIONALE_EMPTY:{fid}")
        refs = _EVIDENCE_REF_RE.findall(evidence)
        if not refs:
            errors.append(f"CORRECTION_EVIDENCE_LINK_MISSING:{fid}")
            continue
        resolved_refs = []
        for ref in refs:
            path_part, _sep, anchor = ref.partition("#")
            if not anchor:
                errors.append(f"CORRECTION_EVIDENCE_REF_MALFORMED:{fid}")
                continue
            try:
                target = resolve_inside(project, path_part,
                                        label="CORRECTION_EVIDENCE")
            except UALError:
                errors.append(f"CORRECTION_EVIDENCE_LINK_MISSING:{fid}")
                continue
            if not target.is_file():
                errors.append(f"CORRECTION_EVIDENCE_LINK_MISSING:{fid}")
                continue
            try:
                content = target.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                errors.append(f"CORRECTION_EVIDENCE_LINK_MISSING:{fid}")
                continue
            if anchor not in content:
                errors.append(f"CORRECTION_EVIDENCE_ANCHOR_MISSING:{ref}")
            resolved_refs.append(ref)
        if outcome == "NONE_REQUIRED":
            if fid in mandated_ids:
                errors.append(
                    "CORRECTION_CONTRADICTION_NONE_REQUIRED_WITH_"
                    "MANDATED_CHANGE:" + fid)
            continue
        if outcome == "LESSON_RECORDED":
            bound = {r.split("#", 1)[0] for r in resolved_refs}
            if len(resolved_refs) != 1 or bound != {lessons_path}:
                errors.append(
                    f"CORRECTION_LESSON_RECORDED_NOT_LESSONS_FILE:{fid}")
        elif outcome == "RULE_PROMOTED":
            rule_refs = [r for r in resolved_refs
                         if _RULE_ANCHOR_RE.match(r.split("#", 1)[-1])]
            test_refs = [r for r in resolved_refs
                         if _TEST_REF_RE.search(r)]
            if len(resolved_refs) < 2 or not rule_refs or not test_refs:
                errors.append(
                    "CORRECTION_RULE_PROMOTED_MISSING_RULE_OR_TEST:" + fid)
    return errors


def _convergence_errors(text: str, requirement_ids: list) -> list:
    if not re.search(r"(?m)^" + re.escape(CONVERGENCE_HEADING) + r"\s*$",
                     text):
        return ["CONVERGENCE_DISPOSITION_SECTION_MISSING"]
    section = _section(text, CONVERGENCE_HEADING)
    values = {}
    duplicates = []
    for name, pattern in _CONVERGENCE_FIELD_RES.items():
        matches = pattern.findall(section)
        if not matches:
            values[name] = None
        elif len(matches) > 1:
            duplicates.append(name)
            values[name] = matches[0] if isinstance(matches[0], str) else None
        else:
            values[name] = matches[0]
    errors = [f"CONVERGENCE_FIELD_DUPLICATE:{n}" for n in duplicates]
    for name in _CONVERGENCE_FIELD_RES:
        if values.get(name) is None:
            errors.append(f"CONVERGENCE_FIELD_MISSING:{name}")
    if errors:
        return errors
    disposition = values["disposition"]
    if disposition not in ("CONVERGED", "MATERIAL_DELTA"):
        errors.append(f"CONVERGENCE_DISPOSITION_INVALID:{disposition}")
    def _ids(raw):
        if raw == "NONE":
            return set(), None
        tokens = [t.strip() for t in raw.split(",")]
        if any(not t for t in tokens):
            return set(), "CONVERGENCE_ID_LIST_MALFORMED"
        return set(tokens), None
    covered, err = _ids(values["covered"])
    if err:
        errors.append(err + ":covered")
    remaining, err = _ids(values["remaining"])
    if err:
        errors.append(err + ":remaining")
    frozen = set(requirement_ids or ())
    for rid in sorted(covered - frozen):
        errors.append(f"CONVERGENCE_COVERED_ID_UNKNOWN:{rid}")
    for rid in sorted(remaining - frozen):
        errors.append(f"CONVERGENCE_REMAINING_ID_UNKNOWN:{rid}")
    if covered & remaining:
        errors.append("CONVERGENCE_COVERED_REMAINING_OVERLAP")
    if disposition == "CONVERGED" and remaining:
        errors.append("CONVERGENCE_INCONSISTENT_REMAINING_IDS")
    if disposition == "MATERIAL_DELTA" and not remaining:
        errors.append("CONVERGENCE_DELTA_WITHOUT_REMAINING_IDS")
    if not frozen or covered != frozen:
        errors.append("CONVERGENCE_COVERAGE_INCOMPLETE")
    return errors


def _challenge_errors(text: str, project: Path) -> list:
    section = _section(text, "## Adversarial validity")
    if not section:
        return ["ADVERSARIAL_CHALLENGE_SECTION_MISSING"]
    fields = {}
    missing = []
    for name, pattern in _CHALLENGE_FIELD_RES.items():
        match = pattern.search(section)
        if match is None:
            missing.append(name)
        else:
            fields[name] = match.group(1).strip()
    if missing:
        return ["ADVERSARIAL_CHALLENGE_REQUIRED:"
                "an accepting HIGH-risk review must bind one distinct "
                "reviewer-owned challenge"] + [
            "ADVERSARIAL_CHALLENGE_FIELD_MISSING:" + n for n in missing]
    errors = []
    if fields["type"] not in CHALLENGE_TYPES:
        errors.append(f"ADVERSARIAL_CHALLENGE_TYPE_INVALID:{fields['type']}")
    try:
        artifact = resolve_inside(project, fields["artifact"],
                                  label="CHALLENGE_ARTIFACT")
    except UALError:
        errors.append("ADVERSARIAL_CHALLENGE_ARTIFACT_MISSING:"
                      + fields["artifact"])
        return errors
    if not artifact.is_file():
        errors.append("ADVERSARIAL_CHALLENGE_ARTIFACT_MISSING:"
                      + fields["artifact"])
        return errors
    data = artifact.read_bytes()
    if int(fields["bytes"]) != len(data):
        errors.append("ADVERSARIAL_CHALLENGE_ARTIFACT_BYTES_MISMATCH")
    if fields["sha256"].lower() != hashlib.sha256(data).hexdigest():
        errors.append("ADVERSARIAL_CHALLENGE_ARTIFACT_SHA_MISMATCH")
    same_origin = _contract_evidence_sha(text)
    if same_origin and same_origin == fields["sha256"].lower():
        errors.append("ADVERSARIAL_CHALLENGE_SAME_ORIGIN")
    return errors


def validate_review(text: str, project: Path, task: dict, *,
                    reference_root: str | None = None) -> list:
    from .taskfile import derived_mode, requirement_ids
    if not isinstance(text, str) or not text.strip():
        return ["REVIEW_TEXT_EMPTY"]
    errors = _grammar_errors(text)
    errors.extend(_two_pass_errors(text, Path(project), task["id"]))
    errors.extend(_correction_errors(text, Path(project),
                                     task.get("lessons_path")
                                     or ".agent-loop/lessons.md"))
    if task.get("mode") == "FULL":
        errors.extend(_convergence_errors(text, requirement_ids(task)))
    if task.get("risk") == "HIGH":
        errors.extend(_challenge_errors(text, Path(project)))
    if reference_root is not None:
        errors.extend(_compose_reference_guard(text, Path(project),
                                               task, reference_root))
    return errors


def _compose_reference_guard(text: str, project: Path, task: dict,
                             reference_root: str) -> list:
    guard = _load_reference_guard(reference_root)
    if guard is None:
        return ["REFERENCE_GUARD_UNAVAILABLE:" + str(reference_root)]
    try:
        return ["REFERENCE_GUARD:" + r for r in guard.validate_bound_review(
            text, root=project, task_id=task["id"],
            reference_root=Path(reference_root))]
    except Exception as exc:
        return ["REFERENCE_GUARD_ERROR:" + type(exc).__name__]


def _load_reference_guard(reference_root: str):
    import importlib.util
    import sys
    guard_init = Path(__file__).resolve().parent.parent / "validation" / \
        "review_guard.py"
    if not guard_init.is_file():
        return None
    spec = importlib.util.spec_from_file_location(
        "ual_reference_review_guard", guard_init)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        return None
    return module

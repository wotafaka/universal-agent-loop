"""Hardened bound-review seam over the byte-verified reference core.

Separately versioned validation adapter (universal-agent-loop-review-guard/1).
Before any reused Python is imported, the pinned manifest of the preserved
``../reference`` export is verified against its exact stored-byte SHA-256 and
every listed member is verified against the pinned byte counts and digests.
Only then is the copied ``agent_loop_contract.py`` loaded by explicit path.

On top of the unchanged historical two-pass proof and durable-correction
validators, this seam hardens reproduced acceptance defects of the legacy
pair. Each required heading string (``## Contract compliance``,
``## Adversarial validity``, ``## Findings``, ``## Durable correction``) must
occur exactly once in the whole review text — as its standalone heading line.
Any other literal occurrence (inline narrative mention, a ``(historical)``
suffix, a subheading prefix) is refused, because the delegated historical
parser locates sections by first literal occurrence and could otherwise be
aimed at a different region than this guard validates. The standalone heading
must also appear exactly once: duplicates and absence are both refused, and
section extraction uses that exact standalone heading identity. The reserved
``Verdict`` field is detected broadly inside a required pass — any line whose
first content is an ordinary list marker (``-``, ``*``, ``+``, ``>``, ``#``,
numbered), whitespace, or any letter case followed by the field name and a
colon counts as a verdict declaration: more than one is refused, zero is
refused, and the single declaration's WHOLE line must match the exact
canonical form ``- Verdict: `(PASS|FAIL)``` at column zero. Unsupported
syntax is rejected, never parsed, supported, or silently normalized; multiple
fields on one line can never be canonical. The
``## Findings`` section may contain only blank lines, canonical ``- M1:
text`` style declarations, or one exact ``- NONE`` marker; any nonempty
noncanonical line (prose, tables, ``*`` bullets, indented declarations,
duplicated IDs) is refused instead of silently treated as no findings.
Narrative or historical headings mentioning these strings belong outside the
machine report.

An empty refusal list from :func:`validate_bound_review` means exactly these
bound review and durable-correction checks passed. It is never owner
acceptance, never complete lifecycle approval, and this module is never a
generic launcher. The human-readable ``templates/REVIEW.md`` is not the
machine grammar enforced here.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

GUARD_SCHEMA = "universal-agent-loop-review-guard/1"
GUARD_VERSION = "1.3.0"

REFERENCE_DIRNAME = "reference"
MANIFEST_FILENAME = "manifest.json"
MANIFEST_SCHEMA = "agent-loop-core-export-manifest/1"
MANIFEST_PINNED_BYTES = 1760
MANIFEST_PINNED_SHA256 = (
    "c8f56d81c69a0377d8621144a9bfe3818d0d8ae978c263afcea138f77f7bafc0")
CONTRACT_MEMBER = "agent_loop_contract.py"

TWO_PASS_HEADINGS = ("## Contract compliance", "## Adversarial validity")
HARDENED_SECTION_HEADINGS = TWO_PASS_HEADINGS + (
    "## Findings", "## Durable correction")
FINDINGS_HEADING = "## Findings"

_SECTION_HEADING_RES = {
    heading: re.compile(r"(?m)^" + re.escape(heading) + r"\s*$")
    for heading in HARDENED_SECTION_HEADINGS}
_VERDICT_FIELD_RE = re.compile(
    r"(?:[-*+>#]+|\d+[.)])?[ \t]*verdict[ \t]*:", re.IGNORECASE)
_CANONICAL_VERDICT_RE = re.compile(r"^- Verdict: `(PASS|FAIL)`\s*$")
_FINDING_LINE_RE = re.compile(r"^- ([A-Z]{1,8}\d+): (\S.*?)\s*$")
_NONE_FINDING_RE = re.compile(r"^- NONE\s*$")

_BOUND_CONTRACTS: dict = {}


class ReferenceIdentityError(RuntimeError):
    """The preserved reference did not match its pinned identity."""


def default_reference_root() -> Path:
    """The packaged ``reference/`` directory next to this module."""
    return Path(__file__).resolve().parent.parent / REFERENCE_DIRNAME


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_reference_members(reference_root=None) -> Path:
    """Verify the pinned manifest bytes and every member's stored bytes.

    Runs before any reused Python is imported; a mismatched manifest, a
    missing member, or a drifted member raises instead of executing."""
    root = (Path(reference_root) if reference_root is not None
            else default_reference_root())
    try:
        manifest_bytes = (root / MANIFEST_FILENAME).read_bytes()
    except OSError:
        raise ReferenceIdentityError("MANIFEST_MISSING") from None
    if (len(manifest_bytes) != MANIFEST_PINNED_BYTES
            or _sha256(manifest_bytes) != MANIFEST_PINNED_SHA256):
        raise ReferenceIdentityError("MANIFEST_IDENTITY_MISMATCH")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ReferenceIdentityError("MANIFEST_UNREADABLE") from None
    if (not isinstance(manifest, dict)
            or manifest.get("schema") != MANIFEST_SCHEMA
            or not isinstance(manifest.get("members"), list)):
        raise ReferenceIdentityError("MANIFEST_UNKNOWN_SCHEMA")
    for entry in manifest["members"]:
        if not isinstance(entry, dict):
            raise ReferenceIdentityError("MANIFEST_MALFORMED")
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel:
            raise ReferenceIdentityError("MANIFEST_MALFORMED")
        try:
            data = (root / rel).read_bytes()
        except OSError:
            raise ReferenceIdentityError(f"MEMBER_MISSING:{rel}") from None
        if (len(data) != entry.get("bytes")
                or _sha256(data) != entry.get("sha256")):
            raise ReferenceIdentityError(f"MEMBER_IDENTITY_MISMATCH:{rel}")
    return root


def load_verified_contract(reference_root=None):
    """Verify the reference, then import the copied core by explicit path."""
    root = verify_reference_members(reference_root)
    cache_key = str(root)
    cached = _BOUND_CONTRACTS.get(cache_key)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "review_guard_bound_agent_loop_contract", root / CONTRACT_MEMBER)
    if spec is None or spec.loader is None:
        raise ReferenceIdentityError(f"CONTRACT_UNLOADABLE:{CONTRACT_MEMBER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    _BOUND_CONTRACTS[cache_key] = module
    return module


def _section_by_heading(text: str, heading_re) -> str | None:
    """Extract one section using the exact same standalone heading identity
    as the heading count check; an inline mention or a subheading prefix can
    never substitute for the heading itself."""
    match = heading_re.search(text)
    if match is None:
        return None
    body_start = match.end()
    next_heading = text.find("\n## ", body_start)
    end = next_heading if next_heading >= 0 else len(text)
    return text[body_start:end]


def _verdict_token(declaration: str) -> str:
    after = declaration.split(":", 1)[1] if ":" in declaration else ""
    match = re.search(r"`([^`]*)`", after)
    return match.group(1) if match else (after.strip()[:24] or "EMPTY")


def _verdict_errors(section: str, heading: str) -> list:
    declarations = [line for line in section.splitlines()
                    if _VERDICT_FIELD_RE.match(line.strip())]
    if len(declarations) > 1:
        return [f"REVIEW_GUARD_DUPLICATE_VERDICT:{heading}:"
                + "/".join(_verdict_token(d) for d in declarations)]
    if not declarations:
        return [f"REVIEW_GUARD_VERDICT_MISSING:{heading}"]
    if _CANONICAL_VERDICT_RE.fullmatch(declarations[0]) is None:
        return [f"REVIEW_GUARD_VERDICT_MALFORMED:{heading}:"
                + declarations[0].strip()[:64]]
    return []


def _findings_errors(section: str) -> list:
    errors: list = []
    finding_ids: list = []
    none_markers = 0
    for raw_line in section.splitlines():
        if not raw_line.strip():
            continue
        if raw_line == "- NONE":
            none_markers += 1
            continue
        match = _FINDING_LINE_RE.match(raw_line)
        if match is None:
            errors.append("REVIEW_GUARD_FINDING_MALFORMED:"
                          + raw_line.strip()[:64])
            continue
        finding_ids.append(match.group(1))
    for finding_id in sorted({finding_id for finding_id in finding_ids
                              if finding_ids.count(finding_id) > 1}):
        errors.append(f"REVIEW_GUARD_FINDING_DUPLICATE:{finding_id}")
    if none_markers > 1:
        errors.append("REVIEW_GUARD_FINDING_MALFORMED:duplicate NONE marker")
    if none_markers and finding_ids:
        errors.append("REVIEW_GUARD_FINDING_MALFORMED:NONE marker with "
                      "declared findings")
    return errors


def _hardened_review_errors(text: str) -> list:
    errors: list = []
    for heading in HARDENED_SECTION_HEADINGS:
        if text.count(heading) > 1:
            errors.append(f"REVIEW_GUARD_HEADING_AMBIGUOUS:{heading}")
    for heading, heading_re in _SECTION_HEADING_RES.items():
        count = len(heading_re.findall(text))
        if count > 1:
            errors.append(f"REVIEW_GUARD_DUPLICATE_SECTION:{heading}")
        elif count == 0:
            errors.append(f"REVIEW_GUARD_SECTION_MISSING:{heading}")
    for heading in TWO_PASS_HEADINGS:
        section = _section_by_heading(text, _SECTION_HEADING_RES[heading])
        if section is not None:
            errors.extend(_verdict_errors(section, heading))
    findings = _section_by_heading(
        text, _SECTION_HEADING_RES[FINDINGS_HEADING])
    if findings is not None:
        errors.extend(_findings_errors(findings))
    return errors


def validate_bound_review(text, *, root, task_id,
                          reference_root=None) -> list:
    """Refusal list for one review bound to a real root and task id.

    Mandatory keyword bindings: an absent, ``None``, or non-directory
    ``root`` or an empty ``task_id`` is refused instead of becoming a
    shape-only accepting check. After verify-before-use succeeds, the
    hardened section/verdict/Findings grammar checks run, then the unchanged
    historical two-pass proof and durable-correction validators of the
    reference core. An empty list means these review checks passed; it is
    never owner acceptance or complete lifecycle approval."""
    if not isinstance(text, str):
        return ["REVIEW_GUARD_TEXT_NOT_TEXT"]
    if root is None:
        return ["REVIEW_GUARD_ROOT_UNBOUND"]
    if not isinstance(task_id, str) or not task_id.strip():
        return ["REVIEW_GUARD_TASK_UNBOUND"]
    try:
        root_path = Path(root)
    except TypeError:
        return ["REVIEW_GUARD_ROOT_UNBOUND"]
    if not root_path.is_dir():
        return [f"REVIEW_GUARD_ROOT_NOT_A_DIRECTORY:{root_path}"]
    try:
        contract = load_verified_contract(reference_root)
    except ReferenceIdentityError as exc:
        return [f"REVIEW_GUARD_REFERENCE_IDENTITY:{exc}"]
    errors = _hardened_review_errors(text)
    errors.extend(contract.parse_two_pass_review(
        text, root=root_path, task_id=task_id))
    errors.extend(contract.validate_correction_dispositions(
        text, root=root_path))
    return errors

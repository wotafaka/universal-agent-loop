"""Shared executable agent-loop contract (BRAIN/16 Slice 4).

Pure, stdlib-only validation vocabulary shared by the lifecycle CLI
(``tools/project_memory.py``) and the external-engineer launcher
(``tools/run_external_glm.py``). This module is the machine-checkable form of:

- the ``TaskLifecycle`` and ``EvidenceState`` vocabularies (BRAIN/16 §4) with
  explicit transition validation — ``REVIEW_PASSED`` is the canonical
  review-success state and is never acceptance; legacy ``PENDING_OWNER_R17``
  remains a first-class compatibility alias;
- the flash-first engineer-selection decision (``flash-first/1``) with
  fail-closed pre-spawn route validation, plus the machine-readable
  ``## Adaptive routing facts`` task field set whose declared facts drive the
  deterministic expected engineer route (weather-v0.9.103 repair M1);
- the two-pass review gate (``Contract compliance`` + ``Adversarial
  validity``) and the durable-correction disposition contract (§9, §10);
- the risk-adaptive intent preflight (weather-v0.9.106): one compact,
  versioned, provider-neutral ``## Intent preflight`` task section whose
  LIGHT/FULL depth is derived deterministically from the adaptive facts plus
  the conservative candidate footprint, with fail-closed requirement ->
  success-criterion -> validation-command coverage mapping, and the
  evidence-bound ``## Convergence disposition`` for FULL-task accepting
  reviews;
- fingerprint-based nondeterminism classification (§11): only complete,
  equal fingerprints with conflicting outcomes are ``NONDETERMINISTIC``;
  ``UNKNOWN`` components can never establish equality;
- the canonical byte and hash policy (§12): digests are computed over the
  exact stored bytes, UTF-8 decoding is explicit and strict, and
  normalization exists only as a declared, versioned schema — an unknown
  schema fails closed.

Nothing here performs I/O except the explicit root-bound evidence-link
existence check. No weather, market, capital, or provider domain knowledge.
"""
from __future__ import annotations

import hashlib
import platform
import re
import sys
from pathlib import Path

# --- TaskLifecycle vocabulary (BRAIN/16 §4.1) --------------------------------

REVIEW_PASSED = "REVIEW_PASSED"
# Legacy compatibility alias: the historical review-success state. It is
# accepted everywhere ``REVIEW_PASSED`` is accepted and is never rewritten in
# archived task bytes.
LEGACY_REVIEW_PASSED_ALIAS = "PENDING_OWNER_R17"

TASK_LIFECYCLE_VOCABULARY = (
    "PROPOSED",
    "ACTIVE",
    "FIX_REQUIRED",
    "EVIDENCE_GATHERING",
    "PENDING_CODEX_REVIEW",
    "REVIEW_PASSED",
    "ACCEPTED",
    "REJECTED",
    "BLOCKED",
    "CANCELLED",
    "ABANDONED",
    "SUPERSEDED",
    "RELEASED",
    # Legacy compatibility alias (BRAIN/16 §4.1: "current command
    # compatibility is preserved exactly"). It is the historical spelling of
    # the review-success state, never a distinct acceptance state.
    LEGACY_REVIEW_PASSED_ALIAS,
)

# The canonical BRAIN/16 §4.1 vocabulary (the legacy alias above is the
# explicitly preserved compatibility member).
CANONICAL_TASK_LIFECYCLE_VOCABULARY = tuple(
    state for state in TASK_LIFECYCLE_VOCABULARY
    if state != LEGACY_REVIEW_PASSED_ALIAS)

# ``EVIDENCE_GATHERING`` currently folds into ACTIVE (honest future-neutral
# vocabulary); terminal states (``CANCELLED``/``ABANDONED``/``SUPERSEDED``/
# ``RELEASED``/``REJECTED``) have no outgoing transitions — honest semantics,
# no fake CLI support.
TASK_LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    "PROPOSED": frozenset({"ACTIVE", "CANCELLED"}),
    "ACTIVE": frozenset({
        "FIX_REQUIRED", "EVIDENCE_GATHERING", "PENDING_CODEX_REVIEW",
        "BLOCKED", "CANCELLED", "ABANDONED", "SUPERSEDED"}),
    "EVIDENCE_GATHERING": frozenset({"ACTIVE", "BLOCKED", "CANCELLED"}),
    "FIX_REQUIRED": frozenset({
        "ACTIVE", "PENDING_CODEX_REVIEW", "REJECTED", "CANCELLED", "ABANDONED"}),
    "PENDING_CODEX_REVIEW": frozenset({
        # ``ACCEPTED`` is the compressed standing-delegation acceptance of a
        # reviewed candidate (recorded in the acceptance artifacts); it never
        # bypasses the review gate itself.
        "REVIEW_PASSED", "PENDING_OWNER_R17", "ACCEPTED", "FIX_REQUIRED",
        "SUPERSEDED", "CANCELLED"}),
    "REVIEW_PASSED": frozenset({
        "ACCEPTED", "REJECTED", "FIX_REQUIRED", "SUPERSEDED", "CANCELLED"}),
    "PENDING_OWNER_R17": frozenset({
        "ACCEPTED", "REJECTED", "FIX_REQUIRED", "SUPERSEDED", "CANCELLED"}),
    "ACCEPTED": frozenset({"RELEASED"}),
    "REJECTED": frozenset(),
    "BLOCKED": frozenset({"ACTIVE", "CANCELLED"}),
    "CANCELLED": frozenset(),
    "ABANDONED": frozenset(),
    "SUPERSEDED": frozenset(),
    "RELEASED": frozenset(),
}


def validate_task_transition(current: str, new: str) -> list[str]:
    """Return fail-closed error strings for an invalid lifecycle transition."""
    if current not in TASK_LIFECYCLE_VOCABULARY:
        return [f"UNKNOWN_TASK_STATUS:{current}"]
    if new not in TASK_LIFECYCLE_VOCABULARY:
        return [f"UNKNOWN_TASK_STATUS:{new}"]
    if new not in TASK_LIFECYCLE_TRANSITIONS.get(current, frozenset()):
        return [f"INVALID_TASK_TRANSITION:{current}->{new}"]
    return []


# --- EvidenceState vocabulary (BRAIN/16 §4.2) ---------------------------------

EVIDENCE_STATE_VOCABULARY = (
    "GATHERING",
    "COLLECTED",
    "VERIFIED",
    "CONFLICTING",
    "NONDETERMINISTIC",
    "INVALIDATED",
    "MISSING",
)


def validate_evidence_state(value: str) -> str | None:
    """Return an error string for a value outside the evidence vocabulary."""
    if value in EVIDENCE_STATE_VOCABULARY:
        return None
    return f"UNKNOWN_EVIDENCE_STATE:{value}"


def classify_validation_evidence(*, occurrence_count: int, invalid_captures: int,
                                 nondeterministic_conflicts: int,
                                 unproven_captures: int) -> str:
    """Honest EvidenceState precedence over the derived validation manifest.

    ``MISSING`` (no occurrences) beats ``INVALIDATED`` (a claimed-but-invalid
    capture), which beats ``NONDETERMINISTIC`` (conflicting outcomes over
    equal complete fingerprints), which beats ``COLLECTED`` (some occurrence
    without a complete comparable capture); only occurrences that all carry
    complete valid captures with no conflicts are ``VERIFIED``.
    """
    if occurrence_count <= 0:
        return "MISSING"
    if invalid_captures > 0:
        return "INVALIDATED"
    if nondeterministic_conflicts > 0:
        return "NONDETERMINISTIC"
    if unproven_captures > 0:
        return "COLLECTED"
    return "VERIFIED"


# --- Flash-first engineer selection (flash-first/1) ---------------------------

FLASH_FIRST_POLICY = "flash-first/1"
POLICY_FLASH_FIRST = "FLASH_FIRST"
POLICY_LEGACY = "LEGACY"

ENGINEER_SELECTION_HEADING = "## Engineer selection"
SUPPORTED_ENGINEER_MODELS = (
    "zai-coding-plan/glm-5.3-flash",
    "zai-coding-plan/glm-5.3",
)
FLASH_FIRST_DEFAULT_MODEL = "zai-coding-plan/glm-5.3-flash"
FULL_ESCALATION_MODEL = "zai-coding-plan/glm-5.3"
SUPPORTED_ENGINEER_VARIANTS = ("low", "high", "max")

SELECTION_LEGACY_ABSENT = "LEGACY_ABSENT"
SELECTION_MALFORMED = "MALFORMED"
SELECTION_DECIDED = "DECIDED"

_SELECTION_FIELDS = (
    ("routing_policy", "Engineer routing policy"),
    ("model", "Primary requested model"),
    ("variant", "Requested variant"),
    ("complexity", "Task complexity"),
    ("reason", "Selection reason"),
    ("escalation_evidence", "Escalation evidence"),
)


def _selection_field(section: str, label: str) -> str | None:
    match = re.search(
        r"(?m)^- " + re.escape(label) + r": `([^`]*)`", section)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def parse_policy(active_text: str) -> str:
    """Classify a task contract as new-policy (``flash-first/1``) or legacy.

    A declared ``## Engineer selection`` section (even a malformed one) marks
    the new policy; a task without the section stays legacy and remains
    readable without any history rewrite.
    """
    selection = parse_engineer_selection(active_text)
    if selection["decision"] in (SELECTION_DECIDED, SELECTION_MALFORMED):
        return POLICY_FLASH_FIRST
    return POLICY_LEGACY


def parse_engineer_selection(active_text: str) -> dict:
    """Parse the ``## Engineer selection`` decision from a task contract."""
    heading_at = active_text.find(ENGINEER_SELECTION_HEADING)
    if heading_at < 0:
        return {"decision": SELECTION_LEGACY_ABSENT}
    section_end = active_text.find(
        "\n## ", heading_at + len(ENGINEER_SELECTION_HEADING))
    section = active_text[
        heading_at:section_end if section_end >= 0 else len(active_text)]
    fields = {name: _selection_field(section, label)
              for name, label in _SELECTION_FIELDS}
    missing = sorted(name for name, value in fields.items() if value is None)
    if missing:
        return {"decision": SELECTION_MALFORMED,
                "missing_fields": missing, **fields}
    return {"decision": SELECTION_DECIDED, **fields}


def validate_engineer_route(selection: dict, *, requested_model: str,
                            requested_variant: str) -> list[str]:
    """Validate the requested launch route against the bound task selection.

    Returns fail-closed denial reasons; an empty list authorizes the paid
    spawn. Legacy (section-absent) tasks are never denied here.
    """
    decision = selection.get("decision")
    if decision == SELECTION_LEGACY_ABSENT:
        return []
    if decision == SELECTION_MALFORMED:
        return ["ENGINEER_SELECTION_SECTION_MALFORMED:"
                + ",".join(selection.get("missing_fields", []))]
    errors: list[str] = []
    routing_policy = selection["routing_policy"]
    model = selection["model"]
    variant = selection["variant"]
    complexity = selection["complexity"]
    escalation = selection["escalation_evidence"]
    if routing_policy != FLASH_FIRST_POLICY:
        errors.append(f"ENGINEER_SELECTION_POLICY_UNSUPPORTED:{routing_policy}")
    if variant not in SUPPORTED_ENGINEER_VARIANTS:
        errors.append(f"ENGINEER_SELECTION_VARIANT_UNSUPPORTED:{variant}")
    if model not in SUPPORTED_ENGINEER_MODELS:
        errors.append(f"ENGINEER_SELECTION_MODEL_UNSUPPORTED:{model}")
    if requested_model != model:
        errors.append(
            f"ENGINEER_SELECTION_MODEL_MISMATCH:task={model},"
            f"requested={requested_model}")
    if requested_variant != variant:
        errors.append(
            f"ENGINEER_SELECTION_VARIANT_MISMATCH:task={variant},"
            f"requested={requested_variant}")
    if (model == FULL_ESCALATION_MODEL
            and not (complexity == "EXCEPTIONAL"
                     and escalation.strip().upper() != "NOT_APPLICABLE")):
        errors.append("ENGINEER_SELECTION_ESCALATION_UNJUSTIFIED")
    return errors


# --- Adaptive routing facts (weather-v0.9.103 repair M1) -----------------------
# The machine-readable ``## Adaptive routing facts`` field set is the decision
# input for the expected engineer model/variant. Parsing lives in this shared
# contract; the deterministic derivation from ``decide_route`` lives in
# ``tools/agent_loop_routing.py`` (which already imports this module). Task
# facts are never invented from prose: a declared section is parsed and
# validated, a missing section keeps the legacy behavior, and a malformed
# section fails closed.

ROUTING_FACTS_HEADING = "## Adaptive routing facts"
ROUTING_FACTS_PRESENT = "FACTS_PRESENT"
ROUTING_FACTS_LEGACY_ABSENT = "LEGACY_ABSENT"
ROUTING_FACTS_MALFORMED = "MALFORMED"

_ROUTING_FACTS_FIELDS = (
    ("work_kind", "Work kind"),
    ("risk", "Risk"),
    ("oracle_strength", "Oracle strength"),
    ("novelty", "Novelty"),
    ("ambiguity", "Ambiguity"),
    ("failure_evidence", "Failure evidence"),
    ("escalation_evidence", "Escalation evidence"),
    ("clerical_package", "Clerical package"),
)
_MATERIAL_CONTRADICTION_RE = re.compile(
    r"(?m)^- Material contradiction: `([^`]*)`")
_AUTHORITY_DOMAINS_RE = re.compile(r"(?m)^- Authority domains: (.+)$")
_BACKTICKED_RE = re.compile(r"`([^`]*)`")


def parse_adaptive_routing_facts(active_text: str) -> dict:
    """Parse the ``## Adaptive routing facts`` decision from a task contract.

    Returns ``{"decision": LEGACY_ABSENT}`` when the heading is absent (legacy
    tasks stay readable and unchanged), ``{"decision": MALFORMED,
    "missing_fields": [...]}`` when the section is declared but incomplete or
    unparseable, and ``{"decision": FACTS_PRESENT, ...}`` with the typed fact
    values otherwise. ``authority_domains`` is a list of backticked tokens
    (empty backticks mean no domain); ``material_contradiction`` is a strict
    ``true``/``false`` boolean.
    """
    heading_at = active_text.find(ROUTING_FACTS_HEADING)
    if heading_at < 0:
        return {"decision": ROUTING_FACTS_LEGACY_ABSENT}
    section_end = active_text.find(
        "\n## ", heading_at + len(ROUTING_FACTS_HEADING))
    section = active_text[
        heading_at:section_end if section_end >= 0 else len(active_text)]
    fields: dict = {}
    for name, label in _ROUTING_FACTS_FIELDS:
        match = re.search(
            r"(?m)^- " + re.escape(label) + r": `([^`]*)`", section)
        fields[name] = match.group(1).strip() if match else None
    domains_match = _AUTHORITY_DOMAINS_RE.search(section)
    if domains_match is None:
        fields["authority_domains"] = None
    else:
        fields["authority_domains"] = [
            token.strip() for token in _BACKTICKED_RE.findall(
                domains_match.group(1)) if token.strip()]
    contradiction = None
    contradiction_match = _MATERIAL_CONTRADICTION_RE.search(section)
    if contradiction_match is not None:
        token = contradiction_match.group(1).strip().lower()
        if token == "true":
            contradiction = True
        elif token == "false":
            contradiction = False
    fields["material_contradiction"] = contradiction
    missing = sorted(name for name, value in fields.items() if value is None)
    if missing:
        return {"decision": ROUTING_FACTS_MALFORMED,
                "missing_fields": missing, **fields}
    return {"decision": ROUTING_FACTS_PRESENT, **fields}


# --- Risk-adaptive intent preflight (weather-v0.9.106) -------------------------
# One compact, versioned, provider-neutral ``## Intent preflight`` contract
# inside the existing task: the machine-checkable form of the useful
# Spec-Kit-inspired clarify/analyze mechanisms. A genuinely low-risk clear
# task pays only a tiny LIGHT declaration; material work must prove complete
# requirement -> success criterion -> validation command -> planned evidence
# coverage. No second spec store, generated long-form document, dependency or
# Spec Kit code exists here. Parsing is deterministic across CRLF/LF and
# fails closed on duplicate headings/fields/IDs, malformed tables, unknown
# levels/statuses and out-of-range references.

INTENT_PREFLIGHT_HEADING = "## Intent preflight"
PREFLIGHT_COVERAGE_HEADING = "### Requirement coverage"
PREFLIGHT_SUCCESS_CRITERIA_HEADING = "## Success criteria"
PREFLIGHT_VALIDATION_BUDGET_HEADING = "## Validation command budget"
PREFLIGHT_COVERAGE_COLUMNS = (
    "Requirement", "Success criterion", "Validation command",
    "Planned evidence")

PREFLIGHT_LEGACY_ABSENT = "LEGACY_ABSENT"
PREFLIGHT_PRESENT = "PRESENT"
PREFLIGHT_MALFORMED = "MALFORMED"

PREFLIGHT_MODE_LIGHT = "LIGHT"
PREFLIGHT_MODE_FULL = "FULL"
PREFLIGHT_MODES = (PREFLIGHT_MODE_LIGHT, PREFLIGHT_MODE_FULL)
PREFLIGHT_CLARIFICATION_STATUSES = ("RESOLVED", "NOT_NEEDED", "BLOCKED")

_PREFLIGHT_FIELD_LABELS = (
    ("mode", "Mode"),
    ("clarification_status", "Clarification status"),
    ("open_clarification_ids", "Open material clarification IDs"),
    ("assumption_ids", "Assumption IDs"),
    ("requirement_ids", "Requirement IDs"),
)
# The compact LIGHT declaration: these three fields are always required once
# the section heading is declared. Assumption/requirement IDs are required
# only in FULL mode (R3: LIGHT pays only the compact clarification decision).
_PREFLIGHT_ALWAYS_REQUIRED = ("mode", "clarification_status",
                              "open_clarification_ids")
_PREFLIGHT_FULL_ONLY = ("assumption_ids", "requirement_ids")


def _parse_preflight_id_list(raw: str) -> tuple[tuple[str, ...] | None,
                                                list[str]]:
    """Parse ``NONE`` or a comma-separated non-empty ID token list."""
    if raw == "NONE":
        return (), []
    tokens = tuple(token.strip() for token in raw.split(","))
    if any(not token for token in tokens):
        return None, ["INTENT_PREFLIGHT_ID_LIST_MALFORMED"]
    return tokens, []


def parse_intent_preflight(active_text: str) -> dict:
    """Parse the ``## Intent preflight`` section of a task contract.

    Returns ``{"decision": LEGACY_ABSENT}`` when the heading is absent
    (legacy tasks stay readable and unchanged). A declared section is parsed
    deterministically; structural problems land in ``parse_errors`` and set
    ``decision`` to ``MALFORMED`` while every successfully parsed field stays
    available. Coverage rows are parsed only as raw data — the mode-dependent
    coverage rules live in :func:`validate_intent_preflight`.
    """
    heading_matches = re.findall(
        r"(?m)^" + re.escape(INTENT_PREFLIGHT_HEADING) + r"\s*$", active_text)
    if not heading_matches:
        return {"decision": PREFLIGHT_LEGACY_ABSENT}
    heading_at = active_text.find(INTENT_PREFLIGHT_HEADING)
    section_end = active_text.find(
        "\n## ", heading_at + len(INTENT_PREFLIGHT_HEADING))
    section = active_text[
        heading_at:section_end if section_end >= 0 else len(active_text)]
    errors: list[str] = []
    if len(heading_matches) > 1:
        errors.append("INTENT_PREFLIGHT_DUPLICATE_HEADING")
    fields: dict[str, str | None] = {}
    for name, label in _PREFLIGHT_FIELD_LABELS:
        matches = re.findall(
            r"(?m)^- " + re.escape(label) + r": `([^`]*)`", section)
        if not matches:
            fields[name] = None
            if name in _PREFLIGHT_ALWAYS_REQUIRED:
                errors.append(f"INTENT_PREFLIGHT_FIELD_MISSING:{name}")
        elif len(matches) > 1:
            fields[name] = matches[0].strip()
            errors.append(f"INTENT_PREFLIGHT_FIELD_DUPLICATE:{name}")
        else:
            fields[name] = matches[0].strip()
    mode = fields.get("mode")
    if mode is not None and mode not in PREFLIGHT_MODES:
        errors.append(f"INTENT_PREFLIGHT_MODE_INVALID:{mode}")
    if mode == PREFLIGHT_MODE_FULL:
        for name in _PREFLIGHT_FULL_ONLY:
            if fields.get(name) is None:
                errors.append(f"INTENT_PREFLIGHT_FIELD_MISSING:{name}")
    status = fields.get("clarification_status")
    if status is not None and status not in PREFLIGHT_CLARIFICATION_STATUSES:
        errors.append(f"INTENT_PREFLIGHT_CLARIFICATION_STATUS_INVALID:{status}")
    parsed: dict = {"decision": PREFLIGHT_MALFORMED if errors
                    else PREFLIGHT_PRESENT}
    for name in _PREFLIGHT_ALWAYS_REQUIRED + _PREFLIGHT_FULL_ONLY:
        parsed[name] = fields.get(name)
    for name in ("open_clarification_ids", "assumption_ids",
                 "requirement_ids"):
        raw = parsed.pop(name)
        if raw is None:
            parsed[name] = None
            continue
        tokens, id_errors = _parse_preflight_id_list(raw)
        parsed[name] = tokens
        for id_error in id_errors:
            errors.append(f"{id_error}:{name}")
        if tokens is not None:
            duplicates = sorted({token for token in tokens
                                 if tokens.count(token) > 1})
            if duplicates:
                errors.append(f"INTENT_PREFLIGHT_ID_LIST_DUPLICATE:{name}:"
                              f"{duplicates[0]}")
    coverage = _parse_coverage_table(section)
    errors.extend(coverage["errors"])
    parsed["coverage"] = coverage
    parsed["parse_errors"] = errors
    parsed["decision"] = PREFLIGHT_MALFORMED if errors else PREFLIGHT_PRESENT
    return parsed


def _split_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if len(stripped) < 2 or not (stripped.startswith("|")
                                 and stripped.endswith("|")):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _is_table_delimiter_row(cells: list[str] | None) -> bool:
    if not cells:
        return False
    return all(cell and re.fullmatch(r":?-+:?", cell) is not None
               for cell in cells)


def _parse_coverage_table(section: str) -> dict:
    result: dict = {"heading_present": False, "rows": (), "errors": []}
    heading_at = section.find(PREFLIGHT_COVERAGE_HEADING)
    if heading_at < 0:
        return result
    result["heading_present"] = True
    subsection_end = section.find(
        "\n### ", heading_at + len(PREFLIGHT_COVERAGE_HEADING))
    body = section[heading_at + len(PREFLIGHT_COVERAGE_HEADING):
                   subsection_end if subsection_end >= 0 else len(section)]
    pipe_lines = [line for line in (raw.strip() for raw in body.splitlines())
                  if line.startswith("|")]
    if not pipe_lines:
        result["errors"].append(
            "INTENT_PREFLIGHT_COVERAGE_TABLE_MALFORMED:header")
        return result
    header = _split_table_row(pipe_lines[0])
    if header is None or tuple(header) != PREFLIGHT_COVERAGE_COLUMNS:
        result["errors"].append(
            "INTENT_PREFLIGHT_COVERAGE_TABLE_MALFORMED:header")
    if (len(pipe_lines) < 2
            or not _is_table_delimiter_row(_split_table_row(pipe_lines[1]))):
        result["errors"].append(
            "INTENT_PREFLIGHT_COVERAGE_TABLE_MALFORMED:separator")
    rows: list[tuple[str, int, int, str]] = []
    for ordinal, line in enumerate(pipe_lines[2:], start=1):
        cells = _split_table_row(line)
        parsed_row = None
        if cells is not None and len(cells) == 4:
            requirement, criterion_text, command_text, evidence = (
                cell.strip() for cell in cells)
            if (requirement and evidence
                    and re.fullmatch(r"[0-9]+", criterion_text) is not None
                    and int(criterion_text) >= 1
                    and re.fullmatch(r"[0-9]+", command_text) is not None
                    and int(command_text) >= 1):
                parsed_row = (requirement, int(criterion_text),
                              int(command_text), evidence)
        if parsed_row is None:
            result["errors"].append(
                f"INTENT_PREFLIGHT_COVERAGE_ROW_MALFORMED:{ordinal}")
        else:
            rows.append(parsed_row)
    result["rows"] = tuple(rows)
    return result


def count_numbered_success_criteria(active_text: str) -> int | None:
    """The count of numbered items in ``## Success criteria``, or ``None``
    when the section is absent (an unverifiable anchor fails closed)."""
    if PREFLIGHT_SUCCESS_CRITERIA_HEADING not in active_text:
        return None
    section = _markdown_section(active_text,
                                PREFLIGHT_SUCCESS_CRITERIA_HEADING)
    return len(re.findall(r"(?m)^\d+\.\s+\S", section))


def count_validation_budget_commands(active_text: str) -> int | None:
    """The count of non-empty lines of the ``## Validation command budget``
    ```text fence, or ``None`` when unparseable (fail closed)."""
    if PREFLIGHT_VALIDATION_BUDGET_HEADING not in active_text:
        return None
    section = _markdown_section(active_text,
                                PREFLIGHT_VALIDATION_BUDGET_HEADING)
    fence_at = section.find("```text")
    fence_end = (section.find("```", fence_at + len("```text"))
                 if fence_at >= 0 else -1)
    if fence_at < 0 or fence_end < 0:
        return None
    return sum(1 for line in
               section[fence_at + len("```text"):fence_end].splitlines()
               if line.strip())


def derive_required_preflight_mode(facts: dict | None, *,
                                   restricted_authority: bool = False) -> str:
    """Derive LIGHT versus FULL deterministically from accepted inputs.

    Only LOW-risk, ROUTINE, CLEAR, STRONG-oracle, contradiction-free and
    unrestricted work may use LIGHT; every missing, malformed or restricted
    input derives the conservative FULL mode (R2). The inputs are the
    already-declared adaptive routing facts plus the conservative candidate
    footprint authority — no second subjective classifier.
    """
    if (not isinstance(facts, dict)
            or facts.get("decision") != ROUTING_FACTS_PRESENT):
        return PREFLIGHT_MODE_FULL
    light_class = (
        facts.get("risk") == "LOW"
        and facts.get("novelty") == "ROUTINE"
        and facts.get("ambiguity") == "CLEAR"
        and facts.get("oracle_strength") == "STRONG"
        and facts.get("material_contradiction") is False
        and not restricted_authority)
    return PREFLIGHT_MODE_LIGHT if light_class else PREFLIGHT_MODE_FULL


def validate_intent_preflight(active_text: str, *, required: bool,
                              facts: dict | None = None,
                              restricted_authority: bool = False) -> list[str]:
    """Fail-closed validation of the task's intent preflight.

    An absent section is an error only when ``required`` (open new-policy
    tasks); legacy tasks stay readable without any history rewrite. A
    declared LIGHT mode that understates the derived level fails closed;
    declaring FULL for LIGHT-class work stays allowed. FULL additionally
    requires unique stable requirement IDs with exactly one coverage row per
    requirement mapping to an existing numbered success criterion and an
    existing validation-command ordinal with a non-empty planned evidence
    class (R1-R3).
    """
    parsed = parse_intent_preflight(active_text)
    if parsed["decision"] == PREFLIGHT_LEGACY_ABSENT:
        return ["INTENT_PREFLIGHT_MISSING"] if required else []
    errors = list(parsed.get("parse_errors") or [])
    derived = derive_required_preflight_mode(
        facts, restricted_authority=restricted_authority)
    declared = parsed.get("mode")
    if (declared == PREFLIGHT_MODE_LIGHT
            and derived == PREFLIGHT_MODE_FULL):
        errors.append("INTENT_PREFLIGHT_MODE_UNDERSTATED:"
                      f"declared={declared},derived={derived}")
    if declared == PREFLIGHT_MODE_LIGHT:
        if parsed.get("open_clarification_ids"):
            errors.append("INTENT_PREFLIGHT_LIGHT_OPEN_CLARIFICATION_IDS")
    elif declared == PREFLIGHT_MODE_FULL:
        errors.extend(_validate_requirement_coverage(active_text, parsed))
    return errors


def _validate_requirement_coverage(active_text: str, parsed: dict) -> list[str]:
    errors: list[str] = []
    requirement_ids = list(parsed.get("requirement_ids") or ())
    if not requirement_ids:
        errors.append("INTENT_PREFLIGHT_REQUIREMENT_IDS_REQUIRED")
    coverage = parsed.get("coverage") or {}
    if not coverage.get("heading_present"):
        errors.append("INTENT_PREFLIGHT_COVERAGE_TABLE_MISSING")
        return errors
    rows = list(coverage.get("rows") or ())
    by_requirement: dict[str, list[tuple[str, int, int, str]]] = {}
    for row in rows:
        by_requirement.setdefault(row[0], []).append(row)
    for requirement_id in requirement_ids:
        matches = by_requirement.get(requirement_id, [])
        if not matches:
            errors.append(
                f"INTENT_PREFLIGHT_COVERAGE_ROW_MISSING:{requirement_id}")
        elif len(matches) > 1:
            errors.append(
                f"INTENT_PREFLIGHT_COVERAGE_ROW_DUPLICATE:{requirement_id}")
    declared_set = set(requirement_ids)
    for requirement_id in sorted(set(by_requirement) - declared_set):
        errors.append(f"INTENT_PREFLIGHT_COVERAGE_ROW_ORPHAN:{requirement_id}")
    criteria_count = count_numbered_success_criteria(active_text)
    commands_count = count_validation_budget_commands(active_text)
    criteria_unparseable_reported = False
    budget_unparseable_reported = False
    for requirement_id, criterion, command, _evidence in sorted(rows):
        if criteria_count is None:
            if not criteria_unparseable_reported:
                errors.append("INTENT_PREFLIGHT_SUCCESS_CRITERIA_UNPARSEABLE")
                criteria_unparseable_reported = True
        elif criterion > criteria_count:
            errors.append(
                "INTENT_PREFLIGHT_SUCCESS_CRITERION_OUT_OF_RANGE:"
                f"{requirement_id}:{criterion}")
        if commands_count is None:
            if not budget_unparseable_reported:
                errors.append("INTENT_PREFLIGHT_VALIDATION_BUDGET_UNPARSEABLE")
                budget_unparseable_reported = True
        elif command > commands_count:
            errors.append(
                "INTENT_PREFLIGHT_VALIDATION_COMMAND_OUT_OF_RANGE:"
                f"{requirement_id}:{command}")
    return errors


def intent_preflight_material_ambiguity(parsed: dict,
                                        facts: dict | None = None) -> list[str]:
    """Material ambiguity that can never consume a paid writer run (R5):
    declared ``Ambiguity: AMBIGUOUS`` facts, a ``BLOCKED`` clarification
    status, or any open material clarification ID."""
    errors: list[str] = []
    if (isinstance(facts, dict)
            and facts.get("decision") == ROUTING_FACTS_PRESENT
            and facts.get("ambiguity") == "AMBIGUOUS"):
        errors.append(
            "INTENT_PREFLIGHT_MATERIAL_AMBIGUITY:declared Ambiguity AMBIGUOUS")
    if parsed.get("decision") == PREFLIGHT_PRESENT:
        if parsed.get("clarification_status") == "BLOCKED":
            errors.append("INTENT_PREFLIGHT_MATERIAL_AMBIGUITY:"
                          "Clarification status BLOCKED")
        open_ids = parsed.get("open_clarification_ids") or ()
        if open_ids:
            errors.append(
                "INTENT_PREFLIGHT_MATERIAL_AMBIGUITY:open material "
                "clarification IDs:" + ",".join(open_ids[:8]))
    return errors


# --- Evidence-bound review convergence (weather-v0.9.106, R6) ------------------
# A FULL-task independent review reuses the existing two-pass proof and adds
# one compact ``## Convergence disposition``: an accepting review requires
# CONVERGED with exact coverage of the frozen task requirement IDs and no
# remaining material IDs; a material-delta verdict names the exact remaining
# IDs and can never be accepted. LIGHT-task reviews keep the existing burden.

CONVERGENCE_HEADING = "## Convergence disposition"
CONVERGENCE_ABSENT = "ABSENT"
CONVERGENCE_PRESENT = "PRESENT"
CONVERGENCE_DISPOSITION_CONVERGED = "CONVERGED"
CONVERGENCE_DISPOSITION_MATERIAL_DELTA = "MATERIAL_DELTA"
CONVERGENCE_DISPOSITIONS = (CONVERGENCE_DISPOSITION_CONVERGED,
                            CONVERGENCE_DISPOSITION_MATERIAL_DELTA)

_CONVERGENCE_FIELD_LABELS = (
    ("disposition", "Disposition"),
    ("covered_ids", "Covered requirement IDs"),
    ("remaining_ids", "Remaining material requirement IDs"),
)


def _parse_convergence_id_list(raw: str) -> tuple[tuple[str, ...] | None,
                                                  str | None]:
    if raw == "NONE":
        return (), None
    tokens = tuple(token.strip() for token in raw.split(","))
    if any(not token for token in tokens):
        return None, "CONVERGENCE_ID_LIST_MALFORMED"
    return tokens, None


def parse_convergence_disposition(review_text: str) -> dict:
    """Parse the ``## Convergence disposition`` section of a review artifact.

    ``{"decision": ABSENT}`` when the heading is absent; otherwise the parsed
    fields with structural problems in ``parse_errors`` (deterministic across
    CRLF/LF; duplicate headings/fields and malformed ID lists fail closed).
    """
    heading_matches = re.findall(
        r"(?m)^" + re.escape(CONVERGENCE_HEADING) + r"\s*$", review_text)
    if not heading_matches:
        return {"decision": CONVERGENCE_ABSENT}
    heading_at = review_text.find(CONVERGENCE_HEADING)
    section_end = review_text.find(
        "\n## ", heading_at + len(CONVERGENCE_HEADING))
    section = review_text[
        heading_at:section_end if section_end >= 0 else len(review_text)]
    errors: list[str] = []
    if len(heading_matches) > 1:
        errors.append("CONVERGENCE_DISPOSITION_DUPLICATE_HEADING")
    values: dict[str, str | None] = {}
    for name, label in _CONVERGENCE_FIELD_LABELS:
        matches = re.findall(
            r"(?m)^- " + re.escape(label) + r": `([^`]*)`", section)
        if not matches:
            values[name] = None
            errors.append(f"CONVERGENCE_DISPOSITION_FIELD_MISSING:{name}")
        elif len(matches) > 1:
            values[name] = matches[0].strip()
            errors.append(f"CONVERGENCE_DISPOSITION_FIELD_DUPLICATE:{name}")
        else:
            values[name] = matches[0].strip()
    disposition = values.get("disposition")
    if (disposition is not None
            and disposition not in CONVERGENCE_DISPOSITIONS):
        errors.append(f"CONVERGENCE_DISPOSITION_INVALID:{disposition}")
    parsed: dict = {"decision": CONVERGENCE_PRESENT, **values}
    for name in ("covered_ids", "remaining_ids"):
        raw = parsed.pop(name)
        if raw is None:
            parsed[name] = None
            continue
        tokens, id_error = _parse_convergence_id_list(raw)
        parsed[name] = tokens
        if id_error is not None:
            errors.append(f"{id_error}:{name}")
            continue
        duplicates = sorted({token for token in tokens
                             if tokens.count(token) > 1})
        if duplicates:
            errors.append(f"CONVERGENCE_ID_LIST_DUPLICATE:{name}:"
                          f"{duplicates[0]}")
    parsed["parse_errors"] = errors
    return parsed


def validate_convergence_disposition(review_text: str, requirement_ids,
                                     *, accepting: bool = True) -> list[str]:
    """Validate the convergence disposition against the frozen requirement IDs.

    An accepting review requires ``CONVERGED``, exact coverage of the frozen
    IDs and ``Remaining material requirement IDs: NONE``; a material-delta
    verdict names exact remaining IDs and can never be accepted. Unknown,
    overlapping, duplicated and inconsistent IDs all fail closed.
    """
    parsed = parse_convergence_disposition(review_text)
    if parsed["decision"] == CONVERGENCE_ABSENT:
        return ["CONVERGENCE_DISPOSITION_SECTION_MISSING"]
    errors = list(parsed.get("parse_errors") or [])
    frozen = set(requirement_ids or ())
    covered = set(parsed.get("covered_ids") or ())
    remaining = set(parsed.get("remaining_ids") or ())
    for requirement_id in sorted(covered - frozen):
        errors.append(f"CONVERGENCE_COVERED_ID_UNKNOWN:{requirement_id}")
    for requirement_id in sorted(remaining - frozen):
        errors.append(f"CONVERGENCE_REMAINING_ID_UNKNOWN:{requirement_id}")
    if covered & remaining:
        errors.append("CONVERGENCE_COVERED_REMAINING_OVERLAP")
    disposition = parsed.get("disposition")
    if (disposition == CONVERGENCE_DISPOSITION_CONVERGED and remaining):
        errors.append("CONVERGENCE_INCONSISTENT_REMAINING_IDS")
    if (disposition == CONVERGENCE_DISPOSITION_MATERIAL_DELTA
            and not remaining):
        errors.append("CONVERGENCE_DELTA_WITHOUT_REMAINING_IDS")
    if accepting:
        if disposition != CONVERGENCE_DISPOSITION_CONVERGED:
            errors.append("CONVERGENCE_NOT_CONVERGED_ACCEPTING_REVIEW")
        if not frozen or covered != frozen:
            errors.append("CONVERGENCE_COVERAGE_INCOMPLETE")
    return errors


# --- Two-pass review gate (BRAIN/16 §9) ----------------------------------------

TWO_PASS_HEADINGS = ("## Contract compliance", "## Adversarial validity")
PASS_VERDICT_PASS = "PASS"
PASS_VERDICT_FAIL = "FAIL"

_VERDICT_RE = re.compile(r"(?m)^- Verdict: `(PASS|FAIL)`\s*$")
_EVIDENCE_LINE_RE = re.compile(r"(?m)^- Evidence: (.+?)\s*$")

# --- Proof-backed review evidence (BRAIN/16 §9, validation-review-proof/1) ---
# A two-pass ``Evidence`` line must be a bounded versioned proof record: one
# existing repository-local artifact, its exact stored-byte SHA-256, an
# explicitly reviewer-owned origin, the recorded recomputation/re-execution
# action, and the bound candidate task id. Reviewer prose and
# implementer-reported origins can never satisfy independent verification.

PROOF_RECORD_SCHEMA = "validation-review-proof/1"
PROOF_RECORD_ALLOWED_ORIGINS = ("REVIEWER_RECOMPUTED", "REVIEWER_REEXECUTED")

_PROOF_CONTENT_RE = re.compile(
    r"^(?:- Evidence: )?`validation-review-proof/(\d+)` artifact `([^`]*)`"
    r" sha256 `([^`]*)` origin `([^`]*)` action `([^`]*)` candidate `([^`]*)`$")


def _markdown_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    body_start = start + len(heading)
    next_heading = text.find("\n## ", body_start)
    return text[body_start:next_heading if next_heading >= 0 else len(text)]


def _validate_proof_record(content: str, heading: str, root, task_id) -> list[str]:
    """Validate one two-pass proof record against the stored artifact bytes."""
    errors: list[str] = []
    match = _PROOF_CONTENT_RE.match(content)
    if match is None:
        return [f"REVIEW_TWO_PASS_EVIDENCE_INVALID:{heading}"]
    version, artifact_rel, claimed_sha, origin, action, candidate = (
        match.groups())
    if f"validation-review-proof/{version}" != PROOF_RECORD_SCHEMA:
        return [f"REVIEW_TWO_PASS_EVIDENCE_INVALID:{heading}"]
    if origin not in PROOF_RECORD_ALLOWED_ORIGINS:
        return [f"REVIEW_TWO_PASS_EVIDENCE_ORIGIN_UNPROVEN:{heading}"]
    if not action.strip():
        return [f"REVIEW_TWO_PASS_EVIDENCE_ACTION_EMPTY:{heading}"]
    if root is not None:
        artifact_rel = artifact_rel.strip()
        resolved = None
        try:
            resolved = (Path(root) / artifact_rel).resolve(strict=False)
            resolved.relative_to(Path(root).resolve(strict=False))
        except (ValueError, OSError, RuntimeError):
            resolved = None
        if resolved is None or not resolved.is_file():
            return [f"REVIEW_TWO_PASS_EVIDENCE_ARTIFACT_MISSING:{heading}"]
        actual_sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_sha != claimed_sha.strip().lower():
            return [f"REVIEW_TWO_PASS_EVIDENCE_HASH_MISMATCH:{heading}"]
    if task_id is not None and candidate.strip() != task_id:
        errors.append(f"REVIEW_TWO_PASS_EVIDENCE_TASK_MISMATCH:{heading}")
    return errors


def parse_two_pass_review(review_text: str, root=None,
                          task_id=None) -> list[str]:
    """Enforce both mandatory review passes for an accepting review.

    Missing headings, missing/invalid verdicts, empty evidence, and a ``FAIL``
    pass underneath an accepting verdict fail closed — headings or prose alone
    can never pass. Each pass ``Evidence`` line must be a versioned
    ``validation-review-proof/1`` record bound to one existing repository-local
    artifact whose exact stored bytes hash to the claimed digest and whose
    recorded candidate matches the task; a reviewer-owned origin and a
    nonempty recorded recomputation/re-execution action are required.
    When ``root``/``task_id`` are not supplied, artifact/task bindings are
    skipped and only the record shape is enforced.
    """
    errors: list[str] = []
    for heading in TWO_PASS_HEADINGS:
        if heading not in review_text:
            errors.append(f"REVIEW_TWO_PASS_HEADING_MISSING:{heading}")
            continue
        section = _markdown_section(review_text, heading)
        verdict = _VERDICT_RE.search(section)
        if verdict is None:
            errors.append(f"REVIEW_TWO_PASS_VERDICT_INVALID:{heading}")
        elif verdict.group(1) == PASS_VERDICT_FAIL:
            errors.append(f"REVIEW_TWO_PASS_FAIL_WITH_ACCEPTING_VERDICT:{heading}")
        evidence = _EVIDENCE_LINE_RE.search(section)
        if evidence is None or not evidence.group(1).strip():
            errors.append(f"REVIEW_TWO_PASS_EVIDENCE_EMPTY:{heading}")
            continue
        errors.extend(_validate_proof_record(
            evidence.group(1).strip(), heading, root, task_id))
    return errors


# --- Reviewer-owned adversarial challenge (weather-v0.9.104, A4) -----------------
# Audit finding A4_ADVERSARIAL_CHALLENGE: an accepting HIGH-risk adversarial
# pass could cite only a repeat of the implementer focused suite, preserving
# a shared oracle blind spot. An accepting HIGH-risk review must therefore
# bind one reviewer-owned challenge — a negative counterexample,
# invariant/property case, differential oracle, bounded mutation or explicit
# boundary trace — with type, target, artifact path/bytes/SHA-256 and
# result, distinct from the implementer-suite evidence artifact. Mechanical
# tasks with a demonstrably complete oracle may declare the narrow
# ``COMPLETE_MECHANICAL_ORACLE`` exemption instead.

ADVERSARIAL_HEADING = "## Adversarial validity"
ADVERSARIAL_CONTRACT_COMPLIANCE_HEADING = "## Contract compliance"
ADVERSARIAL_CHALLENGE_TYPES = (
    "NEGATIVE_COUNTEREXAMPLE",
    "INVARIANT_PROPERTY_CASE",
    "DIFFERENTIAL_ORACLE",
    "BOUNDED_MUTATION",
    "BOUNDARY_TRACE",
)
ADVERSARIAL_EXEMPTION_COMPLETE_MECHANICAL_ORACLE = "COMPLETE_MECHANICAL_ORACLE"

_ADVERSARIAL_FIELD_RES = {
    "type": re.compile(r"(?m)^- Challenge type: `([A-Za-z0-9_.-]+)`\s*$"),
    "target": re.compile(r"(?m)^- Challenge target: `([^`]*)`\s*$"),
    "artifact": re.compile(r"(?m)^- Challenge artifact: `([^`]*)`\s*$"),
    "artifact_bytes": re.compile(
        r"(?m)^- Challenge artifact bytes: `([0-9]+)`\s*$"),
    "artifact_sha256": re.compile(
        r"(?m)^- Challenge artifact sha256: `([0-9a-fA-F]{64})`\s*$"),
    "result": re.compile(r"(?m)^- Challenge result: `([^`]*)`\s*$"),
}
_ADVERSARIAL_EXEMPTION_RE = re.compile(
    r"(?m)^- Adversarial exemption: `([A-Za-z0-9_]+)`\s*$")


def _contract_compliance_evidence_sha(review_text: str) -> str | None:
    """The recorded artifact SHA-256 of the Contract-compliance pass, when
    parseable — the same-origin boundary for the challenge artifact."""
    section = _markdown_section(review_text,
                                ADVERSARIAL_CONTRACT_COMPLIANCE_HEADING)
    evidence = _EVIDENCE_LINE_RE.search(section)
    if evidence is None:
        return None
    match = _PROOF_CONTENT_RE.match(evidence.group(1).strip())
    if match is None:
        return None
    return match.group(3).strip().lower()


def validate_adversarial_challenge(review_text: str, root=None,
                                   task_id=None, *,
                                   challenge_required: bool = True,
                                   exemption_allowed: bool = False) -> list[str]:
    """Validate the reviewer-owned challenge of an accepting HIGH-risk review.

    When ``challenge_required`` is false (a review of a task that does not
    declare HIGH risk) the challenge is optional and nothing is enforced.
    When required, the ``## Adversarial validity`` section must either bind
    the complete structured challenge record or — only when
    ``exemption_allowed`` (declared mechanical work) — the narrow
    ``COMPLETE_MECHANICAL_ORACLE`` exemption. The challenge artifact must
    exist under the repository root with the exact recorded bytes and
    SHA-256, and must differ from the Contract-compliance evidence artifact
    (same origin fails closed). Missing, malformed, same-origin and
    mis-scoped exemptions all fail the accepting review."""
    del task_id  # the challenge artifact is reviewer-owned scratch evidence
    if not challenge_required:
        return []
    section = _markdown_section(review_text, ADVERSARIAL_HEADING)
    errors: list[str] = []

    def fail(code: str) -> list[str]:
        return [code]

    exemption = _ADVERSARIAL_EXEMPTION_RE.search(section)
    if exemption is not None:
        value = exemption.group(1)
        if value != ADVERSARIAL_EXEMPTION_COMPLETE_MECHANICAL_ORACLE:
            return fail(f"ADVERSARIAL_EXEMPTION_INVALID:{value}")
        if not exemption_allowed:
            return fail("ADVERSARIAL_EXEMPTION_NOT_ALLOWED:only declared "
                        "MECHANICAL work may claim the complete-oracle "
                        "exemption")
        return []
    fields: dict[str, str] = {}
    missing: list[str] = []
    for name, pattern in _ADVERSARIAL_FIELD_RES.items():
        match = pattern.search(section)
        if match is None:
            missing.append(name)
        else:
            fields[name] = match.group(1).strip()
    if missing:
        return [f"ADVERSARIAL_CHALLENGE_FIELD_MISSING:{name}"
                for name in missing] + [
            "ADVERSARIAL_CHALLENGE_REQUIRED:an accepting HIGH-risk review "
            "must bind one distinct reviewer-owned challenge"]
    if fields["type"] not in ADVERSARIAL_CHALLENGE_TYPES:
        errors.append(f"ADVERSARIAL_CHALLENGE_TYPE_INVALID:{fields['type']}")
    if not fields["target"]:
        errors.append("ADVERSARIAL_CHALLENGE_FIELD_MISSING:target")
    if not fields["result"]:
        errors.append("ADVERSARIAL_CHALLENGE_FIELD_MISSING:result")
    artifact_bytes = (int(fields["artifact_bytes"])
                      if "artifact_bytes" in fields else None)
    claimed_sha = fields.get("artifact_sha256", "")
    if root is not None and "artifact" in fields:
        artifact_rel = fields["artifact"]
        resolved = None
        try:
            resolved = (Path(root) / artifact_rel).resolve(strict=False)
            resolved.relative_to(Path(root).resolve(strict=False))
        except (ValueError, OSError, RuntimeError):
            resolved = None
        if resolved is None or not resolved.is_file():
            errors.append("ADVERSARIAL_CHALLENGE_ARTIFACT_MISSING:"
                          f"{artifact_rel}")
        else:
            data = resolved.read_bytes()
            if artifact_bytes is not None and len(data) != artifact_bytes:
                errors.append("ADVERSARIAL_CHALLENGE_ARTIFACT_BYTES_MISMATCH")
            if claimed_sha.lower() != hashlib.sha256(data).hexdigest():
                errors.append("ADVERSARIAL_CHALLENGE_ARTIFACT_SHA_MISMATCH")
    same_origin = _contract_compliance_evidence_sha(review_text)
    if (same_origin is not None and claimed_sha
            and same_origin == claimed_sha.lower()):
        errors.append("ADVERSARIAL_CHALLENGE_SAME_ORIGIN:the challenge "
                      "artifact must be distinct from the implementer-suite "
                      "evidence")
    return errors


# --- Durable correction contract (BRAIN/16 §10) ---------------------------------

CORRECTION_HEADING = "## Durable correction"
CORRECTION_OUTCOMES = ("NONE_REQUIRED", "LESSON_RECORDED", "RULE_PROMOTED")
CORRECTION_NONE_REQUIRED = "NONE_REQUIRED"
FINDINGS_HEADING = "## Findings"
# ``LESSON_RECORDED`` must bind a real entry in the existing durable lessons
# store — never a duplicate store or an unrelated artifact.
LESSONS_LEARNED_PATH = "BRAIN/LESSONS_LEARNED.md"

_CORRECTION_LINE_RE = re.compile(
    r"(?m)^- ([A-Za-z][A-Za-z0-9._-]*): "
    r"`(NONE_REQUIRED|LESSON_RECORDED|RULE_PROMOTED)`"
    r" — rationale: (.+?) — evidence: (.+?)\s*$")
_CORRECTION_ANY_OUTCOME_RE = re.compile(
    r"(?m)^- ([A-Za-z][A-Za-z0-9._-]*): `([A-Z][A-Z_]*)`"
    r" — rationale: ")
_MANDATED_CHANGE_RE = re.compile(r"(?m)^- Mandated change: `([^`]*)`")
_MANDATED_ID_RE = re.compile(r"([A-Za-z][A-Za-z0-9._-]*):\s")
_MATERIAL_FINDING_RE = re.compile(r"(?m)^- ([A-Z]{1,8}\d+): ")
_CORRECTION_EVIDENCE_REF_RE = re.compile(r"`([^`]+)`")
_RULE_ANCHOR_RE = re.compile(r"^R\d+")
_TEST_REF_RE = re.compile(r"(?:^tests/|#test)")


def _correction_evidence_ref_errors(ref: str, finding_id: str, root) -> list[str]:
    """One anchored, repository-local, resolvable evidence reference."""
    errors: list[str] = []
    path_part, _sep, anchor = ref.partition("#")
    if not anchor:
        return [f"CORRECTION_EVIDENCE_REF_MALFORMED:{finding_id}"]
    try:
        resolved = (Path(root) / path_part).resolve(strict=False)
        resolved.relative_to(Path(root).resolve(strict=False))
    except (ValueError, OSError, RuntimeError):
        return [f"CORRECTION_EVIDENCE_LINK_MISSING:{path_part}"]
    if not resolved.is_file():
        return [f"CORRECTION_EVIDENCE_LINK_MISSING:{path_part}"]
    try:
        content = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return [f"CORRECTION_EVIDENCE_LINK_MISSING:{path_part}"]
    if anchor not in content:
        errors.append(f"CORRECTION_EVIDENCE_ANCHOR_MISSING:{ref}")
    return errors


def validate_correction_dispositions(review_text: str, root) -> list[str]:
    """Validate the durable-correction block of a review artifact.

    Rules: every material finding (``- M1: ...`` style lines in ``## Findings``)
    carries exactly one terminal disposition with a non-empty rationale and a
    verifiable repository-local evidence link; no dispositions for findings
    that do not exist; exactly one mandated-change line; and ``NONE_REQUIRED``
    combined with a mandated change for the same finding is a contradiction
    that fails review. Every disposition — including ``NONE_REQUIRED`` —
    requires at least one anchored (``path#anchor``) backticked evidence
    reference; the anchor must resolve inside the stored file bytes;
    ``LESSON_RECORDED`` must bind the existing lessons file, and
    ``RULE_PROMOTED`` must bind both a rule anchor and a verifying test.
    Zero findings can honestly declare none — nothing is invented.
    """
    errors: list[str] = []
    findings_section = _markdown_section(review_text, FINDINGS_HEADING)
    material = set(_MATERIAL_FINDING_RE.findall(findings_section))
    section = _markdown_section(review_text, CORRECTION_HEADING)
    invalid_outcomes: dict[str, bool] = {}
    for match in _CORRECTION_ANY_OUTCOME_RE.finditer(section):
        finding_id, outcome = match.group(1), match.group(2)
        if outcome not in CORRECTION_OUTCOMES:
            invalid_outcomes[finding_id] = True
            errors.append(f"CORRECTION_DISPOSITION_INVALID_OUTCOME:{finding_id}")
    dispositions: dict[str, tuple[str, str, str]] = {}
    for match in _CORRECTION_LINE_RE.finditer(section):
        finding_id, outcome, rationale, evidence = match.groups()
        if finding_id in dispositions:
            errors.append(f"CORRECTION_DISPOSITION_DUPLICATE:{finding_id}")
            continue
        dispositions[finding_id] = (
            outcome, rationale.strip(), evidence.strip())
    for finding_id in sorted(material):
        if finding_id not in dispositions and finding_id not in invalid_outcomes:
            errors.append(f"CORRECTION_DISPOSITION_MISSING:{finding_id}")
    mandated_matches = _MANDATED_CHANGE_RE.findall(section)
    if len(mandated_matches) > 1:
        errors.append("CORRECTION_MANDATED_CHANGE_DUPLICATE")
    mandated_ids: set[str] = set()
    for mandated_value in mandated_matches:
        if mandated_value.strip().upper() != "NONE":
            mandated_ids.update(_MANDATED_ID_RE.findall(mandated_value))
    for finding_id, (outcome, rationale, evidence) in dispositions.items():
        if finding_id not in material:
            errors.append(f"CORRECTION_DISPOSITION_UNKNOWN_FINDING:{finding_id}")
        if not rationale:
            errors.append(f"CORRECTION_RATIONALE_EMPTY:{finding_id}")
        refs = _CORRECTION_EVIDENCE_REF_RE.findall(evidence)
        if not refs:
            # An unparseable or unanchored evidence blob (e.g. a bare
            # nonexistent filename) verifies nothing and fails closed.
            errors.append(f"CORRECTION_EVIDENCE_LINK_MISSING:{finding_id}")
            continue
        ref_errors: list[str] = []
        for ref in refs:
            ref_errors.extend(
                _correction_evidence_ref_errors(ref, finding_id, root))
        errors.extend(ref_errors)
        if outcome == CORRECTION_NONE_REQUIRED:
            if finding_id in mandated_ids:
                errors.append(
                    "CORRECTION_CONTRADICTION_NONE_REQUIRED_WITH_MANDATED_CHANGE:"
                    f"{finding_id}")
            continue
        if outcome == "LESSON_RECORDED":
            bound_paths = {ref.split("#", 1)[0] for ref in refs}
            if len(refs) != 1 or bound_paths != {LESSONS_LEARNED_PATH}:
                errors.append(
                    f"CORRECTION_LESSON_RECORDED_NOT_LESSONS_FILE:{finding_id}")
        elif outcome == "RULE_PROMOTED":
            rule_refs = [ref for ref in refs
                         if _RULE_ANCHOR_RE.match(ref.split("#", 1)[-1])]
            test_refs = [ref for ref in refs if _TEST_REF_RE.search(ref)]
            if len(refs) < 2 or not rule_refs or not test_refs:
                errors.append(
                    f"CORRECTION_RULE_PROMOTED_MISSING_RULE_OR_TEST:{finding_id}")
    return errors


# --- Fingerprint-based nondeterminism (BRAIN/16 §11) ----------------------------

CONSISTENT = "CONSISTENT"
NONDETERMINISTIC = "NONDETERMINISTIC"
NOT_COMPARABLE = "NOT_COMPARABLE"
CHANGED_CANDIDATE = "CHANGED_CANDIDATE"

FINGERPRINT_FIELDS = (
    "candidate_digest",
    "command_argv",
    "environment_policy_identity",
    "platform_identity",
    "declared_seed",
)


def build_occurrence_fingerprint(*, candidate_digest, command_argv,
                                 environment_policy_identity,
                                 platform_identity, declared_seed) -> dict:
    """Build one comparable run fingerprint; missing parts stay ``UNKNOWN``
    (``None``) and never get guessed."""
    return {
        "candidate_digest": candidate_digest,
        "command_argv": command_argv,
        "environment_policy_identity": environment_policy_identity,
        "platform_identity": platform_identity,
        "declared_seed": declared_seed,
    }


def platform_identity() -> str:
    """The derivation-host platform/interpreter identity component."""
    return (f"{sys.platform}|{platform.python_implementation()}-"
            f"{platform.python_version()}")


def fingerprint_is_complete(fingerprint: dict) -> bool:
    """A fingerprint with any ``UNKNOWN`` member never proves equality."""
    return all(
        isinstance(fingerprint.get(field), str) and fingerprint.get(field)
        for field in FINGERPRINT_FIELDS)


def classify_fingerprint_pair(fingerprint_a: dict, outcome_a,
                              fingerprint_b: dict, outcome_b) -> str:
    """Classify two fingerprint-comparable runs.

    Equal complete fingerprints with conflicting outcomes are
    ``NONDETERMINISTIC``; a changed candidate digest makes the conflict an
    expected changed-candidate outcome (e.g. RED→GREEN), never
    nondeterminism; any ``UNKNOWN`` component leaves the pair
    ``NOT_COMPARABLE`` — equality can never be established from it.
    """
    if not (fingerprint_is_complete(fingerprint_a)
            and fingerprint_is_complete(fingerprint_b)):
        return NOT_COMPARABLE
    if fingerprint_a == fingerprint_b:
        return CONSISTENT if outcome_a == outcome_b else NONDETERMINISTIC
    if fingerprint_a["candidate_digest"] != fingerprint_b["candidate_digest"]:
        return CHANGED_CANDIDATE
    return NOT_COMPARABLE


# --- Canonical byte and hash policy (BRAIN/16 §12) -------------------------------


class UnknownNormalizationSchemaError(ValueError):
    """A normalization schema that is not explicitly declared and versioned."""


# No normalization schema is declared today: stored bytes are canonical by
# default (rule 1). Any future normalization must be registered here with a
# versioned name and recorded next to every digest it produces (rule 2).
KNOWN_NORMALIZATION_SCHEMAS: dict = {}


def digest_stored_bytes(data: bytes) -> str:
    """SHA-256 over the exact stored bytes; never any implicit normalization."""
    return hashlib.sha256(data).hexdigest()


def decode_utf8_strict(data: bytes) -> str:
    """Explicit strict UTF-8 decoding; encoding/line endings stay as stored."""
    return data.decode("utf-8")


def normalize_for_digest(data: bytes, schema):
    """Apply only a declared, versioned normalization; unknown schemas fail
    closed instead of silently normalizing."""
    if schema is None:
        return data
    try:
        transform = KNOWN_NORMALIZATION_SCHEMAS[schema]
    except KeyError:
        raise UnknownNormalizationSchemaError(
            f"UNKNOWN_NORMALIZATION_SCHEMA:{schema}") from None
    return transform(data)

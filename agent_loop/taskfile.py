"""The compact versioned ``ual-task/1`` schema and its fail-closed checks.

One JSON task file is the only authoritative task database. The checks
here refuse materially ambiguous or incomplete tasks before any paid
spawn, derive the conservative candidate footprint from the actual
allowlist (declared facts may strengthen but never weaken it), and map
FULL requirement coverage onto exact validation commands.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import UALError
from .hashing import load_json

TASK_SCHEMA = "ual-task/1"
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
ORACLE_STRENGTHS = ("STRONG", "WEAK", "NONE")
NOVELTY_VALUES = ("ROUTINE", "NOVEL")
AMBIGUITY_VALUES = ("CLEAR", "AMBIGUOUS")
FAILURE_EVIDENCE_VALUES = ("NONE", "REPRODUCED_MATERIAL")
ESCALATION_EVIDENCE_VALUES = ("NONE", "CONCRETE_INABILITY")
AUTHORITY_DOMAINS = ("ACCEPTANCE", "SAFETY", "CAPITAL", "SECURITY",
                     "DATA_INTEGRITY")
RESTRICTED_AUTHORITY_DOMAINS = ("SAFETY", "CAPITAL", "SECURITY",
                                "DATA_INTEGRITY")
WORK_KINDS = ("MECHANICAL", "CLERICAL", "OBSERVATION", "IMPLEMENTATION",
              "ARCHITECTURE", "REVIEW", "AUDIT")
MODES = ("LIGHT", "FULL")
CLARIFICATION_STATUSES = ("RESOLVED", "NOT_NEEDED", "BLOCKED")
EXPECTED_OUTCOMES = ("RED", "GREEN")
REPORT_EXCLUDED_FROM_CAPTURE = True

EXECUTABLE_SUFFIXES = (".py", ".sh", ".ps1", ".bat", ".cmd", ".js",
                       ".ts", ".mjs", ".cjs", ".go", ".rs", ".rb", ".php",
                       ".java", ".c", ".cpp", ".cs")
TEST_DIRECTORY_PREFIX = "tests/"
TEST_STEM_PREFIX = "test_"
DOCUMENT_SUFFIXES = (".md", ".json", ".toml", ".txt", ".cfg", ".ini",
                     ".yaml", ".yml")
GOVERNANCE_PATH_MARKERS = (
    "agent_loop", "project_memory", "external_glm", "external_audit",
    "entrypoint", "delivery_workflow", "contract", "routing",
    "task_template", "agents.md",
)

REQUIRED_FIELDS = ("schema", "id", "title", "mode", "risk", "work_kind",
                   "oracle_strength", "novelty", "ambiguity",
                   "failure_evidence", "escalation_evidence",
                   "authority_domains", "material_contradiction",
                   "clarification_status", "open_clarification_ids",
                   "owner_actor", "validation", "candidate", "review",
                   "audit", "observer", "lessons_path")
OPTIONAL_FIELDS = ("requirements", "success_criteria_count",
                   "generated_state", "required_skills")


def load_task(path: Path) -> dict:
    task = load_json(Path(path))
    if not isinstance(task, dict):
        raise UALError("TASK_MALFORMED", "not-an-object")
    return task


def task_id_of(task: dict) -> str:
    return task.get("id") or ""


def report_rel(task: dict) -> str:
    return (task.get("candidate") or {}).get("report") or ""


def allowlist(task: dict) -> list:
    return list((task.get("candidate") or {}).get("allowlist") or [])


def validation_commands(task: dict) -> list:
    return list((task.get("validation") or {}).get("commands") or [])


def declared_seed(task: dict) -> str:
    return str((task.get("validation") or {}).get("seed") or "")


def environment_policy(task: dict) -> dict:
    env = (task.get("validation") or {}).get("environment") or {}
    return {"base": list(env.get("base") or []),
            "overlay": dict(env.get("overlay") or {})}


def command_facts(task: dict) -> dict:
    facts = {name: task.get(name) for name in (
        "work_kind", "risk", "oracle_strength", "novelty", "ambiguity",
        "failure_evidence", "escalation_evidence", "clerical_package")}
    facts["authority_domains"] = list(task.get("authority_domains") or [])
    facts["material_contradiction"] = bool(
        task.get("material_contradiction"))
    return facts


def classify_candidate_member(member: str) -> str:
    if not isinstance(member, str) or not member.strip():
        return "UNKNOWN"
    normalized = member.strip().replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1].lower()
    if (normalized.lower().startswith(TEST_DIRECTORY_PREFIX)
            or (name.startswith(TEST_STEM_PREFIX)
                and name.endswith(".py"))):
        return "TEST"
    if any(name.endswith(suffix) for suffix in EXECUTABLE_SUFFIXES):
        return "EXECUTABLE"
    if any(name.endswith(suffix) for suffix in DOCUMENT_SUFFIXES):
        return "DOCUMENT"
    return "UNKNOWN"


def _is_governance(member: str, member_class: str) -> bool:
    if member_class == "TEST":
        return False
    normalized = member.strip().replace("\\", "/").lower()
    return any(marker in normalized
               for marker in GOVERNANCE_PATH_MARKERS)


def derive_candidate_footprint(task: dict) -> dict:
    """Conservative footprint from the allowlist, strengthened by the
    user-declared validation commands: any allowlist member referenced
    as a validation command operand is executable regardless of
    suffix/extension, so non-Python projects classify without any
    language registry."""
    members = allowlist(task)
    declared_tokens = set()
    for command in validation_commands(task):
        for token in command.get("argv") or []:
            if isinstance(token, str):
                declared_tokens.add(token.replace("\\", "/").rsplit("/", 1)[-1])
    member_classes = {}
    errors = []
    executable = False
    governance = False
    for member in members:
        member_class = classify_candidate_member(member)
        if member_class in ("DOCUMENT", "UNKNOWN"):
            name = member.strip().replace("\\", "/").rsplit("/", 1)[-1]
            if name in declared_tokens or \
                    any(name.endswith(s) for s in EXECUTABLE_SUFFIXES):
                member_class = "EXECUTABLE"
        member_classes[member] = member_class
        if member_class == "UNKNOWN":
            errors.append(f"TASK_FOOTPRINT_UNKNOWN_MEMBER:{member}")
            continue
        if member_class == "EXECUTABLE":
            executable = True
        if _is_governance(member, member_class):
            governance = True
    restricted = bool(set(task.get("authority_domains") or [])
                      & set(RESTRICTED_AUTHORITY_DOMAINS))
    return {"member_classes": member_classes, "errors": errors,
            "executable": executable, "governance": governance,
            "requires_tdd": executable, "restricted_authority": restricted}


def footprint_refusals(task: dict, footprint: dict) -> list:
    errors = list(footprint.get("errors") or [])
    work_kind = task.get("work_kind")
    if ((footprint.get("governance") or footprint.get("executable"))
            and work_kind in ("MECHANICAL", "CLERICAL", "OBSERVATION")):
        errors.append("TASK_FOOTPRINT_WEAKER_ROUTE:"
                      f"{work_kind} declared for executable/governance "
                      f"candidate")
    if footprint.get("governance"):
        if not footprint.get("restricted_authority"):
            errors.append(
                "TASK_FOOTPRINT_GOVERNANCE_WITHOUT_RESTRICTED_AUTHORITY")
    return errors


def derived_mode(task: dict) -> str:
    light_class = (
        task.get("risk") == "LOW"
        and task.get("novelty") == "ROUTINE"
        and task.get("ambiguity") == "CLEAR"
        and task.get("oracle_strength") == "STRONG"
        and task.get("material_contradiction") is False
        and not (set(task.get("authority_domains") or [])
                 & set(RESTRICTED_AUTHORITY_DOMAINS)))
    return "LIGHT" if light_class else "FULL"


def material_ambiguity(task: dict) -> list:
    errors = []
    if task.get("ambiguity") == "AMBIGUOUS":
        errors.append("PREFLIGHT_MATERIAL_AMBIGUITY:declared Ambiguity "
                      "AMBIGUOUS")
    if task.get("clarification_status") == "BLOCKED":
        errors.append("PREFLIGHT_MATERIAL_AMBIGUITY:"
                      "clarification_status_blocked")
    open_ids = task.get("open_clarification_ids") or []
    if open_ids:
        errors.append("PREFLIGHT_MATERIAL_AMBIGUITY:"
                      "open_clarification_ids:" + ",".join(
                          str(i) for i in open_ids[:8]))
    return errors


def validate_task(task: dict) -> list:
    errors: list = []
    if not isinstance(task, dict):
        return ["TASK_MALFORMED:not-an-object"]
    if task.get("schema") != TASK_SCHEMA:
        errors.append(f"TASK_SCHEMA_UNKNOWN:{task.get('schema')!r}")
        return errors
    for field in REQUIRED_FIELDS:
        if task.get(field) is None:
            errors.append(f"TASK_FIELD_MISSING:{field}")
    if errors:
        return errors
    if not TASK_ID_RE.match(task["id"]):
        errors.append(f"TASK_ID_INVALID:{task['id']!r}")
    if task.get("mode") not in MODES:
        errors.append(f"TASK_MODE_INVALID:{task.get('mode')!r}")
    if task.get("risk") not in RISK_LEVELS:
        errors.append(f"TASK_RISK_INVALID:{task.get('risk')!r}")
    if task.get("work_kind") not in WORK_KINDS:
        errors.append(f"TASK_WORK_KIND_INVALID:{task.get('work_kind')!r}")
    if task.get("oracle_strength") not in ORACLE_STRENGTHS:
        errors.append(f"TASK_ORACLE_INVALID:{task.get('oracle_strength')!r}")
    if task.get("novelty") not in NOVELTY_VALUES:
        errors.append(f"TASK_NOVELTY_INVALID:{task.get('novelty')!r}")
    if task.get("ambiguity") not in AMBIGUITY_VALUES:
        errors.append(f"TASK_AMBIGUITY_INVALID:{task.get('ambiguity')!r}")
    if task.get("failure_evidence") not in FAILURE_EVIDENCE_VALUES:
        errors.append("TASK_FAILURE_EVIDENCE_INVALID")
    if task.get("escalation_evidence") not in ESCALATION_EVIDENCE_VALUES:
        errors.append("TASK_ESCALATION_EVIDENCE_INVALID")
    if task.get("clarification_status") not in CLARIFICATION_STATUSES:
        errors.append("TASK_CLARIFICATION_STATUS_INVALID")
    if not isinstance(task.get("material_contradiction"), bool):
        errors.append("TASK_MATERIAL_CONTRADICTION_INVALID")
    domains = task.get("authority_domains")
    if not isinstance(domains, list) or not all(
            d in AUTHORITY_DOMAINS for d in domains):
        errors.append("TASK_AUTHORITY_DOMAINS_INVALID")
    if not isinstance(task.get("owner_actor"), str) or \
            not task["owner_actor"].strip():
        errors.append("TASK_OWNER_ACTOR_INVALID")
    validation = task.get("validation") or {}
    commands = validation.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("TASK_VALIDATION_COMMANDS_REQUIRED")
        commands = []
    ordinals = set()
    for command in commands:
        if not isinstance(command, dict):
            errors.append("TASK_VALIDATION_COMMAND_MALFORMED")
            continue
        ordinal = command.get("ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) \
                or ordinal < 1 or ordinal in ordinals:
            errors.append(f"TASK_VALIDATION_ORDINAL_INVALID:{ordinal!r}")
        else:
            ordinals.add(ordinal)
        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or not all(
                isinstance(a, str) and a for a in argv):
            errors.append(f"TASK_VALIDATION_ARGV_INVALID:{ordinal!r}")
        outcomes = command.get("expected_outcomes")
        if not isinstance(outcomes, list) or not outcomes or not all(
                o in EXPECTED_OUTCOMES for o in outcomes):
            errors.append(f"TASK_EXPECTED_OUTCOME_INVALID:{ordinal!r}")
    if ordinals and ordinals != set(range(1, len(commands) + 1)):
        errors.append("TASK_VALIDATION_ORDINALS_NOT_CONTIGUOUS")
    candidate = task.get("candidate") or {}
    if not isinstance(candidate.get("allowlist"), list) or \
            not candidate.get("allowlist"):
        errors.append("TASK_ALLOWLIST_REQUIRED")
    if not isinstance(candidate.get("report"), str) or \
            not candidate["report"].strip():
        errors.append("TASK_REPORT_REQUIRED")
    environment = validation.get("environment") or {}
    if not isinstance(environment.get("base"), list) or not all(
            isinstance(k, str) and k for k in environment.get("base") or []):
        errors.append("TASK_ENVIRONMENT_BASE_INVALID")
    if not isinstance(environment.get("overlay"), dict):
        errors.append("TASK_ENVIRONMENT_OVERLAY_INVALID")
    errors.extend(_validate_requirements(task))
    errors.extend(material_ambiguity(task))
    footprint = derive_candidate_footprint(task)
    errors.extend(footprint_refusals(task, footprint))
    if task.get("mode") == "LIGHT" and derived_mode(task) == "FULL":
        errors.append("TASK_MODE_UNDERSTATED:"
                      f"declared=LIGHT,derived={derived_mode(task)}")
    return errors


def _validate_requirements(task: dict) -> list:
    errors: list = []
    if task.get("mode") != "FULL":
        return errors
    requirement_ids = task.get("requirement_ids")
    if not isinstance(requirement_ids, list) or not requirement_ids or \
            not all(isinstance(i, str) and i.strip()
                    for i in requirement_ids):
        errors.append("TASK_REQUIREMENT_IDS_REQUIRED")
        return errors
    duplicates = sorted({i for i in requirement_ids
                         if requirement_ids.count(i) > 1})
    for rid in duplicates:
        errors.append(f"TASK_REQUIREMENT_ID_DUPLICATE:{rid}")
    declared = list(dict.fromkeys(requirement_ids))
    requirements = task.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("TASK_REQUIREMENTS_REQUIRED")
        return errors
    commands = validation_commands(task)
    command_count = len(commands)
    criteria_count = task.get("success_criteria_count")
    rows_by_id: dict = {}
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append("TASK_REQUIREMENT_MALFORMED")
            continue
        rid = requirement.get("id")
        if not isinstance(rid, str) or not rid.strip():
            errors.append("TASK_REQUIREMENT_ID_INVALID")
            continue
        if rid in rows_by_id:
            errors.append(f"TASK_REQUIREMENT_ID_DUPLICATE:{rid}")
        rows_by_id.setdefault(rid, requirement)
        criterion = requirement.get("criterion")
        if not isinstance(criterion, int) or isinstance(criterion, bool) \
                or criterion < 1:
            errors.append(f"TASK_COVERAGE_CRITERION_INVALID:{rid}")
        elif not isinstance(criteria_count, int) or isinstance(
                criteria_count, bool) or criterion > criteria_count:
            errors.append(f"TASK_COVERAGE_CRITERION_OUT_OF_RANGE:{rid}")
        command = requirement.get("command")
        if not isinstance(command, int) or isinstance(command, bool) \
                or command < 1:
            errors.append(f"TASK_COVERAGE_COMMAND_INVALID:{rid}")
        elif command > command_count:
            errors.append(f"TASK_COVERAGE_COMMAND_OUT_OF_RANGE:{rid}")
        evidence = requirement.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"TASK_COVERAGE_EVIDENCE_EMPTY:{rid}")
    for rid in declared:
        if rid not in rows_by_id:
            errors.append(f"TASK_COVERAGE_ROW_MISSING:{rid}")
    for rid in sorted(set(rows_by_id) - set(declared)):
        errors.append(f"TASK_COVERAGE_ROW_ORPHAN:{rid}")
    return errors


def coverage_rows_by_id(task: dict) -> dict:
    rows = {}
    for requirement in task.get("requirements") or []:
        if isinstance(requirement, dict) and isinstance(
                requirement.get("id"), str):
            rows.setdefault(requirement["id"], requirement)
    return rows


def requirement_ids(task: dict) -> list:
    return sorted({r.get("id") for r in task.get("requirements") or []
                   if isinstance(r, dict) and isinstance(r.get("id"), str)})


def observer_policy_declared(task: dict) -> str:
    observer = task.get("observer") or {}
    policy = observer.get("policy") or "AUTO"
    if policy not in ("AUTO", "NONE", "DEFERRED", "IMMEDIATE"):
        raise UALError("TASK_OBSERVER_POLICY_INVALID", str(policy))
    return policy


def capture_exclusions(task: dict) -> tuple:
    return (report_rel(task),)

"""Mechanical observer policy and machine-visible run receipts.

The observer is chosen deterministically from risk/oracle facts: NONE
for clear routine strong-oracle work, IMMEDIATE for high risk, weak or
absent oracles, novelty, reproduced material failure, restricted
authority or contradiction, DEFERRED otherwise; unknown facts fail
closed to IMMEDIATE. A receipt is terminal evidence with raw inline
spans: the recorded span digests must match the actual run log bytes,
so paths alone never count as delivered evidence. Missing observed
provider identity stays UNKNOWN; the observer never writes candidates,
clears claims, reviews or accepts.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import lifecycle
from .errors import UALError
from .hashing import exclusive_write_json, load_json, next_sequence, \
    sha256_hex
from .paths import resolve_inside, run_dir, task_dir
from .runner import load_sidecar

RECEIPT_SCHEMA = "ual-observer-receipt/1"
RECEIPT_MAX_BYTES = 64 * 1024
RECEIPT_MAX_FILES = 128
TERMINAL_STATES = ("ATTACHED", "ROUTE_UNAVAILABLE")

RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")


def decide_observer_policy(task: dict) -> dict:
    facts = {
        "risk": task.get("risk"),
        "oracle_strength": task.get("oracle_strength"),
        "novelty": task.get("novelty"),
        "ambiguity": task.get("ambiguity"),
        "failure_evidence": task.get("failure_evidence"),
        "authority_domains": task.get("authority_domains"),
        "material_contradiction": task.get("material_contradiction"),
    }
    from .taskfile import (AMBIGUITY_VALUES, AUTHORITY_DOMAINS,
                           FAILURE_EVIDENCE_VALUES, NOVELTY_VALUES,
                           ORACLE_STRENGTHS, RISK_LEVELS)
    known = (facts["risk"] in RISK_LEVELS
             and facts["oracle_strength"] in ORACLE_STRENGTHS
             and facts["novelty"] in NOVELTY_VALUES
             and facts["ambiguity"] in AMBIGUITY_VALUES
             and facts["failure_evidence"] in FAILURE_EVIDENCE_VALUES
             and isinstance(facts["material_contradiction"], bool)
             and isinstance(facts["authority_domains"], list)
             and all(d in AUTHORITY_DOMAINS
                     for d in facts["authority_domains"]))
    if not known:
        raise UALError("OBSERVER_FACTS_UNKNOWN", str(facts))
    from .taskfile import RESTRICTED_AUTHORITY_DOMAINS
    reasons = []
    if facts["risk"] == "HIGH":
        reasons.append("HIGH_RISK")
    if facts["oracle_strength"] in ("WEAK", "NONE"):
        reasons.append("WEAK_OR_NO_ORACLE")
    if facts["novelty"] == "NOVEL":
        reasons.append("NOVEL_WORK")
    if facts["failure_evidence"] == "REPRODUCED_MATERIAL":
        reasons.append("REPRODUCED_MATERIAL_FAILURE")
    if set(facts["authority_domains"]) & set(
            RESTRICTED_AUTHORITY_DOMAINS):
        reasons.append("RESTRICTED_AUTHORITY")
    if facts["material_contradiction"]:
        reasons.append("MATERIAL_CONTRADICTION")
    if reasons:
        return {"policy": "IMMEDIATE", "reasons": reasons}
    if (facts["risk"] == "LOW" and facts["novelty"] == "ROUTINE"
            and facts["ambiguity"] == "CLEAR"
            and facts["oracle_strength"] == "STRONG"):
        return {"policy": "NONE",
                "reasons": ["LOW_ROUTINE_STRONG_ORACLE_CLEAR"]}
    return {"policy": "DEFERRED", "reasons": ["MEDIUM_ROUTINE_STRONG"]}


def resolved_policy(task: dict) -> str:
    declared = task.get("observer") or {}
    policy = declared.get("policy") or "AUTO"
    if policy == "AUTO":
        return decide_observer_policy(task)["policy"]
    return policy


def receipts_dir(project: Path, task_id: str) -> Path:
    from .attempts import current_dir
    directory = current_dir(project, task_id) / "receipts"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def scan_receipts(project: Path, task_id: str) -> list:
    from .attempts import current_seq, attempt_dir
    seq = current_seq(project, task_id)
    if seq is None:
        return []
    directory = attempt_dir(project, task_id, seq) / "receipts"
    if not directory.is_dir():
        return []
    records = []
    for entry in sorted(directory.iterdir()):
        if not entry.name.endswith(".json") or not entry.is_file():
            raise UALError("OBSERVER_RECEIPT_DIRTY", entry.name)
        records.append((entry, load_json(entry,
                                         max_bytes=RECEIPT_MAX_BYTES)))
    return records


def record_receipt(project: Path, task: dict, payload) -> dict:
    task_id = task["id"]
    if not isinstance(payload, dict):
        raise UALError("OBSERVER_RECEIPT_INVALID", "not-an-object")
    if payload.get("schema") != RECEIPT_SCHEMA:
        raise UALError("OBSERVER_RECEIPT_SCHEMA_INVALID",
                       str(payload.get("schema")))
    if payload.get("task") != task_id:
        raise UALError("OBSERVER_RECEIPT_TASK_MISMATCH",
                       str(payload.get("task")))
    run_id = payload.get("run_id")
    sidecar = load_sidecar(project, str(run_id or ""))
    if sidecar is None or sidecar.get("task") != task_id:
        raise UALError("OBSERVER_RECEIPT_RUN_UNBOUND", str(run_id))
    state = payload.get("state")
    if state not in TERMINAL_STATES:
        raise UALError("OBSERVER_RECEIPT_STATE_INVALID", str(state))
    observed = payload.get("observed_identity")
    if not isinstance(observed, str) or not observed.strip():
        raise UALError("OBSERVER_RECEIPT_OBSERVED_IDENTITY_MISSING", "")
    if observed != "UNKNOWN" and not payload.get(
            "observed_identity_proof"):
        raise UALError("OBSERVER_OBSERVED_IDENTITY_NOT_HONEST", observed)
    if state == "ATTACHED":
        spans = payload.get("evidence_spans")
        if not isinstance(spans, list) or not spans:
            raise UALError("OBSERVER_RECEIPT_EVIDENCE_INVALID",
                           "empty spans")
    else:
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise UALError("OBSERVER_RECEIPT_REASON_MISSING", "")
    for entry, existing in scan_receipts(project, task_id):
        if isinstance(existing, dict) and existing.get("run_id") == run_id:
            raise UALError("OBSERVER_RECEIPT_DUPLICATE_RUN", str(run_id))
    directory = receipts_dir(project, task_id)
    sequence = next_sequence(directory, "receipt_", ".json",
                             max_files=RECEIPT_MAX_FILES)
    path = directory / f"receipt_{sequence:04d}.json"
    exclusive_write_json(path, payload, max_bytes=RECEIPT_MAX_BYTES)
    return {"ok": True, "path": str(path)}


def _span_errors(project: Path, span: dict) -> list:
    errors = []
    run_id = span.get("source_run")
    sidecar = load_sidecar(project, str(run_id or ""))
    if sidecar is None:
        return [f"OBSERVER_RECEIPT_INVALID:span run unbound:{run_id}"]
    log_rel = (sidecar.get("log") or {}).get("path")
    if not isinstance(log_rel, str) or not log_rel:
        return ["OBSERVER_RECEIPT_INVALID:span log unavailable"]
    log_path = Path(project) / log_rel
    if not log_path.is_file():
        return ["OBSERVER_RECEIPT_INVALID:span log missing"]
    try:
        lines = log_path.read_text(encoding="utf-8",
                                   errors="replace").splitlines()
        start = int(span.get("start_line"))
        end = int(span.get("end_line"))
    except (TypeError, ValueError):
        return ["OBSERVER_RECEIPT_INVALID:span bounds invalid"]
    if start < 1 or end < start or end > len(lines):
        return ["OBSERVER_RECEIPT_INVALID:span bounds invalid"]
    chunk = "\n".join(lines[start - 1:end])
    digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
    if digest != span.get("sha256"):
        errors.append("OBSERVER_RECEIPT_INVALID:span digest mismatch")
    return errors


def _writer_ids(project: Path, task_id: str) -> list:
    """Every writer whose terminal state an observer receipt must cover:
    finished ENGINEER child runs plus confirmed native handoff requests
    for the current attempt."""
    writer_ids = []
    runs_root = Path(project) / ".agent-loop" / "runs"
    if runs_root.is_dir():
        for entry in sorted(runs_root.iterdir()):
            sidecar_path = entry / "run.json"
            if not sidecar_path.is_file():
                continue
            try:
                sidecar = load_json(sidecar_path,
                                    max_bytes=RECEIPT_MAX_BYTES)
            except UALError:
                continue
            if isinstance(sidecar, dict) and \
                    sidecar.get("task") == task_id and \
                    sidecar.get("purpose") == "ENGINEER" and \
                    sidecar.get("status") == "FINISHED":
                writer_ids.append(sidecar.get("run_id"))
    from .attempts import current_seq, attempt_dir
    seq = current_seq(project, task_id)
    if seq is not None:
        results_dir = attempt_dir(project, task_id, seq) / "results"
        if results_dir.is_dir():
            for entry in sorted(results_dir.iterdir()):
                if entry.name.startswith("terminal_") and \
                        entry.name.endswith(".json"):
                    try:
                        terminal = load_json(entry,
                                             max_bytes=RECEIPT_MAX_BYTES)
                    except UALError:
                        continue
                    if isinstance(terminal, dict) and \
                            terminal.get("decision") == "COMPLETED":
                        writer_ids.append(terminal.get("request_id"))
    return [w for w in writer_ids if w]


def gate_errors(project: Path, task: dict) -> tuple:
    policy = resolved_policy(task)
    receipt_digests = []
    if policy == "NONE":
        return [], receipt_digests
    writer_ids = _writer_ids(project, task["id"])
    receipts = []
    for entry, payload in scan_receipts(project, task["id"]):
        if isinstance(payload, dict) and \
                payload.get("state") in TERMINAL_STATES:
            receipts.append((entry, payload))
    errors = []
    for run_id in writer_ids:
        matching = [p for _e, p in receipts if p.get("run_id") == run_id]
        if len(matching) > 1:
            errors.append(f"OBSERVER_RECEIPT_DUPLICATE:{run_id}")
            continue
        if not matching:
            errors.append(f"OBSERVER_RECEIPT_MISSING:{run_id}")
            continue
        receipt = matching[0]
        if receipt.get("state") == "ATTACHED":
            for span in receipt.get("evidence_spans") or []:
                errors.extend(_span_errors(project, span))
    directory = receipts_dir(project, task["id"])
    for entry, payload in receipts:
        if any(payload.get("run_id") == wid for wid in writer_ids):
            receipt_digests.append(
                {"path": entry.name,
                 "sha256": sha256_hex(entry.read_bytes()),
                 "run_id": payload.get("run_id")})
    return errors, receipt_digests

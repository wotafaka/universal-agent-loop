"""Task state, lifecycle transitions and the declared close sequence.

Task states are not evidence states. The current status lives in one
bounded, atomically replaced state file and moves only along the
portable lifecycle vocabulary. The close sequence is enforced in the
declared order: final GREEN, report finalized, generated-state refresh,
report check, engineer close. After a successful close no further tool,
run or validation event is accepted for the task.
"""
from __future__ import annotations

from pathlib import Path

from .errors import UALError
from .hashing import (atomic_write_json, load_json, next_sequence,
                      sha256_hex)
from .paths import resolve_inside, task_dir
from .validation import Ledger, close_time_errors

STATE_SCHEMA = "ual-state/1"
STATE_MAX_BYTES = 64 * 1024
RECORD_MAX_BYTES = 256 * 1024
MAX_RECORDS = 4096
RESERVED_EVIDENCE_STATUSES = ("PENDING_CODEX_REVIEW", "REVIEW_PASSED",
                              "ACCEPTED", "REJECTED", "RELEASED")

TASK_STATUSES = (
    "PROPOSED", "ACTIVE", "FIX_REQUIRED", "EVIDENCE_GATHERING",
    "PENDING_CODEX_REVIEW", "REVIEW_PASSED", "ACCEPTED", "REJECTED",
    "BLOCKED", "CANCELLED", "ABANDONED", "SUPERSEDED", "RELEASED",
)
TRANSITIONS = {
    "PROPOSED": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"FIX_REQUIRED", "EVIDENCE_GATHERING", "PENDING_CODEX_REVIEW",
               "BLOCKED", "CANCELLED", "ABANDONED", "SUPERSEDED"},
    "EVIDENCE_GATHERING": {"ACTIVE", "BLOCKED", "CANCELLED"},
    "FIX_REQUIRED": {"ACTIVE", "PENDING_CODEX_REVIEW", "REJECTED",
                     "CANCELLED", "ABANDONED"},
    "PENDING_CODEX_REVIEW": {"REVIEW_PASSED", "ACCEPTED", "FIX_REQUIRED",
                             "SUPERSEDED", "CANCELLED"},
    "REVIEW_PASSED": {"ACCEPTED", "REJECTED", "FIX_REQUIRED", "SUPERSEDED",
                      "CANCELLED"},
    "ACCEPTED": {"RELEASED"},
    "REJECTED": set(),
    "BLOCKED": {"ACTIVE", "CANCELLED"},
    "CANCELLED": set(),
    "ABANDONED": set(),
    "SUPERSEDED": set(),
    "RELEASED": set(),
}


def state_path(project: Path, task_id: str) -> Path:
    return task_dir(project, task_id) / "state.json"


def load_state(project: Path, task_id: str) -> dict | None:
    path = state_path(project, task_id)
    if not path.is_file():
        return None
    state = load_json(path, max_bytes=STATE_MAX_BYTES)
    if not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA:
        raise UALError("TASK_STATE_MALFORMED", str(path))
    return state


def save_state(project: Path, task_id: str, state: dict) -> None:
    atomic_write_json(state_path(project, task_id), state,
                      max_bytes=STATE_MAX_BYTES)


def ensure_state(project: Path, task_id: str) -> dict:
    state = load_state(project, task_id)
    if state is None:
        from .claims import utc_now_iso
        state = {"schema": STATE_SCHEMA, "task": task_id,
                 "status": "ACTIVE", "seq": 0, "updated_at":
                 utc_now_iso(), "last_material_claim_identity": None}
        save_state(project, task_id, state)
    return state


def validate_transition(current: str, new: str) -> None:
    if current not in TASK_STATUSES:
        raise UALError("UNKNOWN_TASK_STATUS", current)
    if new not in TASK_STATUSES:
        raise UALError("UNKNOWN_TASK_STATUS", new)
    if new not in TRANSITIONS.get(current, set()):
        raise UALError("INVALID_TASK_TRANSITION", f"{current}->{new}")


def set_status(project: Path, task_id: str, new_status: str,
               _internal: bool = False) -> dict:
    if not _internal and new_status in RESERVED_EVIDENCE_STATUSES:
        raise UALError("STATUS_RESERVED_FOR_EVIDENCE", new_status)
    state = load_state(project, task_id)
    if state is None:
        if new_status != "ACTIVE":
            state = {"schema": STATE_SCHEMA, "task": task_id,
                     "status": "PROPOSED", "seq": 0,
                     "updated_at": "", "last_material_claim_identity":
                     None}
        else:
            return {"ok": True, "status": ensure_state(
                project, task_id)["status"]}
    if state["status"] != new_status:
        validate_transition(state["status"], new_status)
        state["status"] = new_status
    from .claims import utc_now_iso
    state["updated_at"] = utc_now_iso()
    save_state(project, task_id, state)
    return {"ok": True, "status": state["status"]}


def _task_records_dir(project: Path, task_id: str) -> Path:
    from .attempts import current_dir
    directory = current_dir(project, task_id) / "records"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_timeline_record(project: Path, task: dict, kind: str,
                          payload: dict) -> tuple:
    state = ensure_state(project, task["id"])
    state["seq"] = state.get("seq", 0) + 1
    payload = dict(payload)
    payload["seq"] = state["seq"]
    payload["kind"] = kind
    payload["task"] = task["id"]
    directory = _task_records_dir(project, task["id"])
    sequence = next_sequence(directory, f"{kind}_", ".json",
                             max_files=MAX_RECORDS)
    path = directory / f"{kind}_{sequence:04d}.json"
    from .hashing import exclusive_write_json
    exclusive_write_json(path, payload, max_bytes=RECORD_MAX_BYTES)
    save_state(project, task["id"], state)
    return path, payload


def read_records(project: Path, task_id: str, kind: str) -> list:
    from .attempts import current_seq, attempt_dir
    seq = current_seq(project, task_id)
    if seq is None:
        return []
    directory = attempt_dir(project, task_id, seq) / "records"
    if not directory.is_dir():
        return []
    records = []
    for entry in sorted(directory.iterdir()):
        if entry.name.startswith(kind + "_") and entry.name.endswith(".json"):
            records.append(load_json(entry, max_bytes=RECORD_MAX_BYTES))
    return records


def latest_record(project: Path, task_id: str, kind: str):
    records = read_records(project, task_id, kind)
    return records[-1] if records else None


def closed_record(project: Path, task: dict):
    return latest_record(project, task["id"], "close")


def refresh(project: Path, task: dict) -> dict:
    from .claims import utc_now_iso
    if closed_record(project, task) is not None:
        raise UALError("POST_CLOSE_REFRESH", task["id"])
    ledger = Ledger(project, task)
    generated = {}
    for rel in task.get("generated_state") or []:
        path = resolve_inside(project, rel, label="GENERATED")
        if path.is_file():
            generated[rel] = {"bytes": path.stat().st_size,
                              "sha256": sha256_hex(path.read_bytes())}
        else:
            generated[rel] = {"bytes": None, "sha256": None}
    path, payload = write_timeline_record(
        project, task, "refresh", {
            "ledger_sha256": (sha256_hex(ledger.path.read_bytes())
                              if ledger.path.is_file() else None),
            "ledger_seq": ledger.last_seq(),
            "generated": generated,
            "at": utc_now_iso(),
        })
    return {"ok": True, "record": str(path)}


def report_check(project: Path, task: dict) -> dict:
    from .claims import utc_now_iso
    if closed_record(project, task) is not None:
        raise UALError("POST_CLOSE_REPORT_CHECK", task["id"])
    refresh_record = latest_record(project, task["id"], "refresh")
    if refresh_record is None:
        raise UALError("VALIDATION_REFRESH_REQUIRED", task["id"])
    ledger = Ledger(project, task)
    if refresh_record.get("ledger_seq", 0) < ledger.last_seq():
        raise UALError("VALIDATION_REFRESH_REQUIRED",
                       "ledger advanced after refresh")
    report_rel = (task.get("candidate") or {}).get("report") or ""
    report_path = resolve_inside(project, report_rel, label="REPORT")
    if not report_path.is_file():
        raise UALError("VALIDATION_REPORT_MISSING", report_rel)
    report_bytes = report_path.read_bytes()
    path, payload = write_timeline_record(
        project, task, "reportcheck", {
            "report": {"path": report_rel, "bytes": len(report_bytes),
                       "sha256": sha256_hex(report_bytes)},
            "at": utc_now_iso(),
        })
    return {"ok": True, "record": str(path)}


def close(project: Path, task: dict, observer_gate=None) -> dict:
    from .attempts import current_dir
    from .claims import utc_now_iso
    if closed_record(project, task) is not None:
        raise UALError("TASK_ALREADY_CLOSED", task["id"])
    ledger = Ledger(project, task)
    errors = close_time_errors(project, task, ledger)
    refresh_record = latest_record(project, task["id"], "refresh")
    if refresh_record is None or refresh_record.get(
            "ledger_seq", 0) < ledger.last_seq():
        errors.append("VALIDATION_REFRESH_REQUIRED")
    reportcheck = latest_record(project, task["id"], "reportcheck")
    if reportcheck is None:
        errors.append("VALIDATION_REPORT_CHECK_REQUIRED")
    receipt_digests = []
    if observer_gate is not None:
        gate_errors, receipt_digests = observer_gate()
        errors.extend(gate_errors)
    completeness = "UNKNOWN"
    events_meta_path = current_dir(project, task["id"]) / "events_meta.json"
    if events_meta_path.is_file():
        meta = load_json(events_meta_path, max_bytes=64 * 1024)
        if isinstance(meta, dict):
            completeness = meta.get("completeness", "UNKNOWN")
    events_path = current_dir(project, task["id"]) / "events.jsonl"
    events_digest = sha256_hex(events_path.read_bytes()) \
        if events_path.is_file() else None
    from .paths import state_root
    config_path = state_root(project) / "config.json"
    if config_path.is_file():
        config = load_json(config_path, max_bytes=64 * 1024)
        required = (config or {}).get("required_evidence") or {}
        demand = required.get("complete_transcript")
        if demand is True and completeness == "UNKNOWN":
            errors.append("CLOSE_TRANSCRIPT_COMPLETENESS_UNKNOWN")
        if demand == "VERIFIED" and completeness != "VERIFIED":
            errors.append("CLOSE_TRANSCRIPT_COMPLETENESS_REQUIRED:"
                          f"required=VERIFIED, actual={completeness}; "
                          f"owner attestation is never relabeled VERIFIED")
    if errors:
        raise UALError("VALIDATION_CLOSE_REFUSED", ";".join(errors[:4]))
    path, payload = write_timeline_record(
        project, task, "close", {
            "ledger_sha256": sha256_hex(ledger.path.read_bytes()),
            "ledger_seq": ledger.last_seq(),
            "refresh_seq": refresh_record.get("seq"),
            "reportcheck_seq": reportcheck.get("seq"),
            "observer_receipts": receipt_digests,
            "transcript_completeness": completeness,
            "events_sha256": events_digest,
            "at": utc_now_iso(),
        })
    return {"ok": True, "record": str(path),
            "observer_receipts": receipt_digests,
            "transcript_completeness": completeness}

"""Checkout-scoped single-writer claims with OS birth identity.

The claim covers the entire resolved project root, across task IDs: two
distinct tasks can never write one checkout concurrently. A duplicate
writer is refused before any child process is created. Release requires
a proven terminal run bound to the claim plus a verified log identity;
unproven or ambiguous claims stay ACTIVE until an explicit owner
adjudication. No stale claim is ever deleted automatically.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
from datetime import datetime, timezone
from pathlib import Path

from .errors import UALError
from .hashing import (atomic_write_json, exclusive_write_json, load_json,
                      next_sequence, sha256_hex)
from .paths import claims_dir
from . import prockid

CLAIM_SCHEMA = "ual-writer-claim/1"
CLAIM_FILE_RE = re.compile(r"^claim_(\d{8})\.json$")
CLAIM_MAX_FILES = 100000
CLAIM_MAX_BYTES = 16 * 1024
IDENTITY_UNBOUND = "UNBOUND"
IDENTITY_OBTAINED = "OBTAINED"
IDENTITY_CHILD_EXITED = "CHILD_EXITED_BEFORE_IDENTITY"
IDENTITY_UNOBTAINABLE_ALIVE = "UNOBTAINABLE_ALIVE"
STATUS_ACTIVE = "ACTIVE"
STATUS_RELEASED = "RELEASED"
STATUS_ABANDONED = "ABANDONED"
IDENTITY_BIND_RETRY_S = 2.0
CLAIM_STATUS_VOCABULARY = (STATUS_ACTIVE, STATUS_RELEASED, STATUS_ABANDONED)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _claim_path(project: Path, sequence: int) -> Path:
    return claims_dir(project) / f"claim_{sequence:08d}.json"


def _validate_claim_object(record, name: str) -> dict:
    """A malformed or unknown claim record is dirty evidence: it must
    block the directory instead of implying that no active writer
    exists."""
    if not isinstance(record, dict):
        raise UALError("WRITER_CLAIM_DIR_DIRTY", name + ":not-an-object")
    if record.get("schema") != CLAIM_SCHEMA:
        raise UALError("WRITER_CLAIM_DIR_DIRTY", name + ":schema")
    for field in ("claim_id", "task", "host", "acquired_at"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise UALError("WRITER_CLAIM_DIR_DIRTY", name + f":{field}")
    if record.get("status") not in CLAIM_STATUS_VOCABULARY:
        raise UALError("WRITER_CLAIM_DIR_DIRTY", name + ":status")
    launcher_pid = record.get("launcher_pid")
    if isinstance(launcher_pid, bool) or not isinstance(launcher_pid, int):
        raise UALError("WRITER_CLAIM_DIR_DIRTY", name + ":launcher_pid")
    return record


def scan_claims(project: Path) -> list:
    directory = claims_dir(project)
    if not directory.is_dir():
        return []
    entries = []
    for entry in sorted(directory.iterdir()):
        if CLAIM_FILE_RE.match(entry.name) is None or not entry.is_file():
            raise UALError("WRITER_CLAIM_DIR_DIRTY", entry.name)
        record = _validate_claim_object(
            load_json(entry, max_bytes=CLAIM_MAX_BYTES), entry.name)
        entries.append((entry, record))
    if len(entries) > CLAIM_MAX_FILES:
        raise UALError("WRITER_CLAIM_STORAGE_BOUND", str(len(entries)))
    return entries


def active_claim(project: Path):
    for path, record in scan_claims(project):
        if record.get("status") == STATUS_ACTIVE:
            return path, record
    return None


def acquire(project: Path, task: str) -> dict:
    directory = claims_dir(project)
    directory.mkdir(parents=True, exist_ok=True)
    existing = scan_claims(project)
    active_count = 0
    for path, record in existing:
        if record.get("status") == STATUS_ACTIVE:
            active_count += 1
            raise UALError("WRITER_CLAIM_ACTIVE",
                           f"{path.name}:second writer refused")
    if active_count >= 1:
        raise UALError("WRITER_CLAIM_ACTIVE", "second writer refused")
    numbers = []
    for path, _record in existing:
        match = CLAIM_FILE_RE.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    sequence = max(numbers, default=0) + 1
    if sequence > 99999999:
        raise UALError("WRITER_CLAIM_SEQUENCE_BOUND", str(sequence))
    launcher_identity = prockid.process_start_identity(os.getpid())
    claim = {
        "schema": CLAIM_SCHEMA,
        "claim_id": secrets.token_hex(16),
        "task": task,
        "host": socket.gethostname(),
        "launcher_pid": os.getpid(),
        "launcher_identity": launcher_identity,
        "acquired_at": utc_now_iso(),
        "status": STATUS_ACTIVE,
        "child_pid": None,
        "child_identity": None,
        "identity_state": IDENTITY_UNBOUND,
        "bound_at": None,
        "released_at": None,
        "terminal_evidence": None,
        "adjudication": None,
    }
    path = _claim_path(project, sequence)
    try:
        exclusive_write_json(path, claim, max_bytes=CLAIM_MAX_BYTES)
    except UALError:
        raise UALError("WRITER_CLAIM_RACE_SEQUENCE_LOST",
                       path.name) from None
    return {"claim": claim, "path": path, "claim_id": claim["claim_id"],
            "sequence": sequence}


def _read_claim(path: Path) -> dict:
    claim = load_json(path, max_bytes=CLAIM_MAX_BYTES)
    if not isinstance(claim, dict):
        raise UALError("WRITER_CLAIM_UNREADABLE", str(path))
    return claim


def bind_child(project: Path, claim_id: str, pid, identity,
               identity_state: str) -> dict:
    path, claim = _find_claim(project, claim_id)
    if claim.get("status") != STATUS_ACTIVE:
        raise UALError("WRITER_CLAIM_NOT_ACTIVE",
                       str(claim.get("status")))
    if identity_state != IDENTITY_UNBOUND and identity_state not in (
            IDENTITY_OBTAINED, IDENTITY_CHILD_EXITED,
            IDENTITY_UNOBTAINABLE_ALIVE):
        raise UALError("WRITER_CLAIM_IDENTITY_STATE_INVALID",
                       identity_state)
    if identity_state == IDENTITY_OBTAINED and not _valid_identity(identity):
        raise UALError("WRITER_CLAIM_IDENTITY_INVALID", "")
    claim["child_pid"] = pid
    claim["child_identity"] = identity
    claim["identity_state"] = identity_state
    claim["bound_at"] = utc_now_iso()
    atomic_write_json(path, claim, max_bytes=CLAIM_MAX_BYTES)
    return claim


def _find_claim(project: Path, claim_id: str):
    for path, record in scan_claims(project):
        if record.get("claim_id") == claim_id:
            return path, record
    raise UALError("WRITER_CLAIM_UNKNOWN", claim_id)


def _valid_identity(identity) -> bool:
    return (isinstance(identity, dict)
            and isinstance(identity.get("method"), str)
            and isinstance(identity.get("value"), str)
            and identity["method"].strip()
            and identity["value"].strip())


def release(project: Path, claim_id: str, run_id: str,
            sidecar_loader) -> dict:
    path, claim = _find_claim(project, claim_id)
    if claim.get("status") != STATUS_ACTIVE:
        raise UALError("WRITER_CLAIM_NOT_ACTIVE",
                       str(claim.get("status")))
    if claim.get("identity_state") == IDENTITY_UNBOUND:
        sidecar = sidecar_loader(run_id)
        if sidecar is None or sidecar.get("purpose") != "ENGINEER" or \
                sidecar.get("claim_id") != claim_id:
            raise UALError("WRITER_CLAIM_RUN_MISMATCH", run_id)
    if claim.get("identity_state") != IDENTITY_OBTAINED or \
            not _valid_identity(claim.get("child_identity")):
        raise UALError("WRITER_CLAIM_IDENTITY_UNPROVEN",
                       str(claim.get("identity_state")))
    sidecar = sidecar_loader(run_id)
    if sidecar is None or sidecar.get("purpose") != "ENGINEER" or \
            sidecar.get("claim_id") != claim_id:
        raise UALError("WRITER_CLAIM_RUN_MISMATCH", run_id)
    if sidecar.get("task") != claim.get("task"):
        raise UALError("WRITER_CLAIM_TASK_MISMATCH",
                       f"{sidecar.get('task')}!={claim.get('task')}")
    _compare_child_identity(claim, sidecar)
    if str(sidecar.get("status")) != "FINISHED":
        raise UALError("WRITER_CLAIM_TERMINAL_UNPROVEN",
                       str(sidecar.get("status")))
    log = sidecar.get("log") or {}
    log_path = Path(project) / str(log.get("path") or "")
    if not log_path.is_file():
        raise UALError("WRITER_CLAIM_LOG_MISSING", str(log.get("path")))
    actual = sha256_hex(log_path.read_bytes())
    if actual != log.get("sha256"):
        raise UALError("WRITER_CLAIM_LOG_DRIFT", str(log.get("path")))
    sidecar_path = Path(project) / ".agent-loop" / "runs" / run_id / "run.json"
    sidecar_bytes = sidecar_path.read_bytes()
    claim["status"] = STATUS_RELEASED
    claim["released_at"] = utc_now_iso()
    claim["terminal_evidence"] = {
        "class": "LAUNCHER_PROVEN_TERMINAL",
        "run_id": run_id,
        "sidecar_sha256": sha256_hex(sidecar_bytes),
        "sidecar_bytes": len(sidecar_bytes),
        "exit_code": sidecar.get("exit_code"),
        "log_sha256": log.get("sha256"),
        "log_bytes": log.get("bytes"),
    }
    atomic_write_json(path, claim, max_bytes=CLAIM_MAX_BYTES)
    return {"status": "PASS", "claim_id": claim_id}


def _compare_child_identity(claim: dict, sidecar: dict) -> None:
    """Release is bound to host, child PID and OS birth identity as one
    complete binding; any component mismatch is identity drift."""
    if claim.get("host") is not None and \
            sidecar.get("host") is not None and \
            claim.get("host") != sidecar.get("host"):
        raise UALError("WRITER_CLAIM_IDENTITY_DRIFT",
                       f"host {sidecar.get('host')}!={claim.get('host')}")
    if claim.get("child_pid") is not None and \
            claim.get("child_pid") != sidecar.get("pid"):
        raise UALError("WRITER_CLAIM_IDENTITY_DRIFT",
                       f"pid {sidecar.get('pid')}!={claim.get('child_pid')}")
    recorded = claim.get("child_identity")
    sidecar_identity = sidecar.get("child_identity")
    if _valid_identity(recorded):
        if not _valid_identity(sidecar_identity) or \
                recorded["method"] != sidecar_identity["method"] or \
                recorded["value"] != sidecar_identity["value"]:
            raise UALError("WRITER_CLAIM_IDENTITY_DRIFT",
                           "child birth identity mismatch")


def release_native(project: Path, claim_id: str, evidence: dict) -> dict:
    """Release a retained native-handoff claim through the explicit
    owner-confirmation path. Never fabricates PID/exit or
    launcher-proven termination: the terminal evidence origin stays
    OWNER_ATTESTED."""
    path, claim = _find_claim(project, claim_id)
    if claim.get("status") != STATUS_ACTIVE:
        raise UALError("WRITER_CLAIM_NOT_ACTIVE",
                       str(claim.get("status")))
    claim["status"] = STATUS_RELEASED
    claim["released_at"] = utc_now_iso()
    claim["terminal_evidence"] = dict(evidence)
    atomic_write_json(path, claim, max_bytes=CLAIM_MAX_BYTES)
    return {"status": "PASS", "claim_id": claim_id}


def abandon(project: Path, claim_id: str, actor: str, reason: str) -> dict:
    if not isinstance(reason, str) or not reason.strip():
        raise UALError("ADJUDICATION_REASON_REQUIRED", "")
    path, claim = _find_claim(project, claim_id)
    if claim.get("status") != STATUS_ACTIVE:
        raise UALError("WRITER_CLAIM_NOT_ACTIVE",
                       str(claim.get("status")))
    raw = path.read_bytes()
    claim["status"] = STATUS_ABANDONED
    claim["adjudication"] = {
        "actor": actor,
        "reason": reason.strip(),
        "original_claim_sha256": sha256_hex(raw),
        "original_claim_bytes": len(raw),
        "decided_at": utc_now_iso(),
    }
    atomic_write_json(path, claim, max_bytes=CLAIM_MAX_BYTES)
    return claim

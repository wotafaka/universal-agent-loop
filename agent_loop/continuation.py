"""Hash-bound terminal-only continuation records.

A continuation record may exist only for a proven terminal writer run
with a verified log identity and no active claim; the record binds the
exact prior sidecar, log and task bytes. Verification recomputes every
binding; drift fails closed, and unverified prose is never upgraded
into a binding.
"""
from __future__ import annotations

from pathlib import Path

from . import claims
from .errors import UALError
from .hashing import exclusive_write_json, load_json, sha256_hex
from .paths import inside_rel, run_dir, task_dir
from .runner import load_sidecar

RECORD_SCHEMA = "ual-continuation-record/1"
RECORD_MAX_BYTES = 256 * 1024
TERMINAL_STATUSES = ("FINISHED",)


def record_path(project: Path, task_id: str) -> Path:
    return task_dir(project, task_id) / "continuation.json"


def prepare(project: Path, task: dict) -> dict:
    task_id = task["id"]
    active = claims.active_claim(project)
    if active is not None:
        raise UALError("CONTINUATION_LIVE_CLAIM",
                       str(active[1].get("claim_id")))
    existing = record_path(project, task_id)
    if existing.is_file():
        raise UALError("CONTINUATION_RECORD_EXISTS", str(existing))
    runs_root = Path(project) / ".agent-loop" / "runs"
    latest = None
    latest_path = None
    if runs_root.is_dir():
        for entry in sorted(runs_root.iterdir()):
            sidecar_path = entry / "run.json"
            if not sidecar_path.is_file():
                continue
            sidecar = load_json(sidecar_path, max_bytes=RECORD_MAX_BYTES)
            if isinstance(sidecar, dict) and \
                    sidecar.get("task") == task_id and \
                    sidecar.get("purpose") == "ENGINEER":
                latest = sidecar
                latest_path = sidecar_path
    if latest is None:
        raise UALError("CONTINUATION_NO_TERMINAL_RUN", task_id)
    status = str(latest.get("status") or "")
    if status not in TERMINAL_STATUSES:
        raise UALError("CONTINUATION_SIDECAR_NOT_TERMINAL", status)
    log_rel = (latest.get("log") or {}).get("path")
    log_path = Path(project) / str(log_rel or "")
    if not log_path.is_file():
        raise UALError("CONTINUATION_LOG_MISSING", str(log_rel))
    actual_log_sha = sha256_hex(log_path.read_bytes())
    if actual_log_sha != (latest.get("log") or {}).get("sha256"):
        raise UALError("CONTINUATION_LOG_IDENTITY", str(log_rel))
    task_bytes = (project / "task.json").read_bytes()
    sidecar_bytes = latest_path.read_bytes()
    record = {
        "schema": RECORD_SCHEMA,
        "task": task_id,
        "prior_run_id": latest.get("run_id"),
        "prior_status": status,
        "sidecar": {"path": inside_rel(project, latest_path),
                    "bytes": len(sidecar_bytes),
                    "sha256": sha256_hex(sidecar_bytes)},
        "log": {"path": log_rel, "bytes": log_path.stat().st_size,
                "sha256": actual_log_sha},
        "task_file": {"bytes": len(task_bytes),
                      "sha256": sha256_hex(task_bytes)},
        "launch_identity": {
            "pid": latest.get("pid"),
            "child_identity": latest.get("child_identity"),
            "identity_state": latest.get("identity_state"),
        },
        "last_checkpoint": {
            "running_at": latest.get("running_at"),
            "finished_at": latest.get("finished_at"),
        },
        "built_at": claims.utc_now_iso(),
    }
    exclusive_write_json(existing, record, max_bytes=RECORD_MAX_BYTES)
    return {"ok": True, "prior_status": status,
            "prior_run_id": latest.get("run_id")}


def verify(project: Path, task: dict) -> dict:
    task_id = task["id"]
    path = record_path(project, task_id)
    if not path.is_file():
        raise UALError("CONTINUATION_RECORD_MISSING", task_id)
    record = load_json(path, max_bytes=RECORD_MAX_BYTES)
    errors = []
    if not isinstance(record, dict) or \
            record.get("schema") != RECORD_SCHEMA:
        raise UALError("CONTINUATION_RECORD_MALFORMED", str(path))
    active = claims.active_claim(project)
    if active is not None:
        errors.append("CONTINUATION_LIVE_CLAIM:"
                      + str(active[1].get("claim_id")))
    sidecar_binding = record.get("sidecar") or {}
    sidecar_path = Path(project) / str(sidecar_binding.get("path") or "")
    if not sidecar_path.is_file():
        errors.append("CONTINUATION_SIDECAR_MISSING")
    else:
        data = sidecar_path.read_bytes()
        if sidecar_binding.get("sha256") != sha256_hex(data):
            errors.append("CONTINUATION_SIDECAR_DRIFT")
        sidecar = load_json(sidecar_path, max_bytes=RECORD_MAX_BYTES)
        if not isinstance(sidecar, dict) or \
                str(sidecar.get("status")) not in TERMINAL_STATUSES:
            errors.append("CONTINUATION_SIDECAR_NOT_TERMINAL")
        log_rel = (sidecar.get("log") or {}).get("path")
        log_path = Path(project) / str(log_rel or "")
        log_binding = record.get("log") or {}
        if not log_path.is_file():
            errors.append("CONTINUATION_LOG_MISSING")
        else:
            actual = sha256_hex(log_path.read_bytes())
            if actual != log_binding.get("sha256") or \
                    actual != (sidecar.get("log") or {}).get("sha256"):
                errors.append("CONTINUATION_LOG_DRIFT")
    task_bytes = (project / "task.json").read_bytes()
    if (record.get("task_file") or {}).get("sha256") != \
            sha256_hex(task_bytes):
        errors.append("CONTINUATION_TASK_DRIFT")
    if errors:
        raise UALError("CONTINUATION_VERIFY_REFUSED",
                       ";".join(errors[:4]))
    return {"ok": True, "prior_run_id": record.get("prior_run_id")}

"""Attempt-scoped tool-event ingestion with honest transcript bounds.

Events are appended only through the CLI, in order, per attempt. A
missing transcript is a normal early state, never a crash. Transcript
completeness stays UNKNOWN: only a verified host export (a signed
digest of the whole ingested stream) can mark an attempt VERIFIED, and a
required-but-missing completeness blocks only the operations whose
declared guarantee needs it. After a successful close no further tool
event is accepted for that attempt.
"""
from __future__ import annotations

import json
from pathlib import Path

from .errors import UALError
from .hashing import atomic_write_json, load_json, sha256_hex
from .paths import task_dir

EVENTS_MAX_BYTES = 1024 * 1024
EXPORT_MAX_BYTES = 64 * 1024


def _attempt_dir(project: Path, task_id: str) -> Path:
    from .attempts import ensure_current
    return Path(task_dir(project, task_id)) / "attempts"


def _current_attempt_dir(project: Path, task_id: str) -> Path:
    from . import attempts
    return attempts.current_dir(project, task_id)


def events_path(project: Path, task_id: str) -> Path:
    return _current_attempt_dir(project, task_id) / "events.jsonl"


def meta_path(project: Path, task_id: str) -> Path:
    return _current_attempt_dir(project, task_id) / "events_meta.json"


def record_event(project: Path, task: dict, tool: str, detail: str,
                 exit_code) -> dict:
    from .lifecycle import closed_record
    from . import attempts
    if closed_record(project, task) is not None:
        raise UALError("POST_CLOSE_EVENT", tool)
    attempts.ensure_current(project, task)
    path = events_path(project, task["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    seq = 0
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                seq += 1
        if path.stat().st_size > EVENTS_MAX_BYTES:
            raise UALError("EVENTS_OVER_BOUND", str(path))
    from .claims import utc_now_iso
    from .attempts import current_seq
    line = json.dumps({
        "seq": seq + 1, "at": utc_now_iso(), "tool": tool,
        "detail": detail, "exit": exit_code,
        "attempt": current_seq(project, task["id"]),
    }, ensure_ascii=True, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return {"ok": True, "seq": seq + 1}


def ingest_export(project: Path, task: dict, export_rel: str,
                  attested_by: str | None = None) -> dict:
    """A self-authored export is not VERIFIED. Completeness upgrades only
    through a configured trusted verifier binding in the authority
    config, or an explicit OWNER attestation recorded as the distinct
    OWNER_ATTESTED guarantee (never relabeled VERIFIED)."""
    from .lifecycle import closed_record
    from . import authority
    if closed_record(project, task) is not None:
        raise UALError("POST_CLOSE_EVENT", "transcript export")
    export_path = Path(project) / export_rel
    if not export_path.is_file():
        raise UALError("TRANSCRIPT_EXPORT_MISSING", export_rel)
    export = load_json(export_path, max_bytes=EXPORT_MAX_BYTES)
    if not isinstance(export, dict) or \
            export.get("schema") != "ual-transcript-export/1":
        raise UALError("TRANSCRIPT_EXPORT_SCHEMA", export_rel)
    path = events_path(project, task["id"])
    if not path.is_file():
        raise UALError("TRANSCRIPT_EVENTS_MISSING", export_rel)
    data = path.read_bytes()
    if export.get("events_sha256") != sha256_hex(data):
        raise UALError("TRANSCRIPT_EXPORT_DIGEST_MISMATCH", export_rel)
    if export.get("task") != task["id"]:
        raise UALError("TRANSCRIPT_EXPORT_TASK_MISMATCH", export_rel)
    if export.get("complete") is not True:
        raise UALError("TRANSCRIPT_EXPORT_NOT_COMPLETE", export_rel)
    config = authority.load_config(project)
    verifier = (config or {}).get("transcript_verifier")
    if attested_by is not None:
        if not authority.is_configured_owner(project, attested_by):
            raise UALError("AUTHORITY_ACTOR_NOT_OWNER", attested_by)
        completeness = "OWNER_ATTESTED"
    elif isinstance(verifier, str) and verifier.strip():
        session = authority.get_session(project, verifier)
        if session is None or session.get("role") not in ("REVIEWER",
                                                          "OBSERVER"):
            raise UALError("TRANSCRIPT_VERIFIER_INVALID", verifier)
        completeness = "VERIFIED"
    else:
        raise UALError("TRANSCRIPT_VERIFIER_REQUIRED",
                       "a self-authored export is not VERIFIED; configure "
                       "transcript_verifier or pass an owner attestation")
    meta = {"schema": "ual-events-meta/1", "completeness": completeness,
            "export_sha256": sha256_hex(export_path.read_bytes()),
            "events_sha256": sha256_hex(data),
            "event_count": export.get("event_count"),
            "attested_by": attested_by}
    atomic_write_json(meta_path(project, task["id"]), meta,
                      max_bytes=64 * 1024)
    return {"ok": True, "completeness": completeness}


def completeness(project: Path, task_id: str) -> str:
    path = meta_path(project, task_id)
    if not path.is_file():
        return "UNKNOWN"
    meta = load_json(path, max_bytes=64 * 1024)
    if isinstance(meta, dict):
        return meta.get("completeness", "UNKNOWN")
    return "UNKNOWN"

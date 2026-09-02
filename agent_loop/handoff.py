"""Native/manual handoff: request, bounded result, owner confirmation.

For a natively driven writer the launcher cannot fabricate OS PID, exit
codes or launcher-proven termination. Instead one immutable request binds
request id, task/attempt, authority digest, actor/session/role, the
retained claim, the verified context payload and the candidate capture;
the receiver result is stored with its digests and UNKNOWN transcript
completeness; only an explicit configured OWNER confirmation terminalizes
the writer with terminal_evidence_origin OWNER_ATTESTED. Matching fields
prove local correlation, never external delivery or model identity.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from . import attempts, authority, claims
from .errors import UALError
from .hashing import (atomic_write_json, exclusive_write_json, load_json,
                      next_sequence, sha256_hex)
from .paths import resolve_inside
from .runner import capture_digest

REQUEST_SCHEMA = "ual-handoff-request/1"
REQUEST_MAX_BYTES = 256 * 1024
RESULT_MAX_BYTES = 8 * 1024 * 1024
MAX_REQUESTS = 4096


def requests_dir(project: Path, task_id: str, attempt: int) -> Path:
    directory = attempts.attempt_dir(project, task_id, attempt) / "requests"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def results_dir(project: Path, task_id: str, attempt: int) -> Path:
    directory = attempts.attempt_dir(project, task_id, attempt) / "results"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _request_path(directory: Path, request_id: str) -> Path:
    return directory / f"request_{request_id}.json"


def _engineer_transport(config: dict, task: dict) -> str:
    _role_class, binding = authority.engineer_binding(config, task)
    if not isinstance(binding, dict) or \
            binding.get("transport") not in ("command", "native"):
        raise UALError("ROUTE_UNUSABLE",
                       "no usable engineer route binding is configured")
    return binding["transport"]


def issue(project: Path, task: dict, session_id: str) -> dict:
    task_id = task["id"]
    gate = attempts.prelaunch(project, task, session_id)
    config = gate["config"]
    if _engineer_transport(config, task) != "native":
        raise UALError("HANDOFF_NOT_NATIVE",
                       "the configured engineer transport is command; "
                       "use run")
    if gate["session"].get("transport") != "native":
        raise UALError("AUTHORITY_SESSION_TRANSPORT_MISMATCH",
                       f"{session_id}:{gate['session'].get('transport')}")
    attempt = gate["attempt"]
    session = gate["session"]
    from .lifecycle import closed_record
    if closed_record(project, task) is not None:
        raise UALError("ATTEMPT_CLOSED", task_id)
    context_pack = task_dir_context(project, task_id)
    authority_digest = authority.config_digest(project)
    claim = claims.acquire(project, task_id)
    request_id = secrets.token_hex(8)
    directory = requests_dir(project, task_id, attempt)
    if len(list(directory.iterdir())) >= MAX_REQUESTS:
        raise UALError("HANDOFF_REQUESTS_BOUND", str(MAX_REQUESTS))
    request = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "task": task_id,
        "attempt": attempt,
        "authority_sha256": authority_digest,
        "actor": session.get("actor"),
        "session_id": session_id,
        "role": "ENGINEER",
        "transport": "native",
        "claim_id": claim["claim_id"],
        "context_pack": context_pack,
        "candidate_sha256": capture_digest(Path(project), task),
        "expected_result": "BOUNDED_RESULT",
        "status": "OPEN",
        "issued_at": claims.utc_now_iso(),
    }
    exclusive_write_json(_request_path(directory, request_id), request,
                         max_bytes=REQUEST_MAX_BYTES)
    return {"ok": True, "request_id": request_id, "attempt": attempt,
            "claim_id": claim["claim_id"],
            "context_pack": context_pack,
            "observed_identity": "UNKNOWN"}


def task_dir_context(project: Path, task_id: str) -> dict:
    from .context import verify_pack
    pack_rel = f".agent-loop/tasks/{task_id}/context_pack.md"
    try:
        verify_pack(Path(project), {"id": task_id}, pack_rel)
    except UALError as exc:
        raise UALError("HANDOFF_CONTEXT_UNVERIFIED", exc.code)
    pack_path = resolve_inside(Path(project), pack_rel, label="PACK")
    return {"path": pack_rel, "sha256": sha256_hex(pack_path.read_bytes())}


def receive(project: Path, task: dict, request_id: str, result_rel: str,
            session_id: str) -> dict:
    task_id = task["id"]
    request = _load_request(project, task_id, request_id)
    if request.get("status") != "OPEN":
        raise UALError("REQUEST_ALREADY_RECEIVED", request_id)
    session = authority.get_session(project, session_id)
    if session is None or session.get("session_id") != \
            request.get("session_id"):
        raise UALError("HANDOFF_SESSION_MISMATCH", session_id)
    result_path = resolve_inside(project, result_rel, label="HANDOFF_RESULT")
    if not result_path.is_file():
        raise UALError("HANDOFF_RESULT_MISSING", result_rel)
    data = result_path.read_bytes()
    if len(data) > RESULT_MAX_BYTES:
        raise UALError("HANDOFF_RESULT_OVER_BOUND", result_rel)
    results = results_dir(project, task_id, request["attempt"])
    payload_path = results / f"result_{request_id}.bin"
    exclusive_write_json(
        results / f"result_{request_id}.json", {
            "schema": "ual-handoff-result/1",
            "request_id": request_id,
            "task": task_id,
            "attempt": request["attempt"],
            "session_id": session_id,
            "bytes": len(data),
            "sha256": sha256_hex(data),
            "transcript_completeness": "UNKNOWN",
            "observed_identity": "UNKNOWN",
            "received_at": claims.utc_now_iso(),
        }, max_bytes=REQUEST_MAX_BYTES)
    exclusive_write_bytes_guarded(payload_path, data, RESULT_MAX_BYTES)
    request["status"] = "RECEIVED"
    request["result_sha256"] = sha256_hex(data)
    atomic_write_json(_request_path(requests_dir(project, task_id,
                                                  request["attempt"]),
                                   request_id),
                      request, max_bytes=REQUEST_MAX_BYTES)
    return {"ok": True, "request_id": request_id, "status": "RECEIVED",
            "transcript_completeness": "UNKNOWN",
            "observed_identity": "UNKNOWN"}


def confirm(project: Path, task: dict, request_id: str, actor: str,
            decision: str) -> dict:
    task_id = task["id"]
    config = authority.require_config(project)
    if not authority.is_configured_owner(project, actor):
        raise UALError("AUTHORITY_ACTOR_NOT_OWNER", actor)
    if decision not in ("COMPLETED", "FAILED"):
        raise UALError("HANDOFF_DECISION_INVALID", decision)
    request = _load_request(project, task_id, request_id)
    if request.get("status") != "RECEIVED":
        raise UALError("HANDOFF_CONFIRM_requires_RECEIVED", request_id)
    attempt = request["attempt"]
    results = results_dir(project, task_id, attempt)
    terminal = {
        "schema": "ual-handoff-terminal/1",
        "request_id": request_id,
        "task": task_id,
        "attempt": attempt,
        "decision": decision,
        "terminal_evidence_origin": "OWNER_ATTESTED",
        "observed_identity": "UNKNOWN",
        "transcript_completeness": "UNKNOWN",
        "confirmed_by": actor,
        "confirmed_at": claims.utc_now_iso(),
    }
    exclusive_write_json(results / f"terminal_{request_id}.json", terminal,
                         max_bytes=REQUEST_MAX_BYTES)
    if decision == "COMPLETED":
        claims.release_native(project, request.get("claim_id"), {
            "class": "OWNER_ATTESTED_NATIVE",
            "origin": "OWNER_ATTESTED",
            "request_id": request_id,
            "result_sha256": request.get("result_sha256"),
            "observed_identity": "UNKNOWN",
        })
    else:
        claims.abandon(project, request.get("claim_id"), actor,
                       "native handoff failed; owner adjudicated")
    request["status"] = "CONFIRMED"
    request["decision"] = decision
    atomic_write_json(_request_path(requests_dir(project, task_id, attempt),
                                    request_id),
                      request, max_bytes=REQUEST_MAX_BYTES)
    state = attempts._load_state(project, task_id)
    state["writer_terminal"] = {
        "attempt": attempt, "origin": "OWNER_ATTESTED",
        "request_id": request_id, "decision": decision,
    }
    attempts._save_state(project, task_id, state)
    return {"ok": True, "request_id": request_id, "decision": decision,
            "terminal_evidence_origin": "OWNER_ATTESTED",
            "observed_identity": "UNKNOWN",
            "transcript_completeness": "UNKNOWN"}


def _load_request(project: Path, task_id: str, request_id: str) -> dict:
    if not isinstance(request_id, str) or not request_id.strip():
        raise UALError("HANDOFF_REQUEST_INVALID", request_id)
    attempt = attempts.current_seq(project, task_id)
    if attempt is None:
        raise UALError("ATTEMPT_MISSING", task_id)
    path = _request_path(requests_dir(project, task_id, attempt), request_id)
    if not path.is_file():
        raise UALError("HANDOFF_REQUEST_MISSING", request_id)
    request = load_json(path, max_bytes=REQUEST_MAX_BYTES)
    if not isinstance(request, dict) or request.get("schema") != REQUEST_SCHEMA:
        raise UALError("HANDOFF_REQUEST_MALFORMED", request_id)
    return request


def exclusive_write_bytes_guarded(path: Path, data: bytes,
                                  max_bytes: int) -> None:
    from .hashing import exclusive_write_bytes
    exclusive_write_bytes(path, data, max_bytes=max_bytes)

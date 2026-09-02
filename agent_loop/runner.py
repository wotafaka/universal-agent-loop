"""Supervised child runs: argv without a shell, allowlisted environment,
durable bounded logs, atomic sidecars and receiver-bound acknowledgment.

Each run writes a STARTING sidecar before the single child exists, binds
the child's PID plus OS birth identity immediately after spawn, and
finishes with an honest terminal sidecar carrying the actual exit code,
log bytes/digest and truncation state. Delivery of prompt bytes is only
PROVEN by a receiver-side acknowledgment bound to the run ID and the
exact stdin digest; anything else stays UNKNOWN or REFUSED.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from . import claims, prockid
from .errors import UALError
from .hashing import (atomic_write_json, exclusive_write_bytes, load_json,
                      sha256_hex)
from .paths import inside_rel, resolve_inside, run_dir, runs_dir
from .taskfile import allowlist, capture_exclusions, declared_seed, \
    environment_policy

RUN_SCHEMA = "ual-run/1"
DEFAULT_LOG_CAP_BYTES = 2 * 1024 * 1024


def _host_name() -> str:
    import socket
    return socket.gethostname()
SIDECAR_MAX_BYTES = 64 * 1024
POLL_INTERVAL_S = 0.05
RUNNER_ENV_KEYS = ("UAL_RUN_ID", "UAL_TASK", "UAL_STDIN_SHA256")


def capture_digest(project: Path, task: dict) -> str | None:
    """Candidate capture digest: allowlist bytes minus the report, in order."""
    excluded = set(capture_exclusions(task))
    pairs = []
    for member in allowlist(task):
        if member in excluded:
            continue
        path = (Path(project) / member)
        if not path.is_file():
            continue
        pairs.append((member, sha256_hex(path.read_bytes())))
    if not pairs:
        return None
    from .hashing import member_digest
    return member_digest(pairs)


def env_policy_identity(policy: dict) -> str:
    return sha256_hex((b"ual-env-policy/1\x1f"
                       + json.dumps(policy, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")))


def _build_env(project: Path, task: dict, overlay: dict | None,
               run_id: str, stdin_sha: str) -> dict:
    declared = environment_policy(task)
    base_keys = list(declared["base"])
    merged_overlay = dict(declared["overlay"])
    if overlay:
        merged_overlay.update(overlay)
    env = {}
    for key in base_keys:
        if key in os.environ:
            env[key] = os.environ[key]
    env.update(merged_overlay)
    env["UAL_RUN_ID"] = run_id
    env["UAL_TASK"] = task.get("id") or ""
    env["UAL_STDIN_SHA256"] = stdin_sha
    env["UAL_SEED"] = declared_seed(task)
    return env


def run_child(project: Path, task: dict, *, purpose: str, argv: list,
              stdin_bytes: bytes = b"", overlay: dict | None = None,
              ack_rel: str | None = None, session_id: str | None = None,
              log_cap_bytes: int = DEFAULT_LOG_CAP_BYTES,
              basis_text: str | None = None,
              identity_probe=None) -> dict:
    project = Path(project)
    if purpose not in ("VALIDATION", "ENGINEER", "OTHER"):
        raise UALError("RUN_PURPOSE_INVALID", purpose)
    if not isinstance(argv, list) or not argv or not all(
            isinstance(a, str) and a for a in argv):
        raise UALError("RUN_ARGV_REQUIRED", "")
    claim_info = None
    if purpose == "ENGINEER":
        claim_info = claims.acquire(project, task["id"])
    run_id = uuid.uuid4().hex[:16]
    directory = run_dir(project, run_id)
    runs_dir(project).mkdir(parents=True, exist_ok=True)
    sidecar_path = directory / "run.json"
    log_path = directory / "log.txt"
    stdin_sha = sha256_hex(stdin_bytes) if stdin_bytes else ""
    env = _build_env(project, task, overlay, run_id, stdin_sha)
    policy = environment_policy(task)
    seed = declared_seed(task)
    if overlay:
        policy = {"base": policy["base"],
                  "overlay": {**policy["overlay"], **overlay}}
    policy["seed"] = seed
    identity = env_policy_identity(policy)
    from . import taskfile as tf
    basis = None
    if basis_text:
        from .packs import stable_progress_basis
        basis = stable_progress_basis(task["id"], basis_text)
        if basis is None:
            raise UALError("PROGRESS_BASIS_NOT_DERIVABLE", "basis-file")
    sidecar = {
        "schema": RUN_SCHEMA,
        "run_id": run_id,
        "task": task["id"],
        "purpose": purpose,
        "argv": list(argv),
        "cwd": ".",
        "host": _host_name(),
        "env_policy_sha256": identity,
        "seed": seed,
        "status": "STARTING",
        "started_at": claims.utc_now_iso(),
        "running_at": None,
        "finished_at": None,
        "pid": None,
        "child_identity": None,
        "identity_state": claims.IDENTITY_UNBOUND,
        "exit_code": None,
        "overflow": False,
        "log": {"path": None, "bytes": 0, "sha256": None,
                "truncated": False},
        "ack": {"path": ack_rel, "state": "UNKNOWN", "reason": None},
        "session_id": session_id,
        "claim_id": claim_info["claim_id"] if claim_info else None,
        "capture": {"sha256": capture_digest(project, task)},
        "launch_identity": {"progress_basis": basis,
                            "material_progress_claim": None},
    }
    atomic_write_json(sidecar_path, sidecar, max_bytes=SIDECAR_MAX_BYTES)
    try:
        exclusive_write_bytes(log_path, b"", max_bytes=log_cap_bytes * 2)
    except UALError:
        _mark_spawn_failed(sidecar_path, sidecar, "RUN_LOG_EXISTS")
        if claim_info:
            _release_failed_claim(project, claim_info, sidecar_path, sidecar)
        raise
    popen = None
    handle = None
    try:
        handle = open(log_path, "ab")
        popen = subprocess.Popen(
            argv, shell=False, cwd=str(project),
            stdin=subprocess.PIPE if stdin_bytes else subprocess.DEVNULL,
            stdout=handle, stderr=subprocess.STDOUT, env=env)
    except BaseException as exc:
        if handle is not None:
            handle.close()
        _mark_spawn_failed(sidecar_path, sidecar,
                           "RUN_SPAWN_FAILED:" + type(exc).__name__)
        if claim_info:
            _release_failed_claim(project, claim_info, sidecar_path, sidecar)
        raise UALError("RUN_SPAWN_FAILED", type(exc).__name__) from None
    identity_state, child_identity = _bind_identity(
        project, claim_info, popen, identity_probe)
    sidecar["pid"] = popen.pid
    sidecar["child_identity"] = child_identity
    sidecar["identity_state"] = identity_state
    sidecar["status"] = "RUNNING"
    sidecar["running_at"] = claims.utc_now_iso()
    sidecar["log"] = {"path": inside_rel(project, log_path),
                      "bytes": log_path.stat().st_size, "sha256": None,
                      "truncated": False}
    atomic_write_json(sidecar_path, sidecar, max_bytes=SIDECAR_MAX_BYTES)
    overflow = False
    stdin_error = []
    if stdin_bytes:
        import threading

        def _feed():
            try:
                popen.stdin.write(stdin_bytes)
                popen.stdin.close()
            except (OSError, ValueError) as exc:
                stdin_error.append(exc)
        feeder = threading.Thread(target=_feed, daemon=True)
        feeder.start()
    while True:
        size = log_path.stat().st_size
        if size > log_cap_bytes:
            overflow = True
            popen.kill()
            try:
                popen.wait(timeout=15)
            except subprocess.TimeoutExpired:
                popen.terminate()
                popen.wait(timeout=15)
            break
        exit_code = popen.poll()
        if exit_code is not None:
            break
        time.sleep(POLL_INTERVAL_S)
    if stdin_bytes:
        feeder.join(timeout=5)
    exit_code = popen.wait()
    if handle is not None:
        handle.close()
    size = log_path.stat().st_size
    if size > log_cap_bytes:
        overflow = True
    if overflow:
        with open(log_path, "r+b") as log_handle:
            log_handle.truncate(log_cap_bytes)
    data = log_path.read_bytes()
    truncated = overflow or len(data) > log_cap_bytes
    sidecar["status"] = "FINISHED"
    sidecar["finished_at"] = claims.utc_now_iso()
    sidecar["exit_code"] = exit_code
    sidecar["overflow"] = overflow
    sidecar["log"] = {"path": inside_rel(project, log_path),
                      "bytes": len(data), "sha256": sha256_hex(data),
                      "truncated": truncated,
                      "stored_bytes": len(data)}
    sidecar["ack"] = _verify_ack(project, task, run_id, ack_rel, stdin_sha)
    atomic_write_json(sidecar_path, sidecar, max_bytes=SIDECAR_MAX_BYTES)
    claim_state = None
    if claim_info is not None:
        if identity_state == claims.IDENTITY_OBTAINED:
            try:
                claims.release(project, claim_info["claim_id"], run_id,
                               _sidecar_loader(project))
                claim_state = "RELEASED"
            except UALError:
                claim_state = "ACTIVE"
        else:
            claim_state = "ACTIVE"
    return {
        "ok": True,
        "run_id": run_id,
        "task": task["id"],
        "purpose": purpose,
        "status": sidecar["status"],
        "exit_code": exit_code,
        "overflow": overflow,
        "log": sidecar["log"],
        "delivered": {"PROVEN": True, "REFUSED": False,
                      "UNKNOWN": None}[sidecar["ack"]["state"]],
        "identity_state": identity_state,
        "claim": ({"id": claim_info["claim_id"], "state": claim_state}
                  if claim_info else None),
        "session_id": session_id,
        "seed": seed,
    }


def _bind_identity(project, claim_info, popen, identity_probe):
    probe = identity_probe or prockid.process_start_identity
    if claim_info is None:
        identity = probe(popen.pid) if probe is not None else None
        state = (claims.IDENTITY_OBTAINED if identity is not None
                 else claims.IDENTITY_CHILD_EXITED)
        return state, identity
    deadline = time.monotonic() + claims.IDENTITY_BIND_RETRY_S
    while True:
        try:
            identity = probe(popen.pid)
        except Exception:
            identity = None
        if identity is not None:
            break
        if popen.poll() is not None:
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    if identity is not None:
        state = claims.IDENTITY_OBTAINED
    elif popen.poll() is not None:
        state = claims.IDENTITY_CHILD_EXITED
    else:
        state = claims.IDENTITY_UNOBTAINABLE_ALIVE
    try:
        claims.bind_child(project, claim_info["claim_id"], popen.pid,
                          identity, state)
    except UALError:
        state = claims.IDENTITY_UNOBTAINABLE_ALIVE
    return state, identity


def _mark_spawn_failed(sidecar_path: Path, sidecar: dict, reason: str):
    sidecar["status"] = "SPAWN_FAILED"
    sidecar["spawn_error"] = reason
    sidecar["finished_at"] = claims.utc_now_iso()
    try:
        atomic_write_json(sidecar_path, sidecar,
                          max_bytes=SIDECAR_MAX_BYTES)
    except UALError:
        pass


def _release_failed_claim(project, claim_info, sidecar_path, sidecar):
    from .hashing import atomic_write_json as _aw
    from .paths import claims_dir
    try:
        path = claims_dir(project) / f"claim_{claim_info['sequence']:08d}.json"
        claim = claims._read_claim(path)
        if claim.get("claim_id") == claim_info["claim_id"] and \
                claim.get("status") == claims.STATUS_ACTIVE and \
                claim.get("identity_state") == claims.IDENTITY_UNBOUND:
            claim["status"] = claims.STATUS_RELEASED
            claim["released_at"] = claims.utc_now_iso()
            claim["terminal_evidence"] = {
                "class": "SPAWN_FAILED_NO_CHILD",
                "spawn_error": sidecar.get("spawn_error"),
            }
            _aw(path, claim, max_bytes=claims.CLAIM_MAX_BYTES)
    except (UALError, OSError):
        pass


def _verify_ack(project: Path, task: dict, run_id: str, ack_rel,
                stdin_sha: str):
    if not ack_rel:
        return {"path": None, "state": "UNKNOWN",
                "reason": "no acknowledgment requested"}
    try:
        ack_path = resolve_inside(project, ack_rel, label="ACK")
    except UALError as exc:
        return {"path": ack_rel, "state": "REFUSED", "reason": exc.refusal()}
    if not ack_path.is_file():
        return {"path": ack_rel, "state": "UNKNOWN",
                "reason": "receiver acknowledgment absent"}
    try:
        payload = json.loads(ack_path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {"path": ack_rel, "state": "REFUSED",
                "reason": "acknowledgment unreadable"}
    if not isinstance(payload, dict) or \
            payload.get("schema") != "ual-ack/1":
        return {"path": ack_rel, "state": "REFUSED",
                "reason": "acknowledgment schema invalid"}
    if payload.get("run_id") != run_id or payload.get("task") != task["id"]:
        return {"path": ack_rel, "state": "REFUSED",
                "reason": "acknowledgment not bound to this run"}
    if not stdin_sha or payload.get("stdin_sha256") != stdin_sha:
        return {"path": ack_rel, "state": "REFUSED",
                "reason": "stdin digest mismatch"}
    return {"path": ack_rel, "state": "PROVEN", "reason": None}


def _sidecar_loader(project: Path):
    def loader(run_id: str):
        path = run_dir(project, run_id) / "run.json"
        if not path.is_file():
            return None
        return load_json(path, max_bytes=SIDECAR_MAX_BYTES)
    return loader


def load_sidecar(project: Path, run_id: str):
    path = run_dir(project, run_id) / "run.json"
    if not path.is_file():
        return None
    return load_json(path, max_bytes=SIDECAR_MAX_BYTES)


def load_sidecar_file(project: Path, path: Path):
    return load_json(path, max_bytes=SIDECAR_MAX_BYTES)

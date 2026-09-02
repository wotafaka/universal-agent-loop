"""Same-task attempts: the minimal explicit repair iteration.

An attempt owns one ledger, one close chain, one envelope, its receipts,
events and handoff requests. Attempt 1 opens without gates; a repair
attempt opens only from a closed, frozen predecessor carrying a negative
review seal, with a substantively changed progress basis plus a
structured material claim, and with any pending efficiency dispositions
acknowledged. Predecessor evidence is linked immutably and never
rewritten; a new task ID or deleted history is not a repair.
"""
from __future__ import annotations

from pathlib import Path

from . import authority, claims, packs
from .errors import UALError
from .hashing import (exclusive_write_json, load_json, next_sequence,
                      sha256_hex)
from .paths import task_dir

ATTEMPT_SCHEMA = "ual-attempt/1"
ATTEMPT_MAX_BYTES = 256 * 1024
MAX_CHECKPOINTS = 4096


def attempts_root(project: Path, task_id: str) -> Path:
    return task_dir(project, task_id) / "attempts"


def attempt_dir(project: Path, task_id: str, seq: int) -> Path:
    return attempts_root(project, task_id) / f"attempt_{seq:08d}"


def current_seq(project: Path, task_id: str) -> int | None:
    root = attempts_root(project, task_id)
    if not root.is_dir():
        return None
    seqs = []
    for entry in root.iterdir():
        if entry.is_dir() and entry.name.startswith("attempt_"):
            try:
                seqs.append(int(entry.name[len("attempt_"):]))
            except ValueError:
                continue
    return max(seqs) if seqs else None


def current_dir(project: Path, task_id: str) -> Path:
    seq = current_seq(project, task_id)
    if seq is None:
        raise UALError("ATTEMPT_MISSING", task_id)
    return attempt_dir(project, task_id, seq)


def current_payload(project: Path, task_id: str) -> dict:
    return load_json(current_dir(project, task_id) / "attempt.json",
                     max_bytes=ATTEMPT_MAX_BYTES)


def ensure_current(project: Path, task: dict) -> int:
    """Open attempt 1 without gates if no attempt exists yet. Attempt
    creation is an authority-bearing event: it refuses until a trusted
    local config exists, so authority_sha256 is never manufactured as
    NONE."""
    task_id = task["id"]
    seq = current_seq(project, task_id)
    if seq is not None:
        return seq
    authority.require_config(project)
    _write_attempt(project, task, seq=1, predecessor=None, progress=None,
                   efficiency_acks=[])
    return 1


def _write_attempt(project: Path, task: dict, *, seq: int, predecessor,
                   progress, efficiency_acks: list) -> dict:
    task_id = task["id"]
    directory = attempt_dir(project, task_id, seq)
    if directory.exists():
        raise UALError("ATTEMPT_EXISTS", str(directory))
    try:
        authority_digest = authority.config_digest(project)
    except UALError:
        raise UALError("ATTEMPT_AUTHORITY_REQUIRED",
                       "attempts refuse to open before a trusted local "
                       "authority config exists") from None
    task_bytes = (Path(project) / "task.json").read_bytes()
    payload = {
        "schema": ATTEMPT_SCHEMA,
        "task": task_id,
        "attempt": seq,
        "opened_at": claims.utc_now_iso(),
        "authority_sha256": authority_digest,
        "task_sha256": sha256_hex(task_bytes),
        "predecessor": predecessor,
        "progress": progress,
        "efficiency_acks": efficiency_acks,
    }
    directory.mkdir(parents=True, exist_ok=False)
    exclusive_write_json(directory / "attempt.json", payload,
                         max_bytes=ATTEMPT_MAX_BYTES)
    state = _load_state(project, task_id)
    state["current_attempt"] = seq
    _save_state(project, task_id, state)
    return payload


def _load_state(project: Path, task_id: str) -> dict:
    from .lifecycle import load_state
    state = load_state(project, task_id)
    if state is None:
        state = {"schema": "ual-state/1", "task": task_id, "status": "ACTIVE",
                 "seq": 0, "updated_at": "",
                 "last_material_claim_identity": None}
    return state


def _save_state(project: Path, task_id: str, state: dict) -> None:
    from .claims import utc_now_iso
    from .lifecycle import save_state
    state["updated_at"] = utc_now_iso()
    save_state(project, task_id, state)


def open_attempt(project: Path, task: dict, batch_rel: str | None,
                 claim_file: str | None,
                 efficiency_acks: list,
                 consume_pending_from_task: str | None = None,
                 pack_iteration: int | None = None) -> dict:
    task_id = task["id"]
    authority.require_config(project)
    if consume_pending_from_task:
        if consume_pending_from_task == task_id:
            raise UALError("EFFICIENCY_SOURCE_TASK_INVALID",
                           consume_pending_from_task)
        consume_pending_from(project, task, consume_pending_from_task)
    state = _load_state(project, task_id)
    predecessor_seq = current_seq(project, task_id)
    predecessor = None
    progress = None
    if predecessor_seq is not None:
        if state.get("status") != "FIX_REQUIRED":
            raise UALError("ATTEMPT_OPEN_REFUSED",
                           "repair attempts require the FIX_REQUIRED state "
                           "recorded by a negative review")
        from . import envelope as envelope_mod
        from .lifecycle import closed_record, latest_record
        if closed_record(project, task) is None:
            raise UALError("ATTEMPT_OPEN_REFUSED",
                           "predecessor attempt is not closed")
        try:
            envelope_path, envelope = envelope_mod.latest_envelope(
                project, task_id)
        except (UALError, FileNotFoundError):
            raise UALError("ATTEMPT_OPEN_REFUSED",
                           "predecessor attempt has no frozen envelope")
        seal = envelope_mod.latest_seal(project, task_id)
        if seal is None or seal[1].get("verdict") != "FAIL":
            raise UALError("ATTEMPT_OPEN_REFUSED",
                           "predecessor attempt has no negative review seal")
        seal_path = seal[0]
        predecessor = {
            "attempt": predecessor_seq,
            "envelope_sha256": sha256_hex(envelope_path.read_bytes()),
            "negative_seal_sha256": sha256_hex(seal_path.read_bytes()),
        }
    _require_efficiency_acks(project, task_id, efficiency_acks)
    pack_binding = None
    if pack_iteration is not None:
        pack_binding = _require_verified_pack(project, task_id,
                                              pack_iteration)
    if batch_rel is not None:
        progress = _evaluate_progress(project, task, batch_rel, claim_file,
                                      predecessor is not None)
    if predecessor is not None and progress is None:
        raise UALError("ATTEMPT_OPEN_REFUSED",
                       "repair attempts require a changed substantive "
                       "progress basis (--batch)")
    if progress is not None and pack_binding is not None:
        progress["pack_iteration"] = pack_binding["iteration"]
    seq = 1 if predecessor_seq is None else predecessor_seq + 1
    payload = _write_attempt(project, task, seq=seq, predecessor=predecessor,
                             progress=progress,
                             efficiency_acks=efficiency_acks)
    if predecessor is not None:
        _save_state(project, task_id,
                    _transition_to_active(_load_state(project, task_id)))
    return {"ok": True, "attempt": seq, "task": task_id,
            "authority_sha256": payload["authority_sha256"],
            "progress": payload["progress"]}


def prelaunch(project: Path, task: dict, session_id: str) -> dict:
    """The shared prelaunch gate for BOTH entry transports (command run
    and native handoff): trusted authority config, registered ENGINEER
    session, attempt authorization, verified continuation, and a still-
    valid repair pack binding when the attempt declared one. No claim,
    log or child may exist yet."""
    config = authority.require_config(project)
    if not session_id:
        raise UALError("AUTHORITY_SESSION_REQUIRED",
                       "engineer launches require --session-id")
    session = authority.require_session_role(project, session_id, "ENGINEER")
    attempt = ensure_current(project, task)
    if attempt > 1:
        payload = current_payload(project, task["id"])
        if not payload.get("progress"):
            raise UALError("ATTEMPT_PROGRESS_BLOCKED",
                           "the repair attempt opened without an "
                           "authorized progress basis")
        pack_iteration = (payload.get("progress") or {}).get(
            "pack_iteration")
        if pack_iteration is not None:
            _require_verified_pack(project, task["id"], pack_iteration,
                                   current=False)
    from .continuation import record_path, verify
    if record_path(project, task["id"]).is_file():
        verify(project, task)
    return {"config": config, "session": session, "attempt": attempt}


def _require_verified_pack(project: Path, task_id: str, iteration: int,
                           current: bool = True) -> dict:
    from . import packs
    directory = (task_dir(project, task_id) / "packs" /
                 f"iteration_{iteration}")
    receipt_path = directory / "verification.json"
    if current and not receipt_path.is_file():
        raise UALError("PACK_NOT_VERIFIED",
                       "verify-first: the repair pack needs a verification "
                       "receipt before the attempt opens")
    receipt = load_json(receipt_path, max_bytes=64 * 1024) \
        if receipt_path.is_file() else None
    if not isinstance(receipt, dict) or \
            receipt.get("schema") != "ual-pack-verification/1":
        raise UALError("PACK_NOT_VERIFIED", "receipt malformed")
    pack_path = directory / "repair_pack.md"
    manifest_path = directory / "manifest.json"
    for field, path in (("pack_sha256", pack_path),
                        ("manifest_sha256", manifest_path)):
        bound = receipt.get(field)
        if bound is None or not path.is_file() or \
                sha256_hex(path.read_bytes()) != bound:
            raise UALError("ATTEMPT_PACK_DRIFT" if not current
                           else "PACK_NOT_VERIFIED",
                           f"{path.name} drifted from its verification "
                           f"receipt; full canonical startup is required")
    # Full read-only revalidation of every manifest-bound live input:
    # task bytes, required skills, AGENTS.md, repair batch, touched map.
    # Any drift refuses before claim, run log or child creation.
    errors = packs.verify_pack_readonly(project, task_id, iteration)
    if errors:
        raise UALError("ATTEMPT_PACK_DRIFT",
                       ";".join(errors[:4]) +
                       "; full canonical startup is required")
    return {"iteration": iteration, "receipt": receipt}


def save_checkpoint(project: Path, task: dict, phase: str) -> dict:
    """Persist one phase-boundary checkpoint binding the current ledger,
    timeline records, events and context index. Context compaction may
    only run against a verified checkpoint; never mid-mutation."""
    from .lifecycle import latest_record
    from .attempts import current_dir
    task_id = task["id"]
    seq = current_seq(project, task_id)
    if seq is None:
        raise UALError("ATTEMPT_MISSING", task_id)
    directory = current_dir(project, task_id) / "checkpoints"
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()) and \
            len(list(directory.iterdir())) >= MAX_CHECKPOINTS:
        raise UALError("CHECKPOINT_DIRTY", str(directory))
    ledger_path = current_dir(project, task_id) / "ledger.json"
    records = {}
    for kind in ("refresh", "reportcheck", "close"):
        record = latest_record(project, task_id, kind)
        if record is not None:
            records[kind] = record.get("seq")
    events_path = current_dir(project, task_id) / "events.jsonl"
    index_path = task_dir(project, task_id) / "context_pack_index.json"
    checkpoint = {
        "schema": "ual-checkpoint/1",
        "task": task_id,
        "attempt": seq,
        "phase": phase,
        "ledger_bytes": ledger_path.stat().st_size
        if ledger_path.is_file() else 0,
        "ledger_sha256": sha256_hex(ledger_path.read_bytes())
        if ledger_path.is_file() else None,
        "record_seqs": records,
        "events_sha256": sha256_hex(events_path.read_bytes())
        if events_path.is_file() else None,
        "context_index_sha256": sha256_hex(index_path.read_bytes())
        if index_path.is_file() else None,
        "saved_at": claims.utc_now_iso(),
    }
    sequence = next_sequence(directory, "checkpoint_", ".json",
                             max_files=MAX_CHECKPOINTS)
    path = directory / f"checkpoint_{sequence:08d}.json"
    exclusive_write_json(path, checkpoint, max_bytes=ATTEMPT_MAX_BYTES)
    return {"ok": True, "path": str(path), "phase": phase}


def verify_checkpoint(project: Path, task: dict) -> dict:
    from .attempts import current_dir
    task_id = task["id"]
    directory = current_dir(project, task_id) / "checkpoints"
    entries = sorted(p for p in directory.iterdir()
                     if p.name.startswith("checkpoint_")) \
        if directory.is_dir() else []
    if not entries:
        raise UALError("CHECKPOINT_MISSING", task_id)
    checkpoint = load_json(entries[-1], max_bytes=ATTEMPT_MAX_BYTES)
    errors = []
    ledger_path = current_dir(project, task_id) / "ledger.json"
    bound_ledger = checkpoint.get("ledger_sha256")
    if bound_ledger and (not ledger_path.is_file() or
                         sha256_hex(ledger_path.read_bytes()) != bound_ledger):
        errors.append("CHECKPOINT_LEDGER_DRIFT")
    events_path = current_dir(project, task_id) / "events.jsonl"
    bound_events = checkpoint.get("events_sha256")
    if bound_events and (not events_path.is_file() or
                         sha256_hex(events_path.read_bytes()) != bound_events):
        errors.append("CHECKPOINT_EVENTS_DRIFT")
    index_path = task_dir(project, task_id) / "context_pack_index.json"
    bound_index = checkpoint.get("context_index_sha256")
    if bound_index and (not index_path.is_file() or
                        sha256_hex(index_path.read_bytes()) != bound_index):
        errors.append("CHECKPOINT_CONTEXT_DRIFT")
    if errors:
        raise UALError("CHECKPOINT_VERIFY_REFUSED", ";".join(errors[:4]))
    return {"ok": True, "phase": checkpoint.get("phase"),
            "path": str(entries[-1])}


def consume_pending_from(project: Path, task: dict, source_task: str) -> dict:
    """Carry a predecessor task's pending efficiency decisions into this
    task so measured recommendations reach the NEXT task, not only
    another attempt under the same ID."""
    task_id = task["id"]
    state = _load_state(project, task_id)
    from .lifecycle import load_state
    source_state = load_state(project, source_task)
    if source_state is None:
        raise UALError("EFFICIENCY_SOURCE_TASK_UNKNOWN", source_task)
    pending = source_state.get("pending_efficiency") or []
    if pending:
        state["pending_efficiency"] = pending
        _save_state(project, task_id, state)
    return {"ok": True, "consumed": len(pending), "from": source_task}


def _transition_to_active(state: dict) -> dict:
    from .lifecycle import validate_transition
    if state.get("status") == "FIX_REQUIRED":
        validate_transition("FIX_REQUIRED", "ACTIVE")
        state["status"] = "ACTIVE"
    return state


def _evaluate_progress(project: Path, task: dict, batch_rel: str,
                       claim_file: str | None, require_change: bool) -> dict:
    try:
        gate = packs.attempt_progress(project, task, batch_rel, claim_file)
    except UALError as exc:
        if exc.code == "PROGRESS_BASIS_NOT_DERIVABLE":
            raise UALError("ATTEMPT_PROGRESS_BASIS_NOT_DERIVABLE",
                           exc.detail)
        raise
    if gate["decision"] == "DUPLICATE_BLOCKED":
        raise UALError("ATTEMPT_PROGRESS_BLOCKED",
                       "identical substantive basis as the predecessor; "
                       "no arbitrary duplicate is authorized")
    if gate["decision"] == "MATERIAL_CLAIM_NON_AUTHORIZING":
        raise UALError("ATTEMPT_PROGRESS_BLOCKED", gate.get("basis_note"))
    return {"decision": gate["decision"], "basis": gate["basis"],
            "claim_identity": gate.get("claim_identity")}


def _require_efficiency_acks(project: Path, task_id: str,
                             efficiency_acks: list) -> dict:
    state = _load_state(project, task_id)
    pending = {entry["id"]: entry for entry in
               (state.get("pending_efficiency") or [])}
    acknowledged = {}
    for ack in efficiency_acks:
        if "=" not in ack or ":" not in ack:
            raise UALError("EFFICIENCY_ACK_MALFORMED", ack)
        rid, rest = ack.split("=", 1)
        action, reason = rest.split(":", 1)
        rid = rid.strip()
        if not rid or not action.strip() or not reason.strip():
            raise UALError("EFFICIENCY_ACK_MALFORMED", ack)
        acknowledged[rid] = {"action": action.strip(),
                             "reason": reason.strip()}
    missing = sorted(set(pending) - set(acknowledged))
    if missing:
        raise UALError("EFFICIENCY_PENDING_UNACKNOWLEDGED",
                       ",".join(missing))
    for rid in acknowledged:
        if rid not in pending:
            raise UALError("EFFICIENCY_ACK_UNKNOWN", rid)
    if acknowledged:
        state["pending_efficiency"] = [
            entry for entry in (state.get("pending_efficiency") or [])
            if entry["id"] not in acknowledged]
        state["applied_efficiency"] = (state.get("applied_efficiency") or [])
        for rid, ack in acknowledged.items():
            state["applied_efficiency"].append({"id": rid, **ack})
        _save_state(project, task_id, state)
    return acknowledged

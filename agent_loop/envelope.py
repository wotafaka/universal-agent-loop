"""Candidate envelope freeze, review seal and manual acceptance binding.

The envelope freezes the exact candidate allowlist bytes, the task and
skill closure, the validation evidence, the declared close chain and the
observer receipt digests. Every hash is recomputed at review time and
again at acceptance time; any drift refuses. Acceptance belongs only to
the configured owner actor and is always an explicit decision bound to
this exact reviewed candidate; a required latest-candidate audit must
have returned a valid PASS before the owner decision.
"""
from __future__ import annotations

from pathlib import Path

from . import authority, lifecycle, reviewgate, validation
from .errors import UALError
from .hashing import (exclusive_write_json, load_json, next_sequence,
                      sha256_hex)
from .paths import resolve_inside, task_dir
from .runner import load_sidecar
from .taskfile import (allowlist, derive_candidate_footprint,
                       requirement_ids, report_rel, validation_commands)

ENVELOPE_SCHEMA = "ual-candidate-envelope/1"
SEAL_SCHEMA = "ual-review-seal/1"
ACCEPTANCE_SCHEMA = "ual-acceptance-record/1"
ENVELOPE_MAX_BYTES = 8 * 1024 * 1024


def _envelope_dir(project: Path, task_id: str) -> Path:
    from .attempts import current_dir
    directory = current_dir(project, task_id) / "envelope"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def latest_envelope(project: Path, task_id: str):
    directory = _envelope_dir(project, task_id)
    entries = sorted(p for p in directory.iterdir()
                     if p.name.startswith("envelope_"))
    if not entries:
        return None
    path = entries[-1]
    payload = load_json(path, max_bytes=ENVELOPE_MAX_BYTES)
    if not isinstance(payload, dict):
        raise UALError("ENVELOPE_MALFORMED", str(path))
    return path, payload


def freeze_envelope(project: Path, task: dict) -> dict:
    task_id = task["id"]
    if lifecycle.closed_record(project, task) is None:
        raise UALError("ENVELOPE_CLOSE_REQUIRED", task_id)
    if latest_envelope(project, task_id) is not None:
        raise UALError("ENVELOPE_EXISTS", task_id)
    errors = []
    members = []
    for rel in allowlist(task):
        try:
            path = resolve_inside(project, rel, label="MEMBER")
        except UALError as exc:
            errors.append(f"CANDIDATE_MEMBER_ESCAPE:{rel}")
            continue
        if not path.is_file():
            errors.append(f"CANDIDATE_MEMBER_MISSING:{rel}")
            continue
        data = path.read_bytes()
        members.append({"path": rel, "bytes": len(data),
                        "sha256": sha256_hex(data)})
    report_rel_path = report_rel(task)
    try:
        report_path = resolve_inside(project, report_rel_path,
                                     label="REPORT")
    except UALError:
        report_path = None
    if report_path is None or not report_path.is_file():
        errors.append(f"CANDIDATE_REPORT_MISSING:{report_rel_path}")
    else:
        data = report_path.read_bytes()
        members.append({"path": report_rel_path, "bytes": len(data),
                        "sha256": sha256_hex(data)})
    skills = []
    for rel in task.get("required_skills") or []:
        try:
            skill_path = resolve_inside(project, rel, label="SKILL")
        except UALError:
            errors.append(f"CANDIDATE_SKILL_MISSING:{rel}")
            continue
        if not skill_path.is_file():
            errors.append(f"CANDIDATE_SKILL_MISSING:{rel}")
            continue
        data = skill_path.read_bytes()
        skills.append({"path": rel, "bytes": len(data),
                       "sha256": sha256_hex(data)})
    if errors:
        raise UALError("ENVELOPE_FREEZE_REFUSED", ";".join(errors[:4]))
    task_path = project / "task.json"
    ledger = validation.Ledger(project, task)
    ledger_bytes = ledger.path.read_bytes()
    close = lifecycle.closed_record(project, task)
    refresh_record = lifecycle.latest_record(project, task_id, "refresh")
    reportcheck = lifecycle.latest_record(project, task_id, "reportcheck")
    receipts = list((close or {}).get("observer_receipts") or [])
    from . import attempts as _attempts
    attempt_payload = _attempts.current_payload(project, task_id)
    attempt_json_path = (_attempts.attempt_dir(project, task_id,
                                               attempt_payload["attempt"])
                         / "attempt.json")
    attempt_binding = {
        "attempt": attempt_payload["attempt"],
        "authority_sha256": attempt_payload.get("authority_sha256"),
        "attempt_json_sha256": sha256_hex(attempt_json_path.read_bytes()),
    }
    footprint = derive_candidate_footprint(task)
    records_dir = _attempts.current_dir(project, task_id) / "records"
    validation_logs = _bind_validation_logs(project, task, ledger)
    capture_closure = _bind_capture_closure(project, task)
    from .claims import utc_now_iso
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "task": task_id,
        "created_at": utc_now_iso(),
        "guarantee_level": "LOCAL_INTEGRITY",
        "task_file": {"path": "task.json",
                      "bytes": task_path.stat().st_size,
                      "sha256": sha256_hex(task_path.read_bytes())},
        "members": members,
        "skills": skills,
        "candidate_sha256": _member_digest_of(members),
        "footprint": footprint,
        "validation": {
            "evidence_state": validation.evidence_state(ledger),
            "ledger_seq": ledger.last_seq(),
            "declared_commands": [c["argv"]
                                  for c in validation_commands(task)],
        },
        "validation_logs": validation_logs,
        "capture_closure": capture_closure,
        "close_chain": {
            "ledger_sha256": sha256_hex(ledger_bytes),
            "close": _record_digest(records_dir, close),
            "refresh": _record_digest(records_dir, refresh_record),
            "reportcheck": _record_digest(records_dir, reportcheck),
        },
        "observer_receipts": receipts,
        "attempt": attempt_binding,
        "git": {"claimed": False,
                "note": "no VCS metadata consulted; explicit member "
                        "inventory only; git absence does not prove a "
                        "clean diff"},
    }
    directory = _envelope_dir(project, task_id)
    sequence = next_sequence(directory, "envelope_", ".json",
                             max_files=64)
    path = directory / f"envelope_{sequence:04d}.json"
    exclusive_write_json(path, envelope, max_bytes=ENVELOPE_MAX_BYTES)
    return {"ok": True, "path": str(path),
            "sha256": sha256_hex(path.read_bytes()),
            "members": members,
            "candidate_sha256": envelope["candidate_sha256"]}


def _member_digest_of(members) -> str:
    from .hashing import member_digest
    return member_digest([(m["path"], m["sha256"]) for m in members]) or ""


def _bind_validation_logs(project: Path, task: dict, ledger) -> list:
    """Bind every counted occurrence's raw validation log bytes at
    freeze; re-verified at review and acceptance (PB10)."""
    from .runner import load_sidecar, SIDECAR_MAX_BYTES
    bound = []
    for record in ledger.occurrences:
        run_id = record.get("run_id")
        sidecar = load_sidecar(project, run_id)
        if sidecar is None:
            raise UALError("CAPTURE_CLOSURE_MEMBER_MISSING",
                           f"run {run_id}")
        log_rel = (sidecar.get("log") or {}).get("path")
        log_path = Path(project) / str(log_rel or "")
        if not log_path.is_file():
            raise UALError("CAPTURE_CLOSURE_MEMBER_MISSING", str(log_rel))
        data = log_path.read_bytes()
        bound.append({"run_id": run_id, "path": log_rel,
                      "bytes": len(data), "sha256": sha256_hex(data)})
    return bound


def _bind_capture_closure(project: Path, task: dict) -> list:
    """Bind the declared command scripts/fixtures that the validation
    evidence depends on but the candidate allowlist may not cover."""
    from .paths import inside_rel
    closure = {}
    allow_set = set(allowlist(task))
    for command in validation_commands(task):
        for token in command.get("argv") or []:
            try:
                path = resolve_inside(project, token, label="CLOSURE")
            except UALError:
                continue
            if not path.is_file():
                continue
            rel = inside_rel(project, path)
            if rel in allow_set or rel in closure:
                continue
            data = path.read_bytes()
            closure[rel] = {"path": rel, "bytes": len(data),
                            "sha256": sha256_hex(data)}
    return sorted(closure.values(), key=lambda item: item["path"])


def _record_digest(records_dir: Path, record) -> dict | None:
    if record is None:
        return None
    for entry in sorted(records_dir.iterdir()):
        if not entry.name.endswith(".json"):
            continue
        try:
            if load_json(entry, max_bytes=RECORD_MAX) == record:
                return {"path": entry.name,
                        "sha256": sha256_hex(entry.read_bytes())}
        except (UALError, OSError):
            continue
    return None


RECORD_MAX = lifecycle.RECORD_MAX_BYTES


def _receipt_digests(project: Path, task_id: str) -> list:
    receipts_dir = task_dir(project, task_id) / "receipts"
    digests = []
    if receipts_dir.is_dir():
        for entry in sorted(receipts_dir.iterdir()):
            if entry.is_file() and entry.name.endswith(".json"):
                digests.append({"path": entry.name,
                                "sha256": sha256_hex(entry.read_bytes())})
    return digests


def verify_envelope(project: Path, task: dict) -> dict:
    task_id = task["id"]
    loaded = latest_envelope(project, task_id)
    if loaded is None:
        raise UALError("ENVELOPE_MISSING", task_id)
    path, envelope = loaded
    errors = []
    if envelope.get("task") != task_id:
        errors.append("ENVELOPE_TASK_MISMATCH")
    task_path = Path(project) / "task.json"
    bound_task = envelope.get("task_file") or {}
    if bound_task.get("sha256") != sha256_hex(task_path.read_bytes()):
        errors.append("TASK_CONTRACT_DRIFT")
    for member in envelope.get("members") or []:
        rel = member.get("path")
        try:
            member_path = resolve_inside(project, rel, label="MEMBER")
        except UALError:
            errors.append(f"CANDIDATE_MEMBER_ESCAPE:{rel}")
            continue
        if not member_path.is_file():
            errors.append(f"CANDIDATE_MEMBER_DRIFT:{rel}")
            continue
        data = member_path.read_bytes()
        if member.get("sha256") != sha256_hex(data) or \
                member.get("bytes") != len(data):
            errors.append(f"CANDIDATE_MEMBER_DRIFT:{rel}")
    for skill in envelope.get("skills") or []:
        rel = skill.get("path")
        skill_path = Path(project) / rel
        if not skill_path.is_file() or \
                skill.get("sha256") != sha256_hex(skill_path.read_bytes()):
            errors.append(f"CANDIDATE_SKILL_DRIFT:{rel}")
    ledger = validation.Ledger(project, task)
    if envelope.get("close_chain", {}).get("ledger_sha256") != \
            sha256_hex(ledger.path.read_bytes()):
        errors.append("VALIDATION_LEDGER_DRIFT")
    for record_kind in ("close", "refresh", "reportcheck"):
        bound = envelope.get("close_chain", {}).get(record_kind)
        if bound is None:
            continue
        current = lifecycle.latest_record(project, task_id, record_kind)
        from .attempts import current_dir
        records_dir = current_dir(project, task_id) / "records"
        current_digest = _record_digest(records_dir, current)
        if current_digest is None or \
                current_digest["sha256"] != bound.get("sha256"):
            errors.append(f"CLOSE_CHAIN_DRIFT:{record_kind}")
    from .attempts import current_dir as _cur
    attempt_dir_path = _cur(project, task_id)
    for bound in envelope.get("observer_receipts") or []:
        receipt_path = attempt_dir_path / "receipts" / \
            bound.get("path", "")
        if not receipt_path.is_file() or bound.get("sha256") != \
                sha256_hex(receipt_path.read_bytes()):
            errors.append("OBSERVER_RECEIPT_DRIFT:" + bound.get("path", ""))
    for bound in envelope.get("validation_logs") or []:
        log_path = Path(project) / str(bound.get("path") or "")
        if not log_path.is_file() or bound.get("sha256") != \
                sha256_hex(log_path.read_bytes()) or \
                bound.get("bytes") != log_path.stat().st_size:
            errors.append("VALIDATION_LOG_DRIFT:" + str(bound.get("path")))
    for bound in envelope.get("capture_closure") or []:
        closure_path = Path(project) / str(bound.get("path") or "")
        if not closure_path.is_file() or bound.get("sha256") != \
                sha256_hex(closure_path.read_bytes()):
            errors.append("CAPTURE_CLOSURE_DRIFT:" + str(bound.get("path")))
    attempt_binding = envelope.get("attempt") or {}
    if attempt_binding:
        attempt_json = attempt_dir_path / "attempt.json"
        if not attempt_json.is_file() or \
                attempt_binding.get("attempt_json_sha256") != \
                sha256_hex(attempt_json.read_bytes()):
            errors.append("ATTEMPT_BINDING_DRIFT")
    if errors:
        raise UALError("ENVELOPE_VERIFY_REFUSED", ";".join(errors[:4]))
    return {"ok": True, "path": str(path),
            "candidate_sha256": envelope["candidate_sha256"]}


def latest_seal(project: Path, task_id: str):
    directory = _envelope_dir(project, task_id)
    entries = sorted(p for p in directory.iterdir()
                     if p.name.startswith("seal_"))
    if not entries:
        return None
    path = entries[-1]
    return path, load_json(path, max_bytes=ENVELOPE_MAX_BYTES)


def write_review_seal(project: Path, task: dict, review_rel: str,
                      verdict: str, reviewer_session: str) -> dict:
    task_id = task["id"]
    if not reviewer_session:
        raise UALError("REVIEWER_SESSION_REQUIRED",
                       "review seals bind a configured REVIEWER session")
    session = authority.require_session_role(project, reviewer_session,
                                             "REVIEWER")
    state = lifecycle.load_state(project, task_id) or {}
    engineer_session = state.get("engineer_session")
    if engineer_session and engineer_session == reviewer_session:
        raise UALError("REVIEWER_SESSION_NOT_DISTINCT",
                       str(engineer_session))
    verify_envelope(project, task)
    if verdict not in ("PASS", "FAIL"):
        raise UALError("SEAL_VERDICT_INVALID", verdict)
    review_path = resolve_inside(project, review_rel, label="REVIEW")
    if not review_path.is_file():
        raise UALError("REVIEW_ARTIFACT_UNREADABLE", review_rel)
    review_bytes = review_path.read_bytes()
    loaded = latest_envelope(project, task_id)
    envelope_path, envelope = loaded
    envelope_bytes = envelope_path.read_bytes()
    if verdict == "PASS":
        text = review_bytes.decode("utf-8")
        refusals = reviewgate.validate_review(text, project, task)
        if "FAIL" in reviewgate.review_verdicts(text):
            refusals.append("REVIEW_TWO_PASS_FAIL_WITH_ACCEPTING_VERDICT")
        binding = reviewgate.envelope_binding(text)
        if binding is None:
            refusals.append(
                "REVIEW_PROOF_ENVELOPE_UNBOUND:an accepting review must "
                "bind the current frozen envelope digest")
        elif binding != sha256_hex(envelope_bytes):
            refusals.append(
                f"REVIEW_PROOF_ENVELOPE_MISMATCH:proof binds {binding}, "
                f"current envelope is "
                f"{sha256_hex(envelope_bytes)}")
        if refusals:
            raise UALError("REVIEW_GATE_REFUSED", ";".join(refusals[:4]))
    from .claims import utc_now_iso
    directory = _envelope_dir(project, task_id)
    sequence = next_sequence(directory, "seal_", ".json", max_files=64)
    seal = {
        "schema": SEAL_SCHEMA,
        "task": task_id,
        "verdict": verdict,
        "reviewer_session": reviewer_session,
        "reviewer_actor": session.get("actor"),
        "candidate_envelope": {"path": envelope_path.name,
                               "bytes": len(envelope_bytes),
                               "sha256": sha256_hex(envelope_bytes)},
        "review": {"path": review_rel, "bytes": len(review_bytes),
                   "sha256": sha256_hex(review_bytes)},
        "sealed_at": utc_now_iso(),
    }
    path = directory / f"seal_{sequence:04d}.json"
    exclusive_write_json(path, seal, max_bytes=ENVELOPE_MAX_BYTES)
    if verdict == "PASS":
        state = lifecycle.ensure_state(project, task_id)
        if state["status"] not in ("PENDING_CODEX_REVIEW",
                                   "REVIEW_PASSED"):
            lifecycle.set_status(project, task_id, "PENDING_CODEX_REVIEW",
                                 _internal=True)
    else:
        state = lifecycle.ensure_state(project, task_id)
        if state["status"] != "FIX_REQUIRED":
            lifecycle.set_status(project, task_id, "FIX_REQUIRED",
                                 _internal=True)
    return {"ok": True, "verdict": verdict, "path": str(path)}


def latest_audit_record(project: Path, task_id: str):
    from .attempts import current_seq, attempt_dir
    seq = current_seq(project, task_id)
    if seq is None:
        return None
    directory = attempt_dir(project, task_id, seq) / "audit" / "records"
    if not directory.is_dir():
        return None
    entries = sorted(p for p in directory.iterdir()
                     if p.name.startswith("audit_"))
    if not entries:
        return None
    return load_json(entries[-1], max_bytes=ENVELOPE_MAX_BYTES)


def accept(project: Path, task: dict, actor: str, decision: str,
           review_rel: str) -> dict:
    task_id = task["id"]
    from . import attempts as _attempts
    attempt_payload = _attempts.current_payload(project, task_id)
    config = authority.require_config(project)
    if authority.config_digest(project) != \
            attempt_payload.get("authority_sha256"):
        raise UALError("AUTHORITY_CONFIG_DRIFT",
                       "the trusted authority config changed after the "
                       "attempt opened")
    if not authority.is_configured_owner(project, actor):
        raise UALError("ACCEPTANCE_ACTOR_NOT_OWNER", actor)
    if decision not in ("ACCEPTED", "REJECTED"):
        raise UALError("ACCEPTANCE_DECISION_INVALID", decision)
    verify_envelope(project, task)
    seal = latest_seal(project, task_id)
    if seal is None:
        raise UALError("REVIEW_SEAL_MISSING", task_id)
    seal_path, seal_payload = seal
    if seal_payload.get("verdict") != "PASS":
        raise UALError("REVIEW_SEAL_NOT_PASS",
                       str(seal_payload.get("verdict")))
    envelope_path, envelope = latest_envelope(project, task_id)
    envelope_bytes = envelope_path.read_bytes()
    if (seal_payload.get("candidate_envelope") or {}).get("sha256") != \
            sha256_hex(envelope_bytes):
        raise UALError("REVIEW_SEAL_ENVELOPE_MISMATCH", task_id)
    review_path = resolve_inside(project, review_rel, label="REVIEW")
    if not review_path.is_file():
        raise UALError("REVIEW_ARTIFACT_UNREADABLE", review_rel)
    review_bytes = review_path.read_bytes()
    if (seal_payload.get("review") or {}).get("sha256") != \
            sha256_hex(review_bytes):
        raise UALError("REVIEW_SEAL_ARTIFACT_DRIFT", review_rel)
    text = review_bytes.decode("utf-8")
    refusals = reviewgate.validate_review(text, project, task)
    if refusals:
        raise UALError("ACCEPTANCE_REVIEW_REFUSED",
                       ";".join(refusals[:4]))
    if (task.get("audit") or {}).get("required"):
        from . import audit as audit_mod
        audit_mod.validate_record_for_acceptance(
            project, task, latest_audit_record(project, task_id),
            sha256_hex(envelope_bytes))
    from .claims import utc_now_iso
    directory = _envelope_dir(project, task_id)
    sequence = next_sequence(directory, "acceptance_", ".json",
                             max_files=64)
    record = {
        "schema": ACCEPTANCE_SCHEMA,
        "task": task_id,
        "actor": actor,
        "decision": decision,
        "candidate_envelope": {"bytes": len(envelope_bytes),
                               "sha256": sha256_hex(envelope_bytes)},
        "candidate_sha256": envelope["candidate_sha256"],
        "review_seal": {"path": seal_path.name,
                        "sha256": sha256_hex(seal_path.read_bytes())},
        "recorded_at": utc_now_iso(),
    }
    path = directory / f"acceptance_{sequence:04d}.json"
    exclusive_write_json(path, record, max_bytes=ENVELOPE_MAX_BYTES)
    lifecycle.set_status(project, task_id, "REVIEW_PASSED", _internal=True)
    lifecycle.set_status(project, task_id, decision, _internal=True)
    return {"ok": True, "decision": decision, "actor": actor,
            "path": str(path),
            "candidate_sha256": envelope["candidate_sha256"]}


def acceptance_record(project: Path, task_id: str):
    from .attempts import attempts_root
    root = attempts_root(project, task_id)
    if not root.is_dir():
        return None
    for attempt_dir_path in sorted(root.iterdir(), reverse=True):
        directory = attempt_dir_path / "envelope"
        if not directory.is_dir():
            continue
        entries = sorted(p for p in directory.iterdir()
                         if p.name.startswith("acceptance_"))
        if entries:
            return load_json(entries[-1], max_bytes=ENVELOPE_MAX_BYTES)
    return None

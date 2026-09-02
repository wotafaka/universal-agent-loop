"""Validation ledger: exact occurrence fence, fingerprints, capture binding.

Every counted validation occurrence must be ingested through the CLI from
a real finished run sidecar bound by digest; hand-authored records can
never count. The declared order, duplicate counts and RED/GREEN expected
outcomes are enforced exactly: an unexpected extra RED returns the task
to the architect instead of creating a retry cap. The candidate capture
set excludes exactly the implementation report, which is finalized after
the captured GREEN but still bound by the final envelope.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

from .errors import UALError
from .hashing import (atomic_write_json, canonical_json, load_json,
                      member_digest, sha256_hex)
from .paths import resolve_inside, run_dir, task_dir
from .runner import SIDECAR_MAX_BYTES, capture_digest, env_policy_identity
from .taskfile import (allowlist, capture_exclusions, declared_seed,
                       validation_commands)

LEDGER_SCHEMA = "ual-validation-ledger/1"
LEDGER_MAX_BYTES = 1024 * 1024
FINGERPRINT_FIELDS = ("candidate_digest", "command_argv",
                      "environment_policy_identity", "platform_identity",
                      "declared_seed")


class Ledger:
    def __init__(self, project: Path, task: dict, attempt_seq: int | None = None):
        self.project = Path(project)
        self.task = task
        from . import attempts as _attempts
        seq = attempt_seq
        if seq is None:
            seq = _attempts.current_seq(self.project, task["id"])
        if seq is None:
            seq = _attempts.ensure_current(self.project, task)
        self.attempt_seq = seq
        self.path = (_attempts.attempt_dir(self.project, task["id"], seq) /
                     "ledger.json")
        if self.path.is_file():
            payload = load_json(self.path, max_bytes=LEDGER_MAX_BYTES)
            if not isinstance(payload, dict) or \
                    payload.get("schema") != LEDGER_SCHEMA:
                raise UALError("LEDGER_MALFORMED", str(self.path))
        else:
            payload = {"schema": LEDGER_SCHEMA, "task": task["id"],
                       "attempt": seq,
                       "occurrences": [], "rejected_conflicts": [],
                       "seq": 0}
        self.payload = payload

    def save(self) -> None:
        atomic_write_json(self.path, self.payload,
                          max_bytes=LEDGER_MAX_BYTES)

    def save(self) -> None:
        atomic_write_json(self.path, self.payload,
                          max_bytes=LEDGER_MAX_BYTES)

    @property
    def occurrences(self) -> list:
        return self.payload["occurrences"]

    def records_for(self, ordinal: int) -> list:
        return [o for o in self.occurrences if o["ordinal"] == ordinal]

    def last_seq(self) -> int:
        return self.payload.get("seq", 0)


def platform_identity() -> str:
    return (f"{sys.platform}|{platform.python_implementation()}-"
            f"{platform.python_version()}")


def build_fingerprint(candidate_digest, command_argv, env_identity,
                      seed) -> dict:
    if isinstance(command_argv, list):
        command_argv = canonical_json(command_argv)
    return {
        "candidate_digest": candidate_digest,
        "command_argv": command_argv,
        "environment_policy_identity": env_identity,
        "platform_identity": platform_identity(),
        "declared_seed": seed,
    }


def fingerprint_is_complete(fingerprint: dict) -> bool:
    return all(isinstance(fingerprint.get(f), str) and fingerprint.get(f)
               for f in FINGERPRINT_FIELDS)


def classify_pair(fingerprint_a, outcome_a, fingerprint_b, outcome_b) -> str:
    if not (fingerprint_is_complete(fingerprint_a)
            and fingerprint_is_complete(fingerprint_b)):
        return "NOT_COMPARABLE"
    if fingerprint_a == fingerprint_b:
        return "CONSISTENT" if outcome_a == outcome_b else "NONDETERMINISTIC"
    if fingerprint_a["candidate_digest"] != fingerprint_b["candidate_digest"]:
        return "CHANGED_CANDIDATE"
    return "NOT_COMPARABLE"


def record_occurrence(project: Path, task: dict, run_id: str, ordinal: int,
                      seed_override: str | None = None) -> dict:
    commands = validation_commands(task)
    if not isinstance(ordinal, int) or ordinal < 1 or ordinal > len(commands):
        raise UALError("VALIDATION_ORDINAL_INVALID", str(ordinal))
    command = commands[ordinal - 1]
    sidecar_path = run_dir(project, run_id) / "run.json"
    if not sidecar_path.is_file():
        raise UALError("VALIDATION_RUN_SIDECAR_MISSING", run_id)
    sidecar_bytes = sidecar_path.read_bytes()
    sidecar = load_json(sidecar_path, max_bytes=SIDECAR_MAX_BYTES)
    from .lifecycle import closed_record
    if closed_record(project, task) is not None:
        raise UALError("POST_CLOSE_RECORD", run_id)
    log = sidecar.get("log") or {}
    if log.get("truncated") is not False or sidecar.get("overflow"):
        raise UALError("VALIDATION_OUTPUT_TRUNCATION_INVALID",
                       f"run={run_id} logged output overflow is never "
                       f"counted evidence")
    if sidecar.get("task") != task["id"] or \
            sidecar.get("purpose") != "VALIDATION":
        raise UALError("VALIDATION_RUN_MISMATCH", run_id)
    if sidecar.get("argv") != command["argv"]:
        raise UALError("VALIDATION_ARGV_MISMATCH", run_id)
    if str(sidecar.get("status")) != "FINISHED":
        raise UALError("VALIDATION_RUN_NOT_FINISHED", run_id)
    seed = seed_override if seed_override is not None else declared_seed(task)
    if sidecar.get("seed") != seed:
        raise UALError("VALIDATION_SEED_MISMATCH",
                       f"run={sidecar.get('seed')} declared={seed}")
    ledger = Ledger(project, task)
    prior = ledger.records_for(ordinal)
    index = len(prior)
    expected = list(command["expected_outcomes"])
    if index >= len(expected):
        raise UALError("VALIDATION_OCCURRENCE_EXTRA",
                       f"ordinal={ordinal} occurrence={index + 1}")
    outcome = "RED" if sidecar.get("exit_code") != 0 else "GREEN"
    if outcome != expected[index]:
        raise UALError("VALIDATION_UNEXPECTED_OUTCOME",
                       f"ordinal={ordinal} expected={expected[index]} "
                       f"observed={outcome}")
    earlier_ordinal_commands = {c["ordinal"]: c for c in commands}
    for other in range(1, ordinal):
        if len(ledger.records_for(other)) < len(
                earlier_ordinal_commands[other]["expected_outcomes"]):
            raise UALError("VALIDATION_OUT_OF_ORDER",
                           f"ordinal={ordinal} follows incomplete "
                           f"ordinal={other}")
    fingerprint = build_fingerprint(
        (sidecar.get("capture") or {}).get("sha256"),
        sidecar.get("argv"),
        sidecar.get("env_policy_sha256"),
        sidecar.get("seed"))
    for record in ledger.occurrences:
        classification = classify_pair(record["fingerprint"],
                                       record["outcome"],
                                       fingerprint, outcome)
        if classification == "NONDETERMINISTIC":
            ledger.payload["rejected_conflicts"].append({
                "run_id": run_id,
                "against_record_seq": record["seq"],
            })
            ledger.save()
            raise UALError("VALIDATION_NONDETERMINISTIC_CONFLICT",
                           f"ordinal={ordinal}")
    for conflict in ledger.payload["rejected_conflicts"]:
        pass
    sidecar_rel = str(sidecar.get("log") or {}).strip()
    record = {
        "seq": ledger.last_seq() + 1,
        "ordinal": ordinal,
        "run_id": run_id,
        "sidecar_binding": {"bytes": len(sidecar_bytes),
                            "sha256": sha256_hex(sidecar_bytes)},
        "argv": list(command["argv"]),
        "exit_code": sidecar.get("exit_code"),
        "outcome": outcome,
        "capture_sha256": (sidecar.get("capture") or {}).get("sha256"),
        "fingerprint": fingerprint,
    }
    ledger.occurrences.append(record)
    ledger.payload["seq"] = record["seq"]
    ledger.save()
    return {"ok": True, "ordinal": ordinal, "outcome": outcome,
            "run_id": run_id,
            "capture_sha256": record["capture_sha256"]}


def evidence_state(ledger: Ledger) -> str:
    invalid = 0
    unproven = 0
    for record in ledger.occurrences:
        if not record.get("capture_sha256"):
            unproven += 1
    conflicts = len(ledger.payload.get("rejected_conflicts") or [])
    count = len(ledger.occurrences)
    if count == 0:
        return "MISSING"
    if invalid:
        return "INVALIDATED"
    if conflicts:
        return "NONDETERMINISTIC"
    if unproven:
        return "COLLECTED"
    return "VERIFIED"


def close_time_errors(project: Path, task: dict, ledger: Ledger) -> list:
    errors: list = []
    for record in ledger.occurrences:
        sidecar_path = run_dir(project, record["run_id"]) / "run.json"
        if not sidecar_path.is_file():
            errors.append("VALIDATION_RUN_SIDECAR_MISSING:"
                          + record["run_id"])
            continue
        data = sidecar_path.read_bytes()
        binding = record.get("sidecar_binding") or {}
        if binding.get("sha256") != sha256_hex(data) or \
                binding.get("bytes") != len(data):
            errors.append("VALIDATION_RUN_SIDECAR_DRIFT:" + record["run_id"])
    if ledger.payload.get("rejected_conflicts"):
        errors.append("VALIDATION_NONDETERMINISTIC_CONFLICT:"
                      f"{len(ledger.payload['rejected_conflicts'])}")
    for ordinal, command in enumerate(validation_commands(task), start=1):
        records = ledger.records_for(ordinal)
        expected = list(command["expected_outcomes"])
        if len(records) != len(expected):
            errors.append("VALIDATION_FENCE_INCOMPLETE:"
                          f"ordinal={ordinal} "
                          f"expected={len(expected)} actual={len(records)}")
            continue
        if records[-1]["outcome"] != "GREEN":
            errors.append("VALIDATION_FINAL_NOT_GREEN:"
                          f"ordinal={ordinal}")
    current = capture_digest(project, task)
    for command in validation_commands(task):
        records = ledger.records_for(command["ordinal"])
        if not records:
            continue
        final = records[-1]
        if final.get("capture_sha256") and \
                final["capture_sha256"] != current:
            errors.append("VALIDATION_FINAL_CAPTURE_MEMBER_MISMATCH:"
                          f"ordinal={command['ordinal']}")
    return errors

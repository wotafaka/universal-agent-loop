"""Bounded measured delivery feedback and efficiency reports.

One current efficiency report per task: measured wall time and measured
context-restoration time are reported as measured; token and cost totals
stay UNKNOWN unless actually recorded, and no saving is ever inferred
from byte counts. The example calibrated recommendation (restoration at
least 300 s and at least 25 percent of completed wall time) uses
measured evidence only. A successful completed delivery is separate from
merely terminal writers: a terminal nonzero writer never produces a
review-ready success summary, and delivery requires the explicit
acceptance record.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import context, envelope, lifecycle
from .errors import UALError
from .hashing import atomic_write_json, load_json
from .paths import run_dir, task_dir
from .runner import SIDECAR_MAX_BYTES

RESTORATION_THRESHOLD_S = 300.0
WALL_SHARE_THRESHOLD = 0.25
REPORT_MAX_BYTES = 128 * 1024
TIMINGS_MAX_LINES = 128
USAGE_DIR_MAX_FILES = 4096


def _task_runs(project: Path, task_id: str) -> tuple:
    """Returns (runs, invalid_sidecar_count). A malformed or unknown
    sidecar is never silently skipped into GREEN statistics."""
    from .errors import UALError as _E
    from .hashing import load_json as _lj
    runs_root = Path(project) / ".agent-loop" / "runs"
    runs = []
    invalid = 0
    if not runs_root.is_dir():
        return runs, invalid
    for entry in sorted(runs_root.iterdir()):
        sidecar_path = entry / "run.json"
        if not sidecar_path.is_file():
            continue
        try:
            sidecar = _lj(sidecar_path, max_bytes=SIDECAR_MAX_BYTES)
        except _E:
            invalid += 1
            continue
        if isinstance(sidecar, dict) and sidecar.get("task") == task_id:
            runs.append(sidecar)
        else:
            invalid += 1
    return runs, invalid


def _duration(sidecar: dict):
    try:
        start = datetime.fromisoformat(sidecar["started_at"])
        finish = datetime.fromisoformat(sidecar["finished_at"])
        return (finish - start).total_seconds()
    except (KeyError, TypeError, ValueError):
        return None


def _usage_receipts(project: Path, task_id: str) -> list:
    from .attempts import attempts_root
    receipts = []
    root = attempts_root(project, task_id)
    if not root.is_dir():
        return receipts
    for attempt_path in sorted(root.iterdir()):
        usage_dir = attempt_path / "usage"
        if not usage_dir.is_dir():
            continue
        for entry in sorted(usage_dir.iterdir()):
            if not entry.name.startswith("usage_"):
                continue
            try:
                record = load_json(entry, max_bytes=64 * 1024)
            except UALError:
                continue
            if isinstance(record, dict) and \
                    record.get("schema") == "ual-usage-receipt/1":
                receipts.append(record)
    return receipts


def record_usage_receipt(project: Path, task: dict, run_id: str,
                         usage: dict) -> dict:
    """Emit one neutral factual usage receipt bound to a real run. Any
    field the provider did not report stays UNKNOWN; nothing is ever
    inferred from byte counts or timings."""
    from .runner import load_sidecar
    from . import attempts
    from .attempts import current_dir
    from .hashing import exclusive_write_json, next_sequence
    attempts.ensure_current(project, task)
    sidecar = load_sidecar(project, run_id)
    if sidecar is None or sidecar.get("task") != task["id"]:
        raise UALError("USAGE_RUN_UNBOUND", run_id)
    if sidecar.get("status") != "FINISHED":
        raise UALError("USAGE_RUN_NOT_FINISHED", run_id)
    tokens = usage.get("tokens")
    cost = usage.get("cost")
    if isinstance(tokens, (int, float)) and not isinstance(tokens, bool) \
            and tokens < 0:
        raise UALError("USAGE_VALUE_INVALID", f"tokens={tokens!r}")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool) \
            and cost < 0:
        raise UALError("USAGE_VALUE_INVALID", f"cost={cost!r}")
    model_observed = usage.get("model") or usage.get("model_observed")
    receipt = {
        "schema": "ual-usage-receipt/1",
        "task": task["id"],
        "run_id": run_id,
        "tokens": tokens if isinstance(tokens, int) and
        not isinstance(tokens, bool) else "UNKNOWN",
        "cost": cost if isinstance(cost, (int, float)) and
        not isinstance(cost, bool) else "UNKNOWN",
        "model_observed": model_observed if isinstance(model_observed, str)
        and model_observed.strip() else "UNKNOWN",
        "recorded_at": claims_utc_now(),
    }
    directory = current_dir(project, task["id"]) / "usage"
    directory.mkdir(parents=True, exist_ok=True)
    sequence = next_sequence(directory, "usage_", ".json",
                             max_files=USAGE_DIR_MAX_FILES)
    path = directory / f"usage_{sequence:08d}.json"
    exclusive_write_json(path, receipt, max_bytes=64 * 1024)
    return {"ok": True, "path": str(path), "tokens": receipt["tokens"],
            "cost": receipt["cost"],
            "model_observed": receipt["model_observed"]}


def claims_utc_now() -> str:
    from .claims import utc_now_iso
    return utc_now_iso()


def _timings_entries(project: Path, task_id: str) -> list:
    path = task_dir(project, task_id) / "timings.jsonl"
    entries = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
    return entries


def record_checkpoint(project: Path, task: dict, run_id: str, kind: str,
                      seconds: float) -> dict:
    """Ingest one run-bound measured checkpoint. Restoration and
    first-write durations are only ever measured here, bound to a real
    finished run; anything unmeasured stays UNKNOWN."""
    from .runner import load_sidecar
    if kind not in ("restoration", "first_write"):
        raise UALError("CHECKPOINT_KIND_INVALID", kind)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) \
            or seconds < 0:
        raise UALError("CHECKPOINT_SECONDS_INVALID", repr(seconds))
    sidecar = load_sidecar(project, run_id)
    if sidecar is None or sidecar.get("task") != task["id"]:
        raise UALError("CHECKPOINT_RUN_UNBOUND", run_id)
    if sidecar.get("status") != "FINISHED":
        raise UALError("CHECKPOINT_RUN_NOT_FINISHED", run_id)
    from .claims import utc_now_iso
    path = task_dir(project, task["id"]) / "timings.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [l for l in path.read_text(encoding="utf-8").splitlines()
             if l.strip()] if path.is_file() else []
    lines.append(json.dumps({
        "kind": "checkpoint", "checkpoint_kind": kind,
        "run_id": run_id, "seconds": round(float(seconds), 6),
        "at": utc_now_iso()}, sort_keys=True))
    lines = lines[-TIMINGS_MAX_LINES:]
    from .hashing import atomic_write_bytes
    atomic_write_bytes(path, ("\n".join(lines) + "\n").encode("utf-8"),
                       max_bytes=64 * 1024)
    return {"ok": True, "kind": kind, "seconds": round(float(seconds), 6)}


_DISPOSITION_RE = None


def parse_dispositions(project: Path, task: dict, review_rel: str) -> dict:
    """Parse ``## Efficiency disposition`` lines into pending decisions
    consumed by the next attempt: ``- <ID>: APPLY_NEXT_TASK|"
    "NO_ACTION_WITH_REASON — reason``."""
    review_path = Path(project) / review_rel
    if not review_path.is_file():
        raise UALError("DISPOSITION_SOURCE_MISSING", review_rel)
    text = review_path.read_text(encoding="utf-8")
    marker = "## Efficiency disposition"
    if marker not in text:
        raise UALError("DISPOSITION_SECTION_MISSING", review_rel)
    section = text.split(marker, 1)[1]
    nxt = section.find("\n## ")
    section = section[:nxt] if nxt >= 0 else section
    import re
    line_re = re.compile(
        r"^- ([A-Za-z0-9._-]+): (APPLY_NEXT_TASK|NO_ACTION_WITH_REASON)"
        r" — (.+?)\s*$")
    pending = []
    seen = set()
    for line in section.splitlines():
        match = line_re.match(line.strip())
        if match is None:
            continue
        rid, decision, reason = match.groups()
        if rid in seen:
            raise UALError("EFFICIENCY_DISPOSITION_DUPLICATE", rid)
        seen.add(rid)
        if not reason.strip():
            raise UALError("EFFICIENCY_DISPOSITION_REASON_EMPTY", rid)
        pending.append({"id": rid, "decision": decision,
                        "reason": reason.strip()})
    if not pending:
        raise UALError("EFFICIENCY_DISPOSITION_EMPTY", review_rel)
    state = lifecycle.ensure_state(project, task["id"])
    state["pending_efficiency"] = pending
    lifecycle.save_state(project, task["id"], state)
    return {"ok": True, "pending": pending}


def efficiency_report(project: Path, task: dict,
                      dispositions_rel: str | None = None) -> dict:
    task_id = task["id"]
    if dispositions_rel:
        return parse_dispositions(project, task, dispositions_rel)
    directory = task_dir(project, task_id) / "efficiency"
    json_path = directory / "report.json"
    generation = 1
    if json_path.is_file():
        previous = load_json(json_path, max_bytes=REPORT_MAX_BYTES)
        if isinstance(previous, dict):
            generation = int(previous.get("generation", 1)) + 1
    runs, invalid_sidecars = _task_runs(project, task_id)
    wall = 0.0
    measured_any = False
    for sidecar in runs:
        duration = _duration(sidecar)
        if duration is not None and duration >= 0:
            wall += duration
            measured_any = True
    entries = _timings_entries(project, task_id)
    context_verify_seconds = None
    restoration = "UNKNOWN"
    first_write = "UNKNOWN"
    for entry in entries:
        if entry.get("kind") == "context_verify":
            context_verify_seconds = entry.get("restoration_seconds",
                                               entry.get(
                                                   "context_verify_seconds"))
        elif entry.get("kind") == "checkpoint":
            value = entry.get("seconds")
            if entry.get("checkpoint_kind") == "restoration":
                restoration = value
            elif entry.get("checkpoint_kind") == "first_write":
                first_write = value
    recommendation = "NO_RECOMMENDATION"
    if not measured_any or restoration == "UNKNOWN":
        reason = "insufficient measured evidence (no run-bound checkpoint)"
    elif restoration >= RESTORATION_THRESHOLD_S and wall > 0 and \
            restoration >= WALL_SHARE_THRESHOLD * wall:
        recommendation = "RECOMMEND_COMPACT_CONTEXT"
        reason = ("measured restoration >= 300s and >= 25% of completed "
                  "wall time (example calibrated policy)")
    else:
        reason = "measured evidence below the example calibrated thresholds"
    usage_receipts = _usage_receipts(project, task_id)
    tokens_values = [r["tokens"] for r in usage_receipts
                     if isinstance(r.get("tokens"), int)]
    cost_values = [r["cost"] for r in usage_receipts
                   if isinstance(r.get("cost"), (int, float))]
    usage_tokens: object = sum(tokens_values) if tokens_values else "UNKNOWN"
    usage_cost: object = round(sum(cost_values), 6) if cost_values \
        else "UNKNOWN"
    accepted = envelope.acceptance_record(project, task_id)
    all_writers_terminal = all(
        s.get("status") == "FINISHED" for s in runs) if runs else False
    successful_delivery = bool(accepted) and \
        accepted.get("decision") == "ACCEPTED"
    payload = {
        "ok": True,
        "task": task_id,
        "generation": generation,
        "wall_seconds": round(wall, 3) if measured_any else None,
        "context_verify_seconds": context_verify_seconds,
        "restoration_seconds": restoration,
        "first_write_seconds": first_write,
        "run_count": len(runs),
        "invalid_sidecars": invalid_sidecars,
        "all_writers_terminal": all_writers_terminal and invalid_sidecars == 0,
        "successful_completed_delivery": successful_delivery,
        "review_ready": bool(accepted),
        "tokens_total": usage_tokens,
        "cost_total": usage_cost,
        "recommendation": recommendation,
        "recommendation_reason": reason,
        "thresholds": {"restoration_seconds": RESTORATION_THRESHOLD_S,
                       "wall_share": WALL_SHARE_THRESHOLD},
        "pending_efficiency": lifecycle.load_state(
            project, task_id).get("pending_efficiency") if
        lifecycle.load_state(project, task_id) else [],
        "note": "verify duration, agent restoration and first-write are "
                "different measured quantities; usage totals bind only to "
                "provider-reported receipts, else UNKNOWN",
    }
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(json_path, payload, max_bytes=REPORT_MAX_BYTES)
    atomic_write_json(directory / "report.md", {
        "note": "machine payload in report.json; see docs/CONTEXT.md"},
        max_bytes=REPORT_MAX_BYTES)
    return payload


def delivery_report(project: Path, task: dict) -> dict:
    task_id = task["id"]
    accepted = envelope.acceptance_record(project, task_id)
    if accepted is None:
        raise UALError("DELIVERY_NOT_PROVEN",
                       "no explicit acceptance record exists")
    if accepted.get("decision") != "ACCEPTED":
        raise UALError("DELIVERY_NOT_ACCEPTED",
                       f"decision={accepted.get('decision')}; only an "
                       f"ACCEPTED candidate may deliver")
    envelope.verify_envelope(project, task)
    runs, invalid_sidecars = _task_runs(project, task_id)
    terminal_nonzero = 0
    delivered_ack = False
    for sidecar in runs:
        if sidecar.get("status") == "FINISHED" and \
                sidecar.get("purpose") in ("ENGINEER", "OTHER") and \
                isinstance(sidecar.get("exit_code"), int) and \
                sidecar.get("exit_code") != 0:
            terminal_nonzero += 1
        if (sidecar.get("ack") or {}).get("state") == "PROVEN":
            delivered_ack = True
    payload = {
        "ok": True,
        "task": task_id,
        "delivered": True,
        "decision": accepted.get("decision"),
        "actor": accepted.get("actor"),
        "candidate_sha256": accepted.get("candidate_sha256"),
        "delivered_ack": delivered_ack,
        "terminal_nonzero_runs": terminal_nonzero,
        "invalid_sidecars": invalid_sidecars,
        "note": "terminal nonzero writers are terminal, not successful "
                "deliveries; delivered=true binds the explicit owner "
                "ACCEPTED record only",
    }
    return payload

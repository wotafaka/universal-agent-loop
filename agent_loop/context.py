"""Compact hash-linked context packs and measured verify timings.

The pack carries the complete task, the required skill bodies and a
hash index of the canonical originals; history stays on demand. Verifying
a pack measures an actual restoration duration that the efficiency
report later uses as measured evidence; token and cost totals are never
inferred and stay UNKNOWN unless actually recorded.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .errors import UALError
from .hashing import (atomic_write_bytes, exclusive_write_bytes, load_json,
                      sha256_hex)
from .paths import resolve_inside, task_dir

PACK_MAX_BYTES = 2 * 1024 * 1024
INDEX_MAX_BYTES = 256 * 1024
TIMINGS_MAX_LINES = 128


def mandatory_closure(project: Path, task: dict) -> list:
    """The one mandatory-context closure shared by startup packs and
    repair assembly: complete task, triggered skill bodies and the small
    canonical rules file when present."""
    members = [("task.json", "task")]
    for rel in task.get("required_skills") or []:
        members.append((rel, "skill"))
    rules = Path(project) / "AGENTS.md"
    if rules.is_file():
        members.append(("AGENTS.md", "rules"))
    return members


def _render_context_pack(task_id: str, members: list,
                         bodies: dict) -> bytes:
    """The one deterministic context-pack renderer, shared by build and
    verify so re-rendered expected bytes are comparable byte-for-byte."""
    lines = [
        f"# Context pack — {task_id}",
        "",
        "Compact derivative context. The stable common prefix is the",
        "complete triggered skill/rule instructions; the task material",
        "is the suffix. Canonical originals remain the authority; this",
        "pack is regenerated, never hand-edited into authority.",
        "",
    ]
    task_entry = None
    for member in members:
        if member["role"] == "task":
            task_entry = member
            continue
        body = bodies[member["path"]].rstrip("\n")
        lines += [f"## {member['role']}: {member['path']}", "", "```",
                  body, "```", ""]
    if task_entry:
        body = bodies[task_entry["path"]].rstrip("\n")
        lines += [f"## Task (delta suffix): {task_entry['path']}", "",
                  "```json", body, "```", ""]
    for member in members:
        lines.append(f"- `{member['path']}` ({member['role']}): sha256 "
                     f"`{member['sha256']}`, bytes {member['bytes']}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_pack(project: Path, task: dict) -> dict:
    task_id = task["id"]
    directory = task_dir(project, task_id)
    pack_path = directory / "context_pack.md"
    index_path = directory / "context_pack_index.json"
    if pack_path.is_file():
        _require_compaction_safety(project, task_id)
    closure = mandatory_closure(project, task)
    index_members = []
    bodies = {}
    for rel, role in closure:
        path = project / rel
        if not path.is_file():
            if role in ("task", "skill"):
                raise UALError("CONTEXT_SKILL_MISSING", rel)
            continue
        data = path.read_bytes()
        bodies[rel] = data.decode("utf-8")
        index_members.append({"path": rel, "role": role,
                              "bytes": len(data),
                              "sha256": sha256_hex(data)})
    pack_bytes = _render_context_pack(task_id, index_members, bodies)
    if pack_path.is_file():
        atomic_write_bytes(pack_path, pack_bytes, max_bytes=PACK_MAX_BYTES)
    else:
        exclusive_write_bytes(pack_path, pack_bytes,
                              max_bytes=PACK_MAX_BYTES)
    index = {"schema": "ual-context-index/1", "task": task_id,
             "members": index_members,
             "payload_sha256": sha256_hex(pack_bytes),
             "commands": [c.get("argv") for c in
                          (task.get("validation") or {}).get("commands") or []]}
    atomic_write_bytes(index_path, (
        json.dumps(index, indent=2, sort_keys=True)
        + "\n").encode("utf-8"), max_bytes=INDEX_MAX_BYTES)
    total = sum(m["bytes"] for m in index_members)
    pack_rel = pack_path.relative_to(Path(project).resolve(strict=False))
    return {"ok": True, "pack": pack_rel.as_posix(), "total_bytes": total,
            "members": index_members}


def _require_compaction_safety(project: Path, task_id: str) -> None:
    """Rebuilding an existing pack is context compaction: it may only
    run at a verified phase boundary, never in the middle of a
    mutation-heavy attempt."""
    from . import attempts
    seq = attempts.current_seq(project, task_id)
    if seq is None:
        return
    try:
        attempts.verify_checkpoint(project, {"id": task_id})
    except UALError as exc:
        raise UALError("CONTEXT_COMPACTION_UNSAFE",
                       f"{exc.code}: save and verify a phase-boundary "
                       f"checkpoint before compaction")


def retrieve(project: Path, task: dict, need: str, run_id: str) -> dict:
    """Progressive bounded evidence retrieval: digest-bound spans from
    the bound run's raw log matching the need. Retrieval stops when the
    evidence fingerprint is unchanged since the previous request — a
    substantive stop, never a hard cycle cap."""
    from .runner import load_sidecar
    from .attempts import current_seq
    from .paths import state_root
    sidecar = load_sidecar(project, run_id)
    if sidecar is None or sidecar.get("task") != task["id"]:
        raise UALError("RETRIEVAL_RUN_UNBOUND", run_id)
    log_rel = (sidecar.get("log") or {}).get("path")
    log_path = project / str(log_rel or "")
    if not log_path.is_file():
        raise UALError("RETRIEVAL_LOG_MISSING", str(log_rel))
    tokens = [t for t in (need or "").split() if t.strip()]
    if not tokens:
        raise UALError("RETRIEVAL_NEED_EMPTY", str(need))
    lines = log_path.read_text(encoding="utf-8",
                               errors="replace").splitlines()
    lowered = [line.lower() for line in lines]
    spans = []
    start = None
    for index, line in enumerate(lowered, start=1):
        hit = any(token.lower() in line for token in tokens)
        if hit and start is None:
            start = index
        elif not hit and start is not None:
            spans.append((start, index - 1))
            start = None
        if len(spans) >= 20:
            break
    if start is not None and len(spans) < 20:
        spans.append((start, len(lines)))
    bound_spans = []
    for start_line, end_line in spans:
        chunk = "\n".join(lines[start_line - 1:end_line])
        text = chunk
        if len(text) > 2000:
            text = text[:2000] + "…[bounded]"
        bound_spans.append({"source": log_rel, "run_id": run_id,
                            "start_line": start_line,
                            "end_line": end_line,
                            "sha256": sha256_hex(chunk.encode("utf-8")),
                            "text": text})
    events_path = current_attempt_events(project, task["id"])
    span_digests = "\x1f".join(span["sha256"] for span in bound_spans)
    fingerprint = sha256_hex(("\x1f".join([
        str(sorted(tokens)), run_id,
        sha256_hex(events_path.read_bytes()) if events_path.is_file()
        else "no-events",
        sha256_hex(log_path.read_bytes()),
        span_digests,
    ]).encode("utf-8")))
    from .lifecycle import ensure_state, save_state
    state = ensure_state(project, task["id"])
    previous = (state.get("last_retrieval") or {})
    if isinstance(previous, dict) and \
            previous.get("fingerprint") == fingerprint:
        raise UALError("RETRIEVAL_NO_NEW_EVIDENCE",
                       "the evidence fingerprint is unchanged since "
                       "the previous bounded retrieval")
    state["last_retrieval"] = {"fingerprint": fingerprint, "run_id": run_id,
                               "need": need,
                               "attempt": state.get("current_attempt")}
    save_state(project, task["id"], state)
    return {"ok": True, "spans": bound_spans,
            "evidence_fingerprint": fingerprint,
            "note": "bounded delta; further retrieval with an unchanged "
                    "fingerprint refuses"}


def current_attempt_events(project: Path, task_id: str) -> Path:
    from .attempts import current_seq, attempt_dir
    seq = current_seq(project, task_id)
    if seq is None:
        return Path(project)
    return attempt_dir(project, task_id, seq) / "events.jsonl"


def verify_pack(project: Path, task: dict, pack_rel: str) -> dict:
    pack_path = resolve_inside(project, pack_rel, label="PACK")
    if not pack_path.is_file():
        raise UALError("CONTEXT_PACK_MISSING", pack_rel)
    index_path = pack_path.parent / "context_pack_index.json"
    if not index_path.is_file():
        raise UALError("CONTEXT_INDEX_MISSING", str(index_path))
    index = load_json(index_path, max_bytes=INDEX_MAX_BYTES)
    if not isinstance(index, dict) or \
            index.get("schema") != "ual-context-index/1":
        raise UALError("CONTEXT_INDEX_MISSING", str(index_path))
    if index.get("task") != task["id"]:
        raise UALError("CONTEXT_INDEX_TASK_MISMATCH",
                       f"{index.get('task')!r}!={task['id']!r}")
    pack_bytes = pack_path.read_bytes()
    if index.get("payload_sha256") != sha256_hex(pack_bytes):
        raise UALError("CONTEXT_PAYLOAD_DRIFT", pack_rel)
    start = time.perf_counter()
    errors = []
    expected = []
    for rel, role in mandatory_closure(project, task):
        if not (project / rel).is_file():
            if role in ("task", "skill"):
                errors.append(f"CONTEXT_INDEX_DRIFT:{rel}")
            continue
        expected.append((rel, role))
    members = index.get("members")
    if not isinstance(members, list) or \
            [(m.get("path"), m.get("role")) for m in members] != expected:
        raise UALError(
            "CONTEXT_INDEX_SET_DRIFT",
            "index members do not match the live task closure")
    render_ok = True
    bodies = {}
    for member in members:
        path = project / member["path"]
        data = path.read_bytes()
        if member.get("sha256") != sha256_hex(data) or \
                member.get("bytes") != len(data):
            errors.append(f"CONTEXT_INDEX_DRIFT:{member['path']}")
            render_ok = False
            continue
        try:
            bodies[member["path"]] = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"CONTEXT_INDEX_DRIFT:{member['path']}")
            render_ok = False
    if render_ok and \
            _render_context_pack(task["id"], members, bodies) != pack_bytes:
        errors.append("CONTEXT_PAYLOAD_CONTENT_MISMATCH:pack bytes differ "
                      "from the re-rendered index-bound content")
    restoration = time.perf_counter() - start
    if errors:
        raise UALError("CONTEXT_VERIFY_REFUSED", ";".join(errors[:4]))
    _record_timing(project, task["id"], restoration)
    return {"ok": True, "context_verify_seconds": round(restoration, 6)}


def _record_timing(project: Path, task_id: str, seconds: float) -> None:
    from .claims import utc_now_iso
    path = task_dir(project, task_id) / "timings.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.is_file():
        lines = [l for l in path.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    lines.append(json.dumps({
        "kind": "context_verify", "restoration_seconds": round(seconds, 6),
        "at": utc_now_iso()}, sort_keys=True))
    lines = lines[-TIMINGS_MAX_LINES:]
    atomic_write_bytes(path, ("\n".join(lines) + "\n").encode("utf-8"),
                       max_bytes=64 * 1024)


def latest_restoration_seconds(project: Path, task_id: str):
    path = task_dir(project, task_id) / "timings.jsonl"
    if not path.is_file():
        return None
    value = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and \
                entry.get("kind") == "context_verify":
            value = entry.get("restoration_seconds")
    return value

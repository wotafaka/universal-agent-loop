"""Stable progress bases, material-progress claims and repair packs.

Progress is compared through stable substantive bases over the frozen
repair batch content, never through iteration numbers, timestamps, log
paths or token totals. A post-baseline changed basis additionally needs
a structured material-progress claim binding stable finding IDs and one
material reason; unreadable prior records block instead of becoming an
empty baseline. Repair packs are built write-once LAST by the architect
and verified FIRST by the engineer; any drift fails closed to the full
canonical startup.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import lifecycle
from .errors import UALError
from .hashing import (exclusive_write_json, load_json, next_sequence,
                      sha256_hex)
from .paths import resolve_inside, task_dir

PACK_SCHEMA = "ual-repair-pack/1"
PACK_MAX_BYTES = 1024 * 1024
PACK_MAX_FILES = 64
BASIS_PREFIX = "stable-progress-basis/1"
MATERIAL_CLAIM_SCHEMA = "material-progress-claim/1"
MATERIAL_REASONS = ("NEW_EVIDENCE_HASH", "CANDIDATE_HASH_CHANGE",
                    "FALSIFIED_HYPOTHESIS", "ROUTE_FAILURE")
SECRET_PATTERNS = (
    ("PRIVATE_KEY_BLOCK", re.compile(rb"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
    ("API_KEY_ASSIGN", re.compile(rb"api[_-]?key\s*[:=]", re.IGNORECASE)),
    ("SECRET_ASSIGN", re.compile(rb"secret\s*[:=]", re.IGNORECASE)),
    ("PASSWORD_ASSIGN", re.compile(rb"pass(word|wd)\s*[:=]",
                                   re.IGNORECASE)),
    ("ACCESS_TOKEN_ASSIGN", re.compile(rb"access[_-]?token\s*[:=]",
                                       re.IGNORECASE)),
    ("AWS_ACCESS_KEY_ID", re.compile(rb"AKIA[0-9A-Z]{16}")),
)
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def find_secret(data: bytes) -> str | None:
    for category, pattern in SECRET_PATTERNS:
        if pattern.search(data):
            return category
    return None


def verify_engineer_stdin(project: Path, task_id: str, rel: str,
                          data: bytes) -> str:
    """Authorize ENGINEER stdin as an immutable task-authorized pack.

    The only admitted payloads are this task's context pack (bytes
    equal to the digest recorded in ``context_pack_index.json``) or a
    manifest-bound repair pack for this task (bytes equal to the pack
    digest in its ``manifest.json``; when the current attempt declares
    a pack iteration, exactly that iteration). The conservative secret
    scan runs after authorization. Anything else refuses before a
    claim, log or child exists. Returns the pack kind."""
    from . import attempts
    from .context import INDEX_MAX_BYTES
    normalized = Path(rel.replace("\\", "/"))
    task_prefix = Path(".agent-loop") / "tasks" / task_id
    kind = None
    iteration = None
    if normalized == task_prefix / "context_pack.md":
        index_path = (task_dir(project, task_id) /
                      "context_pack_index.json")
        if index_path.is_file():
            index = load_json(index_path, max_bytes=INDEX_MAX_BYTES)
            if isinstance(index, dict) and \
                    index.get("schema") == "ual-context-index/1" and \
                    index.get("task") == task_id and \
                    index.get("payload_sha256") == sha256_hex(data):
                kind = "CONTEXT_PACK"
    else:
        parts = normalized.parts
        packs_prefix = tuple((task_prefix / "packs").parts)
        if len(parts) == len(packs_prefix) + 2 and \
                parts[:len(packs_prefix)] == packs_prefix and \
                parts[-1] == "repair_pack.md" and \
                parts[-2].startswith("iteration_"):
            try:
                iteration = int(parts[-2][len("iteration_"):])
            except ValueError:
                iteration = None
            if iteration is not None:
                manifest_path = (task_dir(project, task_id) / "packs" /
                                 f"iteration_{iteration}" /
                                 "manifest.json")
                if manifest_path.is_file():
                    manifest = load_json(manifest_path,
                                         max_bytes=PACK_MAX_BYTES)
                    if isinstance(manifest, dict) and \
                            manifest.get("schema") == PACK_SCHEMA and \
                            manifest.get("task") == task_id and \
                            manifest.get("iteration") == iteration and \
                            (manifest.get("pack") or {}).get("sha256") \
                            == sha256_hex(data):
                        kind = "REPAIR_PACK"
    if kind is None:
        raise UALError("ENGINEER_STDIN_UNAUTHORIZED", rel)
    if kind == "REPAIR_PACK" and iteration is not None:
        seq = attempts.current_seq(project, task_id)
        if seq is not None:
            payload = attempts.current_payload(project, task_id)
            bound = (payload.get("progress") or {}).get("pack_iteration")
            if bound is not None and bound != iteration:
                raise UALError("ENGINEER_STDIN_UNAUTHORIZED",
                               f"attempt {seq} binds pack iteration "
                               f"{bound}, not {iteration}")
    category = find_secret(data)
    if category is not None:
        raise UALError("SECRET_MATERIAL_SUSPECTED", f"{category}:{rel}")
    return kind


def stable_progress_basis(task: str, repair_batch_text: str) -> str | None:
    if (not isinstance(task, str) or not task.strip()
            or not isinstance(repair_batch_text, str)):
        return None
    lines = repair_batch_text.replace("\r\n", "\n").split("\n")
    if not lines or not lines[0].startswith("# "):
        return None
    body = "\n".join(lines[1:]).strip()
    if not body:
        return None
    digest_input = "\x1f".join((BASIS_PREFIX, task.strip(), body))
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def material_claim_identity(claim) -> str | None:
    if not isinstance(claim, dict):
        return None
    finding_ids = claim.get("finding_ids")
    reason = claim.get("reason")
    evidence = claim.get("evidence")
    if (not isinstance(finding_ids, list) or not finding_ids
            or not all(isinstance(i, str) and i.strip()
                       for i in finding_ids)
            or not isinstance(reason, str)
            or reason.strip() not in MATERIAL_REASONS
            or not isinstance(evidence, dict)):
        return None
    payload = json.dumps({"finding_ids": finding_ids,
                          "reason": reason.strip(),
                          "evidence": evidence},
                         ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _material_claim_content_errors(claim: dict) -> list:
    reason = claim.get("reason")
    evidence = claim.get("evidence")
    errors = []
    if reason not in MATERIAL_REASONS:
        return [f"MATERIAL_CLAIM_MALFORMED:reason:{reason!r}"]
    if not isinstance(evidence, dict):
        return ["MATERIAL_CLAIM_MALFORMED:evidence"]

    def sha(value):
        return isinstance(value, str) and bool(_HEX64_RE.match(value.strip()))

    if reason == "NEW_EVIDENCE_HASH":
        if not sha(evidence.get("evidence_sha256")):
            errors.append("MATERIAL_CLAIM_MALFORMED:evidence_sha256")
    elif reason == "CANDIDATE_HASH_CHANGE":
        prior = evidence.get("prior_candidate_sha256")
        new = evidence.get("new_candidate_sha256")
        if not sha(prior) or not sha(new):
            errors.append("MATERIAL_CLAIM_MALFORMED:candidate_hashes")
        elif prior.strip() == new.strip():
            errors.append("MATERIAL_CLAIM_MALFORMED:candidate_hash_unchanged")
    elif reason == "FALSIFIED_HYPOTHESIS":
        hypothesis = evidence.get("hypothesis")
        if (not isinstance(hypothesis, str) or not hypothesis.strip()
                or evidence.get("outcome") != "FALSIFIED"
                or not sha(evidence.get("evidence_sha256"))):
            errors.append("MATERIAL_CLAIM_MALFORMED:falsified_hypothesis")
    else:
        failure = evidence.get("route_failure")
        if (not isinstance(failure, str) or not failure.strip()
                or not sha(evidence.get("evidence_sha256"))):
            errors.append("MATERIAL_CLAIM_MALFORMED:route_failure")
    return errors


def last_engineer_sidecar(project: Path, task_id: str):
    runs_root = Path(project) / ".agent-loop" / "runs"
    if not runs_root.is_dir():
        return None
    latest = None
    for entry in sorted(runs_root.iterdir()):
        sidecar_path = entry / "run.json"
        if not sidecar_path.is_file():
            continue
        try:
            sidecar = load_json(sidecar_path, max_bytes=1024 * 1024)
        except (UALError, OSError):
            return {"malformed": True, "path": str(sidecar_path)}
        if isinstance(sidecar, dict) and \
                sidecar.get("task") == task_id and \
                sidecar.get("purpose") == "ENGINEER":
            latest = sidecar
    return latest


def progress_gate(project: Path, task: dict, batch_rel: str,
                  claim_file: str | None) -> dict:
    task_id = task["id"]
    try:
        batch_path = resolve_inside(project, batch_rel, label="BATCH")
        batch_text = batch_path.read_text(encoding="utf-8")
    except (UALError, OSError, UnicodeError):
        raise UALError("PROGRESS_BATCH_UNREADABLE", batch_rel)
    request_basis = stable_progress_basis(task_id, batch_text)
    prior = last_engineer_sidecar(project, task_id)
    if isinstance(prior, dict) and prior.get("malformed"):
        raise UALError("PROGRESS_PRIOR_RECORD_MALFORMED",
                       str(prior.get("path")))
    if prior is None:
        decision = "BASELINE_ALLOWED"
        basis_note = "NO_COMPLETE_PRIOR_PROGRESS_RECORD"
        errors = []
    else:
        prior_basis = (prior.get("launch_identity") or {}).get(
            "progress_basis")
        if request_basis is None:
            raise UALError("PROGRESS_BASIS_NOT_DERIVABLE",
                           "malformed batch cannot authorize a "
                           "post-baseline repair")
        if not isinstance(prior_basis, str) or not prior_basis.strip():
            decision = "BASELINE_ALLOWED"
            basis_note = "NO_COMPLETE_PRIOR_PROGRESS_RECORD"
            errors = []
        elif prior_basis == request_basis:
            decision = "DUPLICATE_BLOCKED"
            basis_note = "IDENTICAL_SUBSTANTIVE_PROGRESS_BASIS"
            errors = ["PROGRESS_DUPLICATE_BLOCKED:identical "
                      "candidate/evidence/hypothesis basis"]
        else:
            decision = "PROGRESSING_ALLOWED"
            basis_note = "CHANGED_SUBSTANTIVE_PROGRESS_BASIS"
            errors = []
    payload = {"ok": True, "decision": decision, "basis": request_basis,
               "basis_note": basis_note, "errors": errors}
    if claim_file is not None:
        claim_payload = load_json(resolve_inside(project, claim_file,
                                                 label="CLAIM"),
                                  max_bytes=64 * 1024)
        claim_decision = _evaluate_material_claim(
            project, task_id, request_basis, claim_payload)
        payload["decision"] = claim_decision
        if claim_decision == "MATERIALLY_AUTHORIZED":
            state = lifecycle.ensure_state(project, task_id)
            state["last_material_claim_identity"] = \
                material_claim_identity(claim_payload)
            lifecycle.save_state(project, task_id, state)
    return payload


def _evaluate_material_claim(project: Path, task_id: str, basis,
                             claim) -> str:
    if basis is None:
        raise UALError("PROGRESS_BASIS_NOT_DERIVABLE", "claim")
    identity = material_claim_identity(claim)
    if identity is None:
        raise UALError("MATERIAL_CLAIM_MALFORMED", "shapeless claim")
    errors = _material_claim_content_errors(claim)
    if errors:
        raise UALError(errors[0].split(":")[0], ";".join(errors))
    bound = claim.get("progress_basis")
    if not isinstance(bound, str) or bound.strip() != basis.strip():
        raise UALError("MATERIAL_CLAIM_BASIS_MISMATCH", task_id)
    state = lifecycle.load_state(project, task_id) or {}
    previous = state.get("last_material_claim_identity")
    if previous is not None and previous == identity:
        return "MATERIAL_CLAIM_NON_AUTHORIZING"
    return "MATERIALLY_AUTHORIZED"


def attempt_progress(project: Path, task: dict, batch_rel: str,
                     claim_file: str | None) -> dict:
    """Progress evaluation consumed by the attempt-open gate.

    Returns the decision, the stable basis and the material claim
    identity (when a claim authorizes a changed basis). Raises stable
    refusals instead of returning non-authorizing decisions so a repair
    attempt can never open on a duplicate or unevidenced basis."""
    task_id = task["id"]
    try:
        batch_path = resolve_inside(project, batch_rel, label="BATCH")
        batch_text = batch_path.read_text(encoding="utf-8")
    except (UALError, OSError, UnicodeError):
        raise UALError("PROGRESS_BATCH_UNREADABLE", batch_rel)
    request_basis = stable_progress_basis(task_id, batch_text)
    prior = last_engineer_sidecar(project, task_id)
    if isinstance(prior, dict) and prior.get("malformed"):
        raise UALError("PROGRESS_PRIOR_RECORD_MALFORMED",
                       str(prior.get("path")))
    prior_basis = None
    if prior is not None:
        prior_basis = (prior.get("launch_identity") or {}).get(
            "progress_basis")
    if request_basis is None:
        if prior is None:
            return {"decision": "BASELINE_ALLOWED", "basis": None,
                    "claim_identity": None}
        raise UALError("PROGRESS_BASIS_NOT_DERIVABLE",
                       "malformed batch cannot authorize a repair")
    if prior is None or not isinstance(prior_basis, str) or \
            not prior_basis.strip():
        decision = "BASELINE_ALLOWED"
    elif prior_basis == request_basis:
        raise UALError("ATTEMPT_PROGRESS_BLOCKED",
                       "identical substantive basis as the predecessor")
    else:
        decision = "PROGRESSING_ALLOWED"
    claim_identity = None
    if decision == "PROGRESSING_ALLOWED":
        if claim_file is None:
            raise UALError("MATERIAL_CLAIM_MISSING",
                           "changed-basis progress requires a structured "
                           "material-progress claim")
        claim = load_json(resolve_inside(project, claim_file, label="CLAIM"),
                          max_bytes=64 * 1024)
        identity = material_claim_identity(claim)
        if identity is None:
            raise UALError("MATERIAL_CLAIM_MALFORMED", "shapeless claim")
        errors = _material_claim_content_errors(claim)
        if errors:
            raise UALError(errors[0].split(":")[0], ";".join(errors))
        bound = claim.get("progress_basis")
        if not isinstance(bound, str) or bound.strip() != request_basis:
            raise UALError("MATERIAL_CLAIM_BASIS_MISMATCH", task_id)
        claim_identity = identity
    return {"decision": decision, "basis": request_basis,
            "claim_identity": claim_identity}


def _render_repair_pack(task_id: str, iteration: int, basis: str,
                        task_text: str, commands: list, batch_text: str,
                        touched_text: str, members: list,
                        bodies: dict) -> bytes:
    """The one deterministic repair-pack renderer, shared by build and
    verify so re-rendered expected bytes are comparable byte-for-byte."""
    pack_lines = [
        f"# Repair pack — `{task_id}` — iteration {iteration}",
        "",
        f"> Schema `{PACK_SCHEMA}`. Deterministic, credential-free,",
        "> project-local, built write-once LAST by the architect and",
        "> verified FIRST by the engineer. Any drift fails closed to the",
        "> full canonical startup; never repair from an unverified pack.",
        "",
        "## Pack header",
        "",
        f"- task: `{task_id}`",
        "- task_status: `FIX_REQUIRED`",
        f"- iteration: `{iteration}`",
        f"- schema: `{PACK_SCHEMA}`",
        f"- progress_basis: `{basis}`",
        "- fallback: `FULL_CANONICAL_STARTUP_ON_ANY_DRIFT`",
        "",
        "## Complete task",
        "",
        "```json",
        task_text.rstrip("\n"),
        "```",
        "",
        "## Required skills (complete bodies)",
        "",
    ]
    for member in members:
        if member["role"] == "skill":
            body = bodies[member["path"]]
            pack_lines += [f"### {member['path']}", "",
                           body.rstrip("\n"), ""]
    for member in members:
        if member["role"] == "rules":
            body = bodies[member["path"]]
            pack_lines += [f"### {member['path']} (rules)", "",
                           body.rstrip("\n"), ""]
    pack_lines += [
        "## Validation command budget",
        "",
    ]
    for ordinal, argv in commands:
        pack_lines.append(f"- ordinal `{ordinal}`: "
                          f"`{json.dumps(argv, ensure_ascii=True)}`")
    pack_lines += [
        "",
        "## Frozen repair batch",
        "",
        batch_text.rstrip("\n"),
        "",
        "## Touched source/test map",
        "",
        touched_text.rstrip("\n"),
        "",
        "## Canonical member manifest",
        "",
    ]
    for member in members:
        pack_lines.append(f"- `{member['path']}` ({member['role']}): "
                          f"sha256 `{member['sha256']}`, "
                          f"bytes {member['bytes']}")
    return ("\n".join(pack_lines) + "\n").encode("utf-8")


def build_pack(project: Path, task: dict, iteration: int, batch_rel: str,
               touched_rel: str) -> dict:
    task_id = task["id"]
    state = lifecycle.ensure_state(project, task_id)
    if state.get("status") != "FIX_REQUIRED":
        raise UALError("STATUS_NOT_FIX_REQUIRED",
                       str(state.get("status")))
    if not isinstance(iteration, int) or isinstance(iteration, bool) \
            or iteration < 1:
        raise UALError("ITERATION_INVALID", str(iteration))
    batch_path = resolve_inside(project, batch_rel, label="BATCH")
    touched_path = resolve_inside(project, touched_rel, label="TOUCHED")
    batch_bytes = batch_path.read_bytes()
    touched_bytes = touched_path.read_bytes()
    batch_text = batch_bytes.decode("utf-8")
    for label, data in (("batch", batch_bytes), ("touched", touched_bytes)):
        category = find_secret(data)
        if category is not None:
            raise UALError("SECRET_MATERIAL_SUSPECTED",
                           f"{category}:{label}")
    basis = stable_progress_basis(task_id, batch_text)
    if basis is None:
        raise UALError("PROGRESS_BASIS_NOT_DERIVABLE", batch_rel)
    task_path = project / "task.json"
    task_bytes = task_path.read_bytes()
    from .context import mandatory_closure
    members = []
    for rel, role in mandatory_closure(project, task):
        path = project / rel
        if not path.is_file():
            if role in ("task", "skill"):
                raise UALError("PACK_MEMBER_MISSING", rel)
            continue
        data = path.read_bytes()
        members.append({"path": rel, "role": role, "bytes": len(data),
                        "sha256": sha256_hex(data)})
    members.append({"path": batch_rel, "role": "repair_batch",
                    "bytes": len(batch_bytes),
                    "sha256": sha256_hex(batch_bytes)})
    members.append({"path": touched_rel, "role": "touched_map",
                    "bytes": len(touched_bytes),
                    "sha256": sha256_hex(touched_bytes)})
    commands = [(c.get("ordinal"), c.get("argv"))
                for c in (task.get("validation") or {}).get("commands") or []]
    bodies = {}
    for member in members:
        if member["role"] in ("skill", "rules"):
            bodies[member["path"]] = (project /
                                      member["path"]).read_bytes() \
                .decode("utf-8")
    pack_bytes = _render_repair_pack(
        task_id, iteration, basis,
        task_bytes.decode("utf-8"), commands,
        batch_bytes.decode("utf-8"), touched_bytes.decode("utf-8"),
        members, bodies)
    if len(pack_bytes) > PACK_MAX_BYTES:
        raise UALError("PACK_OVER_BOUND", str(len(pack_bytes)))
    category = find_secret(pack_bytes)
    if category is not None:
        raise UALError("SECRET_MATERIAL_SUSPECTED",
                       category + ":repair_pack")
    directory = task_dir(project, task_id) / "packs" / f"iteration_{iteration}"
    if directory.exists():
        raise UALError("PACK_TARGET_EXISTS", str(directory))
    directory.mkdir(parents=True, exist_ok=False)
    pack_path = directory / "repair_pack.md"
    exclusive_write_bytes_guarded(pack_path, pack_bytes, PACK_MAX_BYTES)
    manifest = {
        "schema": PACK_SCHEMA,
        "task": task_id,
        "iteration": iteration,
        "task_status": "FIX_REQUIRED",
        "progress_basis": basis,
        "pack": {"path": "repair_pack.md", "bytes": len(pack_bytes),
                 "sha256": sha256_hex(pack_bytes)},
        "task_file": {"path": "task.json", "bytes": len(task_bytes),
                      "sha256": sha256_hex(task_bytes)},
        "members": members,
    }
    manifest_bytes = exclusive_write_json(directory / "manifest.json",
                                          manifest,
                                          max_bytes=PACK_MAX_BYTES)
    return {"ok": True, "pack": str(pack_path),
            "progress_basis": basis,
            "manifest_sha256": sha256_hex(manifest_bytes)}


def exclusive_write_bytes_guarded(path: Path, data: bytes,
                                  max_bytes: int) -> None:
    from .hashing import exclusive_write_bytes
    exclusive_write_bytes(path, data, max_bytes=max_bytes)


def verify_pack_readonly(project: Path, task_id: str,
                         iteration: int) -> list:
    """Read-only full pack revalidation: manifest identity, pack/task
    hashes, the exact expected member set derived from the live task
    contract, every manifest-bound live input, the recomputed progress
    basis, and a byte-exact re-render of the pack from those
    manifest-bound live inputs — so synchronized inner-content plus
    outer-hash tampering still refuses. Returns an error list; empty
    means the pack still matches the repository. Writes nothing."""
    directory = task_dir(project, task_id) / "packs" / f"iteration_{iteration}"
    pack_path = directory / "repair_pack.md"
    manifest_path = directory / "manifest.json"
    if not pack_path.is_file() or not manifest_path.is_file():
        return [f"PACK_MISSING:{directory}"]
    pack_bytes = pack_path.read_bytes()
    manifest = load_json(manifest_path, max_bytes=PACK_MAX_BYTES)
    if not isinstance(manifest, dict) or manifest.get("schema") != PACK_SCHEMA:
        return ["MANIFEST_WRONG_SCHEMA"]
    errors = []
    if manifest.get("task") != task_id:
        errors.append(f"PACK_TASK_MISMATCH:{manifest.get('task')!r}")
    if manifest.get("iteration") != iteration:
        errors.append(
            f"PACK_ITERATION_MISMATCH:{manifest.get('iteration')!r}")
    pack_binding = manifest.get("pack") or {}
    if pack_binding.get("sha256") != sha256_hex(pack_bytes) or \
            pack_binding.get("bytes") != len(pack_bytes):
        errors.append("PACK_HASH_CONFLICT")
    task_path = project / "task.json"
    task_bytes = task_path.read_bytes()
    task_binding = manifest.get("task_file") or {}
    if task_binding.get("sha256") != sha256_hex(task_bytes) or \
            task_binding.get("bytes") != len(task_bytes):
        errors.append("PACK_TASK_DRIFT")
    try:
        live_task = json.loads(task_bytes.decode("utf-8"))
        if not isinstance(live_task, dict):
            live_task = None
    except (UnicodeDecodeError, ValueError):
        live_task = None
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        errors.append("PACK_MEMBER_SET_DRIFT:manifest members missing")
        return errors
    expected = [("task.json", "task")]
    if live_task is not None:
        expected += [(rel, "skill")
                     for rel in live_task.get("required_skills") or []]
    if (project / "AGENTS.md").is_file():
        expected.append(("AGENTS.md", "rules"))
    batch_rels = [m.get("path") for m in members
                  if m.get("role") == "repair_batch"]
    touched_rels = [m.get("path") for m in members
                    if m.get("role") == "touched_map"]
    if len(batch_rels) != 1 or len(touched_rels) != 1:
        errors.append("PACK_MEMBER_INCOMPLETE:repair batch/touched map")
    else:
        expected += [(batch_rels[0], "repair_batch"),
                     (touched_rels[0], "touched_map")]
    if [(m.get("path"), m.get("role")) for m in members] != expected:
        errors.append("PACK_MEMBER_SET_DRIFT:manifest members do not "
                      "match the live task closure plus the declared "
                      "repair inputs")
        return errors
    render_ok = True
    bodies = {}
    role_bytes = {}
    for member in members:
        rel = member.get("path")
        try:
            member_path = resolve_inside(project, rel, label="PACK_MEMBER")
        except UALError:
            errors.append(f"PACK_MEMBER_ESCAPE:{rel}")
            render_ok = False
            continue
        if not member_path.is_file():
            errors.append(f"PACK_MEMBER_MISSING:{rel}")
            render_ok = False
            continue
        data = member_path.read_bytes()
        if member.get("sha256") != sha256_hex(data) or \
                member.get("bytes") != len(data):
            errors.append(f"PACK_MEMBER_DRIFT:{rel}")
            render_ok = False
            continue
        role_bytes[member["role"]] = data
        if member["role"] in ("skill", "rules"):
            try:
                bodies[rel] = data.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"PACK_MEMBER_DRIFT:{rel}")
                render_ok = False
    if not render_ok or live_task is None:
        if live_task is None:
            errors.append("PACK_TASK_DRIFT")
        return errors
    batch_text = role_bytes["repair_batch"].decode("utf-8")
    touched_text = role_bytes["touched_map"].decode("utf-8")
    if stable_progress_basis(task_id, batch_text) != \
            manifest.get("progress_basis"):
        errors.append("PACK_BASIS_DRIFT")
    commands = [(c.get("ordinal"), c.get("argv"))
                for c in (live_task.get("validation") or {}).get("commands")
                or []]
    rendered = _render_repair_pack(
        task_id, iteration, manifest.get("progress_basis"),
        task_bytes.decode("utf-8"), commands, batch_text, touched_text,
        members, bodies)
    if rendered != pack_bytes:
        errors.append("PACK_CONTENT_DRIFT:pack bytes differ from the "
                      "re-rendered manifest-bound content")
    return errors


def verify_pack(project: Path, task_id: str, iteration: int) -> dict:
    errors = verify_pack_readonly(project, task_id, iteration)
    if errors:
        return _pack_fail(errors)
    directory = task_dir(project, task_id) / "packs" / f"iteration_{iteration}"
    pack_path = directory / "repair_pack.md"
    manifest_path = directory / "manifest.json"
    receipt_path = directory / "verification.json"
    pack_bytes = pack_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    from .claims import utc_now_iso
    receipt = {
        "schema": "ual-pack-verification/1",
        "task": task_id,
        "iteration": iteration,
        "pack_sha256": sha256_hex(pack_bytes),
        "manifest_sha256": sha256_hex(manifest_bytes),
        "verified_at": utc_now_iso(),
    }
    from .errors import UALError as _E
    try:
        from .hashing import exclusive_write_json as _ewj
        _ewj(receipt_path, receipt, max_bytes=64 * 1024)
    except _E as exc:
        if exc.code == "TARGET_EXISTS":
            existing = load_json(receipt_path, max_bytes=64 * 1024)
            if isinstance(existing, dict) and \
                    existing.get("pack_sha256") == receipt["pack_sha256"] \
                    and existing.get("manifest_sha256") == \
                    receipt["manifest_sha256"]:
                pass
            else:
                raise UALError("PACK_VERIFICATION_CONFLICT",
                               str(receipt_path)) from None
        else:
            raise
    manifest = load_json(manifest_path, max_bytes=PACK_MAX_BYTES)
    return {"ok": True, "progress_basis": manifest.get("progress_basis"),
            "verification_receipt": str(receipt_path)}


def _pack_fail(errors: list) -> dict:
    from .errors import UALError as _E
    raise _E("PACK_VERIFY_REFUSED", ";".join(errors[:4]))

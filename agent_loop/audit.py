"""Deterministic audit packages, verdict binding and fallback policy.

A frozen secret-scanned package binds the exact latest candidate before
any transmission; the returned result must carry a valid structured
inner verdict. A process exit of zero is never a PASS. A valid FAIL is
a real result and never an outage; fallback requires both an explicit
policy and an objective route failure, and a local package-integrity
failure is BLOCKED, never a reason to transmit elsewhere. When a task requires
an audit and config names a primary auditor, missing observed model identity
fails closed instead of being accepted as UNKNOWN.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import UALError
from .hashing import load_json, sha256_hex
from .paths import inside_rel, resolve_inside, task_dir
from .packs import find_secret

PACKAGE_SCHEMA = "ual-audit-package/1"
PAYLOAD_NAME = "audit_payload.bin"
MANIFEST_NAME = "manifest.json"
MAX_INPUTS = 32
MAX_TOTAL_BYTES = 8 * 1024 * 1024
INPUT_ROLES = ("input", "instruction", "validation")
RESULT_MAX_BYTES = 1024 * 1024
ROUTE_RECEIPT_SCHEMA = "ual-audit-route-receipt/1"
ROUTE_RECEIPT_MAX_BYTES = 64 * 1024
ROUTE_KIND_RESULT = "AUDIT_RESULT"
ROUTE_KIND_FAILURE = "PROVIDER_FAILURE"
ROUTE_KINDS = (ROUTE_KIND_RESULT, ROUTE_KIND_FAILURE)
VALID_VERDICTS = ("PASS", "CONDITIONAL_PASS", "FAIL", "BLOCKED")
VALID_SEVERITIES = ("P0", "P1", "P2", "P3")
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def render_package_payload(entries) -> bytes:
    """The one deterministic audit payload renderer, shared by build and
    verify: framing marker plus exact input bytes in declared order, so
    verification can require byte equality with no trailing or unlisted
    bytes."""
    chunks = []
    for role, rel, data in entries:
        marker = (f">>>FILE role={json.dumps(role)} "
                  f"path={json.dumps(rel)} sha256={sha256_hex(data)} "
                  f"bytes={len(data)}\n")
        chunks.append(marker.encode("utf-8"))
        chunks.append(data)
    return b"".join(chunks)


def audit_dir(project: Path, task_id: str, iteration: int) -> Path:
    from .attempts import current_dir
    return (current_dir(project, task_id) / "audit" /
            f"iteration_{iteration}")


def build_package(project: Path, task: dict, iteration: int,
                  roles: dict) -> dict:
    from . import envelope as envelope_mod
    task_id = task["id"]
    if not isinstance(iteration, int) or isinstance(iteration, bool) \
            or iteration < 1:
        raise UALError("ITERATION_INVALID", str(iteration))
    loaded = envelope_mod.latest_envelope(project, task_id)
    if loaded is None:
        raise UALError("AUDIT_ENVELOPE_REQUIRED", task_id)
    envelope_path, envelope = loaded
    collected = []
    for role, rels in roles.items():
        if role not in INPUT_ROLES:
            raise UALError("AUDIT_ROLE_INVALID", role)
        for rel in rels:
            collected.append((role, rel))
    if not collected:
        raise UALError("AUDIT_NO_INPUTS", task_id)
    if len(collected) > MAX_INPUTS:
        raise UALError("AUDIT_INPUT_COUNT_CAP", str(len(collected)))
    directory = audit_dir(project, task_id, iteration)
    if directory.exists():
        raise UALError("AUDIT_TARGET_EXISTS", str(directory))
    validated = []
    seen = set()
    total = 0
    for role, rel in collected:
        path = resolve_inside(project, rel, label="AUDIT_INPUT")
        if not path.is_file():
            raise UALError("AUDIT_INPUT_NOT_FILE", rel)
        resolved = path.resolve(strict=False)
        if resolved in seen:
            raise UALError("AUDIT_DUPLICATE_INPUT", rel)
        seen.add(resolved)
        data = path.read_bytes()
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise UALError("AUDIT_TOTAL_BYTES_CAP", str(total))
        category = find_secret(data)
        if category is not None:
            raise UALError("SECRET_MATERIAL_SUSPECTED",
                           f"{category}:{rel}")
        validated.append((role, rel, data))
    validated.sort(key=lambda item: item[1])
    directory.mkdir(parents=True, exist_ok=False)
    try:
        payload = render_package_payload(
            [(role, rel, data) for role, rel, data in validated])
        (directory / PAYLOAD_NAME).write_bytes(payload)
        manifest = {
            "schema": PACKAGE_SCHEMA,
            "task": task_id,
            "iteration": iteration,
            "envelope_sha256": sha256_hex(envelope_path.read_bytes()),
            "candidate_sha256": envelope.get("candidate_sha256"),
            "input_count": len(validated),
            "total_bytes": sum(len(d) for _r, _p, d in validated),
            "inputs": [{"path": rel, "role": role, "bytes": len(data),
                        "sha256": sha256_hex(data)}
                       for role, rel, data in validated],
            "payload": {"path": PAYLOAD_NAME, "bytes": len(payload),
                        "sha256": sha256_hex(payload)},
        }
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")
        (directory / MANIFEST_NAME).write_bytes(manifest_bytes)
    except BaseException:
        import shutil
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return {"ok": True, "package": inside_rel(project, directory),
            "manifest_sha256": sha256_hex(manifest_bytes),
            "payload_sha256": manifest["payload"]["sha256"]}


def verify_package(project: Path, task_id: str, package_rel: str) -> dict:
    """Full package verification: manifest identity (exact task and
    iteration), unique complete declared input set, per-input live byte
    counts and hashes, totals, outer payload identity, and a byte-exact
    re-render of the payload from the manifest-bound live inputs — so
    synchronized inner-content plus outer-hash tampering refuses and
    every declared embedded input is proven, not merely searched for."""
    directory = resolve_inside(project, package_rel, label="AUDIT_PACKAGE")
    if not directory.is_dir():
        raise UALError("AUDIT_PACKAGE_MISSING", package_rel)
    payload_path = directory / PAYLOAD_NAME
    manifest_path = directory / MANIFEST_NAME
    if not payload_path.is_file() or not manifest_path.is_file():
        raise UALError("AUDIT_PACKAGE_INCOMPLETE", package_rel)
    payload = payload_path.read_bytes()
    manifest = load_json(manifest_path, max_bytes=MAX_TOTAL_BYTES)
    if not isinstance(manifest, dict) or manifest.get("schema") != \
            PACKAGE_SCHEMA:
        raise UALError("AUDIT_MANIFEST_SCHEMA", package_rel)
    if manifest.get("task") != task_id:
        raise UALError("AUDIT_PACKAGE_TASK_MISMATCH",
                       f"{manifest.get('task')!r}!={task_id!r}")
    name = directory.name
    if not name.startswith("iteration_") or \
            not name[len("iteration_"):].isdigit():
        raise UALError("AUDIT_PACKAGE_ITERATION_MISMATCH", name)
    if manifest.get("iteration") != int(name[len("iteration_"):]):
        raise UALError("AUDIT_PACKAGE_ITERATION_MISMATCH",
                       f"{manifest.get('iteration')!r} vs {name}")
    for field in ("envelope_sha256", "candidate_sha256"):
        value = manifest.get(field)
        if not isinstance(value, str) or not _HEX64_RE.match(value):
            raise UALError("AUDIT_MANIFEST_SCHEMA", field)
    declared = manifest.get("inputs")
    if not isinstance(declared, list) or not declared:
        raise UALError("AUDIT_MANIFEST_SCHEMA", "inputs")
    if len(declared) > MAX_INPUTS:
        raise UALError("AUDIT_INPUT_COUNT_CAP", str(len(declared)))
    seen = set()
    total = 0
    entries = []
    for entry in declared:
        if not isinstance(entry, dict) or \
                not isinstance(entry.get("path"), str) or \
                not isinstance(entry.get("role"), str) or \
                not isinstance(entry.get("bytes"), int) or \
                isinstance(entry.get("bytes"), bool) or \
                not isinstance(entry.get("sha256"), str) or \
                not _HEX64_RE.match(entry["sha256"]):
            raise UALError("AUDIT_MANIFEST_SCHEMA", "input entry")
        rel = entry["path"]
        if entry["role"] not in INPUT_ROLES:
            raise UALError("AUDIT_ROLE_INVALID", entry["role"])
        if rel in seen:
            raise UALError("AUDIT_INPUT_DUPLICATE", rel)
        seen.add(rel)
        live_path = resolve_inside(project, rel, label="AUDIT_INPUT")
        if not live_path.is_file():
            raise UALError("AUDIT_INPUT_DRIFT", rel)
        data = live_path.read_bytes()
        if entry["sha256"] != sha256_hex(data) or \
                entry["bytes"] != len(data):
            raise UALError("AUDIT_INPUT_DRIFT", rel)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise UALError("AUDIT_TOTAL_BYTES_CAP", str(total))
        entries.append((entry["role"], rel, data))
    declared_paths = [entry["path"] for entry in declared]
    if declared_paths != sorted(declared_paths):
        raise UALError("AUDIT_INPUT_ORDER_INVALID",
                       "manifest inputs must use canonical path order")
    if manifest.get("input_count") != len(declared):
        raise UALError("AUDIT_TOTALS_MISMATCH",
                       f"input_count {manifest.get('input_count')!r} "
                       f"!={len(declared)}")
    if manifest.get("total_bytes") != total:
        raise UALError("AUDIT_TOTALS_MISMATCH",
                       f"total_bytes {manifest.get('total_bytes')!r} "
                       f"!={total}")
    payload_binding = manifest.get("payload") or {}
    if payload_binding.get("sha256") != sha256_hex(payload) or \
            payload_binding.get("bytes") != len(payload):
        raise UALError("AUDIT_PAYLOAD_IDENTITY_MISMATCH", package_rel)
    if render_package_payload(entries) != payload:
        raise UALError("AUDIT_PAYLOAD_CONTENT_MISMATCH",
                       "payload bytes differ from the re-rendered "
                       "manifest-bound inputs")
    return {"ok": True, "package": package_rel,
            "manifest_sha256": sha256_hex(manifest_path.read_bytes()),
            "payload_sha256": sha256_hex(payload),
            "envelope_sha256": manifest.get("envelope_sha256"),
            "candidate_sha256": manifest.get("candidate_sha256")}


def load_route_receipt(project: Path, receipt_rel: str, task: dict,
                       verified: dict,
                       result_path: Path | None = None) -> dict:
    """Load and fully validate one ``ual-audit-route-receipt/1``. Binds
    task, exact package manifest/payload digests, requested/observed
    models, terminal FINISHED status, integer exit code, and — for result
    receipts — the exact result file bytes/hash; for failure receipts the
    raw provider-error file bytes/hash plus structured terminal evidence."""
    from .paths import resolve_inside as _ri
    receipt_path = _ri(project, receipt_rel, label="ROUTE_RECEIPT")
    receipt = load_json(receipt_path, max_bytes=ROUTE_RECEIPT_MAX_BYTES)
    if not isinstance(receipt, dict) or \
            receipt.get("schema") != ROUTE_RECEIPT_SCHEMA:
        raise UALError("ROUTE_RECEIPT_SCHEMA_INVALID", receipt_rel)
    if receipt.get("task") != task["id"]:
        raise UALError("ROUTE_RECEIPT_TASK_MISMATCH",
                       f"{receipt.get('task')!r}!={task['id']!r}")
    if receipt.get("package_manifest_sha256") != \
            verified.get("manifest_sha256") or \
            receipt.get("package_payload_sha256") != \
            verified.get("payload_sha256"):
        raise UALError("ROUTE_RECEIPT_PACKAGE_MISMATCH", receipt_rel)
    if receipt.get("status") != "FINISHED":
        raise UALError("ROUTE_RECEIPT_STATUS_INVALID",
                       str(receipt.get("status")))
    exit_code = receipt.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise UALError("ROUTE_RECEIPT_STATUS_INVALID",
                       f"exit_code={exit_code!r}")
    for field in ("requested_model", "model_observed"):
        value = receipt.get(field)
        if not isinstance(value, str) or not value.strip():
            raise UALError("ROUTE_RECEIPT_MODEL_MISSING", field)
    kind = receipt.get("kind")
    if kind not in ROUTE_KINDS:
        raise UALError("ROUTE_RECEIPT_KIND_INVALID", str(kind))
    if kind == ROUTE_KIND_RESULT:
        if result_path is None:
            raise UALError("ROUTE_RECEIPT_KIND_INVALID",
                           "result receipt without a result file")
        binding = receipt.get("result") or {}
        data = result_path.read_bytes()
        if binding.get("path") is not None and \
                _ri(project, str(binding["path"]),
                    label="ROUTE_RESULT") != result_path.resolve(
                        strict=False):
            raise UALError("ROUTE_RECEIPT_RESULT_BYTES_MISMATCH",
                           str(binding.get("path")))
        if binding.get("sha256") != sha256_hex(data) or \
                binding.get("bytes") != len(data):
            raise UALError("ROUTE_RECEIPT_RESULT_BYTES_MISMATCH", receipt_rel)
    else:
        binding = receipt.get("raw_error") or {}
        raw_rel = binding.get("path")
        if not isinstance(raw_rel, str) or not raw_rel:
            raise UALError("ROUTE_RECEIPT_RAW_BYTES_MISMATCH",
                           "raw_error.path missing")
        raw_path = _ri(project, raw_rel, label="ROUTE_RAW")
        if not raw_path.is_file():
            raise UALError("ROUTE_RECEIPT_RAW_BYTES_MISMATCH", raw_rel)
        raw_data = raw_path.read_bytes()
        if binding.get("sha256") != sha256_hex(raw_data) or \
                binding.get("bytes") != len(raw_data):
            raise UALError("ROUTE_RECEIPT_RAW_BYTES_MISMATCH", raw_rel)
        raw_evidence = _structured_raw_evidence(raw_data, raw_rel)
        for field in ("provider_status", "error_code", "terminal"):
            if binding.get(field) != raw_evidence.get(field):
                raise UALError("ROUTE_RECEIPT_RAW_EVIDENCE_MISMATCH",
                               field)
        if raw_evidence.get("terminal") is not True:
            raise UALError("ROUTE_RECEIPT_NOT_TERMINAL", raw_rel)
    return receipt


def _structured_raw_evidence(data: bytes, label: str) -> dict:
    """Read provider-failure facts from the bound raw bytes themselves.

    CLI flags may cross-check these facts, but can never manufacture them.
    """
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        raise UALError("ROUTE_RECEIPT_RAW_EVIDENCE_INVALID", label)
    terminal = payload.get("terminal")
    provider_status = payload.get("provider_status")
    error_code = payload.get("error_code")
    if terminal is not True:
        raise UALError("ROUTE_RECEIPT_NOT_TERMINAL", label)
    if isinstance(provider_status, bool) or \
            (provider_status is not None and
             not isinstance(provider_status, int)):
        raise UALError("ROUTE_RECEIPT_RAW_EVIDENCE_INVALID",
                       "provider_status")
    if error_code is not None and \
            (not isinstance(error_code, str) or not error_code.strip()):
        raise UALError("ROUTE_RECEIPT_RAW_EVIDENCE_INVALID", "error_code")
    return {"provider_status": provider_status,
            "error_code": error_code,
            "terminal": terminal}


def quota_classification(receipt: dict):
    """Mechanically derive PRIMARY_QUOTA_EXHAUSTED from structured raw
    provider-error evidence (HTTP/API status 429 or an explicit provider
    quota code) with a terminal error. Provider-neutral; prose alone is
    never sufficient."""
    raw = receipt.get("raw_error") or {}
    if raw.get("terminal") is not True:
        return None
    if raw.get("provider_status") == 429:
        return "PRIMARY_QUOTA_EXHAUSTED"
    if raw.get("error_code") == "PROVIDER_QUOTA_EXHAUSTED":
        return "PRIMARY_QUOTA_EXHAUSTED"
    return None


def record_route_receipt(project: Path, task: dict, package_rel: str,
                         kind: str, requested_model: str,
                         model_observed: str, exit_code: int,
                         status: str, out_rel: str,
                         result_rel: str | None = None,
                         raw_error_rel: str | None = None,
                         provider_status=None, error_code=None,
                         terminal=None) -> dict:
    """Write-once builder for one immutable bound route receipt. Package
    identity is verified; result/raw bindings capture exact path, bytes
    and SHA-256 at creation time."""
    task_id = task["id"]
    verified = verify_package(project, task_id, package_rel)
    if kind not in ROUTE_KINDS:
        raise UALError("ROUTE_RECEIPT_KIND_INVALID", kind)
    if status != "FINISHED":
        raise UALError("ROUTE_RECEIPT_STATUS_INVALID", status)
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise UALError("ROUTE_RECEIPT_STATUS_INVALID",
                       f"exit_code={exit_code!r}")
    for value in (requested_model, model_observed):
        if not isinstance(value, str) or not value.strip():
            raise UALError("ROUTE_RECEIPT_MODEL_MISSING", "")
    receipt = {
        "schema": ROUTE_RECEIPT_SCHEMA,
        "kind": kind,
        "task": task_id,
        "package": package_rel,
        "package_manifest_sha256": verified["manifest_sha256"],
        "package_payload_sha256": verified["payload_sha256"],
        "requested_model": requested_model,
        "model_observed": model_observed,
        "status": status,
        "exit_code": exit_code,
        "recorded_at": _now(),
    }
    if kind == ROUTE_KIND_RESULT:
        if not result_rel:
            raise UALError("ROUTE_RECEIPT_RESULT_BYTES_MISMATCH",
                           "result receipt requires --result-file")
        result_path = resolve_inside(project, result_rel,
                                     label="ROUTE_RESULT")
        if not result_path.is_file():
            raise UALError("ROUTE_RECEIPT_RESULT_BYTES_MISMATCH", result_rel)
        data = result_path.read_bytes()
        receipt["result"] = {"path": result_rel, "bytes": len(data),
                             "sha256": sha256_hex(data)}
    else:
        if not raw_error_rel:
            raise UALError("ROUTE_RECEIPT_RAW_BYTES_MISMATCH",
                           "failure receipt requires --raw-error-file")
        raw_path = resolve_inside(project, raw_error_rel,
                                  label="ROUTE_RAW")
        if not raw_path.is_file():
            raise UALError("ROUTE_RECEIPT_RAW_BYTES_MISMATCH", raw_error_rel)
        data = raw_path.read_bytes()
        raw_evidence = _structured_raw_evidence(data, raw_error_rel)
        supplied = {"provider_status": provider_status,
                    "error_code": error_code,
                    "terminal": terminal}
        for field, value in supplied.items():
            if value is not None and value != raw_evidence.get(field):
                raise UALError("ROUTE_RECEIPT_RAW_EVIDENCE_MISMATCH",
                               field)
        binding = {"path": raw_error_rel, "bytes": len(data),
                   "sha256": sha256_hex(data), **raw_evidence}
        receipt["raw_error"] = binding
    from .hashing import exclusive_write_json
    out_path = resolve_inside(project, out_rel, label="ROUTE_RECEIPT_OUT")
    exclusive_write_json(out_path, receipt, max_bytes=ROUTE_RECEIPT_MAX_BYTES)
    return {"ok": True, "path": str(out_path),
            "sha256": sha256_hex(out_path.read_bytes())}


def _quota_receipt_ok(project: Path, task: dict, package_rel: str,
                      policy: dict, verified: dict) -> bool:
    from .attempts import current_dir
    task_id = task["id"]
    receipts_dir = current_dir(project, task_id) / "audit" / "receipts"
    if not receipts_dir.is_dir():
        return False
    for entry in sorted(receipts_dir.iterdir()):
        if not entry.name.startswith("quota_"):
            continue
        receipt = load_json(entry, max_bytes=64 * 1024)
        if not isinstance(receipt, dict):
            continue
        if receipt.get("schema") != "ual-audit-quota-receipt/1" or \
                receipt.get("task") != task_id:
            continue
        if receipt.get("reason") != "PRIMARY_QUOTA_EXHAUSTED":
            continue
        if receipt.get("package_manifest_sha256") != \
                verified.get("manifest_sha256") or \
                receipt.get("package_payload_sha256") != \
                verified.get("payload_sha256"):
            continue
        if receipt.get("fallback") != policy.get("fallback"):
            continue
        route_binding = receipt.get("route_receipt") or {}
        route_rel = route_binding.get("path")
        if not isinstance(route_rel, str) or not route_rel:
            continue
        try:
            route_path = resolve_inside(project, route_rel,
                                        label="ROUTE_RECEIPT")
            route_bytes = route_path.read_bytes()
            if route_binding.get("bytes") != len(route_bytes) or \
                    route_binding.get("sha256") != sha256_hex(route_bytes):
                continue
            route = load_route_receipt(project, route_rel, task, verified)
        except (OSError, UALError):
            continue
        if route.get("kind") != ROUTE_KIND_FAILURE or \
                route.get("requested_model") != policy.get("primary") or \
                route.get("model_observed") != policy.get("primary") or \
                route.get("exit_code") == 0 or \
                quota_classification(route) != "PRIMARY_QUOTA_EXHAUSTED":
            continue
        return True
    return False


def record_quota_receipt(project: Path, task: dict, package_rel: str,
                         reason: str,
                         route_receipt_rel: str | None = None) -> dict:
    """One machine-readable primary-quota receipt bound to the exact
    frozen package AND a fully bound primary failure route receipt whose
    structured raw provider-error evidence mechanically classifies as
    PRIMARY_QUOTA_EXHAUSTED. ``--reason`` is only a cross-check."""
    from . import authority
    task_id = task["id"]
    if not route_receipt_rel:
        raise UALError("QUOTA_ROUTE_RECEIPT_REQUIRED",
                       "a bound primary failure route receipt is required")
    verified = verify_package(project, task_id, package_rel)
    route = load_route_receipt(project, route_receipt_rel, task, verified)
    if route.get("kind") != ROUTE_KIND_FAILURE:
        raise UALError("QUOTA_ROUTE_RECEIPT_INVALID",
                       f"kind={route.get('kind')!r}; a primary failure "
                       f"route receipt is required")
    policy = (authority.load_config(project) or {}).get("audit_policy") or {}
    primary = policy.get("primary")
    if not primary or \
            route.get("requested_model") != primary or \
            route.get("model_observed") != primary:
        raise UALError("QUOTA_ROUTE_RECEIPT_INVALID",
                       "failure receipt must bind the configured primary "
                       "as both requested and observed model")
    if route.get("exit_code") == 0:
        raise UALError("QUOTA_ROUTE_RECEIPT_INVALID",
                       "a terminal primary failure requires a nonzero "
                       "exit")
    classification = quota_classification(route)
    if classification is None:
        raise UALError("QUOTA_CLASSIFICATION_UNPROVEN",
                       "raw provider error lacks terminal 429/quota-code "
                       "evidence")
    if reason != classification:
        raise UALError("QUOTA_RECEIPT_REASON_INVALID",
                       f"{reason!r} != derived {classification!r}")
    from .attempts import current_dir
    from .hashing import exclusive_write_json, next_sequence
    directory = current_dir(project, task_id) / "audit" / "receipts"
    directory.mkdir(parents=True, exist_ok=True)
    sequence = next_sequence(directory, "quota_", ".json", max_files=128)
    route_path = resolve_inside(project, route_receipt_rel,
                                label="ROUTE_RECEIPT")
    receipt = {
        "schema": "ual-audit-quota-receipt/1",
        "task": task_id,
        "package": package_rel,
        "package_manifest_sha256": verified["manifest_sha256"],
        "package_payload_sha256": verified["payload_sha256"],
        "route_receipt": {"path": route_receipt_rel,
                          "bytes": route_path.stat().st_size,
                          "sha256": sha256_hex(route_path.read_bytes())},
        "primary": primary,
        "fallback": policy.get("fallback"),
        "reason": reason,
        "recorded_at": _now(),
    }
    path = directory / f"quota_{sequence:04d}.json"
    exclusive_write_json(path, receipt, max_bytes=64 * 1024)
    return {"ok": True, "path": str(path), "reason": reason}


def record_audit(project: Path, task: dict, package_rel: str,
                 result_rel: str,
                 route_receipt_rel: str | None = None,
                 allow_fallback: bool = False) -> dict:
    from . import authority
    from . import envelope as envelope_mod
    task_id = task["id"]
    verified = verify_package(project, task_id, package_rel)
    envelope_mod.verify_envelope(project, task)
    _envelope_path, envelope = envelope_mod.latest_envelope(project, task_id)
    if envelope.get("candidate_sha256") != verified.get("candidate_sha256"):
        raise UALError("AUDIT_CANDIDATE_MISMATCH",
                       "the package is not bound to the current frozen "
                       "candidate")
    result_path = resolve_inside(project, result_rel, label="AUDIT_RESULT")
    if not result_path.is_file():
        raise UALError("AUDIT_RESULT_MISSING", result_rel)
    data = result_path.read_bytes()
    if len(data) > RESULT_MAX_BYTES:
        raise UALError("AUDIT_RESULT_OVER_BOUND", result_rel)
    try:
        verdict_payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        verdict_payload = None
    verdict = None
    findings_ok = False
    requested_model = None
    if isinstance(verdict_payload, dict):
        raw_verdict = verdict_payload.get("verdict")
        requested_model = verdict_payload.get("requested_model")
        if raw_verdict in VALID_VERDICTS:
            verdict = raw_verdict
            findings = verdict_payload.get("findings")
            findings_ok = isinstance(findings, list) and all(
                isinstance(f, dict)
                and f.get("severity") in VALID_SEVERITIES
                and isinstance(f.get("location"), str)
                and f.get("location")
                and isinstance(f.get("observed_evidence"), str)
                and f.get("observed_evidence")
                for f in findings)
        if verdict_payload.get("requested_model") is None:
            verdict = None
    policy = (authority.load_config(project) or {}).get("audit_policy") or {}
    primary = policy.get("primary")
    fallback = policy.get("fallback")
    audit_required = bool((task.get("audit") or {}).get("required"))
    route = None
    route_model = None
    route_exit_code = None
    if route_receipt_rel:
        route = load_route_receipt(project, route_receipt_rel, task,
                                   verified, result_path=result_path)
        route_model = route.get("model_observed")
        route_exit_code = route.get("exit_code")
    if primary:
        # Required configured-primary policy: a fully bound route receipt
        # is mandatory, and identity is proven by the receipt, never by
        # auditor self-assertion.
        if route is None:
            raise UALError(
                "AUDIT_PRIMARY_IDENTITY_REQUIRED",
                "a required audit with a configured primary needs a bound "
                "ual-audit-route-receipt/1")
        if route.get("kind") == ROUTE_KIND_FAILURE:
            raise UALError(
                "AUDIT_ROUTE_KIND_INVALID",
                "a provider-failure receipt cannot record an audit result; "
                "use quota-receipt then dispatch the fallback")
        observed = route.get("model_observed")
        if route.get("requested_model") != observed:
            raise UALError("AUDIT_ROUTE_MODEL_MISMATCH",
                           "route requested and observed models differ")
        if observed == fallback:
            if not _quota_receipt_ok(project, task, package_rel,
                                     policy, verified):
                raise UALError("AUDIT_FALLBACK_NOT_PERMITTED",
                               "the fallback auditor needs a machine-"
                               "readable PRIMARY_QUOTA_EXHAUSTED receipt "
                               "for this exact frozen package")
        elif observed != primary:
            raise UALError("AUDIT_MODEL_NOT_PRIMARY",
                           f"observed {observed!r} is neither the "
                           f"configured primary nor fallback auditor")
        if requested_model is not None and requested_model != observed:
            raise UALError(
                "AUDIT_RESULT_MODEL_MISMATCH",
                f"result requested_model {requested_model!r} does not match "
                f"observed route model {observed!r}")
        if verdict == "PASS" and route_exit_code != 0:
            raise UALError("AUDIT_PRIMARY_EXIT_NONZERO",
                           "a primary PASS requires terminal exit 0")
        if verdict in ("FAIL", "BLOCKED"):
            # A structurally present negative primary verdict is classified
            # before any route-failure fallback: invalid findings stay
            # AUDIT_RESULT_INVALID, valid ones stay a real result. Neither
            # is a fallback trigger.
            if not findings_ok:
                raise UALError("AUDIT_RESULT_INVALID",
                               f"negative verdict {verdict} carries "
                               f"malformed findings; fallback is never a "
                               f"repair for a negative verdict")
            disposition = "AUDIT_RESULT"
        elif verdict is not None:
            if not findings_ok:
                raise UALError("AUDIT_RESULT_INVALID",
                               f"{verdict} findings structure invalid")
            disposition = "AUDIT_RESULT"
        else:
            raise UALError("AUDIT_RESULT_INVALID",
                           "no valid inner verdict; exit zero is never "
                           "a PASS")
    else:
        # Optional configuration without a named primary: honest UNKNOWN
        # identity, objective-failure fallback still evidence-bound.
        observed_model = route_model or "UNKNOWN"
        if verdict in ("FAIL", "BLOCKED"):
            if not findings_ok:
                raise UALError("AUDIT_RESULT_INVALID",
                               f"negative verdict {verdict} carries "
                               f"malformed findings")
            disposition = "AUDIT_RESULT"
        elif verdict is not None and (findings_ok or verdict == "PASS"):
            disposition = "AUDIT_RESULT"
        else:
            if not verified.get("ok"):
                raise UALError("AUDIT_PACKAGE_INTEGRITY_BLOCKED", package_rel)
            route_failure = route is not None and \
                route.get("kind") == ROUTE_KIND_FAILURE
            if allow_fallback:
                from .paths import state_root
                config_path = state_root(project) / "config.json"
                policy_enabled = False
                if config_path.is_file():
                    config = load_json(config_path, max_bytes=64 * 1024)
                    policy_enabled = bool(
                        (config.get("audit_policy") or {})
                        .get("fallback_enabled"))
                if policy_enabled and route_failure:
                    disposition = "FALLBACK_REQUIRED"
                else:
                    raise UALError("AUDIT_FALLBACK_NOT_AUTHORIZED",
                                   "policy or objective route failure "
                                   "missing")
            else:
                raise UALError("AUDIT_RESULT_INVALID",
                               "no valid inner verdict; exit zero is never "
                               "a PASS")
    from .attempts import current_dir
    directory = current_dir(project, task_id) / "audit" / "records"
    directory.mkdir(parents=True, exist_ok=True)
    from .hashing import exclusive_write_json, next_sequence
    sequence = next_sequence(directory, "audit_", ".json", max_files=128)
    record = {
        "schema": "ual-audit-record/1",
        "task": task_id,
        "package": package_rel,
        "package_manifest_sha256": verified.get("manifest_sha256"),
        "package_payload_sha256": verified.get("payload_sha256"),
        "package_sha256": _package_digest(project, package_rel),
        "envelope_sha256": verified.get("envelope_sha256"),
        "candidate_sha256": verified.get("candidate_sha256"),
        "authority_sha256": authority.config_digest(project),
        "route_receipt": ({"path": route_receipt_rel,
                           "sha256": sha256_hex(
                               resolve_inside(project, route_receipt_rel,
                                              label="ROUTE_RECEIPT")
                               .read_bytes())}
                          if route_receipt_rel and route is not None
                          else None),
        "disposition": disposition,
        "verdict": verdict,
        "findings_valid": findings_ok if verdict is not None else None,
        "observed_model": (route.get("model_observed") if route is not None
                           else "UNKNOWN"),
        "route_exit_code": route_exit_code,
        "result": {"path": result_rel, "bytes": len(data),
                   "sha256": sha256_hex(data)},
        "result_sha256": sha256_hex(data),
        "recorded_at": _now(),
    }
    path = directory / f"audit_{sequence:04d}.json"
    exclusive_write_json(path, record, max_bytes=64 * 1024)
    payload = {"ok": True, "disposition": disposition,
               "verdict": verdict,
               "observed_model": record["observed_model"]}
    if disposition == "FALLBACK_REQUIRED":
        payload["fallback"] = "FALLBACK_REQUIRED"
    return payload


def validate_record_for_acceptance(project: Path, task: dict,
                                   record: dict,
                                   envelope_sha256: str) -> None:
    """Revalidate an audit record against current policy and live bytes.

    Acceptance cannot trust the policy that happened to be present when the
    record was created: a transient edit may have been reverted byte-for-byte.
    """
    from . import authority
    if not isinstance(record, dict) or \
            record.get("schema") != "ual-audit-record/1" or \
            record.get("task") != task["id"] or \
            record.get("disposition") != "AUDIT_RESULT":
        raise UALError("ACCEPTANCE_AUDIT_REQUIRED", task["id"])
    if record.get("verdict") != "PASS":
        raise UALError("ACCEPTANCE_AUDIT_NOT_CLEAN_PASS",
                       f"verdict={record.get('verdict')}; acceptance "
                       f"requires a clean PASS")
    if record.get("envelope_sha256") != envelope_sha256:
        raise UALError("ACCEPTANCE_AUDIT_STALE", task["id"])

    package_rel = record.get("package")
    if not isinstance(package_rel, str) or not package_rel:
        raise UALError("ACCEPTANCE_AUDIT_PACKAGE_INVALID", task["id"])
    verified = verify_package(project, task["id"], package_rel)
    if record.get("package_manifest_sha256") != \
            verified.get("manifest_sha256") or \
            record.get("package_payload_sha256") != \
            verified.get("payload_sha256") or \
            record.get("package_sha256") != \
            _package_digest(project, package_rel) or \
            record.get("candidate_sha256") != \
            verified.get("candidate_sha256") or \
            record.get("envelope_sha256") != \
            verified.get("envelope_sha256"):
        raise UALError("ACCEPTANCE_AUDIT_PACKAGE_INVALID", task["id"])

    result_binding = record.get("result") or {}
    result_rel = result_binding.get("path")
    if not isinstance(result_rel, str) or not result_rel:
        raise UALError("ACCEPTANCE_AUDIT_RESULT_INVALID", task["id"])
    result_path = resolve_inside(project, result_rel, label="AUDIT_RESULT")
    if not result_path.is_file():
        raise UALError("ACCEPTANCE_AUDIT_RESULT_INVALID", result_rel)
    result_data = result_path.read_bytes()
    if result_binding.get("bytes") != len(result_data) or \
            result_binding.get("sha256") != sha256_hex(result_data) or \
            record.get("result_sha256") != sha256_hex(result_data):
        raise UALError("ACCEPTANCE_AUDIT_RESULT_INVALID", result_rel)

    policy = (authority.load_config(project) or {}).get("audit_policy") or {}
    if record.get("authority_sha256") != authority.config_digest(project):
        raise UALError("ACCEPTANCE_AUDIT_POLICY_MISMATCH",
                       "audit was recorded under a different authority policy")
    try:
        result_payload = json.loads(result_data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        result_payload = None
    if not isinstance(result_payload, dict) or \
            result_payload.get("verdict") != "PASS":
        raise UALError("ACCEPTANCE_AUDIT_RESULT_INVALID", result_rel)
    primary = policy.get("primary")
    route_binding = record.get("route_receipt")
    if not primary:
        if route_binding is None and record.get("observed_model") == "UNKNOWN":
            return
    if not isinstance(route_binding, dict):
        raise UALError("ACCEPTANCE_AUDIT_POLICY_MISMATCH",
                       "current primary policy requires a bound route receipt")
    route_rel = route_binding.get("path")
    if not isinstance(route_rel, str) or not route_rel:
        raise UALError("ACCEPTANCE_AUDIT_POLICY_MISMATCH",
                       "route receipt path missing")
    route_path = resolve_inside(project, route_rel, label="ROUTE_RECEIPT")
    if not route_path.is_file() or \
            route_binding.get("sha256") != sha256_hex(route_path.read_bytes()):
        raise UALError("ACCEPTANCE_AUDIT_POLICY_MISMATCH",
                       "route receipt drifted")
    route = load_route_receipt(project, route_rel, task, verified,
                               result_path=result_path)
    observed = route.get("model_observed")
    if route.get("kind") != ROUTE_KIND_RESULT or \
            route.get("requested_model") != observed or \
            result_payload.get("requested_model") != observed or \
            record.get("observed_model") != observed or \
            record.get("route_exit_code") != route.get("exit_code"):
        raise UALError("ACCEPTANCE_AUDIT_POLICY_MISMATCH",
                       "audit route identity does not match the record")
    if primary and observed == primary:
        if route.get("exit_code") != 0:
            raise UALError("ACCEPTANCE_AUDIT_POLICY_MISMATCH",
                           "primary PASS requires exit 0")
        return
    fallback = policy.get("fallback")
    if primary and observed == fallback and \
            _quota_receipt_ok(project, task, package_rel, policy, verified):
        return
    if primary:
        raise UALError("ACCEPTANCE_AUDIT_POLICY_MISMATCH",
                       f"observed {observed!r} is not the current primary "
                       "or an authorized fallback")


def audit_status(project: Path, task_id: str) -> dict:
    from .attempts import current_dir
    latest_pass = None
    try:
        directory = current_dir(project, task_id) / "audit" / "records"
    except UALError:
        return {"ok": True, "latest_pass": None}
    if directory.is_dir():
        for entry in sorted(directory.iterdir()):
            if not entry.name.startswith("audit_"):
                continue
            record = load_json(entry, max_bytes=64 * 1024)
            if record.get("disposition") == "AUDIT_RESULT" and \
                    record.get("verdict") in ("PASS", "CONDITIONAL_PASS"):
                latest_pass = record.get("envelope_sha256")
    return {"ok": True, "latest_pass": latest_pass}


def _package_digest(project: Path, package_rel: str) -> str:
    directory = resolve_inside(project, package_rel, label="AUDIT_PACKAGE")
    hasher = None
    import hashlib
    hasher = hashlib.sha256()
    for entry in sorted(directory.iterdir()):
        if entry.is_file():
            hasher.update(entry.name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(sha256_hex(entry.read_bytes()).encode("ascii"))
            hasher.update(b"\n")
    return hasher.hexdigest()


def _now() -> str:
    from .claims import utc_now_iso
    return utc_now_iso()

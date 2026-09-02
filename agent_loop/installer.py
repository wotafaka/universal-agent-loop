"""Minimal installer lifecycle: plan -> dry-run -> apply -> doctor.

Installs a source tree into a target project under one ownership
manifest (``<target>/.ual-install/ownership.json``). Only installer-
owned files may later be updated; an existing unowned project file is
refused, never overwritten. The doctor verifies owned bytes and reports
modified or missing files; re-apply updates only owned files.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .errors import UALError
from .hashing import atomic_write_json, load_json, sha256_hex

MANIFEST_SCHEMA = "ual-install-ownership/1"
OWNERSHIP_DIR = ".ual-install"
MAX_FILES = 8192
MAX_TOTAL_BYTES = 512 * 1024 * 1024


def _ownership_path(target: Path) -> Path:
    from .paths import resolve_inside
    return resolve_inside(Path(target), OWNERSHIP_DIR + "/ownership.json",
                          label="INSTALL_OWNERSHIP")


def _scan_source(source: Path) -> dict:
    from .paths import resolve_inside
    source_root = Path(source)
    if not source_root.is_dir():
        raise UALError("INSTALL_SOURCE_MISSING", str(source))
    resolved_root = source_root.resolve(strict=False)
    members = {}
    total = 0
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_root).as_posix()
        if rel.startswith(OWNERSHIP_DIR + "/"):
            continue
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            raise UALError("INSTALL_SOURCE_ESCAPE",
                           rel + " resolves outside the source root") from None
        data = resolved.read_bytes()
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise UALError("INSTALL_SOURCE_OVER_BOUND", str(total))
        members[rel] = {"bytes": len(data), "sha256": sha256_hex(data)}
        if len(members) > MAX_FILES:
            raise UALError("INSTALL_SOURCE_FILE_BOUND", str(MAX_FILES))
    if not members:
        raise UALError("INSTALL_SOURCE_EMPTY", str(source))
    return members


def _plan(source: Path, target: Path) -> tuple:
    source = Path(source)
    target = Path(target)
    members = _scan_source(source)
    target_root = target.resolve(strict=False)
    if target.exists() and not target_root.is_dir():
        raise UALError("INSTALL_TARGET_ESCAPE", str(target))
    ownership = _load_ownership(target)
    copy = []
    update = []
    refused = []
    for rel, meta in sorted(members.items()):
        destination = target / rel
        if destination.exists() or destination.is_symlink():
            resolved = destination.resolve(strict=False)
            try:
                resolved.relative_to(target_root)
            except ValueError:
                refused.append({"path": rel,
                                "reason": "resolves outside the target root"})
                continue
            if destination.is_symlink() and not destination.exists():
                refused.append({"path": rel,
                                "reason": "dangling symlink in target"})
                continue
        if not destination.exists():
            copy.append({"path": rel, **meta})
        elif rel in ownership:
            current = destination.read_bytes()
            if sha256_hex(current) != meta["sha256"]:
                update.append({"path": rel, **meta})
        else:
            refused.append({"path": rel,
                            "reason": "existing unowned project file"})
    return members, ownership, {"copy": copy, "update": update,
                                "refused": refused}


def _load_ownership(target: Path) -> dict:
    path = _ownership_path(target)
    if not path.is_file():
        return {}
    manifest = load_json(path, max_bytes=1024 * 1024)
    if not isinstance(manifest, dict) or \
            manifest.get("schema") != MANIFEST_SCHEMA:
        raise UALError("INSTALL_OWNERSHIP_MALFORMED", str(path))
    members = manifest.get("owned") or {}
    if not isinstance(members, dict):
        raise UALError("INSTALL_OWNERSHIP_MALFORMED", str(path))
    return members


def plan_install(source: Path, target: Path) -> dict:
    _members, _ownership, plan = _plan(Path(source), Path(target))
    return {"ok": True, "mode": "plan", **plan,
            "note": "refused entries are never overwritten; only "
                    "installer-owned files may be updated"}


def dry_run(source: Path, target: Path) -> dict:
    _members, _ownership, plan = _plan(Path(source), Path(target))
    return {"ok": True, "mode": "dry-run", **plan,
            "wrote": False}


def apply_install(source: Path, target: Path) -> dict:
    source = Path(source)
    target = Path(target)
    members, ownership, plan = _plan(source, target)
    if plan["refused"]:
        raise UALError("INSTALL_REFUSED_UNOWNED_OVERWRITE",
                       ";".join(item["path"]
                                for item in plan["refused"][:4]))
    copied = 0
    from .paths import resolve_inside
    for item in plan["copy"] + plan["update"]:
        rel = item["path"]
        contained = resolve_inside(target, rel, label="INSTALL_DEST")
        contained.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / rel, contained)
        actual = sha256_hex(contained.read_bytes())
        if actual != item["sha256"]:
            raise UALError("INSTALL_COPY_IDENTITY_MISMATCH", rel)
        ownership[rel] = {"bytes": item["bytes"], "sha256": item["sha256"]}
        copied += 1
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "owned": ownership,
        "updated_count": copied,
    }
    atomic_write_json(_ownership_path(target), manifest,
                      max_bytes=1024 * 1024)
    return {"ok": True, "mode": "apply", "copied": copied,
            "owned_total": len(ownership)}


def doctor(source: Path, target: Path) -> dict:
    source = Path(source)
    target = Path(target)
    ownership = _load_ownership(target)
    modified = []
    missing = []
    for rel in sorted(ownership):
        destination = target / rel
        if not destination.is_file():
            missing.append(rel)
            continue
        expected = ownership[rel].get("sha256")
        if expected and sha256_hex(destination.read_bytes()) != expected:
            modified.append(rel)
    members = _scan_source(source) if source.is_dir() else {}
    available_updates = sorted(
        rel for rel, meta in members.items()
        if rel in ownership and (target / rel).is_file() and
        sha256_hex((target / rel).read_bytes()) != meta["sha256"])
    return {"ok": True, "mode": "doctor", "modified": modified,
            "missing": missing, "available_updates": available_updates,
            "owned_total": len(ownership)}

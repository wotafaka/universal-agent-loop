"""Canonical bytes, digests and bounded atomic writes.

Digests are SHA-256 over exact stored bytes with no implicit
normalization. Current-state files are replaced atomically through a
temporary file plus ``os.replace``; write-once evidence is created
exclusively so two writers can never both succeed. Every durable write
carries a declared byte bound.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .errors import UALError

DEFAULT_MAX_BYTES = 8 * 1024 * 1024


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"))


def canonical_json_bytes(value) -> bytes:
    return canonical_json(value).encode("utf-8")


def member_digest(pairs) -> str | None:
    """SHA-256 over ``name\\0sha256-of-stored-bytes\\n`` in declared order.

    Returns ``None`` when no comparable digest exists (no members, or any
    member without a complete digest); ``None`` never equals a capture.
    """
    if not pairs:
        return None
    hasher = hashlib.sha256()
    for name, sha in pairs:
        if not isinstance(name, str) or not name:
            return None
        if not isinstance(sha, str) or len(sha) != 64:
            return None
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(sha.encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def load_json(path: Path, *, max_bytes: int = DEFAULT_MAX_BYTES):
    path = Path(path)
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise UALError("JSON_OVER_BOUND", str(path))
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise UALError("JSON_UNREADABLE", str(path)) from None


def atomic_write_json(path: Path, payload, *, max_bytes: int) -> bytes:
    data = (json.dumps(payload, ensure_ascii=True, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")
    atomic_write_bytes(path, data, max_bytes=max_bytes)
    return data


def atomic_write_bytes(path: Path, data: bytes, *, max_bytes: int) -> bytes:
    if len(data) > max_bytes:
        raise UALError("WRITE_OVER_BOUND", str(path))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent),
                                    prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return data


def exclusive_write_bytes(path: Path, data: bytes, *,
                          max_bytes: int) -> bytes:
    if len(data) > max_bytes:
        raise UALError("WRITE_OVER_BOUND", str(path))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        raise UALError("TARGET_EXISTS", str(path)) from None
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return data


def exclusive_write_json(path: Path, payload, *, max_bytes: int) -> bytes:
    data = (json.dumps(payload, ensure_ascii=True, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")
    exclusive_write_bytes(path, data, max_bytes=max_bytes)
    return data


def next_sequence(directory: Path, prefix: str, suffix: str,
                  *, max_files: int) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    numbers = []
    for entry in directory.iterdir():
        name = entry.name
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        middle = name[len(prefix):-len(suffix)] if suffix else name[len(prefix):]
        if middle.isdigit():
            numbers.append(int(middle))
    sequence = max(numbers, default=0) + 1
    if sequence > max_files:
        raise UALError("SEQUENCE_EXHAUSTED", f"{prefix}*{suffix}")
    return sequence

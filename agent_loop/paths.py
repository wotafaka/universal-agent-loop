"""Explicit project-root path resolution with containment enforcement.

The runtime always operates on an explicit arbitrary project root and
keeps its state under ``<project>/.agent-loop/``. Every relative path is
resolved and proven to stay inside the resolved root before any byte is
read or written; escaping absolute paths, drives or links refuse closed.
Task identifiers are validated at the same choke point so a raw CLI
string can never compose an escaping state path.
"""
from __future__ import annotations

import re
import stat as _stat
from pathlib import Path

from .errors import UALError

STATE_DIRNAME = ".agent-loop"
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def state_root(project: Path) -> Path:
    return Path(project) / STATE_DIRNAME


def validate_task_id(task_id: str) -> str:
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id or ""):
        raise UALError("TASK_ID_INVALID", repr(task_id))
    return task_id


def task_dir(project: Path, task_id: str) -> Path:
    validate_task_id(task_id)
    return state_root(project) / "tasks" / task_id


def claims_dir(project: Path) -> Path:
    return state_root(project) / "claims"


def runs_dir(project: Path) -> Path:
    return state_root(project) / "runs"


def run_dir(project: Path, run_id: str) -> Path:
    return runs_dir(project) / run_id


def resolve_inside(project: Path, rel: str, *, label: str = "PATH") -> Path:
    """Resolve ``rel`` under ``project`` and refuse any escape."""
    if not isinstance(rel, str) or not rel.strip():
        raise UALError(f"{label}_REQUIRED", "")
    raw = Path(rel)
    if raw.is_absolute() or raw.drive or raw.root:
        raise UALError(f"{label}_ESCAPE", rel)
    root = Path(project).resolve(strict=False)
    candidate = (root / raw).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError:
        raise UALError(f"{label}_ESCAPE", rel) from None
    return candidate


def inside_rel(project: Path, path: Path) -> str:
    root = Path(project).resolve(strict=False)
    return Path(path).resolve(strict=False).relative_to(root).as_posix()


def read_regular_file(project: Path, rel: str, *, label: str,
                      max_bytes: int) -> bytes:
    """Containment read for task-supplied transmission paths.

    Resolves ``rel`` inside ``project`` (absolute paths, drives and
    ``..`` escapes refuse), refuses any symlink or Windows junction
    component along the way, requires a regular file, and enforces a
    hard byte cap before any byte is returned."""
    path = resolve_inside(project, rel, label=label)
    current = Path(project).resolve(strict=False)
    for part in Path(rel).parts:
        current = current / part
        if current.is_symlink() or _is_junction(current):
            raise UALError(f"{label}_ESCAPE", rel)
    if not path.is_file():
        raise UALError(f"{label}_NOT_FILE", rel)
    info = path.stat()
    if not _stat.S_ISREG(info.st_mode):
        raise UALError(f"{label}_NOT_FILE", rel)
    if info.st_size > max_bytes:
        raise UALError(f"{label}_OVER_BOUND", rel)
    return path.read_bytes()


def _is_junction(path: Path) -> bool:
    probe = getattr(path, "is_junction", None)
    if probe is None:
        return False
    try:
        return bool(probe())
    except OSError:
        return False

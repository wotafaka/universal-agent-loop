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

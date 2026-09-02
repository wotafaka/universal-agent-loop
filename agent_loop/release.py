"""Exact public release construction: allowlist, secret gate, manifest.

The publishable archive is built exclusively from one versioned
allowlist of exact repository-relative paths (``release-allowlist/1``).
Nothing outside the allowlist can enter the archive, so a stray private
file can never ship. The builder refuses missing, duplicate,
non-canonical, escaping or symlink/junction members, scans every
included byte sequence for a conservative documented set of secret and
credential patterns before writing anything, emits deterministic ZIP
metadata/order, and writes an exact generated manifest with member
bytes and SHA-256. Verification recomputes the archive membership and
hashes against that manifest; any drift refuses. This is release
hygiene, not a proof that a remote upload happened.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from .errors import UALError
from .hashing import atomic_write_bytes, load_json, sha256_hex

ALLOWLIST_SCHEMA = "release-allowlist/1"
MANIFEST_SCHEMA = "release-manifest/1"
MANIFEST_MAX_BYTES = 4 * 1024 * 1024
ZIP_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
MAX_MEMBER_BYTES = 64 * 1024 * 1024

CANONICAL_PATH_RE = re.compile(
    r"^[.A-Za-z0-9][A-Za-z0-9._\-]*(?:/[.A-Za-z0-9._\-]+)*$")

# Always-refused private engineering members, even if someone lists them.
PRIVATE_MEMBERS = (
    ".env", "PACKAGED_FILES.json", "docs/SOURCE_SNAPSHOT.json",
    "IMPLEMENTATION_REPORT.md", "REPAIR_TASK.md", "REVIEW_BATCH_1.md",
    "AUTHORITY_REPAIR_DECISION.md", "CONTINUATION_TASK_1.md",
    "CONTINUATION_TASK_2.md", "CONTINUATION_TASK_3.md",
    "CONTINUATION_TASK_4.md", "CONTINUATION_TASK_5.md",
)
PRIVATE_PREFIXES = (".source/", ".validation/", "archive/")

# Conservative, documented secret/credential patterns (same family as the
# audit/repair-pack scanner). A hit fails the build closed without echoing
# the suspected value.
SECRET_PATTERNS = (
    ("PRIVATE_KEY_BLOCK", re.compile(rb"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
    ("API_KEY_ASSIGN", re.compile(rb"api[_-]?key\s*[:=]", re.IGNORECASE)),
    ("SECRET_ASSIGN", re.compile(rb"secret\s*[:=]", re.IGNORECASE)),
    ("PASSWORD_ASSIGN", re.compile(rb"pass(word|wd)\s*[:=]", re.IGNORECASE)),
    ("PRIVATE_KEY_ASSIGN", re.compile(rb"private[_-]?key\s*[:=]",
                                      re.IGNORECASE)),
    ("ACCESS_TOKEN_ASSIGN", re.compile(rb"access[_-]?token\s*[:=]",
                                       re.IGNORECASE)),
    ("BEARER_TOKEN", re.compile(rb"bearer\s+[A-Za-z0-9._\-]{20,}",
                                re.IGNORECASE)),
    ("AWS_ACCESS_KEY_ID", re.compile(rb"AKIA[0-9A-Z]{16}")),
)


def find_secret(data: bytes) -> str | None:
    for category, pattern in SECRET_PATTERNS:
        if pattern.search(data):
            return category
    return None


def _allowlist_path_and_identity(root: Path, allowlist_rel: str) -> tuple:
    root_resolved = Path(root).resolve(strict=False)
    path = (Path(root) / allowlist_rel).resolve(strict=False)
    try:
        identity = path.relative_to(root_resolved).as_posix()
    except ValueError:
        raise UALError("RELEASE_ALLOWLIST_MISSING",
                       "allowlist resolves outside release root") from None
    return path, identity


def load_allowlist(root: Path, allowlist_rel: str) -> list:
    path, _ = _allowlist_path_and_identity(root, allowlist_rel)
    if not path.is_file():
        raise UALError("RELEASE_ALLOWLIST_MISSING", allowlist_rel)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise UALError("RELEASE_ALLOWLIST_UNREADABLE",
                       repr(exc)) from None
    lines = text.splitlines()
    first = lines[0].strip() if lines else ""
    if first.startswith("#"):
        first = first[1:].strip()
    if first != ALLOWLIST_SCHEMA:
        raise UALError("RELEASE_ALLOWLIST_SCHEMA_INVALID",
                       str(path))
    members: list = []
    seen: set = set()
    for raw in lines[1:]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\\" in line or line.endswith("/"):
            raise UALError("RELEASE_MEMBER_NON_CANONICAL", line)
        if not CANONICAL_PATH_RE.match(line) or ".." in line.split("/"):
            raise UALError("RELEASE_MEMBER_NON_CANONICAL", line)
        if line in seen:
            raise UALError("RELEASE_MEMBER_DUPLICATE", line)
        if line in PRIVATE_MEMBERS or \
                any(line.startswith(prefix) for prefix in PRIVATE_PREFIXES):
            raise UALError("RELEASE_MEMBER_REFUSED",
                           line + ": private engineering input")
        seen.add(line)
        members.append(line)
    if not members:
        raise UALError("RELEASE_ALLOWLIST_EMPTY", allowlist_rel)
    return sorted(members)


def _resolved_member(root: Path, rel: str) -> Path:
    root_absolute = Path(root).absolute()
    candidate = (Path(root) / rel).absolute()
    current = candidate
    while True:
        is_junction = getattr(current, "is_junction", lambda: False)
        if current.is_symlink() or is_junction():
            raise UALError("RELEASE_MEMBER_REFUSED",
                           rel + ": symlink/junction members are refused")
        if current == root_absolute:
            break
        parent = current.parent
        if parent == current:
            raise UALError("RELEASE_MEMBER_REFUSED",
                           rel + ": is outside the release root")
        current = parent
    resolved = candidate.resolve(strict=False)
    root_resolved = root_absolute.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise UALError("RELEASE_MEMBER_REFUSED",
                       rel + ": resolves outside the release root") from None
    if not resolved.is_file():
        raise UALError("RELEASE_MEMBER_REFUSED", rel + ": missing")
    return resolved


def _collect(root: Path, members: list) -> list:
    root = Path(root)
    collected = []
    for rel in members:
        resolved = _resolved_member(root, rel)
        data = resolved.read_bytes()
        if len(data) > MAX_MEMBER_BYTES:
            raise UALError("RELEASE_MEMBER_OVER_BOUND", rel)
        category = find_secret(data)
        if category is not None:
            raise UALError("RELEASE_SECRET_SUSPECTED",
                           f"{category}:{rel}")
        collected.append((rel, data))
    return collected


def build_release(root: Path, allowlist_rel: str, out_zip: Path,
                  out_manifest: Path) -> dict:
    root = Path(root)
    members = load_allowlist(root, allowlist_rel)
    _, allowlist_identity = _allowlist_path_and_identity(root, allowlist_rel)
    collected = _collect(root, members)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel, data in collected:
            info = zipfile.ZipInfo(rel, date_time=ZIP_FIXED_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    zip_bytes = buffer.getvalue()
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "allowlist": allowlist_identity,
        "members": [
            {"path": rel, "bytes": len(data), "sha256": sha256_hex(data)}
            for rel, data in collected
        ],
        "archive_bytes": len(zip_bytes),
        "archive_sha256": sha256_hex(zip_bytes),
    }
    atomic_write_bytes(Path(out_zip), zip_bytes, max_bytes=256 * 1024 * 1024)
    atomic_write_bytes(Path(out_manifest), (
        json.dumps(manifest, indent=2, sort_keys=True)
        + "\n").encode("utf-8"), max_bytes=MANIFEST_MAX_BYTES)
    return {"ok": True, "members": [rel for rel, _ in collected],
            "archive_sha256": manifest["archive_sha256"],
            "manifest": str(out_manifest)}


def verify_release(root: Path, allowlist_rel: str, archive_path: Path,
                   manifest_path: Path) -> dict:
    root = Path(root)
    expected_members = load_allowlist(root, allowlist_rel)
    _, allowlist_identity = _allowlist_path_and_identity(root, allowlist_rel)
    manifest = load_json(Path(manifest_path), max_bytes=MANIFEST_MAX_BYTES)
    if not isinstance(manifest, dict) or \
            manifest.get("schema") != MANIFEST_SCHEMA:
        raise UALError("RELEASE_MANIFEST_SCHEMA_INVALID", str(manifest_path))
    if manifest.get("allowlist") != allowlist_identity:
        raise UALError("RELEASE_MANIFEST_SCHEMA_INVALID",
                       "manifest is bound to a different allowlist")
    archive_bytes = Path(archive_path).read_bytes()
    if manifest.get("archive_bytes") != len(archive_bytes):
        raise UALError("RELEASE_ARCHIVE_DRIFT", str(archive_path))
    if manifest.get("archive_sha256") != sha256_hex(archive_bytes):
        raise UALError("RELEASE_ARCHIVE_DRIFT", str(archive_path))
    bound_members = manifest.get("members") or []
    if not isinstance(bound_members, list) or \
            len(bound_members) != len(expected_members) or \
            any(not isinstance(member, dict) or
                not isinstance(member.get("path"), str)
                for member in bound_members):
        raise UALError("RELEASE_MEMBER_DRIFT",
                       "manifest member list is malformed or duplicated")
    bound_by_path = {m.get("path"): m for m in bound_members
                     if isinstance(m, dict)}
    expected_set = set(expected_members)
    bound_set = set(bound_by_path)
    if bound_set != expected_set:
        for extra in sorted(bound_set - expected_set):
            raise UALError("RELEASE_MEMBER_REFUSED",
                           f"manifest member not in allowlist: {extra}")
        for missing in sorted(expected_set - bound_set):
            raise UALError("RELEASE_MEMBER_DRIFT",
                           f"manifest member missing: {missing}")
    with zipfile.ZipFile(Path(archive_path)) as archive:
        archive_members = archive.namelist()
        if archive_members != expected_members:
            raise UALError(
                "RELEASE_ARCHIVE_DRIFT",
                "archive membership differs from the manifest")
        for rel in expected_members:
            data = archive.read(rel)
            bound = bound_by_path[rel]
            if bound.get("sha256") != sha256_hex(data) or \
                    bound.get("bytes") != len(data):
                raise UALError("RELEASE_MEMBER_DRIFT", rel)
            actual_source = _resolved_member(root, rel)
            if sha256_hex(actual_source.read_bytes()) != bound.get("sha256"):
                raise UALError("RELEASE_MEMBER_DRIFT",
                               rel + ": current source bytes drifted")
    return {"ok": True, "verified": expected_members,
            "archive_sha256": manifest.get("archive_sha256")}


build = build_release
verify = verify_release

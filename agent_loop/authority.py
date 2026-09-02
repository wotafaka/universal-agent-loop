"""Trusted local authority: config, actors, role sessions, operation gates.

One trusted local configuration defines the owner actor, permitted
actors/roles and command/native route bindings. It is excluded from the
engineer write allowlist, its exact bytes are bound at attempt opening
and into review/acceptance, and task facts can strengthen but never
weaken it. Role sessions are registered by the controller (or the owner
for OWNER sessions); an arbitrary --actor string cannot register or act
as OWNER/REVIEWER. This is local consistency under LOCAL_INTEGRITY, not
protection against hostile same-account code: no signing services,
credentials or multi-tenant security exist here.
"""
from __future__ import annotations

import re
from pathlib import Path

from .errors import UALError
from .hashing import (exclusive_write_json, load_json, next_sequence,
                      sha256_hex)
from .paths import state_root

CONFIG_SCHEMA = "ual-config/1"
CONFIG_MAX_BYTES = 64 * 1024
SESSION_SCHEMA = "ual-session/1"
SESSION_MAX_BYTES = 16 * 1024
ROLE_CLASSES = ("NO_MODEL", "CLERK_LOW", "OBSERVER_LOW",
                "ENGINEER_PRIMARY", "ENGINEER_ESCALATED",
                "ARCHITECT_INDEPENDENT", "AUDITOR_RISK_GATED")
ROLES = ("OWNER", "ENGINEER", "REVIEWER", "OBSERVER")
TRANSPORTS = ("command", "native", "owner", "manual")
ORIGINS = ("controller", "owner")
ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RESERVED_EVIDENCE_STATUSES = ("PENDING_CODEX_REVIEW", "REVIEW_PASSED",
                              "ACCEPTED", "REJECTED", "RELEASED")


def config_path(project: Path) -> Path:
    return state_root(project) / "config.json"


def load_config(project: Path) -> dict | None:
    path = config_path(project)
    if not path.is_file():
        return None
    config = load_json(path, max_bytes=CONFIG_MAX_BYTES)
    if not isinstance(config, dict) or config.get("schema") != CONFIG_SCHEMA:
        raise UALError("CONFIG_SCHEMA_UNKNOWN", str(path))
    errors = validate_config(config)
    if errors:
        raise UALError("CONFIG_INVALID", ";".join(errors[:4]))
    return config


def validate_config(config: dict) -> list:
    errors = []
    owner = config.get("owner_actor")
    if not isinstance(owner, str) or not owner.strip():
        errors.append("CONFIG_OWNER_ACTOR_INVALID")
    actors = config.get("actors")
    if not isinstance(actors, dict) or not actors:
        errors.append("CONFIG_ACTORS_REQUIRED")
        return errors
    for actor, entry in actors.items():
        if not isinstance(actor, str) or not ACTOR_RE.match(actor):
            errors.append(f"CONFIG_ACTOR_INVALID:{actor!r}")
            continue
        roles = (entry or {}).get("roles") if isinstance(entry, dict) else None
        if not isinstance(roles, list) or not roles or not all(
                r in ROLES for r in roles):
            errors.append(f"CONFIG_ACTOR_ROLES_INVALID:{actor}")
    if isinstance(owner, str) and isinstance(actors, dict):
        owner_entry = actors.get(owner)
        owner_roles = (owner_entry or {}).get("roles") \
            if isinstance(owner_entry, dict) else None
        if not isinstance(owner_roles, list) or "OWNER" not in owner_roles:
            errors.append("CONFIG_OWNER_NOT_OWNER_ROLE")
    bindings = config.get("role_bindings") or {}
    if not isinstance(bindings, dict):
        errors.append("CONFIG_ROLE_BINDINGS_INVALID")
    else:
        for role_class, binding in bindings.items():
            if role_class not in ROLE_CLASSES:
                errors.append(f"CONFIG_BINDING_ROLE_UNKNOWN:{role_class}")
                continue
            transport = (binding or {}).get("transport")
            if transport not in ("command", "native"):
                errors.append(f"CONFIG_BINDING_TRANSPORT_INVALID:"
                              f"{role_class}:{transport!r}")
            elif transport == "command" and not (
                    isinstance((binding or {}).get("argv"), list)
                    and binding["argv"]):
                errors.append(f"CONFIG_BINDING_ARGV_REQUIRED:{role_class}")
    return errors


def require_config(project: Path) -> dict:
    config = load_config(project)
    if config is None:
        raise UALError("AUTHORITY_CONFIG_REQUIRED",
                       "no trusted local authority config exists")
    return config


def config_digest(project: Path) -> str:
    path = config_path(project)
    if not path.is_file():
        raise UALError("AUTHORITY_CONFIG_REQUIRED", str(path))
    return sha256_hex(path.read_bytes())


def actor_has_role(config: dict, actor: str, role: str) -> bool:
    entry = (config.get("actors") or {}).get(actor)
    roles = (entry or {}).get("roles") if isinstance(entry, dict) else None
    return isinstance(roles, list) and role in roles


def require_actor_role(project: Path, actor: str, role: str) -> dict:
    config = require_config(project)
    if not isinstance(actor, str) or not actor or \
            not actor_has_role(config, actor, role):
        raise UALError("AUTHORITY_ACTOR_NOT_OWNER" if role == "OWNER"
                       else "AUTHORITY_ACTOR_UNAUTHORIZED",
                       f"{actor}!={role}")
    return config


def is_configured_owner(project: Path, actor: str) -> bool:
    config = load_config(project)
    if config is None:
        return False
    return actor == config.get("owner_actor") and \
        actor_has_role(config, actor, "OWNER")


def sessions_dir(project: Path) -> Path:
    directory = state_root(project) / "sessions"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_session(project: Path, session_id: str):
    if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        raise UALError("AUTHORITY_SESSION_INVALID", str(session_id))
    path = sessions_dir(project) / f"session_{session_id}.json"
    if not path.is_file():
        return None
    session = load_json(path, max_bytes=SESSION_MAX_BYTES)
    if not isinstance(session, dict) or session.get("schema") != SESSION_SCHEMA:
        raise UALError("AUTHORITY_SESSION_MALFORMED", session_id)
    return session


def register_session(project: Path, actor: str, role: str, transport: str,
                     session_id: str, origin: str) -> dict:
    config = require_config(project)
    if role not in ROLES:
        raise UALError("AUTHORITY_ROLE_UNKNOWN", role)
    if transport not in TRANSPORTS:
        raise UALError("AUTHORITY_TRANSPORT_INVALID", transport)
    if origin not in ORIGINS:
        raise UALError("AUTHORITY_ORIGIN_INVALID", origin)
    if not isinstance(session_id, str) or \
            not SESSION_ID_RE.match(session_id):
        raise UALError("AUTHORITY_SESSION_INVALID", session_id)
    if not actor_has_role(config, actor, role):
        raise UALError("AUTHORITY_ACTOR_UNAUTHORIZED", f"{actor}!={role}")
    if role == "OWNER" and origin != "owner":
        raise UALError("AUTHORITY_OWNER_ORIGIN_REQUIRED", session_id)
    directory = sessions_dir(project)
    path = directory / f"session_{session_id}.json"
    session = {
        "schema": SESSION_SCHEMA,
        "session_id": session_id,
        "actor": actor,
        "role": role,
        "transport": transport,
        "origin": origin,
        "registered_at": _now(),
    }
    exclusive_write_json(path, session, max_bytes=SESSION_MAX_BYTES)
    return {"ok": True, "session_id": session_id, "role": role,
            "actor": actor, "transport": transport, "origin": origin}


def require_session_role(project: Path, session_id: str, role: str) -> dict:
    session = get_session(project, session_id)
    if session is None:
        raise UALError("AUTHORITY_SESSION_REQUIRED",
                       f"{session_id} not registered")
    if session.get("role") != role:
        raise UALError("AUTHORITY_SESSION_ROLE_MISMATCH",
                       f"{session_id}:{session.get('role')}!={role}")
    return session


def route_check(project: Path, role: str) -> dict:
    if role not in ROLE_CLASSES:
        raise UALError("ROUTE_ROLE_UNKNOWN", role)
    config = load_config(project)
    bindings = (config or {}).get("role_bindings") or {}
    binding = bindings.get(role)
    if not isinstance(binding, dict) or not binding:
        return {"ok": True, "role": role, "decision": "UNAVAILABLE",
                "reason": "no local role binding configured; no "
                          "substitution is performed",
                "observed_identity": "UNKNOWN"}
    transport = binding.get("transport")
    if transport not in ("command", "native"):
        raise UALError("ROUTE_TRANSPORT_INVALID", str(transport))
    if transport == "command" and not (isinstance(binding.get("argv"), list)
                                       and binding["argv"]):
        return {"ok": True, "role": role, "decision": "UNAVAILABLE",
                "reason": "command binding has no usable argv",
                "observed_identity": "UNKNOWN"}
    return {"ok": True, "role": role, "decision": "AVAILABLE",
            "binding": binding, "observed_identity": "UNKNOWN"}


def engineer_binding(config: dict, task: dict) -> tuple:
    role_class = "ENGINEER_PRIMARY"
    if task.get("escalation_evidence") == "CONCRETE_INABILITY":
        role_class = "ENGINEER_ESCALATED"
    binding = (config.get("role_bindings") or {}).get(role_class) or \
        (config.get("role_bindings") or {}).get("ENGINEER_PRIMARY")
    return role_class, binding


def _now() -> str:
    from .claims import utc_now_iso
    return utc_now_iso()

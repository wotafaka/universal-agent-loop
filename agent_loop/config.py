"""Optional trusted local configuration and neutral role-route checks.

Role bindings are configured locally and are entirely provider-neutral:
the runtime ships no default brand and no mandatory model. An absent
binding is an honest UNAVAILABLE route, never a silent substitution;
observed provider identity is UNKNOWN unless machine-readable proof is
recorded.
"""
from __future__ import annotations

from pathlib import Path

from .errors import UALError
from .hashing import load_json
from .paths import state_root

CONFIG_SCHEMA = "ual-config/1"
CONFIG_MAX_BYTES = 64 * 1024
ROLE_CLASSES = ("NO_MODEL", "CLERK_LOW", "OBSERVER_LOW",
                "ENGINEER_PRIMARY", "ENGINEER_ESCALATED",
                "ARCHITECT_INDEPENDENT", "AUDITOR_RISK_GATED")


def load_config(project: Path) -> dict | None:
    path = state_root(project) / "config.json"
    if not path.is_file():
        return None
    config = load_json(path, max_bytes=CONFIG_MAX_BYTES)
    if not isinstance(config, dict) or config.get("schema") != CONFIG_SCHEMA:
        raise UALError("CONFIG_SCHEMA_UNKNOWN", str(path))
    return config


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
    return {"ok": True, "role": role, "decision": "AVAILABLE",
            "binding": binding,
            "observed_identity": "UNKNOWN"}

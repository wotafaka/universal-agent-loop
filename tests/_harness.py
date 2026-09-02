"""Shared CLI test harness for the Universal Agent Loop runtime tests.

Every test drives the real ``python -m agent_loop`` CLI against isolated
fixture projects created inside this checkout, using only the standard
library and synthetic stdlib fake children. No provider, network or
credential is involved; synthetic actors are fixture labels.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parent.parent
SCRATCH = CHECKOUT / "tests" / ".scratch"


def _purge_scratch():
    """Remove test-owned scratch projects left by any previous run.

    Only entries inside this checkout's tests/.scratch are touched; the
    base directory itself is recreated on demand.
    """
    if not SCRATCH.is_dir():
        return
    import shutil
    for entry in SCRATCH.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)


_purge_scratch()


def fresh_project(name: str, testcase=None) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=name + "-", dir=str(SCRATCH)))
    if testcase is not None:
        import shutil
        testcase.addCleanup(shutil.rmtree, path, ignore_errors=True)
    (path / "src").mkdir()
    (path / "src" / "demo.py").write_bytes(b"VALUE = 1\n")
    (path / "tests").mkdir()
    (path / "tests" / "test_demo.py").write_bytes(b"import unittest\n\n\nclass T(unittest.TestCase):\n    def test_demo(self):\n        self.assertEqual(1, 1)\n")
    (path / "report").mkdir()
    return path


def cli_argv(project, *args):
    return [sys.executable, "-S", "-B", "-m", "agent_loop",
            "--project", str(project), *args]


def run_cli(project, *args, expect=0):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CHECKOUT)
    proc = subprocess.run(
        cli_argv(project, *args), env=env, cwd=str(project),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    if expect is not None and proc.returncode != expect:
        raise AssertionError(
            f"cli {args} exit {proc.returncode} != {expect}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
    payload = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except ValueError:
            payload = None
    return proc, payload


def expect_refusal(project, *args, code):
    proc, payload = run_cli(project, *args, expect=2)
    assert payload is not None, f"no JSON refusal for {args}: {proc.stdout} {proc.stderr}"
    codes = payload.get("errors") or []
    assert any(code in c for c in codes), f"{code} not in {codes} for {args}"
    return payload


def write_task(project, **overrides):
    task = {
        "schema": "ual-task/1",
        "id": "demo-task",
        "title": "Synthetic demo task",
        "mode": "FULL",
        "risk": "MEDIUM",
        "work_kind": "IMPLEMENTATION",
        "oracle_strength": "STRONG",
        "novelty": "ROUTINE",
        "ambiguity": "CLEAR",
        "failure_evidence": "NONE",
        "escalation_evidence": "NONE",
        "authority_domains": [],
        "material_contradiction": False,
        "clarification_status": "RESOLVED",
        "open_clarification_ids": [],
        "owner_actor": "OWNER",
        "requirement_ids": ["R1", "R2"],
        "success_criteria_count": 2,
        "requirements": [
            {"id": "R1", "criterion": 1, "command": 1, "evidence": "TEST_OUTPUT"},
            {"id": "R2", "criterion": 2, "command": 1, "evidence": "TEST_OUTPUT"},
        ],
        "validation": {
            "commands": [
                {"ordinal": 1, "cwd": ".",
                 "argv": [sys.executable, "check_demo.py"],
                 "expected_outcomes": ["RED", "GREEN"]},
            ],
            "seed": "0",
            "environment": {"base": ["SYSTEMROOT", "PATH", "PATHEXT",
                                     "COMSPEC", "PROCESSOR_ARCHITECTURE",
                                     "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
                                     "NUMBER_OF_PROCESSORS", "OS", "TEMP",
                                     "TMP", "HOME", "LANG"],
                            "overlay": {}},
        },
        "candidate": {"allowlist": ["src/demo.py"],
                      "report": "report/IMPLEMENTATION.md"},
        "required_skills": [],
        "review": {"passes": 2},
        "audit": {"required": False},
        "observer": {"policy": "NONE"},
        "generated_state": [],
        "lessons_path": ".agent-loop/lessons.md",
    }
    task.update(overrides)
    path = project / "task.json"
    path.write_bytes(json.dumps(task, indent=2).encode("utf-8"))
    return task, path


def write_config(project, owner="OWNER", engineer="ENG-SYNTH",
                 reviewer="REV-SYNTH", transport="command", model=None,
                 argv=None):
    """Trusted local authority config (synthetic actor labels)."""
    binding = {"transport": transport}
    if model:
        binding["model"] = model
    if transport == "command":
        binding["argv"] = argv or [
            sys.executable, "-c", "print('engineer ok')"]
    config = {
        "schema": "ual-config/1",
        "owner_actor": owner,
        "actors": {
            owner: {"roles": ["OWNER"]},
            engineer: {"roles": ["ENGINEER"]},
            reviewer: {"roles": ["REVIEWER"]},
        },
        "role_bindings": {"ENGINEER_PRIMARY": binding},
        "audit_policy": {"fallback_enabled": False},
        "required_evidence": {"complete_transcript": False},
    }
    config_dir = project / ".agent-loop"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_bytes(
        json.dumps(config, indent=2).encode("utf-8"))
    return config


def register_sessions(project, owner="OWNER", engineer="ENG-SYNTH",
                      reviewer="REV-SYNTH"):
    """Register one session per configured role (controller/owner origin).
    The engineer session transport follows the configured route binding."""
    cfg_path = project / ".agent-loop" / "config.json"
    engineer_transport = "command"
    if cfg_path.is_file():
        cfg = json.loads(cfg_path.read_text("utf-8"))
        binding = (cfg.get("role_bindings") or {}).get("ENGINEER_PRIMARY") or {}
        engineer_transport = binding.get("transport", "command")
    sessions = []
    for actor, role, transport, origin in (
            (owner, "OWNER", "owner", "owner"),
            (engineer, "ENGINEER", engineer_transport, "controller"),
            (reviewer, "REVIEWER", "manual", "controller")):
        session_id = f"sess-{role.lower()}"
        run_cli(project, "session", "register", "--actor", actor,
                "--role", role, "--transport", transport,
                "--session-id", session_id, "--origin", origin)
        sessions.append(session_id)
    return {"owner": owner, "engineer": engineer, "reviewer": reviewer,
            "engineer_session": sessions[1], "reviewer_session": sessions[2]}


def authority(project, **kwargs):
    write_config(project, **kwargs)
    return register_sessions(project, **{k: v for k, v in kwargs.items()
                                         if k in ("owner", "engineer",
                                                  "reviewer")})


def engineer_argv_for(project):
    """The trusted configured engineer adapter argv for fixtures."""
    cfg = json.loads((project / ".agent-loop" / "config.json")
                     .read_text("utf-8"))
    return cfg["role_bindings"]["ENGINEER_PRIMARY"]["argv"]


def envelope_binding_section(project):
    """Formatted frozen-envelope binding section for review fixtures, or
    '' when no envelope exists yet."""
    envelope_dirs = sorted((project / ".agent-loop" / "tasks").glob(
        "*/attempts/attempt_*/envelope"))
    if not envelope_dirs:
        return ""
    envelopes = sorted(envelope_dirs[-1].glob("envelope_*.json"))
    if not envelopes:
        return ""
    digest = sha256_of(envelopes[-1])
    return ("\n## Frozen envelope binding\n\n"
            "- Frozen envelope sha256: `" + digest + "`\n")


def audit_closure_flags(project):
    """Independently derive the required-audit input closure for the
    demo-task fixture from its frozen envelope (task contract, frozen
    candidate members, required skills, decisive validation evidence),
    returned as (role, rel) pairs in canonical path order."""
    attempts_root = (Path(project) / ".agent-loop" / "tasks" /
                     "demo-task" / "attempts")
    envelope_dir = sorted(attempts_root.glob("attempt_*"))[-1] / "envelope"
    envelope = json.loads(
        sorted(envelope_dir.glob("envelope_*.json"))[-1]
        .read_text("utf-8"))
    claimed = {}

    def claim(role, rel):
        claimed.setdefault(rel, role)

    claim("instruction", "task.json")
    for member in envelope.get("members") or []:
        claim("input", member["path"])
    for skill in envelope.get("skills") or []:
        claim("instruction", skill["path"])
    for bound in (envelope.get("validation_logs") or []) + \
            (envelope.get("capture_closure") or []):
        claim("validation", bound["path"])
    return [(claimed[rel], rel) for rel in sorted(claimed)]


def audit_cli_flags(pairs):
    args = []
    role_flags = {"input": "--input", "instruction": "--instruction",
                  "validation": "--validation"}
    for role, rel in pairs:
        args += [role_flags[role], rel]
    return args


def sys_executable():
    return sys.executable


def sha256_of(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_child(project, name="child.py", body=""):
    path = project / name
    path.write_bytes(body.encode("utf-8"))
    return path


def check_script(fail_first=False):
    return (
        "import json, os, sys\n"
        "marker = 'marker_ok.txt'\n"
        "state = 'check_state.json'\n"
        "runs = 0\n"
        "if os.path.exists(state):\n"
        "    runs = json.loads(open(state).read())['runs']\n"
        "runs += 1\n"
        "open(state, 'w').write(json.dumps({'runs': runs}))\n"
        "fail = runs == 1 and %r\n"
        "print('check run', runs)\n"
        "sys.exit(1 if fail else 0)\n" % (fail_first,)
    )

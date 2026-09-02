#!/usr/bin/env python
"""Offline quickstart: drive the real Universal Agent Loop runtime once.

No network, no provider, no credential, no paid model. This script builds a
small nonweather demo project inside ``examples/.scratch/`` (inside this
checkout, deleted on exit) and drives the actual ``python -m agent_loop`` CLI
through one complete governed cycle, including a bounded synthetic ENGINEER
claim and a same-task negative-review repair attempt:

    task preflight -> RED -> fix -> GREEN -> engineer claim (synthetic) ->
    close -> freeze -> SYNTHETIC negative review -> repair attempt 2 ->
    RED -> fix -> GREEN -> close -> refreeze -> SYNTHETIC positive review ->
    synthetic owner acceptance -> measured delivery report

Every actor here (OWNER, engineer, reviewer) is a SYNTHETIC local fixture
label registered from the local trusted config, never a real owner decision
or an independent review. That is exactly what makes this offline: the same
evidence gates run, but no human or provider is involved. The parent supplies
a genuine model-backed example separately (see examples/lineclean/README.md
for the authentic pilot).

Run from the package root:

    python examples/offline_quickstart.py

Expected final line:

    OFFLINE_QUICKSTART: PASS (synthetic actors; no provider, no credential)

Any other exit code means a gate refused; the printed JSON shows the stable
refusal code.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parent.parent
SCRATCH = CHECKOUT / "examples" / ".scratch"
TASK_ID = "quickstart-line-util"


def step(title, detail=""):
    print(f"[ual] {title}" + (f" — {detail}" if detail else ""))


def cli(project, *args, expect=0):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(CHECKOUT)
    proc = subprocess.run(
        [sys.executable, "-S", "-B", "-m", "agent_loop",
         "--project", str(project), *args],
        env=env, cwd=str(project), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300)
    payload = None
    if proc.stdout.strip():
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    if proc.returncode != expect:
        print(json.dumps(payload, indent=2))
        print(proc.stderr)
        raise SystemExit(
            f"OFFLINE_QUICKSTART: FAIL (exit {proc.returncode} != {expect} "
            f"for {args})")
    return payload


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


TASK = {
    "schema": "ual-task/1",
    "id": TASK_ID,
    "title": "Offline quickstart: lowercase-only line utility",
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
    "requirement_ids": ["R1"],
    "success_criteria_count": 1,
    "requirements": [
        {"id": "R1", "criterion": 1, "command": 1, "evidence": "TEST_OUTPUT"},
    ],
    "validation": {
        "commands": [
            {"ordinal": 1, "cwd": ".",
             "argv": [sys.executable, "check_util.py"],
             "expected_outcomes": ["RED", "GREEN"]},
        ],
        "seed": "0",
        "environment": {"base": ["SYSTEMROOT", "PATH", "PATHEXT", "COMSPEC",
                                 "TEMP", "TMP", "HOME"],
                        "overlay": {}},
    },
    "candidate": {"allowlist": ["util.py"],
                  "report": "report/IMPLEMENTATION.md"},
    "required_skills": [],
    "review": {"passes": 2},
    "audit": {"required": False},
    "observer": {"policy": "NONE"},
    "generated_state": [],
    "lessons_path": ".agent-loop/lessons.md",
}

CHECK_SCRIPT = """import json, os, sys
import util
state = "check_state.json"
runs = 0
if os.path.exists(state):
    runs = json.loads(open(state).read())["runs"]
runs += 1
open(state, "w").write(json.dumps({"runs": runs}))
ok = util.clean("  Hello  ") == "hello" and util.clean("") == ""
print("check run", runs, "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
"""

ENGINEER_CHILD = "print('bounded synthetic engineering step')\n"


def write_task(project):
    (project / "task.json").write_bytes(
        json.dumps(TASK, indent=2).encode("utf-8"))


def write_config(project):
    config = {
        "schema": "ual-config/1",
        "owner_actor": "OWNER",
        "actors": {
            "OWNER": {"roles": ["OWNER"]},
            "ENG-SYNTH": {"roles": ["ENGINEER"]},
            "REV-SYNTH": {"roles": ["REVIEWER"]},
        },
        "role_bindings": {"ENGINEER_PRIMARY": {
            "transport": "command", "model": "synthetic-engineer/1",
            "argv": [sys.executable, "engineer_child.py"]}},
        "audit_policy": {"fallback_enabled": False},
        "required_evidence": {"complete_transcript": False},
    }
    config_dir = project / ".agent-loop"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_bytes(
        json.dumps(config, indent=2).encode("utf-8"))


def register_sessions(project):
    for actor, role, transport, origin, sid in (
            ("OWNER", "OWNER", "owner", "owner", "sess-owner"),
            ("ENG-SYNTH", "ENGINEER", "command", "controller",
             "sess-engineer"),
            ("REV-SYNTH", "REVIEWER", "manual", "controller",
             "sess-reviewer")):
        cli(project, "session", "register", "--actor", actor, "--role", role,
            "--transport", transport, "--session-id", sid, "--origin", origin)


def build_project():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="quickstart-", dir=str(SCRATCH)))
    write_task(project)
    write_config(project)
    register_sessions(project)
    (project / "util.py").write_bytes(b"def clean(s):\n    return s\n")
    (project / "check_util.py").write_bytes(CHECK_SCRIPT.encode("utf-8"))
    (project / "report").mkdir()
    return project


def run_validation(project):
    return cli(project, "run", "--task", TASK_ID, "--purpose", "VALIDATION",
               "--argv-json", json.dumps([sys.executable, "check_util.py"]))


def proof_lines(project):
    return (
        "- Evidence: `validation-review-proof/1` artifact `proof_one.json`"
        " sha256 `" + sha(project / "proof_one.json") + "` origin"
        " `REVIEWER_RECOMPUTED` action `recomputed the frozen envelope"
        " digests` candidate `" + TASK_ID + "`\n"
        "- Evidence: `validation-review-proof/1` artifact `proof_two.json`"
        " sha256 `" + sha(project / "proof_two.json") + "` origin"
        " `REVIEWER_REEXECUTED` action `re-executed the fenced checks`"
        " candidate `" + TASK_ID + "`\n")


def review_text(project, verdict, findings="- NONE\n", corrections=None):
    proofs = []
    first, _, second = proof_lines(project).partition("\n")
    text = (
        "# Independent review — " + TASK_ID + " (SYNTHETIC fixture)\n\n"
        "## Contract compliance\n\n- Verdict: `" + verdict + "`\n" +
        first + "\n\n" +
        "## Adversarial validity\n\n- Verdict: `" + verdict + "`\n" +
        second + "\n" +
        "## Findings\n\n" + findings +
        "\n## Durable correction\n\n" +
        (corrections if corrections is not None
         else "- Mandated change: `NONE`\n") +
        "\n## Convergence disposition\n\n"
        "- Disposition: `CONVERGED`\n"
        "- Covered requirement IDs: `R1`\n"
        "- Remaining material requirement IDs: `NONE`\n")
    envelope_dirs = sorted((project / ".agent-loop" / "tasks" /
                            TASK_ID / "attempts").glob(
                                "attempt_*/envelope"))
    if envelope_dirs:
        envelopes = sorted(envelope_dirs[-1].glob("envelope_*.json"))
        if envelopes:
            digest = sha(envelopes[-1])
            text += ("\n## Frozen envelope binding\n\n"
                     "- Frozen envelope sha256: `" + digest + "`\n")
    (project / "review.md").write_text(text, encoding="utf-8")
    return project / "review.md"


def finalize(project, report_text):
    (project / "report" / "IMPLEMENTATION.md").write_text(
        report_text, encoding="utf-8")
    cli(project, "refresh", "--task", TASK_ID)
    cli(project, "report-check", "--task", TASK_ID)
    cli(project, "close", "--task", TASK_ID)
    return cli(project, "envelope", "freeze", "--task", TASK_ID)


def main() -> int:
    project = build_project()
    try:
        step("1. task preflight (material ambiguity and coverage checked)")
        payload = cli(project, "task-validate", "--task", "task.json")
        assert payload["ok"] and payload["mode"] == "FULL"

        step("2. RED — reproduce the missing behavior first")
        run = run_validation(project)
        assert run["exit_code"] == 1
        payload = cli(project, "validate", "record", "--task", TASK_ID,
                      "--run", run["run_id"], "--ordinal", "1")
        assert payload["outcome"] == "RED"

        step("3. the smallest change; the SAME command repeats as GREEN")
        (project / "util.py").write_bytes(
            b'def clean(s):\n    return s.strip().lower()\n')
        run = run_validation(project)
        assert run["exit_code"] == 0
        payload = cli(project, "validate", "record", "--task", TASK_ID,
                      "--run", run["run_id"], "--ordinal", "1")
        assert payload["outcome"] == "GREEN"

        step("4. SYNTHETIC engineer claim: gated launch, birth identity, "
             "terminal release")
        (project / "engineer_child.py").write_bytes(
            ENGINEER_CHILD.encode("utf-8"))
        run = cli(project, "run", "--task", TASK_ID, "--purpose", "ENGINEER",
                  "--session-id", "sess-engineer")
        assert run["claim"]["state"] == "RELEASED"

        step("5. report, refresh, report-check, close, freeze envelope")
        (project / "proof_one.json").write_bytes(b'{"pass": 1}\n')
        (project / "proof_two.json").write_bytes(b'{"pass": 2}\n')
        payload = finalize(
            project,
            "# Implementation report — quickstart (attempt 1)\n\n"
            "SYNTHETIC demo. Stub RED observed; strip+lowercase "
            "implemented; GREEN repeated the same command.\n")

        step("6. SYNTHETIC reviewer FAILS attempt 1; repair opens attempt 2")
        cli(project, "lessons", "record", "--task", TASK_ID,
            "--finding", "M1", "--text",
            "M1: report did not name the fenced command; corrected")
        review_text(
            project, "FAIL",
            findings="- M1: report lacked the exact fenced command\n",
            corrections=(
                "- M1: `LESSON_RECORDED` — rationale: reporting defect — "
                "evidence: `.agent-loop/lessons.md#M1`\n"))
        cli(project, "review", "validate", "--task", TASK_ID,
            "--review", "review.md", "--reviewer-session", "sess-reviewer")
        cli(project, "review", "seal", "--task", TASK_ID,
            "--review", "review.md", "--verdict", "FAIL",
            "--reviewer-session", "sess-reviewer")
        cli(project, "status", "set", "--task", TASK_ID,
            "--status", "FIX_REQUIRED")
        (project / "batch2.md").write_text(
            "# Repair batch — attempt 2\n\nName the fenced command in the "
            "report and re-verify.\n", encoding="utf-8")
        (project / "touched.md").write_text(
            "- report/IMPLEMENTATION.md\n", encoding="utf-8")
        claim = {"finding_ids": ["M1"], "reason": "CANDIDATE_HASH_CHANGE",
                 "evidence": {"prior_candidate_sha256": "a" * 64,
                              "new_candidate_sha256": "b" * 64},
                 "progress_basis": None}
        (project / "claim.json").write_bytes(json.dumps(claim).encode())
        basis = cli(project, "progress", "check", "--task", TASK_ID,
                    "--batch", "batch2.md")
        claim["progress_basis"] = basis["basis"]
        (project / "claim.json").write_bytes(json.dumps(claim).encode())
        payload = cli(project, "attempt", "open", "--task", TASK_ID,
                      "--batch", "batch2.md", "--claim-file", "claim.json")
        assert payload["attempt"] == 2

        step("7. attempt 2: RED, fix, GREEN, close, refreeze")
        (project / "check_state.json").unlink()
        (project / "util.py").write_bytes(b"def clean(s):\n    return s\n")
        run = run_validation(project)
        assert run["exit_code"] == 1
        cli(project, "validate", "record", "--task", TASK_ID,
            "--run", run["run_id"], "--ordinal", "1")
        (project / "util.py").write_bytes(
            b'def clean(s):\n    return s.strip().lower()\n')
        run = run_validation(project)
        assert run["exit_code"] == 0
        cli(project, "validate", "record", "--task", TASK_ID,
            "--run", run["run_id"], "--ordinal", "1")
        payload = finalize(
            project,
            "# Implementation report — quickstart (attempt 2)\n\n"
            "SYNTHETIC demo. Fenced command: python check_util.py "
            "(RED then GREEN, same command).\n")
        assert "attempt_00000002" in payload["path"]

        step("8. SYNTHETIC positive review, owner acceptance, feedback")
        review_text(project, "PASS")
        cli(project, "review", "validate", "--task", TASK_ID,
            "--review", "review.md", "--reviewer-session", "sess-reviewer")
        cli(project, "review", "seal", "--task", TASK_ID,
            "--review", "review.md", "--verdict", "PASS",
            "--reviewer-session", "sess-reviewer")
        payload = cli(project, "accept", "--task", TASK_ID,
                      "--actor", "OWNER", "--decision", "ACCEPTED",
                      "--review", "review.md")
        assert payload["decision"] == "ACCEPTED"
        payload = cli(project, "report", "efficiency", "--task", TASK_ID)
        assert payload["restoration_seconds"] == "UNKNOWN"
        payload = cli(project, "report", "delivery", "--task", TASK_ID)
        assert payload["delivered"] is True
    finally:
        shutil.rmtree(project, ignore_errors=True)
    print("OFFLINE_QUICKSTART: PASS (synthetic actors; no provider, "
          "no credential)")
    print("The demo project was deleted; nothing outside "
          "examples/.scratch was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

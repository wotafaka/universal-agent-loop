"""Composed operation-path regressions for the continuation repair (B1-B9).

Every case here drives the real CLI spine the way an operator would:
trusted authority config and registered sessions, gated engineer launches,
attempt-scoped same-task repair, native/manual handoff, byte-bound context
and measured feedback consumed by the next attempt. Isolated fixture roots
inside this checkout; bounded stdlib children; synthetic actor labels.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

import _harness as h

sys.path.insert(0, str(h.CHECKOUT))

LINECLEAN = h.CHECKOUT / "examples" / "lineclean"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def claim_file(project, name, sequence):
    directory = project / ".agent-loop" / "claims"
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": "ual-writer-claim/1", "claim_id": f"hist-{sequence:04d}",
        "task": "old", "host": "fixture", "launcher_pid": 1,
        "launcher_identity": {"method": "fixture", "value": str(sequence)},
        "acquired_at": "2026-08-31T00:00:00+00:00", "status": "RELEASED",
        "child_pid": None, "child_identity": None,
        "identity_state": "UNBOUND", "bound_at": None, "released_at": None,
        "terminal_evidence": {"class": "SPAWN_FAILED_NO_CHILD"},
        "adjudication": None,
    }
    path = directory / f"claim_{sequence:08d}.json"
    path.write_bytes(json.dumps(record, indent=2).encode("utf-8") + b"\n")
    return path


def engineer_run(project, script="print('engineering')\\n", batch=None,
                 expect=0):
    body = script if script.endswith("\n") else script + "\n"
    h.write_child(project, "engineer_child.py", body)
    args = ["run", "--task", "demo-task", "--purpose", "ENGINEER",
            "--session-id", "sess-engineer"]
    if batch is not None:
        args += ["--basis-file", batch]
    return h.run_cli(project, *args, expect=expect)


def review_text(project, verdict="PASS", findings="- NONE\n",
                corrections="- Mandated change: `NONE`\n", high_risk=False):
    (project / "proof_one.json").write_bytes(b'{"pass": 1}\n')
    (project / "proof_two.json").write_bytes(b'{"pass": 2}\n')
    challenge = ""
    if high_risk:
        (project / "challenge_artifact.json").write_bytes(b'{"c": 1}\n')
        data = (project / "challenge_artifact.json").read_bytes()
        challenge = (
            "- Challenge type: `NEGATIVE_COUNTEREXAMPLE`\n"
            "- Challenge target: `src/demo.py`\n"
            "- Challenge artifact: `challenge_artifact.json`\n"
            "- Challenge artifact bytes: `" + str(len(data)) + "`\n"
            "- Challenge artifact sha256: `" + sha(
                project / "challenge_artifact.json") + "`\n"
            "- Challenge result: `counterexample refused`\n")
    text = (
        "# Independent review — demo-task (SYNTHETIC fixture)\n\n"
        "## Contract compliance\n\n- Verdict: `" + verdict + "`\n"
        "- Evidence: `validation-review-proof/1` artifact `proof_one.json`"
        " sha256 `" + sha(project / "proof_one.json") + "` origin"
        " `REVIEWER_RECOMPUTED` action `recomputed fixture digests`"
        " candidate `demo-task`\n\n"
        "## Adversarial validity\n\n- Verdict: `" + verdict + "`\n"
        "- Evidence: `validation-review-proof/1` artifact `proof_two.json`"
        " sha256 `" + sha(project / "proof_two.json") + "` origin"
        " `REVIEWER_REEXECUTED` action `re-executed fixture checks`"
        " candidate `demo-task`\n" + challenge +
        "\n## Findings\n\n" + findings +
        "\n## Durable correction\n\n" + corrections + "\n"
        "## Convergence disposition\n\n"
        "- Disposition: `CONVERGED`\n"
        "- Covered requirement IDs: `R1,R2`\n"
        "- Remaining material requirement IDs: `NONE`\n" +
        h.envelope_binding_section(project))
    (project / "review.md").write_text(text, encoding="utf-8")
    return project / "review.md"


class SpineFixture(unittest.TestCase):
    """Attempt-1 happy path through the real CLI, ready for repair."""

    def _build(self, name, with_engineer=True):
        self.project = h.fresh_project(name, self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)
        (self.project / "batch1.md").write_text(
            "# Repair batch — attempt 1\n\n"
            "Engineering change for attempt 1.\n", encoding="utf-8")
        for i in range(2):
            proc, run = h.run_cli(
                self.project, "run", "--task", "demo-task", "--purpose",
                "VALIDATION",
                "--argv-json", json.dumps(
                    [h.sys_executable(), "check_demo.py"]))
            h.run_cli(self.project, "validate", "record", "--task",
                      "demo-task", "--run", run["run_id"], "--ordinal", "1")
            if i == 0:
                (self.project / "src" / "demo.py").write_bytes(
                    b"VALUE = 2\n")
        if with_engineer:
            engineer_run(self.project, batch="batch1.md")
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")


class B1_AuthoritySpine(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("b1", self)
        h.write_task(self.project)
        h.authority(self.project)

    def test_engineer_launch_without_usable_route_refuses_early(self):
        bare = h.fresh_project("b1-noroute", self)
        h.write_task(bare)
        h.write_config(bare)
        cfg = bare / ".agent-loop" / "config.json"
        data = json.loads(cfg.read_text("utf-8"))
        data["role_bindings"] = {}
        cfg.write_text(json.dumps(data, indent=2), "utf-8")
        h.register_sessions(bare)
        h.expect_refusal(bare, "run", "--task", "demo-task", "--purpose",
                         "ENGINEER", "--session-id", "sess-engineer",
                         "--argv-json", json.dumps(
                             [h.sys_executable(), "-c", "print('x')"]),
                         code="ROUTE_UNUSABLE")
        claims_dir = bare / ".agent-loop" / "claims"
        self.assertFalse(claims_dir.is_dir() and any(claims_dir.iterdir()))
        runs = bare / ".agent-loop" / "runs"
        self.assertFalse(runs.is_dir() and any(runs.iterdir()))

    def test_claim_adjudication_is_owner_only(self):
        proc, payload = h.run_cli(self.project, "claim", "acquire",
                                  "--task", "demo-task")
        claim_id = payload["claim_id"]
        h.expect_refusal(self.project, "claim", "abandon", "--claim-id",
                         claim_id, "--actor", "ENG-SYNTH",
                         "--reason", "self granted",
                         code="AUTHORITY_ACTOR_NOT_OWNER")
        proc, payload = h.run_cli(self.project, "claim", "abandon",
                                  "--claim-id", claim_id, "--actor", "OWNER",
                                  "--reason", "owner adjudication")
        self.assertEqual(payload["status"], "ABANDONED")

    def test_reserved_statuses_need_evidence_operations(self):
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "ACTIVE")
        for status in ("PENDING_CODEX_REVIEW", "REVIEW_PASSED",
                       "ACCEPTED", "REJECTED", "RELEASED"):
            h.expect_refusal(self.project, "status", "set", "--task",
                             "demo-task", "--status", status,
                             code="STATUS_RESERVED_FOR_EVIDENCE")

    def test_engineer_launch_requires_registered_session(self):
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--argv-json", json.dumps(
                             [h.sys_executable(), "-c", "print('x')"]),
                         code="AUTHORITY_SESSION_REQUIRED")

    def test_task_owner_actor_must_match_config(self):
        h.write_task(self.project, owner_actor="SPOOFED")
        h.expect_refusal(self.project, "task-validate", "--task",
                         "task.json", code="TASK_OWNER_ACTOR_UNCONFIGURED")


class B2_Containment(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("b2", self)
        h.write_task(self.project)

    def test_escaped_task_id_refused_and_nowhere_written(self):
        scratch_parent = self.project.parent
        h.expect_refusal(self.project, "status", "set", "--task",
                         "../../escaped-fixture", "--status", "ACTIVE",
                         code="TASK_ID_INVALID")
        self.assertNotIn("escaped-fixture",
                         [p.name for p in scratch_parent.iterdir()])

    def test_malformed_claim_blocks_not_admits(self):
        h.run_cli(self.project, "claim", "acquire", "--task", "demo-task")
        claims_dir = self.project / ".agent-loop" / "claims"
        active = sorted(claims_dir.glob("claim_*.json"))[-1]
        active.write_bytes(b"{}\n")
        h.expect_refusal(self.project, "claim", "acquire", "--task",
                         "demo-task", code="WRITER_CLAIM_DIR_DIRTY")


class B3_CapAndIdentity(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("b3", self)
        h.write_task(self.project)
        h.authority(self.project)

    def test_claim_history_is_not_a_lifetime_cap(self):
        for sequence in range(1, 131):
            claim_file(self.project, "old", sequence)
        proc, payload = h.run_cli(self.project, "claim", "acquire",
                                  "--task", "demo-task")
        self.assertEqual(payload["sequence"], 131)

    def test_release_compares_full_child_identity(self):
        proc, payload = h.run_cli(self.project, "claim", "acquire",
                                  "--task", "demo-task")
        claim_id = payload["claim_id"]
        claim_path = (self.project / ".agent-loop" / "claims" /
                      f"claim_{payload['sequence']:04d}.json")
        identity = {"method": "fixture", "value": "birth-77"}
        h.run_cli(self.project, "claim", "bind-child", "--claim-id",
                  claim_id, "--pid", "4242", "--identity-state", "OBTAINED",
                  "--identity-method", "fixture",
                  "--identity-value", "birth-77")
        run_dir = self.project / ".agent-loop" / "runs" / "fixture-run"
        log = run_dir / "log.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(b"engineer output\n")
        sidecar = {
            "schema": "ual-run/1", "run_id": "fixture-run",
            "task": "demo-task", "purpose": "ENGINEER",
            "argv": [h.sys_executable(), "child.py"], "cwd": ".",
            "env_policy_sha256": "f" * 64, "seed": "0",
            "status": "FINISHED", "pid": 4242,
            "child_identity": identity, "identity_state": "OBTAINED",
            "exit_code": 0, "overflow": False,
            "log": {"path": ".agent-loop/runs/fixture-run/log.txt",
                    "bytes": 16, "sha256": sha(log), "truncated": False},
            "ack": {"path": None, "state": "UNKNOWN", "reason": None},
            "session_id": "sess-engineer", "claim_id": claim_id,
            "capture": {"sha256": None},
            "launch_identity": {"progress_basis": None,
                                "material_progress_claim": None},
        }
        (run_dir / "run.json").write_bytes(
            json.dumps(sidecar, indent=2).encode("utf-8") + b"\n")
        sidecar["pid"] = 5150
        (run_dir / "run.json").write_bytes(
            json.dumps(sidecar, indent=2).encode("utf-8") + b"\n")
        h.expect_refusal(self.project, "claim", "release", "--claim-id",
                         claim_id, "--run", "fixture-run",
                         code="WRITER_CLAIM_IDENTITY_DRIFT")
        sidecar["pid"] = 4242
        (run_dir / "run.json").write_bytes(
            json.dumps(sidecar, indent=2).encode("utf-8") + b"\n")
        proc, payload = h.run_cli(self.project, "claim", "release",
                                  "--claim-id", claim_id, "--run",
                                  "fixture-run")
        self.assertEqual(payload["status"], "PASS")


class B4_ComposedRepairSpine(SpineFixture):
    def setUp(self):
        self._build("b4-spine")

    def test_first_event_record_on_fresh_task_does_not_crash(self):
        project = h.fresh_project("b4-events", self)
        h.write_task(project)
        h.write_config(project)
        proc, payload = h.run_cli(project, "event", "record", "--task",
                                  "demo-task", "--tool", "bash",
                                  "--detail", "echo hi", "--exit", "0")
        self.assertTrue(payload["ok"])

    def test_negative_review_opens_repair_attempt_full_cycle(self):
        h.run_cli(self.project, "lessons", "record", "--task", "demo-task",
                  "--finding", "M1",
                  "--text", "M1: constant drift reproduced and fixed")
        review_text(self.project, verdict="FAIL",
                    findings="- M1: wrong constant survived\n",
                    corrections=(
                        "- M1: `LESSON_RECORDED` — rationale: constant "
                        "drift — evidence: "
                        "`.agent-loop/lessons.md#M1`\n"))
        h.run_cli(self.project, "review", "validate", "--task", "demo-task",
                  "--review", "review.md",
                  "--reviewer-session", "sess-reviewer")
        proc, payload = h.run_cli(self.project, "review", "seal", "--task",
                                  "demo-task", "--review", "review.md",
                                  "--verdict", "FAIL",
                                  "--reviewer-session", "sess-reviewer")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "FIX_REQUIRED")
        (self.project / "batch2.md").write_text(
            "# Repair batch — attempt 2\n\nChange VALUE to 3.\n",
            encoding="utf-8")
        (self.project / "touched.md").write_text(
            "- src/demo.py\n", encoding="utf-8")
        claim = {"finding_ids": ["M1"], "reason": "CANDIDATE_HASH_CHANGE",
                 "evidence": {"prior_candidate_sha256": "a" * 64,
                              "new_candidate_sha256": "b" * 64},
                 "progress_basis": None}
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        proc, basis = h.run_cli(self.project, "progress", "check", "--task",
                                "demo-task", "--batch", "batch2.md")
        claim["progress_basis"] = basis["basis"]
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        h.expect_refusal(self.project, "attempt", "open", "--task",
                         "demo-task", "--batch", "batch2.md",
                         code="MATERIAL_CLAIM_MISSING")
        proc, payload = h.run_cli(
            self.project, "attempt", "open", "--task", "demo-task",
            "--batch", "batch2.md", "--claim-file", "claim.json")
        self.assertEqual(payload["attempt"], 2)
        engineer_run(self.project, batch="batch2.md")
        (self.project / "check_state.json").unlink()
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 3\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "repaired\n", encoding="utf-8")
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")
        proc, payload = h.run_cli(self.project, "envelope", "freeze",
                                  "--task", "demo-task")
        self.assertIn("attempt_00000002", payload["path"])
        review2 = review_text(self.project)
        h.run_cli(self.project, "review", "validate", "--task", "demo-task",
                  "--review", "review.md",
                  "--reviewer-session", "sess-reviewer")
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        proc, payload = h.run_cli(self.project, "accept", "--task",
                                  "demo-task", "--actor", "OWNER",
                                  "--decision", "ACCEPTED",
                                  "--review", "review.md")
        self.assertEqual(payload["decision"], "ACCEPTED")
        attempts_dir = (self.project / ".agent-loop" / "tasks" /
                        "demo-task" / "attempts")
        self.assertTrue((attempts_dir / "attempt_00000001" /
                         "envelope").is_dir())
        self.assertTrue((attempts_dir / "attempt_00000002" /
                         "envelope").is_dir())


class B5_PlaunchProgressGate(SpineFixture):
    def setUp(self):
        self._build("b5-gate")

    def test_attempt_open_blocks_duplicate_and_requires_claim(self):
        (self.project / "batch2.md").write_text(
            "# Repair batch — attempt 2\n\nChange VALUE to 3.\n",
            encoding="utf-8")
        review = review_text(self.project, verdict="FAIL",
                             findings="- M1: needs repair\n",
                             corrections=(
                                 "- M1: `NONE_REQUIRED` — rationale: will "
                                 "repair in attempt 2 — evidence: "
                                 "`report/IMPLEMENTATION.md#done`\n"))
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "FAIL",
                  "--reviewer-session", "sess-reviewer")
        same = (self.project / "same.md")
        same.write_text(
            "# Repair batch — unchanged wrapper\n\n"
            "Engineering change for attempt 1.\n", encoding="utf-8")
        h.expect_refusal(self.project, "attempt", "open", "--task",
                         "demo-task", "--batch", "same.md",
                         code="ATTEMPT_PROGRESS_BLOCKED")
        h.expect_refusal(self.project, "attempt", "open", "--task",
                         "demo-task", "--batch", "batch2.md",
                         code="MATERIAL_CLAIM_MISSING")
        claim = {"finding_ids": ["M1"], "reason": "CANDIDATE_HASH_CHANGE",
                 "evidence": {"prior_candidate_sha256": "a" * 64,
                              "new_candidate_sha256": "b" * 64},
                 "progress_basis": None}
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        proc, basis = h.run_cli(self.project, "progress", "check", "--task",
                                "demo-task", "--batch", "batch2.md")
        claim["progress_basis"] = basis["basis"]
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        proc, payload = h.run_cli(self.project, "attempt", "open", "--task",
                                  "demo-task", "--batch", "batch2.md",
                                  "--claim-file", "claim.json")
        self.assertEqual(payload["attempt"], 2)


class B6_ContextClosure(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("b6", self)
        h.write_task(self.project,
                     required_skills=["skills/demo-skill/SKILL.md"])
        skill_dir = self.project / "skills" / "demo-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("demo skill body\n",
                                            encoding="utf-8")

    def test_corrupted_payload_refuses_verify(self):
        h.run_cli(self.project, "context", "build", "--task", "demo-task")
        pack = (self.project / ".agent-loop" / "tasks" / "demo-task" /
                "context_pack.md")
        pack.write_bytes(b"# CORRUPTED CONTEXT\n")
        h.expect_refusal(self.project, "context", "verify", "--task",
                         "demo-task", "--pack",
                         ".agent-loop/tasks/demo-task/context_pack.md",
                         code="CONTEXT_PAYLOAD_DRIFT")

    def test_repair_pack_carries_complete_bodies_and_commands(self):
        (self.project / "batch.md").write_text(
            "# Repair batch\n\nfix\n", encoding="utf-8")
        (self.project / "touched.md").write_text("- src/demo.py\n",
                                                 encoding="utf-8")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "ACTIVE")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "FIX_REQUIRED")
        proc, payload = h.run_cli(self.project, "pack", "build", "--task",
                                  "demo-task", "--iteration", "1",
                                  "--batch", "batch.md", "--touched",
                                  "touched.md")
        pack = Path(payload["pack"])
        text = pack.read_text("utf-8")
        self.assertIn("ual-task/1", text)
        self.assertIn("demo skill body", text)
        self.assertIn("check_demo.py", text)


class B7_FeedbackLoop(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("b7", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.write_config(self.project)

    def test_report_is_updatable_current_state(self):
        proc, first = h.run_cli(self.project, "report", "efficiency",
                                "--task", "demo-task")
        self.assertEqual(first["restoration_seconds"], "UNKNOWN")
        proc, second = h.run_cli(self.project, "report", "efficiency",
                                 "--task", "demo-task")
        self.assertEqual(second["generation"], first["generation"] + 1)

    def test_run_bound_checkpoint_makes_restoration_measured(self):
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(self.project, "report", "checkpoint", "--task",
                  "demo-task", "--run", run["run_id"],
                  "--kind", "restoration", "--seconds", "3.25")
        proc, payload = h.run_cli(self.project, "report", "efficiency",
                                  "--task", "demo-task")
        self.assertEqual(payload["restoration_seconds"], 3.25)

    def test_dispositions_gate_repair_attempt(self):
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "ACTIVE")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "FIX_REQUIRED")
        (self.project / "review.md").write_text(
            "## Efficiency disposition\n\n"
            "- ED-001: APPLY_NEXT_TASK — pack context before repair\n",
            encoding="utf-8")
        h.run_cli(self.project, "report", "efficiency", "--task",
                  "demo-task", "--dispositions", "review.md")
        (self.project / "batch.md").write_text(
            "# Repair batch\n\nfix now\n", encoding="utf-8")
        h.expect_refusal(self.project, "attempt", "open", "--task",
                         "demo-task", "--batch", "batch.md",
                         code="EFFICIENCY_PENDING_UNACKNOWLEDGED")
        proc, payload = h.run_cli(
            self.project, "attempt", "open", "--task", "demo-task",
            "--batch", "batch.md",
            "--efficiency-ack", "ED-001=APPLIED:packed context first")
        self.assertEqual(payload["attempt"], 1)


class B8_NativeHandoff(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("b8", self)
        h.write_task(self.project)
        h.authority(self.project, transport="native")

    def test_native_route_refuses_direct_child_spawn(self):
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         "--argv-json", json.dumps(
                             [h.sys_executable(), "-c", "print('x')"]),
                         code="NATIVE_HANDOFF_REQUIRED")

    def test_native_manual_handoff_cycle(self):
        h.run_cli(self.project, "context", "build", "--task", "demo-task")
        h.run_cli(self.project, "context", "verify", "--task", "demo-task",
                  "--pack", ".agent-loop/tasks/demo-task/context_pack.md")
        proc, payload = h.run_cli(self.project, "handoff", "issue",
                                  "--task", "demo-task",
                                  "--session-id", "sess-engineer")
        request_id = payload["request_id"]
        self.assertEqual(payload["observed_identity"], "UNKNOWN")
        proc, claims = h.run_cli(self.project, "claim", "scan")
        self.assertEqual(claims["claims"][0]["status"], "ACTIVE")
        result = self.project / "native_result.json"
        result.write_bytes(b'{"done": true, "notes": "synthetic receiver"}\n')
        h.run_cli(self.project, "handoff", "receive", "--task", "demo-task",
                  "--request", request_id, "--result-file",
                  "native_result.json", "--session-id", "sess-engineer")
        h.expect_refusal(self.project, "handoff", "receive", "--task",
                         "demo-task", "--request", request_id,
                         "--result-file", "native_result.json",
                         "--session-id", "sess-engineer",
                         code="REQUEST_ALREADY_RECEIVED")
        h.expect_refusal(self.project, "handoff", "confirm", "--task",
                         "demo-task", "--request", request_id,
                         "--actor", "ENG-SYNTH", "--decision", "COMPLETED",
                         code="AUTHORITY_ACTOR_NOT_OWNER")
        proc, payload = h.run_cli(self.project, "handoff", "confirm",
                                  "--task", "demo-task", "--request",
                                  request_id, "--actor", "OWNER",
                                  "--decision", "COMPLETED")
        self.assertEqual(payload["terminal_evidence_origin"],
                         "OWNER_ATTESTED")
        self.assertEqual(payload["observed_identity"], "UNKNOWN")
        proc, claims = h.run_cli(self.project, "claim", "scan")
        self.assertIn(claims["claims"][0]["status"],
                      ("RELEASED", "ABANDONED"))


class B9_Reconciliation(SpineFixture):
    def setUp(self):
        self._build("b9", with_engineer=False)

    def test_seal_requires_reviewer_session(self):
        review = review_text(self.project)
        h.expect_refusal(self.project, "review", "seal", "--task",
                         "demo-task", "--review", "review.md",
                         "--verdict", "PASS",
                         code="REVIEWER_SESSION_REQUIRED")

    def test_acceptance_reverifies_authority_config(self):
        review = review_text(self.project)
        h.run_cli(self.project, "review", "validate", "--task", "demo-task",
                  "--review", "review.md",
                  "--reviewer-session", "sess-reviewer")
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        config = self.project / ".agent-loop" / "config.json"
        original = config.read_bytes()
        data = json.loads(original.decode("utf-8"))
        data["owner_actor"] = "OWNER"
        data["actors"]["OWNER"]["roles"] = ["OWNER", "ENGINEER"]
        config.write_bytes(json.dumps(data, indent=2).encode("utf-8"))
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="AUTHORITY_CONFIG_DRIFT")
        config.write_bytes(original)
        proc, payload = h.run_cli(self.project, "accept", "--task",
                                  "demo-task", "--actor", "OWNER",
                                  "--decision", "ACCEPTED",
                                  "--review", "review.md")
        self.assertEqual(payload["decision"], "ACCEPTED")

    def test_lineclean_example_is_intact_and_green(self):
        provenance = json.loads(
            (LINECLEAN / "PROVENANCE.json").read_text("utf-8"))
        for member in provenance["members"]:
            if member["transform"] != "byte-identical copy":
                continue
            path = LINECLEAN / member["path"]
            self.assertEqual(sha(path), member["public_sha256"],
                             member["path"])
        proc = subprocess.run(
            [h.sys_executable(), "-I", "-S", "-B", "-m", "unittest",
             "discover", "-s", "tests"],
            cwd=str(LINECLEAN), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        self.assertIn("Ran 17 tests", proc.stderr, proc.stderr)
        self.assertIn("OK", proc.stderr, proc.stderr)


class PB10_LogClosure(SpineFixture):
    def setUp(self):
        self._build("pb10", with_engineer=False)

    def test_log_and_script_tamper_after_seal_refuses_acceptance(self):
        review = review_text(self.project)
        h.run_cli(self.project, "review", "validate", "--task", "demo-task",
                  "--review", "review.md",
                  "--reviewer-session", "sess-reviewer")
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        runs_dir = self.project / ".agent-loop" / "runs"
        run_id = sorted(p.name for p in runs_dir.iterdir())[0]
        log = runs_dir / run_id / "log.txt"
        log.write_bytes(log.read_bytes() + b"tampered after seal\n")
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="VALIDATION_LOG_DRIFT")
        log.write_bytes(log.read_bytes().replace(
            b"tampered after seal\n", b""))
        script = self.project / "check_demo.py"
        original = script.read_bytes()
        script.write_bytes(original + b"# mutated fixture\n")
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="CAPTURE_CLOSURE_DRIFT")
        script.write_bytes(original)


class PB11_LightReview(SpineFixture):
    def _build_light(self, name):
        self.project = h.fresh_project(name, self)
        h.write_task(self.project, mode="LIGHT", risk="LOW",
                     novelty="ROUTINE", ambiguity="CLEAR",
                     oracle_strength="STRONG", requirements=[],
                     requirement_ids=[], success_criteria_count=0)
        h.write_child(self.project, "check_demo.py", "print('ok')\n")
        _, path = h.write_task(self.project, mode="LIGHT", risk="LOW",
                               novelty="ROUTINE", ambiguity="CLEAR",
                               oracle_strength="STRONG", requirements=[],
                               requirement_ids=[],
                               success_criteria_count=0)
        task = json.loads(path.read_text("utf-8"))
        task["validation"]["commands"][0]["expected_outcomes"] = ["GREEN"]
        task["validation"]["commands"][0]["argv"] = [
            h.sys_executable(), "check_demo.py"]
        path.write_text(json.dumps(task, indent=2), "utf-8")
        h.authority(self.project)
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")

    def setUp(self):
        self._build_light("pb11")

    def test_light_review_without_convergence_is_usable(self):
        (self.project / "proof_one.json").write_bytes(b'{"p": 1}\n')
        (self.project / "proof_two.json").write_bytes(b'{"p": 2}\n')
        text = (
            "# Independent review — demo-task (SYNTHETIC fixture)\n\n"
            "## Contract compliance\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact"
            " `proof_one.json` sha256 `" + sha(
                self.project / "proof_one.json") + "` origin"
            " `REVIEWER_RECOMPUTED` action `recomputed fixture digests`"
            " candidate `demo-task`\n\n"
            "## Adversarial validity\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact"
            " `proof_two.json` sha256 `" + sha(
                self.project / "proof_two.json") + "` origin"
            " `REVIEWER_REEXECUTED` action `re-executed fixture checks`"
            " candidate `demo-task`\n\n"
            "## Findings\n\n- NONE\n\n## Durable correction\n\n"
            "- Mandated change: `NONE`\n")
        (self.project / "review.md").write_text(text, encoding="utf-8")
        proc, payload = h.run_cli(self.project, "review", "validate",
                                  "--task", "demo-task",
                                  "--review", "review.md",
                                  "--reviewer-session", "sess-reviewer")
        self.assertTrue(payload["ok"])


class PB12_BoundedOverflow(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("pb12", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))

    def test_overflow_bounds_disk_and_rejects_success_evidence(self):
        body = ("import sys\n"
                "sys.stdout.write('x' * 524288)\n"
                "sys.stdout.flush()\n")
        h.write_child(self.project, "burst.py", body)
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "burst.py"]),
            "--log-cap-bytes", "1024")
        self.assertTrue(run["overflow"])
        log = (self.project / ".agent-loop" / "runs" / run["run_id"] /
               "log.txt")
        self.assertLessEqual(log.stat().st_size, 2048)
        self.assertEqual(run["log"]["bytes"], log.stat().st_size)
        h.expect_refusal(self.project, "validate", "record", "--task",
                         "demo-task", "--run", run["run_id"],
                         "--ordinal", "1",
                         code="VALIDATION_OUTPUT_TRUNCATION_INVALID")

    def test_stdin_delivery_supervised_while_child_delayed(self):
        body = ("import sys, time\n"
                "time.sleep(0.4)\n"
                "data = sys.stdin.buffer.read()\n"
                "import hashlib, json, os\n"
                "os.makedirs('report', exist_ok=True)\n"
                "open('report/ack.json', 'w').write(json.dumps({\n"
                "    'schema': 'ual-ack/1',\n"
                "    'run_id': os.environ.get('UAL_RUN_ID'),\n"
                "    'task': os.environ.get('UAL_TASK'),\n"
                "    'stdin_sha256': hashlib.sha256(data).hexdigest()}))\n")
        h.write_child(self.project, "slow_ack.py", body)
        (self.project / "stdin.txt").write_bytes(b"payload line\n" * 100000)
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "slow_ack.py"]),
            "--stdin-file", "stdin.txt", "--ack-path", "report/ack.json",
            "--log-cap-bytes", "1024")
        self.assertIs(run["delivered"], True)
        self.assertFalse(run["overflow"])


class IMP_LifetimeCaps(unittest.TestCase):
    def test_no_lifetime_attempt_or_session_caps(self):
        import agent_loop.attempts as attempts_mod
        import agent_loop.authority as authority_mod
        self.assertFalse(hasattr(attempts_mod, "MAX_ATTEMPTS"),
                         "a lifetime attempt cap reappeared")
        self.assertFalse(hasattr(authority_mod, "MAX_SESSIONS"),
                         "a lifetime session cap reappeared")
        project = h.fresh_project("imp-caps", None)
        try:
            h.write_task(project)
            h.write_config(project)
            cfg = (project / ".agent-loop" / "config.json")
            data = json.loads(cfg.read_text("utf-8"))
            data["actors"]["OWNER"]["roles"] = ["OWNER", "OBSERVER"]
            cfg.write_text(json.dumps(data, indent=2), "utf-8")
            self.assertIsNone(attempts_mod.current_seq(project, "demo-task"))
            task = {"id": "demo-task"}
            seq = attempts_mod.ensure_current(project, task)
            self.assertEqual(seq, 1)
            for expected in range(2, 60):
                attempts_mod._write_attempt(project, task, seq=expected,
                                            predecessor=None, progress=None,
                                            efficiency_acks=[])
                self.assertEqual(
                    attempts_mod.current_seq(project, "demo-task"),
                    expected)
            for index in range(600):
                authority_mod.register_session(
                    project, "OWNER", "OBSERVER", "manual",
                    f"sess-obs-{index:04d}", "owner")
            proc, payload = h.run_cli(project, "session", "register",
                                      "--actor", "OWNER", "--role",
                                      "OBSERVER", "--transport", "manual",
                                      "--session-id", "sess-after-600",
                                      "--origin", "owner")
            self.assertTrue(payload["ok"])
        finally:
            shutil.rmtree(project, ignore_errors=True)


class IMP_NeutralUsageReceipts(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("imp-usage", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)

    def test_receipts_bound_to_run_and_unknown_stays_unknown(self):
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        (self.project / "usage.json").write_bytes(
            b'{"tokens": 123}')
        proc, payload = h.run_cli(
            self.project, "usage", "record", "--task", "demo-task",
            "--run", run["run_id"], "--usage-file", "usage.json")
        self.assertEqual(payload["tokens"], 123)
        self.assertEqual(payload["cost"], "UNKNOWN")
        self.assertEqual(payload["model_observed"], "UNKNOWN")
        proc, payload = h.run_cli(self.project, "report", "efficiency",
                                  "--task", "demo-task")
        self.assertEqual(payload["tokens_total"], 123)
        self.assertEqual(payload["cost_total"], "UNKNOWN")


class IMP_NonPythonClassification(unittest.TestCase):
    def test_user_declared_non_python_validation_preflights(self):
        project = h.fresh_project("imp-nonpy", None)
        try:
            h.write_task(project)
            (project / "src" / "demo.py").unlink()
            (project / "src" / "tool.ps1").write_bytes(
                b"Write-Output 'ok'\n")
            _, path = h.write_task(project)
            task = json.loads(path.read_text("utf-8"))
            task["candidate"]["allowlist"] = ["src/tool.ps1"]
            task["requirement_ids"] = ["R1"]
            task["requirements"] = [
                {"id": "R1", "criterion": 1, "command": 1,
                 "evidence": "TEST_OUTPUT"}]
            task["validation"]["commands"] = [
                {"ordinal": 1, "cwd": ".",
                 "argv": ["pwsh", "-File", "src/tool.ps1"],
                 "expected_outcomes": ["GREEN"]}]
            path.write_text(json.dumps(task, indent=2), "utf-8")
            proc, payload = h.run_cli(project, "task-validate",
                                      "--task", "task.json")
            self.assertTrue(payload["ok"])
        finally:
            shutil.rmtree(project, ignore_errors=True)


class IMP_ProgressiveRetrieval(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("imp-retrieval", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py",
                      "print('retrievable evidence marker')\n")
        h.write_config(self.project)

    def test_bounded_delta_and_stop_on_unchanged_evidence(self):
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        proc, first = h.run_cli(self.project, "context", "retrieve",
                                "--task", "demo-task", "--need",
                                "retrievable evidence", "--run",
                                run["run_id"])
        self.assertTrue(first["spans"])
        span = first["spans"][0]
        self.assertIn("sha256", span)
        log = (self.project / ".agent-loop" / "runs" / run["run_id"] /
               "log.txt")
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        chunk = "\n".join(lines[span["start_line"] - 1:span["end_line"]])
        self.assertEqual(hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                         span["sha256"])
        h.expect_refusal(self.project, "context", "retrieve", "--task",
                         "demo-task", "--need", "retrievable evidence",
                         "--run", run["run_id"],
                         code="RETRIEVAL_NO_NEW_EVIDENCE")


class IMP_PhaseCheckpoints(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("imp-checkpoint", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")

    def test_compaction_requires_verified_checkpoint(self):
        h.run_cli(self.project, "context", "build", "--task", "demo-task")
        h.expect_refusal(self.project, "context", "build", "--task",
                         "demo-task",
                         code="CONTEXT_COMPACTION_UNSAFE")
        h.run_cli(self.project, "checkpoint", "save", "--task", "demo-task",
                  "--phase", "before-compaction")
        proc, payload = h.run_cli(self.project, "checkpoint", "verify",
                                  "--task", "demo-task")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["phase"], "before-compaction")
        proc, payload = h.run_cli(self.project, "context", "build",
                                  "--task", "demo-task")
        self.assertTrue(payload["ok"])
        proc, payload = h.run_cli(self.project, "checkpoint", "save",
                                  "--task", "demo-task",
                                  "--phase", "after-compaction")
        proc, payload = h.run_cli(self.project, "checkpoint", "verify",
                                  "--task", "demo-task")
        self.assertEqual(payload["phase"], "after-compaction")


class IMP_ScopedMemoryPromotion(unittest.TestCase):
    def test_promotion_is_explicit_and_traceable(self):
        project = h.fresh_project("imp-promote", None)
        try:
            h.write_task(project)
            h.write_config(project)
            h.run_cli(project, "lessons", "record", "--task", "demo-task",
                      "--finding", "M2", "--text", "always freeze before review")
            proc, payload = h.run_cli(project, "lessons", "promote",
                                      "--task", "demo-task", "--finding",
                                      "M2", "--to", "GLOBAL_RULES.md")
            self.assertTrue(payload["ok"])
            self.assertTrue((project / "GLOBAL_RULES.md").is_file())
            h.expect_refusal(project, "lessons", "promote", "--task",
                             "demo-task", "--finding", "M2", "--to",
                             "GLOBAL_RULES.md", code="PROMOTION_EXISTS")
        finally:
            shutil.rmtree(project, ignore_errors=True)


class IMP_Inventory(unittest.TestCase):
    def test_duplicates_listed_and_connectors_default_zero(self):
        project = h.fresh_project("imp-inventory", None)
        try:
            (project / "skills" / "a").mkdir(parents=True)
            (project / "skills" / "b").mkdir(parents=True)
            body = "shared instruction body\n"
            (project / "skills" / "a" / "SKILL.md").write_text(body,
                                                               encoding="utf-8")
            (project / "skills" / "b" / "SKILL.md").write_text(body,
                                                               encoding="utf-8")
            proc, payload = h.run_cli(project, "inventory")
            self.assertGreaterEqual(len(payload["duplicate_groups"]), 1)
            self.assertEqual(payload["external_connectors"], 0)
        finally:
            shutil.rmtree(project, ignore_errors=True)


class IMP_InstallerLifecycle(unittest.TestCase):
    def _source(self, project):
        source = project / "_source-pkg"
        (source / "docs").mkdir(parents=True)
        (source / "README.md").write_bytes(b"pkg readme\n")
        (source / "docs" / "guide.md").write_bytes(b"guide\n")
        return source

    def test_plan_dryrun_apply_doctor_and_unowned_refusal(self):
        project = h.fresh_project("imp-install", None)
        try:
            source = self._source(project)
            target = project / "_target"
            target.mkdir()
            (target / "README.md").write_bytes(b"pre-existing unowned\n")
            args = ["--source", str(source), "--target", str(target)]
            proc, plan = h.run_cli(project, "install", "plan", *args)
            self.assertIn("README.md",
                          [item["path"] for item in plan["refused"]])
            h.run_cli(project, "install", "dry-run", *args)
            self.assertEqual((target / "README.md").read_bytes(),
                             b"pre-existing unowned\n")
            (target / "README.md").unlink()
            proc, payload = h.run_cli(project, "install", "apply", *args)
            self.assertTrue((target / ".ual-install" / "ownership.json")
                            .is_file())
            proc, payload = h.run_cli(project, "install", "doctor", *args)
            self.assertEqual(payload["modified"], [])
            (target / "docs" / "guide.md").write_bytes(b"tampered\n")
            proc, payload = h.run_cli(project, "install", "doctor", *args)
            self.assertEqual(payload["modified"], ["docs/guide.md"])
            proc, payload = h.run_cli(project, "install", "apply", *args)
            self.assertEqual((target / "docs" / "guide.md").read_bytes(),
                             b"guide\n")
        finally:
            shutil.rmtree(project, ignore_errors=True)


class AUDIT2_StateAuthority(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("aud2-state", self)
        h.write_task(self.project)
        h.authority(self.project)

    def test_fresh_retrieve_then_lifecycle_keeps_state_schema(self):
        h.write_child(self.project, "check_demo.py",
                      "print('marker')\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps(
                [h.sys_executable(), "check_demo.py"]))
        h.run_cli(self.project, "context", "retrieve", "--task", "demo-task",
                  "--need", "marker", "--run", run["run_id"])
        state_path = (self.project / ".agent-loop" / "tasks" / "demo-task" /
                      "state.json")
        state = json.loads(state_path.read_text("utf-8"))
        self.assertEqual(state.get("schema"), "ual-state/1")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "ACTIVE")

    def test_disposition_recording_before_lifecycle(self):
        (self.project / "review.md").write_text(
            "## Efficiency disposition\n\n"
            "- ED-9: NO_ACTION_WITH_REASON — nothing to apply\n",
            encoding="utf-8")
        proc, payload = h.run_cli(self.project, "report", "efficiency",
                                  "--task", "demo-task",
                                  "--dispositions", "review.md")
        state_path = (self.project / ".agent-loop" / "tasks" / "demo-task" /
                      "state.json")
        state = json.loads(state_path.read_text("utf-8"))
        self.assertEqual(state.get("schema"), "ual-state/1")
        self.assertTrue(state.get("pending_efficiency"))

    def test_attempt_creation_requires_trusted_config(self):
        bare = h.fresh_project("aud2-noauth", self)
        h.write_task(bare)
        h.write_child(bare, "check_demo.py", h.check_script(True))
        h.expect_refusal(bare, "event", "record", "--task", "demo-task",
                         "--tool", "bash", "--detail", "x", "--exit", "0",
                         code="AUTHORITY_CONFIG_REQUIRED")
        self.assertFalse((bare / ".agent-loop" / "tasks" / "demo-task" /
                          "attempts").exists())

    def test_transcript_export_needs_verifier_or_owner_attestation(self):
        h.run_cli(self.project, "event", "record", "--task", "demo-task",
                  "--tool", "bash", "--detail", "step", "--exit", "0")
        events_file = sorted((self.project / ".agent-loop" / "tasks" /
                              "demo-task" / "attempts").glob(
                                  "attempt_*/events.jsonl"))[-1]
        export = {
            "schema": "ual-transcript-export/1",
            "task": "demo-task",
            "events_sha256": hashlib.sha256(
                events_file.read_bytes()).hexdigest(),
            "event_count": 1,
            "complete": True,
        }
        (self.project / "export.json").write_bytes(
            json.dumps(export).encode())
        h.expect_refusal(self.project, "event", "ingest-export", "--task",
                         "demo-task", "--file", "export.json",
                         code="TRANSCRIPT_VERIFIER_REQUIRED")
        proc, payload = h.run_cli(self.project, "event", "ingest-export",
                                  "--task", "demo-task",
                                  "--file", "export.json",
                                  "--attested-by", "OWNER")
        self.assertEqual(payload["completeness"], "OWNER_ATTESTED")
        meta_dir = events_file.parent
        meta = json.loads((meta_dir / "events_meta.json").read_text("utf-8"))
        self.assertNotEqual(meta["completeness"], "VERIFIED")


class AUDIT2_LaunchRouting(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("aud2-launch", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)

    def test_spawn_failure_releases_claim_with_no_child_evidence(self):
        bare = h.fresh_project("aud2-spawnfail", self)
        h.write_task(bare)
        h.write_config(bare, model=None)
        cfg = bare / ".agent-loop" / "config.json"
        data = json.loads(cfg.read_text("utf-8"))
        data["role_bindings"]["ENGINEER_PRIMARY"]["argv"] = [
            "definitely-missing-engineer.exe"]
        cfg.write_text(json.dumps(data, indent=2), "utf-8")
        h.register_sessions(bare)
        proc, run = h.run_cli(
            bare, "run", "--task", "demo-task", "--purpose", "ENGINEER",
            "--session-id", "sess-engineer", expect=2)
        proc, claims = h.run_cli(bare, "claim", "scan")
        active = [c for c in claims["claims"] if c["status"] == "ACTIVE"]
        self.assertEqual(active, [])
        released = [c for c in claims["claims"]
                    if c["status"] == "RELEASED" and
                    (c.get("terminal_evidence") or {}).get("class") ==
                    "SPAWN_FAILED_NO_CHILD"]
        self.assertTrue(released)

    def test_engineer_argv_must_come_from_trusted_binding(self):
        h.write_child(self.project, "engineer_child.py", "print('ok')\n")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         "--argv-json", json.dumps(
                             [h.sys_executable(), "-c", "print('evil')"]),
                         code="ENGINEER_ARGV_NOT_CONFIGURED")
        proc, claims = h.run_cli(self.project, "claim", "scan")
        self.assertEqual([c for c in claims["claims"]
                          if c["status"] == "ACTIVE"], [])
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "ENGINEER", "--session-id", "sess-engineer")
        self.assertEqual(run["exit_code"], 0)

    def test_validation_run_must_use_declared_command(self):
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "VALIDATION",
                         "--argv-json", json.dumps(
                             [h.sys_executable(), "-c", "print('x')"]),
                         code="VALIDATION_ARGV_NOT_DECLARED")

    def test_seed_injected_and_observed(self):
        h.write_child(self.project, "seed_child.py",
                      "import os\nprint('seed=' + os.environ['UAL_SEED'])\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "OTHER", "--argv-json", json.dumps(
                [h.sys_executable(), "seed_child.py"]))
        log = (self.project / ".agent-loop" / "runs" / run["run_id"] /
               "log.txt").read_text("utf-8")
        self.assertIn("seed=0", log)
        self.assertEqual(run["seed"], "0")

    def test_inventory_with_root_agents_md_is_clean_json(self):
        (self.project / "AGENTS.md").write_text("root rules\n",
                                                encoding="utf-8")
        proc, payload = h.run_cli(self.project, "inventory")
        self.assertTrue(payload["ok"])
        self.assertIn("external_connectors", payload)


class AUDIT2_AuditPolicy(unittest.TestCase):
    """R1 continuation 6: bound audit route receipts and quota evidence."""

    POLICY = {
        "primary": "primary-auditor/1",
        "fallback": "fallback-auditor/1",
        "fallback_requires": "PRIMARY_QUOTA_EXHAUSTED",
    }

    def _lifecycle(self, name, with_policy=True):
        project = h.fresh_project(name, None)
        try:
            h.write_task(project, audit={"required": True})
            h.write_child(project, "check_demo.py", h.check_script(True))
            h.authority(project)
            if with_policy:
                config_path = project / ".agent-loop" / "config.json"
                data = json.loads(config_path.read_text("utf-8"))
                data["audit_policy"] = dict(self.POLICY)
                config_path.write_text(json.dumps(data, indent=2), "utf-8")
            for i in range(2):
                proc, run = h.run_cli(
                    project, "run", "--task", "demo-task", "--purpose",
                    "VALIDATION",
                    "--argv-json", json.dumps(
                        [h.sys_executable(), "check_demo.py"]))
                h.run_cli(project, "validate", "record", "--task",
                          "demo-task", "--run", run["run_id"],
                          "--ordinal", "1")
                if i == 0:
                    (project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
            (project / "report" / "IMPLEMENTATION.md").write_text(
                "done\n", encoding="utf-8")
            h.run_cli(project, "refresh", "--task", "demo-task")
            h.run_cli(project, "report-check", "--task", "demo-task")
            h.run_cli(project, "close", "--task", "demo-task")
            h.run_cli(project, "envelope", "freeze", "--task", "demo-task")
            proc, payload = h.run_cli(
                project, "audit", "package", "--task", "demo-task",
                "--iteration", "1", "--input", "src/demo.py",
                "--instruction", "task.json",
                "--validation", "report/IMPLEMENTATION.md")
            return project, payload["package"]
        except BaseException:
            shutil.rmtree(project, ignore_errors=True)
            raise

    def setUp(self):
        project, package = self._lifecycle("aud2-policy")
        self.addCleanup(shutil.rmtree, project, ignore_errors=True)
        self.project = project
        self.package = package

    def _result(self, payload, name="r.json"):
        path = self.project / name
        path.write_bytes(json.dumps(payload).encode("utf-8"))
        return name

    def _pkg_digests(self):
        pkg = self.project / self.package
        return {
            "manifest": hashlib.sha256(
                (pkg / "manifest.json").read_bytes()).hexdigest(),
            "payload": hashlib.sha256(
                (pkg / "audit_payload.bin").read_bytes()).hexdigest(),
        }

    def build_route(self, name="route.json", **kwargs):
        """Write a route receipt via the real CLI builder (defaults to a
        fully bound primary AUDIT_RESULT receipt), then apply any
        test-requested corruptions afterwards."""
        defaults = dict(
            kind="AUDIT_RESULT", requested="primary-auditor/1",
            observed=None, exit_code=0, status="FINISHED",
            result=None, result_sha=None, raw=None, raw_sha=None,
            provider_status=None, error_code=None, terminal=None,
            task="demo-task", schema="ual-audit-route-receipt/1",
            manifest_sha=None, payload_sha=None, package=None,
            drop_models=False, drop_kind=False)
        for key in list(defaults):
            if key in kwargs:
                defaults[key] = kwargs.pop(key)
        defaults.update(kwargs)
        if defaults["package"] is None:
            defaults["package"] = self.package
        observed = defaults["observed"] or defaults["requested"]
        args = ["audit", "route-receipt", "--task", "demo-task",
                "--package", defaults["package"], "--kind", defaults["kind"],
                "--requested-model", defaults["requested"],
                "--model-observed", observed,
                "--exit-code", str(defaults["exit_code"]),
                "--out", name]
        if defaults["result"] is not None:
            args += ["--result-file", defaults["result"]]
        if defaults["raw"] is not None:
            args += ["--raw-error-file", defaults["raw"]]
        if defaults["provider_status"] is not None:
            args += ["--provider-status", str(defaults["provider_status"])]
        if defaults["error_code"] is not None:
            args += ["--error-code", defaults["error_code"]]
        if defaults["terminal"]:
            args += ["--terminal"]
        h.run_cli(self.project, *args)
        receipt = json.loads((self.project / name).read_text("utf-8"))
        pkg_manifest, pkg_payload = self._pkg_digests()
        if defaults["manifest_sha"] is not None:
            receipt["package_manifest_sha256"] = defaults["manifest_sha"]
        if defaults["payload_sha"] is not None:
            receipt["package_payload_sha256"] = defaults["payload_sha"]
        if defaults["task"] != "demo-task":
            receipt["task"] = defaults["task"]
        if defaults["schema"] != "ual-audit-route-receipt/1":
            receipt["schema"] = defaults["schema"]
        if defaults["status"] != "FINISHED":
            receipt["status"] = defaults["status"]
        if defaults["result_sha"] is not None and "result" in receipt:
            receipt["result"]["sha256"] = defaults["result_sha"]
        if defaults["raw_sha"] is not None and "raw_error" in receipt:
            receipt["raw_error"]["sha256"] = defaults["raw_sha"]
        if defaults["drop_models"]:
            receipt.pop("model_observed", None)
        if defaults["drop_kind"]:
            receipt.pop("kind", None)
        (self.project / name).write_text(json.dumps(receipt, indent=2),
                                         "utf-8")
        return name

    def write_raw(self, name="raw_error.json", provider_status=429,
                  error_code=None, terminal=True):
        payload = {"terminal": terminal}
        if provider_status is not None:
            payload["provider_status"] = provider_status
        if error_code is not None:
            payload["error_code"] = error_code
        path = self.project / name
        path.write_bytes(json.dumps(payload).encode("utf-8"))
        return name

    def audit_record(self, result, route=None, allow_fallback=False,
                     expect=0):
        args = ["audit", "record", "--task", "demo-task", "--package",
                self.package, "--result-file", result]
        if route:
            args += ["--route-receipt", route]
        if allow_fallback:
            args += ["--allow-fallback"]
        return h.run_cli(self.project, *args, expect=expect)

    def quota_receipt(self, route=None, reason="PRIMARY_QUOTA_EXHAUSTED",
                      expect=0):
        args = ["audit", "quota-receipt", "--task", "demo-task",
                "--package", self.package, "--reason", reason]
        if route:
            args += ["--route-receipt", route]
        return h.run_cli(self.project, *args, expect=expect)

    def test_valid_primary_pass_records_with_full_receipt(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result)
        proc, payload = self.audit_record(result, route)
        self.assertEqual(payload["disposition"], "AUDIT_RESULT")
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["observed_model"], "primary-auditor/1")

    def test_route_receipt_wrong_schema_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result, schema="route/9")
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="ROUTE_RECEIPT_SCHEMA_INVALID")

    def test_route_receipt_wrong_task_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result, task="other-task")
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="ROUTE_RECEIPT_TASK_MISMATCH")

    def test_route_receipt_wrong_package_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(
            result=result, payload_sha="a" * 64)
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="ROUTE_RECEIPT_PACKAGE_MISMATCH")

    def test_route_receipt_result_bytes_mismatch_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result, result_sha="b" * 64)
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="ROUTE_RECEIPT_RESULT_BYTES_MISMATCH")

    def test_route_receipt_status_running_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result, status="RUNNING")
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="ROUTE_RECEIPT_STATUS_INVALID")

    def test_primary_pass_nonzero_exit_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result, exit_code=1)
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="AUDIT_PRIMARY_EXIT_NONZERO")

    def test_required_audit_refuses_missing_route_receipt(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        h.expect_refusal(
            self.project, "audit", "record", "--task", "demo-task",
            "--package", self.package, "--result-file", result,
            code="AUDIT_PRIMARY_IDENTITY_REQUIRED")

    def test_legacy_simple_route_json_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        (self.project / "legacy_route.json").write_bytes(
            json.dumps({"exit_code": 0}).encode("utf-8"))
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", "legacy_route.json",
                         code="ROUTE_RECEIPT_SCHEMA_INVALID")

    def test_result_request_model_mismatch_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "fallback-auditor/1"})
        route = self.build_route(result=result)
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="AUDIT_RESULT_MODEL_MISMATCH")

    def test_requested_observed_mismatch_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result,
                                 observed="someone-else/1")
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="AUDIT_ROUTE_MODEL_MISMATCH")

    def test_route_requested_model_must_match_observed_model(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result,
                                 requested="different-request/1",
                                 observed="primary-auditor/1")
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="AUDIT_ROUTE_MODEL_MISMATCH")

    def test_failure_facts_must_come_from_bound_raw_bytes(self):
        raw = self.write_raw(provider_status=None, terminal=True)
        h.expect_refusal(
            self.project, "audit", "route-receipt", "--task",
            "demo-task", "--package", self.package,
            "--kind", "PROVIDER_FAILURE",
            "--requested-model", "primary-auditor/1",
            "--model-observed", "primary-auditor/1",
            "--exit-code", "1", "--raw-error-file", raw,
            "--provider-status", "429", "--terminal",
            "--out", "forged-route.json",
            code="ROUTE_RECEIPT_RAW_EVIDENCE_MISMATCH")

    def test_valid_negative_primary_never_falls_back(self):
        result = self._result({
            "verdict": "FAIL",
            "findings": [{"severity": "P2", "location": "x",
                          "observed_evidence": "e", "impact": "i",
                          "reproduction": "r", "recommendation": "rec"}],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result, exit_code=1)
        proc, payload = self.audit_record(result, route,
                                          allow_fallback=True)
        self.assertEqual(payload["disposition"], "AUDIT_RESULT")
        self.assertEqual(payload["verdict"], "FAIL")

    def test_invalid_fail_findings_never_fall_back(self):
        result = self._result({
            "verdict": "FAIL", "findings": [{"severity": "P1"}],
            "requested_model": "primary-auditor/1"})
        route = self.build_route(result=result, exit_code=1)
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         "--allow-fallback",
                         code="AUDIT_RESULT_INVALID")

    def test_fallback_without_quota_receipt_refused(self):
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "fallback-auditor/1"})
        route = self.build_route(requested="fallback-auditor/1",
                                 observed="fallback-auditor/1",
                                 result=result)
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="AUDIT_FALLBACK_NOT_PERMITTED")

    def test_fallback_records_only_with_same_package_quota_receipt(self):
        raw = self.write_raw()
        fail_route = self.build_route(
            name="fail_route.json", kind="PROVIDER_FAILURE",
            requested="primary-auditor/1", observed="primary-auditor/1",
            exit_code=1, raw=raw, provider_status=429, terminal=True)
        self.quota_receipt(route=fail_route)
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "fallback-auditor/1"})
        route = self.build_route(requested="fallback-auditor/1",
                                 observed="fallback-auditor/1",
                                 result=result)
        proc, payload = self.audit_record(result, route)
        self.assertEqual(payload["disposition"], "AUDIT_RESULT")
        self.assertEqual(payload["observed_model"], "fallback-auditor/1")

    def test_fallback_revalidates_quota_evidence_chain(self):
        raw = self.write_raw()
        fail_route = self.build_route(
            name="fail_route.json", kind="PROVIDER_FAILURE",
            requested="primary-auditor/1", observed="primary-auditor/1",
            exit_code=1, raw=raw, provider_status=429, terminal=True)
        self.quota_receipt(route=fail_route)
        (self.project / raw).write_text(
            json.dumps({"terminal": True, "provider_status": 500}),
            "utf-8")
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "fallback-auditor/1"})
        route = self.build_route(requested="fallback-auditor/1",
                                 observed="fallback-auditor/1",
                                 result=result)
        h.expect_refusal(self.project, "audit", "record", "--task",
                         "demo-task", "--package", self.package,
                         "--result-file", result,
                         "--route-receipt", route,
                         code="AUDIT_FALLBACK_NOT_PERMITTED")

    def test_bare_quota_reason_refused(self):
        h.expect_refusal(self.project, "audit", "quota-receipt", "--task",
                         "demo-task", "--package", self.package,
                         "--reason", "PRIMARY_QUOTA_EXHAUSTED",
                         code="QUOTA_ROUTE_RECEIPT_REQUIRED")

    def test_quota_reason_mismatch_refused(self):
        raw = self.write_raw()
        fail_route = self.build_route(
            name="fail_route.json", kind="PROVIDER_FAILURE",
            requested="primary-auditor/1", observed="primary-auditor/1",
            exit_code=1, raw=raw, provider_status=429, terminal=True)
        h.expect_refusal(self.project, "audit", "quota-receipt", "--task",
                         "demo-task", "--package", self.package,
                         "--reason", "SOME_OTHER_REASON",
                         "--route-receipt", fail_route,
                         code="QUOTA_RECEIPT_REASON_INVALID")

    def test_quota_receipt_unproven_classification_refused(self):
        raw = self.write_raw(provider_status=500, terminal=True)
        fail_route = self.build_route(
            name="fail_route.json", kind="PROVIDER_FAILURE",
            requested="primary-auditor/1", observed="primary-auditor/1",
            exit_code=1, raw=raw, provider_status=500, terminal=True)
        h.expect_refusal(self.project, "audit", "quota-receipt", "--task",
                         "demo-task", "--package", self.package,
                         "--reason", "PRIMARY_QUOTA_EXHAUSTED",
                         "--route-receipt", fail_route,
                         code="QUOTA_CLASSIFICATION_UNPROVEN")

    def test_quota_receipt_unbound_raw_refused(self):
        self.write_raw()
        fail_route = self.build_route(
            name="fail_route.json", kind="PROVIDER_FAILURE",
            requested="primary-auditor/1", observed="primary-auditor/1",
            exit_code=1, raw="raw_error.json", raw_sha="c" * 64,
            provider_status=429, terminal=True)
        h.expect_refusal(self.project, "audit", "quota-receipt", "--task",
                         "demo-task", "--package", self.package,
                         "--reason", "PRIMARY_QUOTA_EXHAUSTED",
                         "--route-receipt", fail_route,
                         code="ROUTE_RECEIPT_RAW_BYTES_MISMATCH")

    def test_conditioned_pass_never_accepts(self):
        raw = self.write_raw()
        fail_route = self.build_route(
            name="fail_route.json", kind="PROVIDER_FAILURE",
            requested="primary-auditor/1", observed="primary-auditor/1",
            exit_code=1, raw=raw, provider_status=429, terminal=True)
        self.quota_receipt(route=fail_route)
        result = self._result({
            "verdict": "CONDITIONAL_PASS", "findings": [],
            "requested_model": "fallback-auditor/1"})
        route = self.build_route(requested="fallback-auditor/1",
                                 observed="fallback-auditor/1",
                                 result=result)
        h.run_cli(self.project, "audit", "record", "--task", "demo-task",
                  "--package", self.package, "--result-file", result,
                  "--route-receipt", route)
        self.write_review()
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="ACCEPTANCE_AUDIT_NOT_CLEAN_PASS")

    def test_optional_without_primary_preserves_unknown(self):
        project, package = self._lifecycle("aud2-nopolicy",
                                           with_policy=False)
        self.addCleanup(shutil.rmtree, project, ignore_errors=True)
        result = project / "r.json"
        result.write_bytes(json.dumps({
            "verdict": "PASS", "findings": [],
            "requested_model": "synthetic-auditor/1"}).encode("utf-8"))
        proc, payload = h.run_cli(
            project, "audit", "record", "--task", "demo-task",
            "--package", package, "--result-file", "r.json")
        self.assertEqual(payload["disposition"], "AUDIT_RESULT")
        self.assertEqual(payload["observed_model"], "UNKNOWN")

    def test_acceptance_rejects_transient_primary_policy_bypass(self):
        config_path = self.project / ".agent-loop" / "config.json"
        original = config_path.read_bytes()
        config = json.loads(original.decode("utf-8"))
        config["audit_policy"] = {"fallback_enabled": True}
        config_path.write_text(json.dumps(config, indent=2), "utf-8")
        result = self._result({
            "verdict": "PASS", "findings": [],
            "requested_model": "synthetic-auditor/1"})
        proc, payload = self.audit_record(result)
        self.assertEqual(payload["observed_model"], "UNKNOWN")
        config_path.write_bytes(original)
        self.write_review()
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="ACCEPTANCE_AUDIT_POLICY_MISMATCH")

    def write_review(self):
        (self.project / "proof_one.json").write_bytes(b'{"p": 1}\n')
        (self.project / "proof_two.json").write_bytes(b'{"p": 2}\n')
        envelope_dir = (self.project / ".agent-loop" / "tasks" /
                        "demo-task" / "attempts" / "attempt_00000001" /
                        "envelope")
        envelope_sha = hashlib.sha256(
            sorted(envelope_dir.glob("envelope_*.json"))[-1]
            .read_bytes()).hexdigest()
        text = (
            "# Independent review — demo-task (SYNTHETIC fixture)\n\n"
            "## Contract compliance\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact"
            " `proof_one.json` sha256 `" + sha(
                self.project / "proof_one.json") + "` origin"
            " `REVIEWER_RECOMPUTED` action `recomputed` candidate"
            " `demo-task`\n\n"
            "## Adversarial validity\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact"
            " `proof_two.json` sha256 `" + sha(
                self.project / "proof_two.json") + "` origin"
            " `REVIEWER_REEXECUTED` action `re-executed` candidate"
            " `demo-task`\n\n"
            "## Findings\n\n- NONE\n\n## Durable correction\n\n"
            "- Mandated change: `NONE`\n\n"
            "## Convergence disposition\n\n"
            "- Disposition: `CONVERGED`\n"
            "- Covered requirement IDs: `R1,R2`\n"
            "- Remaining material requirement IDs: `NONE`\n"
            "\n## Frozen envelope binding\n\n"
            "- Frozen envelope sha256: `" + envelope_sha + "`\n")
        (self.project / "review.md").write_text(text, encoding="utf-8")
        return self.project / "review.md"


class AUDIT2_ReviewAndObserver(SpineFixture):
    def setUp(self):
        self._build("aud2-review", with_engineer=False)

    def test_accepting_proof_must_bind_current_envelope(self):
        envelope_dir = (self.project / ".agent-loop" / "tasks" /
                        "demo-task" / "attempts" / "attempt_00000001" /
                        "envelope")
        envelope_sha = hashlib.sha256(
            sorted(envelope_dir.glob("envelope_*.json"))[-1]
            .read_bytes()).hexdigest()
        review_text(self.project)
        text = (self.project / "review.md").read_text("utf-8")
        unbound = text.split("\n## Frozen envelope binding")[0] + "\n"
        (self.project / "review.md").write_text(unbound, encoding="utf-8")
        h.expect_refusal(self.project, "review", "seal", "--task",
                         "demo-task", "--review", "review.md",
                         "--verdict", "PASS",
                         "--reviewer-session", "sess-reviewer",
                         code="REVIEW_PROOF_ENVELOPE_UNBOUND")
        text = (self.project / "review.md").read_text("utf-8")
        bound = text.replace(
            "## Convergence disposition",
            "## Frozen envelope binding\n\n"
            "- Frozen envelope sha256: `" + "0" * 64 + "`\n\n"
            "## Convergence disposition")
        (self.project / "review.md").write_text(bound, encoding="utf-8")
        proc, payload = h.run_cli(self.project, "review", "validate",
                                  "--task", "demo-task",
                                  "--review", "review.md",
                                  "--reviewer-session", "sess-reviewer")
        self.assertTrue(payload["ok"])
        h.expect_refusal(self.project, "review", "seal", "--task",
                         "demo-task", "--review", "review.md",
                         "--verdict", "PASS",
                         "--reviewer-session", "sess-reviewer",
                         code="REVIEW_PROOF_ENVELOPE_MISMATCH")
        bound = bound.replace("`" + "0" * 64 + "`",
                              "`" + envelope_sha + "`")
        (self.project / "review.md").write_text(bound, encoding="utf-8")
        proc, payload = h.run_cli(self.project, "review", "seal",
                                  "--task", "demo-task",
                                  "--review", "review.md",
                                  "--verdict", "PASS",
                                  "--reviewer-session", "sess-reviewer")
        self.assertTrue(payload["ok"])

    def test_native_writer_visible_to_immediate_observer_gate(self):
        project = h.fresh_project("aud2-native-obs", self)
        try:
            h.write_task(project, observer={"policy": "IMMEDIATE"})
            h.authority(project, transport="native")
            h.run_cli(project, "context", "build", "--task", "demo-task")
            h.run_cli(project, "context", "verify", "--task", "demo-task",
                      "--pack",
                      ".agent-loop/tasks/demo-task/context_pack.md")
            proc, payload = h.run_cli(project, "handoff", "issue",
                                      "--task", "demo-task",
                                      "--session-id", "sess-engineer")
            request_id = payload["request_id"]
            (project / "native_result.json").write_bytes(b'{"done": true}\n')
            h.run_cli(project, "handoff", "receive", "--task", "demo-task",
                      "--request", request_id, "--result-file",
                      "native_result.json", "--session-id", "sess-engineer")
            h.run_cli(project, "handoff", "confirm", "--task", "demo-task",
                      "--request", request_id, "--actor", "OWNER",
                      "--decision", "COMPLETED")
            (project / "report" / "IMPLEMENTATION.md").write_text(
                "done\n", encoding="utf-8")
            h.run_cli(project, "refresh", "--task", "demo-task")
            h.run_cli(project, "report-check", "--task", "demo-task")
            proc, payload = h.run_cli(project, "close", "--task",
                                      "demo-task", expect=2)
            codes = payload.get("errors") or []
            self.assertTrue(
                any("OBSERVER_RECEIPT_MISSING" in c and request_id in c
                    for c in codes), codes)
        finally:
            pass


class AUDIT2_PackAndDelivery(SpineFixture):
    def setUp(self):
        self._build("aud2-pack", with_engineer=False)

    def test_pack_verify_first_and_prelaunch_binding(self):
        review_text(self.project, verdict="FAIL",
                    findings="- M1: needs repair\n",
                    corrections=(
                        "- M1: `NONE_REQUIRED` — rationale: will repair — "
                        "evidence: `report/IMPLEMENTATION.md#done`\n"))
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "FAIL",
                  "--reviewer-session", "sess-reviewer")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "FIX_REQUIRED")
        (self.project / "batch2.md").write_text(
            "# Repair batch — attempt 2\n\nChange VALUE to 3.\n",
            encoding="utf-8")
        (self.project / "touched.md").write_text("- src/demo.py\n",
                                                 encoding="utf-8")
        claim = {"finding_ids": ["M1"], "reason": "CANDIDATE_HASH_CHANGE",
                 "evidence": {"prior_candidate_sha256": "a" * 64,
                              "new_candidate_sha256": "b" * 64},
                 "progress_basis": None}
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        proc, basis = h.run_cli(self.project, "progress", "check", "--task",
                                "demo-task", "--batch", "batch2.md")
        claim["progress_basis"] = basis["basis"]
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        h.expect_refusal(self.project, "attempt", "open", "--task",
                         "demo-task", "--batch", "batch2.md",
                         "--claim-file", "claim.json",
                         "--pack-iteration", "1",
                         code="PACK_NOT_VERIFIED")
        (self.project / "packbatch.md").write_bytes(
            (self.project / "batch2.md").read_bytes())
        h.run_cli(self.project, "pack", "build", "--task", "demo-task",
                  "--iteration", "1", "--batch", "batch2.md",
                  "--touched", "touched.md")
        proc, payload = h.run_cli(self.project, "pack", "verify", "--task",
                                  "demo-task", "--iteration", "1")
        proc, payload = h.run_cli(
            self.project, "attempt", "open", "--task", "demo-task",
            "--batch", "batch2.md", "--claim-file", "claim.json",
            "--pack-iteration", "1")
        self.assertEqual(payload["attempt"], 2)
        pack_dir = (self.project / ".agent-loop" / "tasks" / "demo-task" /
                    "packs" / "iteration_1")
        (pack_dir / "repair_pack.md").write_bytes(b"# drift\n")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="ATTEMPT_PACK_DRIFT")

    def test_delivery_requires_accepted_decision(self):
        review = review_text(self.project)
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        h.run_cli(self.project, "accept", "--task", "demo-task",
                  "--actor", "OWNER", "--decision", "REJECTED",
                  "--review", "review.md")
        h.expect_refusal(self.project, "report", "delivery", "--task",
                         "demo-task", code="DELIVERY_NOT_ACCEPTED")

    def test_efficiency_separates_writer_and_delivery_truth(self):
        proc, payload = h.run_cli(self.project, "report", "efficiency",
                                  "--task", "demo-task")
        self.assertFalse(payload["successful_completed_delivery"])
        self.assertFalse(payload["review_ready"])
        self.assertIn("all_writers_terminal", payload)


class AUDIT2_FilesystemRetrieval(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("aud2-fs", self)
        h.write_task(self.project)

    def test_installer_refuses_symlink_escape(self):
        source = self.project / "_src"
        (source / "sub").mkdir(parents=True)
        (source / "ok.txt").write_bytes(b"ok\n")
        outside = self.project / "outside-secret.txt"
        outside.write_bytes(b"outside\n")
        link = source / "escape.txt"
        try:
            os.symlink(outside, link)
        except OSError:
            self.skipTest("symlinks unavailable on this host")
        target = self.project / "_dst"
        target.mkdir()
        h.expect_refusal(self.project, "install", "plan", "--source",
                         str(source), "--target", str(target),
                         code="INSTALL_SOURCE_ESCAPE")

    def test_retrieval_returns_text_and_is_content_sensitive(self):
        h.write_child(self.project, "check_demo.py",
                      "print('alpha evidence line')\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        proc, first = h.run_cli(self.project, "context", "retrieve",
                                "--task", "demo-task", "--need",
                                "alpha evidence", "--run", run["run_id"])
        span = first["spans"][0]
        self.assertIn("alpha", span["text"])
        log = (self.project / ".agent-loop" / "runs" / run["run_id"] /
               "log.txt")
        original = log.read_bytes()
        log.write_bytes(original.replace(b"alpha evidence line",
                                         b"alpha CHANGED evidence"))
        proc, second = h.run_cli(self.project, "context", "retrieve",
                                 "--task", "demo-task", "--need",
                                 "alpha evidence", "--run", run["run_id"])
        self.assertIn("CHANGED", second["spans"][0]["text"])
        self.assertNotEqual(first["evidence_fingerprint"],
                            second["evidence_fingerprint"])


class REL_ReleaseBuilder(unittest.TestCase):
    """Exact public release construction: versioned allowlist, secret gate,
    deterministic ZIP + manifest, verification (CONTINUATION_TASK_5)."""

    def _fixture_root(self, project):
        root = project / "_relsrc"
        (root / "agent_loop").mkdir(parents=True)
        (root / "docs").mkdir()
        (root / "allowlist.txt").write_text(
            "# release-allowlist/1\n"
            "agent_loop/__init__.py\n"
            "docs/README.md\n",
            encoding="utf-8")
        (root / "agent_loop" / "__init__.py").write_bytes(b"__version__ = '1'\n")
        (root / "docs" / "README.md").write_bytes(b"# docs\n")
        return root

    def test_clean_build_verifies_and_is_deterministic(self):
        project = h.fresh_project("rel-clean", None)
        try:
            root = self._fixture_root(project)
            out_zip = project / "u.zip"
            out_manifest = project / "m.json"
            from agent_loop import release
            r1 = release.build(root, root / "allowlist.txt",
                               out_zip, out_manifest)
            r2 = release.build(root, root / "allowlist.txt",
                               project / "u2.zip", project / "m2.json")
            self.assertTrue(r1["ok"])
            self.assertEqual(r1["members"], r2["members"])
            self.assertEqual(out_zip.read_bytes(),
                             (project / "u2.zip").read_bytes())
            ver = release.verify(root, root / "allowlist.txt",
                                 out_zip, out_manifest)
            self.assertTrue(ver["ok"])
            self.assertEqual(ver["verified"], ["agent_loop/__init__.py",
                                               "docs/README.md"])
        finally:
            shutil.rmtree(project, ignore_errors=True)

    def test_private_and_secret_members_are_blocked(self):
        project = h.fresh_project("rel-secret", None)
        try:
            root = self._fixture_root(project)
            (root / ".env").write_bytes(b"TOKEN=1\n")
            (root / "PACKAGED_FILES.json").write_bytes(b"{}\n")
            (root / "allowlist.txt").write_text(
                "# release-allowlist/1\n"
                "agent_loop/__init__.py\n"
                "docs/README.md\n"
                ".env\n"
                "PACKAGED_FILES.json\n",
                encoding="utf-8")
            h.expect_refusal(project, "release", "build", "--release-root",
                             "_relsrc", "--allowlist", "allowlist.txt",
                             "--out-zip", "u.zip",
                             "--out-manifest", "m.json",
                             code="RELEASE_MEMBER_REFUSED")
            (root / "allowlist.txt").write_text(
                "# release-allowlist/1\n"
                "agent_loop/__init__.py\n"
                "docs/README.md\n",
                encoding="utf-8")
            (root / "agent_loop" / "__init__.py").write_bytes(
                b"api" + b"_key = 'deadbeef'\n")
            h.expect_refusal(project, "release", "build", "--release-root",
                             "_relsrc", "--allowlist", "allowlist.txt",
                             "--out-zip", "u.zip",
                             "--out-manifest", "m.json",
                             code="RELEASE_SECRET_SUSPECTED")
        finally:
            shutil.rmtree(project, ignore_errors=True)

    def test_drift_blocks_verification(self):
        project = h.fresh_project("rel-drift", None)
        try:
            root = self._fixture_root(project)
            from agent_loop import release
            out_zip = project / "u.zip"
            out_manifest = project / "m.json"
            release.build(root, root / "allowlist.txt", out_zip, out_manifest)
            (root / "docs" / "README.md").write_bytes(b"# drifted\n")
            h.expect_refusal(project, "release", "verify", "--release-root",
                             "_relsrc", "--allowlist", "allowlist.txt",
                             "--archive", "u.zip",
                             "--manifest", "m.json",
                             code="RELEASE_MEMBER_DRIFT")
        finally:
            shutil.rmtree(project, ignore_errors=True)

    def test_duplicate_archive_member_blocks_verification(self):
        project = h.fresh_project("rel-duplicate-zip", None)
        try:
            root = self._fixture_root(project)
            from agent_loop import release
            out_zip = project / "u.zip"
            out_manifest = project / "m.json"
            release.build(root, root / "allowlist.txt", out_zip, out_manifest)
            with zipfile.ZipFile(out_zip, "a") as archive:
                archive.writestr("docs/README.md", b"# docs\n")
            manifest = json.loads(out_manifest.read_text("utf-8"))
            manifest["archive_bytes"] = out_zip.stat().st_size
            manifest["archive_sha256"] = hashlib.sha256(
                out_zip.read_bytes()).hexdigest()
            out_manifest.write_text(json.dumps(manifest), encoding="utf-8")
            h.expect_refusal(project, "release", "verify", "--release-root",
                             "_relsrc", "--allowlist", "allowlist.txt",
                             "--archive", "u.zip", "--manifest", "m.json",
                             code="RELEASE_ARCHIVE_DRIFT")
        finally:
            shutil.rmtree(project, ignore_errors=True)

    def test_linked_parent_directory_blocks_release_build(self):
        project = h.fresh_project("rel-linked-parent", None)
        link = project / "_relsrc" / "linked"
        try:
            root = project / "_relsrc"
            target = root / "actual"
            target.mkdir(parents=True)
            (target / "member.txt").write_bytes(b"public\n")
            (root / "allowlist.txt").write_text(
                "# release-allowlist/1\nlinked/member.txt\n",
                encoding="utf-8")
            if os.name == "nt":
                made = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                    capture_output=True, text=True).returncode == 0
            else:
                try:
                    os.symlink(target, link, target_is_directory=True)
                    made = True
                except OSError:
                    made = False
            if not made:
                self.skipTest("directory link unavailable on this host")
            h.expect_refusal(project, "release", "build", "--release-root",
                             "_relsrc", "--allowlist", "allowlist.txt",
                             "--out-zip", "u.zip", "--out-manifest", "m.json",
                             code="RELEASE_MEMBER_REFUSED")
        finally:
            if link.is_symlink():
                link.unlink()
            elif link.exists():
                os.rmdir(link)
            shutil.rmtree(project, ignore_errors=True)

    def test_real_allowlist_covers_runtime_and_named_skills(self):
        allowlist = h.CHECKOUT / "RELEASE_ALLOWLIST.txt"
        self.assertTrue(allowlist.is_file(),
                        "RELEASE_ALLOWLIST.txt must exist at the root")
        text = allowlist.read_text("utf-8")
        self.assertIn("release-allowlist/1", text)
        for required in ("skills/karpathy-guidelines/SKILL.md",
                         "skills/ponytail/SKILL.md",
                         "agent_loop/cli.py",
                         "reference/agent_loop_contract.py",
                         "examples/offline_quickstart.py",
                         "tests/test_runtime_delivery_regressions.py"):
            self.assertIn(required, text.splitlines())
        for forbidden in ("PACKAGED_FILES.json", ".source/", ".validation/",
                          "REPAIR_TASK.md", "IMPLEMENTATION_REPORT.md"):
            self.assertNotIn(forbidden, text.splitlines())

    def test_named_skills_are_discoverable_and_frontmattered(self):
        for name in ("karpathy-guidelines", "ponytail"):
            path = (h.CHECKOUT / "skills" / name / "SKILL.md")
            self.assertTrue(path.is_file(), name)
            text = path.read_text("utf-8")
            self.assertTrue(text.startswith("---"), name)
            front = text.split("---", 2)[1]
            self.assertIn(f"name: {name}", front, name)
            self.assertIn("description:", front, name)
            self.assertIn("MIT", text, name)
        matrix = (h.CHECKOUT / "docs" / "SKILLS.md").read_text("utf-8")
        self.assertIn("karpathy-guidelines", matrix)
        self.assertIn("ponytail", matrix)


    def test_real_tree_builds_and_verifies_into_scratch(self):
        from agent_loop import release
        scratch = h.CHECKOUT / "tests" / ".scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        out_zip = scratch / "ual-archive.zip"
        out_manifest = scratch / "release-manifest.json"
        out_zip.unlink(missing_ok=True)
        out_manifest.unlink(missing_ok=True)
        build = release.build(h.CHECKOUT, h.CHECKOUT / "RELEASE_ALLOWLIST.txt",
                              out_zip, out_manifest)
        self.assertTrue(build["ok"])
        ver = release.verify(h.CHECKOUT,
                             h.CHECKOUT / "RELEASE_ALLOWLIST.txt",
                             out_zip, out_manifest)
        self.assertTrue(ver["ok"])
        self.assertGreater(len(ver["verified"]), 50)
        out_zip.unlink()
        out_manifest.unlink()


class AUDIT3_RouteReceiptBuilder(unittest.TestCase):
    def test_route_receipt_builder_writes_bound_receipt(self):
        project = h.fresh_project("aud3-builder", None)
        try:
            h.write_task(project, audit={"required": True})
            h.write_child(project, "check_demo.py", h.check_script(True))
            h.authority(project)
            for i in range(2):
                proc, run = h.run_cli(
                    project, "run", "--task", "demo-task", "--purpose",
                    "VALIDATION",
                    "--argv-json", json.dumps(
                        [h.sys_executable(), "check_demo.py"]))
                h.run_cli(project, "validate", "record", "--task",
                          "demo-task", "--run", run["run_id"],
                          "--ordinal", "1")
                if i == 0:
                    (project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
            (project / "report" / "IMPLEMENTATION.md").write_text(
                "done\n", encoding="utf-8")
            h.run_cli(project, "refresh", "--task", "demo-task")
            h.run_cli(project, "report-check", "--task", "demo-task")
            h.run_cli(project, "close", "--task", "demo-task")
            h.run_cli(project, "envelope", "freeze", "--task", "demo-task")
            proc, payload = h.run_cli(
                project, "audit", "package", "--task", "demo-task",
                "--iteration", "1", "--input", "src/demo.py",
                "--instruction", "task.json",
                "--validation", "report/IMPLEMENTATION.md")
            package = payload["package"]
            result = project / "audit_result.json"
            result.write_bytes(json.dumps({
                "verdict": "PASS", "findings": [],
                "requested_model": "primary-auditor/1"}).encode("utf-8"))
            proc, payload = h.run_cli(
                project, "audit", "route-receipt", "--task", "demo-task",
                "--package", package, "--kind", "AUDIT_RESULT",
                "--requested-model", "primary-auditor/1",
                "--model-observed", "primary-auditor/1",
                "--exit-code", "0", "--result-file", "audit_result.json",
                "--out", "route_receipt.json")
            receipt = json.loads(
                (project / "route_receipt.json").read_text("utf-8"))
            self.assertEqual(receipt["schema"],
                             "ual-audit-route-receipt/1")
            self.assertEqual(receipt["status"], "FINISHED")
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["result"]["sha256"],
                             hashlib.sha256(
                                 result.read_bytes()).hexdigest())
            proc, payload = h.run_cli(
                project, "audit", "record", "--task", "demo-task",
                "--package", package, "--result-file", "audit_result.json",
                "--route-receipt", "route_receipt.json")
            self.assertEqual(payload["observed_model"], "primary-auditor/1")
        finally:
            shutil.rmtree(project, ignore_errors=True)


class INST3_OwnershipContainment(unittest.TestCase):
    def _apply_once(self, project):
        source = project / "_src"
        (source / "docs").mkdir(parents=True)
        (source / "README.md").write_bytes(b"pkg readme\n")
        (source / "docs" / "guide.md").write_bytes(b"guide\n")
        target = project / "_dst"
        target.mkdir(exist_ok=True)
        h.run_cli(project, "install", "apply", "--source", str(source),
                  "--target", str(target))
        return source, target

    def test_ownership_symlink_escape_refused(self):
        project = h.fresh_project("inst3-sym", None)
        try:
            source, target = self._apply_once(project)
            outside = project / "outside-own.json"
            outside.write_bytes(b"{}\n")
            ownership = (target / ".ual-install" / "ownership.json")
            try:
                ownership.unlink()
                os.symlink(outside, ownership)
            except OSError:
                self.skipTest("symlinks unavailable on this host")
            h.expect_refusal(project, "install", "apply", "--source",
                             str(source), "--target", str(target),
                             code="INSTALL_OWNERSHIP")
            h.expect_refusal(project, "install", "doctor", "--source",
                             str(source), "--target", str(target),
                             code="INSTALL_OWNERSHIP")
        finally:
            shutil.rmtree(project, ignore_errors=True)

    def test_ownership_junction_escape_refused(self):
        if os.name != "nt":
            self.skipTest("Windows-only junction regression")
        project = h.fresh_project("inst3-junc", None)
        try:
            source, target = self._apply_once(project)
            outside = project / "outside-ual"
            outside.mkdir(exist_ok=True)
            ual = target / ".ual-install"
            shutil.rmtree(ual)
            proc = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(ual), str(outside)],
                capture_output=True, text=True)
            if proc.returncode != 0:
                self.skipTest("junction creation unavailable: "
                              + proc.stderr.strip())
            h.expect_refusal(project, "install", "apply", "--source",
                             str(source), "--target", str(target),
                             code="INSTALL_OWNERSHIP")
            h.expect_refusal(project, "install", "doctor", "--source",
                             str(source), "--target", str(target),
                             code="INSTALL_OWNERSHIP")
            # no outside write happened
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            shutil.rmtree(project, ignore_errors=True)


class PACK3_PrelaunchPackDrift(unittest.TestCase):
    def setUp(self):
        project = h.fresh_project("pack3", None)
        self.addCleanup(shutil.rmtree, project, ignore_errors=True)
        self.project = project
        h.write_task(self.project,
                     required_skills=["skills/demo-skill/SKILL.md"])
        skill = self.project / "skills" / "demo-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("demo skill body\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("root rules\n",
                                                encoding="utf-8")
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)
        for i in range(2):
            proc, run = h.run_cli(
                self.project, "run", "--task", "demo-task", "--purpose",
                "VALIDATION",
                "--argv-json", json.dumps(
                    [h.sys_executable(), "check_demo.py"]))
            h.run_cli(self.project, "validate", "record", "--task",
                      "demo-task", "--run", run["run_id"], "--ordinal", "1")
            if i == 0:
                (self.project / "src" / "demo.py").write_bytes(
                    b"VALUE = 2\n")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "ACTIVE")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "FIX_REQUIRED")
        (self.project / "batch2.md").write_text(
            "# Repair batch — attempt 1\n\nChange VALUE to 3.\n",
            encoding="utf-8")
        (self.project / "touched.md").write_text("- src/demo.py\n",
                                                 encoding="utf-8")
        claim = {"finding_ids": ["M1"], "reason": "CANDIDATE_HASH_CHANGE",
                 "evidence": {"prior_candidate_sha256": "a" * 64,
                              "new_candidate_sha256": "b" * 64},
                 "progress_basis": None}
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        proc, basis = h.run_cli(self.project, "progress", "check", "--task",
                                "demo-task", "--batch", "batch2.md")
        claim["progress_basis"] = basis["basis"]
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        h.run_cli(self.project, "pack", "build", "--task", "demo-task",
                  "--iteration", "1", "--batch", "batch2.md",
                  "--touched", "touched.md")
        h.run_cli(self.project, "pack", "verify", "--task", "demo-task",
                  "--iteration", "1")
        # close + freeze attempt 1 and record a negative review so the
        # pack-bound repair attempt can open (attempt 2)
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        (self.project / "review.md").write_text(
            "# Independent review — demo-task (SYNTHETIC fixture)\n\n"
            "## Contract compliance\n\n- Verdict: `FAIL`\n"
            "## Adversarial validity\n\n- Verdict: `FAIL`\n"
            "## Findings\n\n- M1: needs repair\n"
            "## Durable correction\n\n- Mandated change: `M1: fix`\n",
            encoding="utf-8")
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "FAIL",
                  "--reviewer-session", "sess-reviewer")
        proc, payload = h.run_cli(
            self.project, "attempt", "open", "--task", "demo-task",
            "--batch", "batch2.md", "--claim-file", "claim.json",
            "--pack-iteration", "1")
        self.assertEqual(payload["attempt"], 2)

    def test_prelaunch_revalidates_every_pack_input(self):
        runs_dir = self.project / ".agent-loop" / "runs"
        runs_before = set(p.name for p in runs_dir.iterdir()) \
            if runs_dir.is_dir() else set()
        tamper_restore = [
            ("task.json",
             lambda p: json.loads(p.read_text("utf-8")).update(title="x")
             or None,
             None),
        ]
        # task bytes drift (keep the task valid so prelaunch is reached)
        task_path = self.project / "task.json"
        original_task = task_path.read_text("utf-8")
        task = json.loads(original_task)
        task["title"] = "drifted after verification"
        task_path.write_text(json.dumps(task, indent=2), "utf-8")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="ATTEMPT_PACK_DRIFT")
        task_path.write_text(original_task, encoding="utf-8")
        # skill body drift
        skill = self.project / "skills" / "demo-skill" / "SKILL.md"
        original_skill = skill.read_bytes()
        skill.write_bytes(original_skill + b"drift\n")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="ATTEMPT_PACK_DRIFT")
        skill.write_bytes(original_skill)
        # AGENTS.md drift
        agents = self.project / "AGENTS.md"
        original_agents = agents.read_bytes()
        agents.write_bytes(original_agents + b"drift\n")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="ATTEMPT_PACK_DRIFT")
        agents.write_bytes(original_agents)
        # repair batch drift
        batch = self.project / "batch2.md"
        original_batch = batch.read_bytes()
        batch.write_bytes(original_batch + b"drift\n")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="ATTEMPT_PACK_DRIFT")
        batch.write_bytes(original_batch)
        # touched map drift
        touched = self.project / "touched.md"
        original_touched = touched.read_bytes()
        touched.write_bytes(original_touched + b"drift\n")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="ATTEMPT_PACK_DRIFT")
        touched.write_bytes(original_touched)
        # no claim/run/child artifacts appeared
        runs_after = set(p.name for p in runs_dir.iterdir()) \
            if runs_dir.is_dir() else set()
        self.assertEqual(runs_before, runs_after)
        proc, payload = h.run_cli(self.project, "claim", "scan")
        self.assertEqual([c for c in payload["claims"]
                          if c["status"] == "ACTIVE"], [])


if __name__ == "__main__":
    unittest.main()

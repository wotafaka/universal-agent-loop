"""Writer-claim ownership and child process supervision regressions.

Source mapping: X01 (pre-spawn claim; duplicate refused before child),
X02 (host/PID/birth identity; PID reuse refused), X03 (terminal release and
owner adjudication; no automatic stale cleanup), X04 (durable bounded logs +
atomic sidecar), X06 (allowlisted child environment), X21 (spawn boundary
honesty), X22 (receiver-bound delivery acknowledgment; multiline stdin).
"""
from __future__ import annotations

import json
import os
import unittest

import _harness as h

FAST_EXIT = "import sys\nsys.exit(0)\n"
LOUD_CHILD = (
    "import sys, time\n"
    "while True:\n"
    "    sys.stdout.write('x' * 1024 + '\\n')\n"
    "    sys.stdout.flush()\n"
    "    time.sleep(0.01)\n"
)
ACK_CHILD = (
    "import hashlib, json, os, sys\n"
    "data = sys.stdin.buffer.read()\n"
    "os.makedirs('report', exist_ok=True)\n"
    "open('report/received.txt', 'wb').write(data)\n"
    "ack = {'schema': 'ual-ack/1', 'run_id': os.environ.get('UAL_RUN_ID'),\n"
    "       'task': os.environ.get('UAL_TASK'),\n"
    "       'stdin_sha256': hashlib.sha256(data).hexdigest()}\n"
    "open('report/ack.json', 'w').write(json.dumps(ack))\n"
    "print('child got', len(data), 'bytes')\n"
)
ENV_CHILD = (
    "import json, os\n"
    "print(json.dumps({'ambient': os.environ.get('UAL_AMBIENT_MARK'),\n"
    "                  'overlay': os.environ.get('UAL_OVERLAY_MARK'),\n"
    "                  'task': os.environ.get('UAL_TASK')}))\n"
)


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("claims", self)
        h.write_task(self.project)
        h.authority(self.project)

    def claim_ids(self):
        proc, payload = h.run_cli(self.project, "claim", "scan")
        return payload["claims"]

    def test_acquire_scan_and_owner_adjudication(self):
        proc, payload = h.run_cli(self.project, "claim", "acquire",
                                  "--task", "demo-task")
        claim_id = payload["claim_id"]
        claims = self.claim_ids()
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["status"], "ACTIVE")
        self.assertNotEqual(claims[0]["host"], "")
        h.expect_refusal(self.project, "claim", "abandon", "--claim-id",
                         claim_id, "--actor", "OWNER", "--reason", "  ",
                         code="ADJUDICATION_REASON_REQUIRED")
        proc, payload = h.run_cli(self.project, "claim", "abandon",
                                  "--claim-id", claim_id, "--actor", "OWNER",
                                  "--reason", "fixture adjudication")
        self.assertEqual(payload["status"], "ABANDONED")
        claims = self.claim_ids()
        self.assertEqual(claims[0]["status"], "ABANDONED")
        self.assertEqual(claims[0]["adjudication"]["actor"], "OWNER")

    def test_duplicate_writer_refused_before_child_creation(self):
        h.run_cli(self.project, "claim", "acquire", "--task", "demo-task")
        runs_before = set(p.name for p in
                          (self.project / ".agent-loop" / "runs").iterdir()) \
            if (self.project / ".agent-loop" / "runs").exists() else set()
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="WRITER_CLAIM_ACTIVE")
        runs_after = set(p.name for p in
                         (self.project / ".agent-loop" / "runs").iterdir()) \
            if (self.project / ".agent-loop" / "runs").exists() else set()
        self.assertEqual(runs_before, runs_after)

    def test_claim_scope_is_whole_checkout_across_tasks(self):
        h.run_cli(self.project, "claim", "acquire", "--task", "task-one")
        h.write_task(self.project, id="task-two")
        h.expect_refusal(self.project, "claim", "acquire", "--task",
                         "task-two", code="WRITER_CLAIM_ACTIVE")
        h.expect_refusal(self.project, "run", "--task", "task-two",
                         "--purpose", "ENGINEER",
                         "--session-id", "sess-engineer",
                         code="WRITER_CLAIM_ACTIVE")

    def test_release_requires_engineer_run_bound_to_claim(self):
        proc, payload = h.run_cli(self.project, "claim", "acquire",
                                  "--task", "demo-task")
        claim_id = payload["claim_id"]
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task",
            "--purpose", "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.expect_refusal(self.project, "claim", "release",
                         "--claim-id", claim_id, "--run", run["run_id"],
                         code="WRITER_CLAIM_RUN_MISMATCH")

    def test_unproven_identity_never_auto_releases_and_no_auto_cleanup(self):
        proc, payload = h.run_cli(self.project, "claim", "acquire",
                                  "--task", "demo-task")
        claim_id = payload["claim_id"]
        h.run_cli(self.project, "claim", "bind-child", "--claim-id", claim_id,
                  "--pid", "999999", "--identity-state",
                  "CHILD_EXITED_BEFORE_IDENTITY")
        h.expect_refusal(self.project, "claim", "release", "--claim-id",
                         claim_id, "--run", "no-such-run",
                         code="WRITER_CLAIM_IDENTITY_UNPROVEN")
        claims = self.claim_ids()
        self.assertEqual(claims[0]["status"], "ACTIVE")

    def test_birth_identity_mismatch_refuses_release(self):
        proc, payload = h.run_cli(self.project, "claim", "acquire",
                                  "--task", "demo-task")
        claim_id = payload["claim_id"]
        h.run_cli(self.project, "claim", "bind-child", "--claim-id", claim_id,
                  "--pid", str(os.getpid()), "--identity-state", "OBTAINED",
                  "--identity-method", "fixture", "--identity-value", "old-1")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task",
            "--purpose", "ENGINEER", "--session-id", "sess-engineer",
            "--argv-json", json.dumps([h.sys_executable(), "-c", "print('e')"]),
            expect=None)
        h.expect_refusal(self.project, "claim", "release", "--claim-id",
                         claim_id, "--run", "fabricated-run",
                         code="WRITER_CLAIM_RUN_MISMATCH")

    def test_engineer_run_releases_on_proven_terminal_identity(self):
        child = h.write_child(self.project, "engineer.py",
                              "print('engineer ok')\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task",
            "--purpose", "ENGINEER", "--session-id", "sess-engineer")
        self.assertEqual(run["status"], "FINISHED")
        self.assertEqual(run["exit_code"], 0)
        self.assertEqual(run["claim"]["state"], "RELEASED")
        self.assertEqual(run["identity_state"], "OBTAINED")
        proc, payload = h.run_cli(self.project, "claim", "scan")
        self.assertEqual(payload["claims"][0]["status"], "RELEASED")
        self.assertIsNotNone(payload["claims"][0]["terminal_evidence"])

    def test_engineer_run_nonzero_is_terminal_not_success(self):
        child = h.write_child(self.project, "fail.py", "import sys\nsys.exit(3)\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "fail.py"]))
        self.assertEqual(run["status"], "FINISHED")
        self.assertEqual(run["exit_code"], 3)
        self.assertIsNone(run["claim"])
        self.assertFalse(run["delivered"] is True)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("runner", self)
        h.write_task(self.project)

    def test_missing_argv_refused(self):
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "OTHER", "--argv-json", "[]",
                         code="RUN_ARGV_REQUIRED")

    def test_ambiguous_spawn_outcome_recorded_honestly(self):
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "-c",
                                       "import sys; sys.exit(0)"]))
        self.assertIn(run["identity_state"],
                      ("OBTAINED", "CHILD_EXITED_BEFORE_IDENTITY"))
        if run["identity_state"] == "CHILD_EXITED_BEFORE_IDENTITY":
            self.assertIsNone(run["claim"]["state"])

    def test_log_overflow_is_bounded_and_reported(self):
        h.write_child(self.project, "loud.py", LOUD_CHILD)
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "loud.py"]),
            "--log-cap-bytes", "20000")
        self.assertTrue(run["overflow"])
        self.assertNotEqual(run["exit_code"], 0)
        self.assertLessEqual(run["log"]["bytes"], 40000)

    def test_multiline_stdin_delivery_with_receiver_ack(self):
        h.write_child(self.project, "ack_child.py", ACK_CHILD)
        stdin_path = self.project / "stdin.txt"
        payload = "line one\nline two \u2014 \u0442\u0435\u0441\u0442\nline three\n"
        stdin_path.write_bytes(payload.encode("utf-8"))
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "ack_child.py"]),
            "--stdin-file", "stdin.txt", "--ack-path", "report/ack.json")
        self.assertTrue(run["delivered"] is True)
        received = (self.project / "report" / "received.txt").read_bytes()
        self.assertEqual(received, payload.encode("utf-8"))

    def test_missing_ack_stays_unknown(self):
        h.write_child(self.project, "plain.py", "print('no ack')\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "plain.py"]),
            "--ack-path", "report/missing.json")
        self.assertIsNone(run["delivered"])

    def test_tampered_ack_is_not_delivery(self):
        h.write_child(self.project, "noack.py", "print('no ack written')\n")
        (self.project / "report").mkdir(exist_ok=True)
        (self.project / "report" / "ack.json").write_bytes(b"{}")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "noack.py"]),
            "--ack-path", "report/ack.json")
        self.assertIs(run["delivered"], False)

    def test_environment_allowlist_and_overlay(self):
        h.write_child(self.project, "env_child.py", ENV_CHILD)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(h.CHECKOUT)
        env["UAL_AMBIENT_MARK"] = "ambient-leak"
        proc = h.subprocess.run(
            h.cli_argv(self.project, "run", "--task", "demo-task",
                       "--purpose", "OTHER",
                       "--argv-json", json.dumps([h.sys_executable(), "env_child.py"]),
                       "--env-overlay-json", json.dumps({"UAL_OVERLAY_MARK": "ov"}),
                       "--env-base-json", json.dumps(
                           ["SYSTEMROOT", "PATH", "PATHEXT", "COMSPEC",
                            "PROCESSOR_ARCHITECTURE", "PROCESSOR_LEVEL",
                            "PROCESSOR_REVISION", "NUMBER_OF_PROCESSORS",
                            "OS", "TEMP", "TMP", "HOME"])),
            env=env, cwd=str(self.project), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        run = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(run["exit_code"], 0)
        log = (self.project / ".agent-loop" / "runs" / run["run_id"]
               / "log.txt").read_text(encoding="utf-8")
        child = json.loads(log.strip().splitlines()[-1])
        self.assertIsNone(child["ambient"])
        self.assertEqual(child["overlay"], "ov")
        self.assertEqual(child["task"], "demo-task")


if __name__ == "__main__":
    unittest.main()

"""Progress basis, repair packs and terminal-only continuation regressions.

Source mapping: X14 (stable substantive progress basis), X15 (structured
material-progress claim), X16 (monotonic records; malformed prior record is
never an empty baseline), X17 (hash-bound terminal continuation), X18
(repair-pack build-last/verify-first with drift fallback).
"""
from __future__ import annotations

import json
import unittest

import _harness as h

BATCH_ONE = "# Repair batch — iteration 1\n\nFix the value.\n"
BATCH_TWO = "# Repair batch — iteration 2\n\nFix the value differently.\n"
TOUCHED = "- src/demo.py: adjust VALUE\n"


class StatusAndPackTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("packs", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))

    def test_invalid_transition_refused(self):
        proc, payload = h.run_cli(self.project, "status", "set", "--task",
                                  "demo-task", "--status", "ACTIVE")
        h.expect_refusal(self.project, "status", "set", "--task",
                         "demo-task", "--status", "PROPOSED",
                         code="INVALID_TASK_TRANSITION")

    def test_pack_requires_fix_required_status(self):
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "ACTIVE")
        self.write_batch()
        h.expect_refusal(self.project, "pack", "build", "--task", "demo-task",
                         "--iteration", "1", "--batch", "batch.md",
                         "--touched", "touched.md",
                         code="STATUS_NOT_FIX_REQUIRED")

    def write_batch(self, one=BATCH_ONE):
        (self.project / "batch.md").write_text(one, encoding="utf-8")
        (self.project / "touched.md").write_text(TOUCHED, encoding="utf-8")

    def to_fix_required(self):
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "ACTIVE")
        h.run_cli(self.project, "status", "set", "--task", "demo-task",
                  "--status", "FIX_REQUIRED")

    def test_pack_build_and_verify(self):
        self.write_batch()
        self.to_fix_required()
        proc, payload = h.run_cli(self.project, "pack", "build", "--task",
                                  "demo-task", "--iteration", "1",
                                  "--batch", "batch.md", "--touched",
                                  "touched.md")
        self.assertTrue(payload["progress_basis"])
        proc, payload = h.run_cli(self.project, "pack", "verify", "--task",
                                  "demo-task", "--iteration", "1")
        self.assertTrue(payload["ok"])

    def test_build_last_drift_fails_to_full_startup(self):
        self.write_batch()
        self.to_fix_required()
        h.run_cli(self.project, "pack", "build", "--task", "demo-task",
                  "--iteration", "1", "--batch", "batch.md", "--touched",
                  "touched.md")
        task_path = self.project / "task.json"
        task = json.loads(task_path.read_text("utf-8"))
        task["title"] = "Changed after pack build"
        task_path.write_text(json.dumps(task), "utf-8")
        proc, payload = h.run_cli(self.project, "pack", "verify", "--task",
                                  "demo-task", "--iteration", "1", expect=2)
        self.assertEqual(payload.get("fallback"), "FULL_CANONICAL_STARTUP")

    def test_pack_write_once(self):
        self.write_batch()
        self.to_fix_required()
        h.run_cli(self.project, "pack", "build", "--task", "demo-task",
                  "--iteration", "1", "--batch", "batch.md", "--touched",
                  "touched.md")
        h.expect_refusal(self.project, "pack", "build", "--task", "demo-task",
                         "--iteration", "1", "--batch", "batch.md",
                         "--touched", "touched.md", code="PACK_TARGET_EXISTS")

    def test_malformed_batch_has_no_basis(self):
        self.write_batch(one="no heading body\n")
        self.to_fix_required()
        h.expect_refusal(self.project, "pack", "build", "--task", "demo-task",
                         "--iteration", "1", "--batch", "batch.md",
                         "--touched", "touched.md",
                         code="PROGRESS_BASIS_NOT_DERIVABLE")


class ProgressGateTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("progress", self)
        h.write_task(self.project)
        h.authority(self.project)
        self.write_batch()

    def write_batch(self):
        (self.project / "batch.md").write_text(BATCH_ONE, encoding="utf-8")
        (self.project / "touched.md").write_text(TOUCHED, encoding="utf-8")

    def engineer_run(self, batch=None):
        args = ["run", "--task", "demo-task", "--purpose", "ENGINEER",
                "--session-id", "sess-engineer"]
        if batch is not None:
            args += ["--basis-file", batch]
        proc, run = h.run_cli(self.project, *args)
        return run

    def test_baseline_then_duplicate_then_progress(self):
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "batch.md")
        self.assertEqual(payload["decision"], "BASELINE_ALLOWED")
        self.engineer_run("batch.md")
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "batch.md")
        self.assertEqual(payload["decision"], "DUPLICATE_BLOCKED")
        (self.project / "batch2.md").write_text(BATCH_TWO, encoding="utf-8")
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "batch2.md")
        self.assertEqual(payload["decision"], "PROGRESSING_ALLOWED")

    def test_malformed_batch_is_non_authorizing_after_baseline(self):
        (self.project / "bad.md").write_text("no heading\n", encoding="utf-8")
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "bad.md")
        self.assertEqual(payload["decision"], "BASELINE_ALLOWED")
        self.engineer_run("batch.md")
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "bad.md", expect=2)

    def test_malformed_prior_record_blocks_not_resets(self):
        self.engineer_run("batch.md")
        runs_dir = self.project / ".agent-loop" / "runs"
        run_ids = sorted(p.name for p in runs_dir.iterdir())
        sidecar = runs_dir / run_ids[-1] / "run.json"
        sidecar.write_text("{not json", encoding="utf-8")
        h.expect_refusal(self.project, "progress", "check", "--task",
                         "demo-task", "--batch", "batch.md",
                         code="PROGRESS_PRIOR_RECORD_MALFORMED")

    def test_material_claim_authorizes_once(self):
        (self.project / "batch2.md").write_text(BATCH_TWO, encoding="utf-8")
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "batch.md")
        self.assertEqual(payload["decision"], "BASELINE_ALLOWED")
        self.engineer_run("batch.md")
        proc, basis = h.run_cli(self.project, "progress", "check", "--task",
                                "demo-task", "--batch", "batch2.md")
        self.assertEqual(basis["decision"], "PROGRESSING_ALLOWED")
        claim = {"finding_ids": ["M1"], "reason": "CANDIDATE_HASH_CHANGE",
                 "evidence": {"prior_candidate_sha256": "a" * 64,
                              "new_candidate_sha256": "b" * 64},
                 "progress_basis": basis["basis"]}
        (self.project / "claim.json").write_bytes(json.dumps(claim).encode())
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "batch2.md",
                                  "--claim-file", "claim.json")
        self.assertEqual(payload["decision"], "MATERIALLY_AUTHORIZED")
        proc, payload = h.run_cli(self.project, "progress", "check", "--task",
                                  "demo-task", "--batch", "batch2.md",
                                  "--claim-file", "claim.json")
        self.assertEqual(payload["decision"], "MATERIAL_CLAIM_NON_AUTHORIZING")


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("continuation", self)
        h.write_task(self.project)
        h.authority(self.project)

    def engineer_run(self):
        h.write_child(self.project, "engineer.py", "print('work')\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "ENGINEER",
            "--session-id", "sess-engineer")
        return run

    def test_prepare_and_verify(self):
        run = self.engineer_run()
        proc, payload = h.run_cli(self.project, "continuation", "prepare",
                                  "--task", "demo-task")
        self.assertEqual(payload["prior_status"], "FINISHED")
        proc, payload = h.run_cli(self.project, "continuation", "verify",
                                  "--task", "demo-task")
        self.assertTrue(payload["ok"])

    def test_prepare_refuses_second_record(self):
        self.engineer_run()
        h.run_cli(self.project, "continuation", "prepare", "--task",
                  "demo-task")
        h.expect_refusal(self.project, "continuation", "prepare", "--task",
                         "demo-task", code="CONTINUATION_RECORD_EXISTS")

    def test_verify_refuses_log_drift(self):
        self.engineer_run()
        h.run_cli(self.project, "continuation", "prepare", "--task",
                  "demo-task")
        runs_dir = self.project / ".agent-loop" / "runs"
        run_id = sorted(p.name for p in runs_dir.iterdir())[-1]
        log = runs_dir / run_id / "log.txt"
        log.write_bytes(log.read_bytes() + b"drift\n")
        h.expect_refusal(self.project, "continuation", "verify", "--task",
                         "demo-task", code="CONTINUATION_LOG_DRIFT")

    def test_prepare_refuses_active_claim(self):
        h.run_cli(self.project, "claim", "acquire", "--task", "demo-task")
        h.expect_refusal(self.project, "continuation", "prepare", "--task",
                         "demo-task", code="CONTINUATION_LIVE_CLAIM")


if __name__ == "__main__":
    unittest.main()

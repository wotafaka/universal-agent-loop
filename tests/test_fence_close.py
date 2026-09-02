"""Validation fence, occurrence capture and lifecycle close regressions.

Source mapping: C05 (validation capture excludes exactly the report), C06
(complete invocation/output proof), C07 (declared seed is actually applied),
C08 (complete-fingerprint nondeterminism), X07 (exact occurrence lifecycle
fence incl. RED/GREEN), X08 (post-successful-close tool ban), R2 ingestion
of run-bound events through the actual CLI only.
"""
from __future__ import annotations

import json
import unittest

import _harness as h


class FenceCloseTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("fence", self)
        h.write_task(self.project)
        h.write_config(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))

    def run_check(self):
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task",
            "--purpose", "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        return run

    def record(self, run_id, ordinal=1, expect=0):
        return h.run_cli(self.project, "validate", "record", "--task",
                         "demo-task", "--run", run_id,
                         "--ordinal", str(ordinal), expect=expect)

    def fix_candidate(self):
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")

    def finalize_report(self):
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")

    def reach_closed(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run = self.run_check()
        self.record(run["run_id"])
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        return h.run_cli(self.project, "close", "--task", "demo-task")

    def test_red_then_green_fences_and_closes(self):
        run = self.run_check()
        self.assertEqual(run["exit_code"], 1)
        proc, payload = self.record(run["run_id"])
        self.assertEqual(payload["outcome"], "RED")
        self.fix_candidate()
        run = self.run_check()
        self.assertEqual(run["exit_code"], 0)
        proc, payload = self.record(run["run_id"])
        self.assertEqual(payload["outcome"], "GREEN")
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        proc, payload = h.run_cli(self.project, "close", "--task", "demo-task")
        self.assertTrue(payload["ok"])

    def test_close_without_complete_fence_refused(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.finalize_report()
        h.expect_refusal(self.project, "close", "--task", "demo-task",
                         code="VALIDATION_FENCE_INCOMPLETE")

    def test_unexpected_final_red_blocks_close(self):
        run = self.run_check()
        self.record(run["run_id"])
        h.write_child(self.project, "check_demo.py", "import sys\nsys.exit(1)\n")
        run = self.run_check()
        h.expect_refusal(self.project, "validate", "record", "--task",
                         "demo-task", "--run", run["run_id"],
                         "--ordinal", "1", code="VALIDATION_UNEXPECTED_OUTCOME")

    def test_extra_occurrence_refused(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run = self.run_check()
        self.record(run["run_id"])
        run = self.run_check()
        h.expect_refusal(self.project, "validate", "record", "--task",
                         "demo-task", "--run", run["run_id"],
                         "--ordinal", "1",
                         code="VALIDATION_OCCURRENCE_EXTRA")

    def test_out_of_order_command_refused(self):
        _, path = h.write_task(self.project)
        task = json.loads(path.read_text("utf-8"))
        task["validation"]["commands"].append(
            {"ordinal": 2, "cwd": ".", "argv": [h.sys_executable(), "second.py"],
             "expected_outcomes": ["GREEN"]})
        task["requirements"][1]["command"] = 2
        path.write_text(json.dumps(task), "utf-8")
        h.write_child(self.project, "second.py", "print('second')\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "second.py"]))
        h.expect_refusal(self.project, "validate", "record", "--task",
                         "demo-task", "--run", run["run_id"],
                         "--ordinal", "2", code="VALIDATION_OUT_OF_ORDER")

    def test_post_green_candidate_drift_blocks_close(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run = self.run_check()
        self.record(run["run_id"])
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 3\n")
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.expect_refusal(self.project, "close", "--task", "demo-task",
                         code="VALIDATION_FINAL_CAPTURE_MEMBER_MISMATCH")

    def test_report_finalized_after_green_and_bound_in_envelope(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run = self.run_check()
        self.record(run["run_id"])
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")
        proc, payload = h.run_cli(self.project, "envelope", "freeze",
                                  "--task", "demo-task")
        members = {m["path"] for m in payload["members"]}
        self.assertIn("report/IMPLEMENTATION.md", members)
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "edited after close\n", encoding="utf-8")
        h.expect_refusal(self.project, "envelope", "verify", "--task",
                         "demo-task", code="CANDIDATE_MEMBER_DRIFT")

    def test_report_check_requires_refresh_first(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run = self.run_check()
        self.record(run["run_id"])
        self.finalize_report()
        h.expect_refusal(self.project, "report-check", "--task", "demo-task",
                         code="VALIDATION_REFRESH_REQUIRED")

    def test_report_check_requires_report_file(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run = self.run_check()
        self.record(run["run_id"])
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.expect_refusal(self.project, "report-check", "--task", "demo-task",
                         code="VALIDATION_REPORT_MISSING")

    def test_post_close_tool_events_refused(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run2 = self.run_check()
        self.record(run2["run_id"])
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")
        h.expect_refusal(self.project, "event", "record", "--task",
                         "demo-task", "--tool", "bash", "--detail",
                         "echo after-close", "--exit", "0",
                         code="POST_CLOSE_EVENT")
        h.expect_refusal(self.project, "run", "--task", "demo-task",
                         "--purpose", "VALIDATION",
                         "--argv-json", json.dumps(
                             [h.sys_executable(), "check_demo.py"]),
                         code="POST_CLOSE_RUN")
        h.expect_refusal(self.project, "validate", "record", "--task",
                         "demo-task", "--run", run2["run_id"],
                         "--ordinal", "1", code="POST_CLOSE_RECORD")

    def test_hand_forged_ledger_record_never_counts(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run = self.run_check()
        self.record(run["run_id"])
        attempts_dir = (self.project / ".agent-loop" / "tasks" /
                        "demo-task" / "attempts")
        ledger_path = sorted(attempts_dir.glob("attempt_*/ledger.json"))[0]
        ledger = json.loads(ledger_path.read_text("utf-8"))
        forged = dict(ledger["occurrences"][1])
        forged["run_id"] = "fabricated-run"
        ledger["occurrences"].append(forged)
        ledger_path.write_text(json.dumps(ledger), "utf-8")
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.expect_refusal(self.project, "close", "--task", "demo-task",
                         code="VALIDATION_RUN_SIDECAR_MISSING")

    def test_tampered_sidecar_binding_refused_at_close(self):
        run = self.run_check()
        self.record(run["run_id"])
        self.fix_candidate()
        run2 = self.run_check()
        self.record(run2["run_id"])
        sidecar = (self.project / ".agent-loop" / "runs" / run2["run_id"]
                   / "run.json")
        data = json.loads(sidecar.read_text("utf-8"))
        data["exit_code"] = 0
        sidecar.write_text(json.dumps(data), "utf-8")
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.expect_refusal(self.project, "close", "--task", "demo-task",
                         code="VALIDATION_RUN_SIDECAR_DRIFT")

    def test_equal_complete_fingerprint_conflict_is_nondeterminism(self):
        run = self.run_check()
        self.record(run["run_id"])
        run = self.run_check()
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1", expect=2)
        self.finalize_report()
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.expect_refusal(self.project, "close", "--task", "demo-task",
                         code="VALIDATION_NONDETERMINISTIC_CONFLICT")

    def test_declared_seed_mismatch_refuses_record(self):
        run = self.run_check()
        h.expect_refusal(self.project, "validate", "record", "--task",
                         "demo-task", "--run", run["run_id"],
                         "--ordinal", "1", "--seed", "1",
                         code="VALIDATION_SEED_MISMATCH")


if __name__ == "__main__":
    unittest.main()

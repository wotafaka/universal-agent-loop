"""Context packs and bounded measured delivery feedback regressions.

Source mapping: P01/P02/P03 (compact hash-linked context; history on
demand), P06/P07 (measured feedback; successful delivery vs terminal
writers), R4 (UNKNOWN stays UNKNOWN; no token/cost inference).
"""
from __future__ import annotations

import json
import unittest

import _harness as h


class ContextPackTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("context", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.write_child(self.project, "engineer.py", "print('work')\n")

    def test_context_build_and_verify(self):
        proc, payload = h.run_cli(self.project, "context", "build", "--task",
                                  "demo-task")
        self.assertGreater(payload["total_bytes"], 0)
        pack = payload["pack"]
        proc, payload = h.run_cli(self.project, "context", "verify", "--task",
                                  "demo-task", "--pack", pack)
        self.assertTrue(payload["ok"])
        self.assertIsNotNone(payload["context_verify_seconds"])
        proc, payload = h.run_cli(self.project, "context", "verify", "--task",
                                  "demo-task", "--pack", pack)
        self.assertTrue(payload["ok"])

    def test_pack_hash_drift_refused(self):
        proc, payload = h.run_cli(self.project, "context", "build", "--task",
                                  "demo-task")
        task_path = self.project / "task.json"
        task = json.loads(task_path.read_text("utf-8"))
        task["title"] = "drifted title"
        task_path.write_text(json.dumps(task), "utf-8")
        h.expect_refusal(self.project, "context", "verify", "--task",
                         "demo-task", "--pack", payload["pack"],
                         code="CONTEXT_INDEX_DRIFT")


class DeliveryReportTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("delivery", self)
        h.write_task(self.project)
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.write_child(self.project, "engineer.py", "print('work')\n")
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
                (self.project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")

    def seal_and_accept(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        (self.project / "proof_one.json").write_bytes(b'{"p": 1}\n')
        (self.project / "proof_two.json").write_bytes(b'{"p": 2}\n')
        text = (
            "# Independent review — demo-task (synthetic fixture)\n\n"
            "## Contract compliance\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact `proof_one.json`"
            " sha256 `" + h.sha256_of(self.project / "proof_one.json")
            + "` origin `REVIEWER_RECOMPUTED` action `recomputed fixture"
              " digests` candidate `demo-task`\n\n"
            "## Adversarial validity\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact `proof_two.json`"
            " sha256 `" + h.sha256_of(self.project / "proof_two.json")
            + "` origin `REVIEWER_REEXECUTED` action `re-executed fixture"
              " checks` candidate `demo-task`\n\n"
            "## Findings\n\n- NONE\n\n## Durable correction\n\n"
            "- Mandated change: `NONE`\n\n"
            "## Convergence disposition\n\n"
            "- Disposition: `CONVERGED`\n"
            "- Covered requirement IDs: `R1,R2`\n"
            "- Remaining material requirement IDs: `NONE`\n" +
            h.envelope_binding_section(self.project))
        (self.project / "review.md").write_text(text, encoding="utf-8")
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        h.run_cli(self.project, "accept", "--task", "demo-task",
                  "--actor", "OWNER", "--decision", "ACCEPTED",
                  "--review", "review.md")

    def test_delivery_refused_before_acceptance(self):
        h.expect_refusal(self.project, "report", "delivery", "--task",
                         "demo-task", code="DELIVERY_NOT_PROVEN")

    def test_efficiency_report_unknown_fields_and_updateable(self):
        proc, first = h.run_cli(self.project, "report", "efficiency",
                                "--task", "demo-task")
        self.assertEqual(first["tokens_total"], "UNKNOWN")
        self.assertEqual(first["cost_total"], "UNKNOWN")
        self.assertEqual(first["restoration_seconds"], "UNKNOWN")
        self.assertIsNotNone(first["wall_seconds"])
        self.assertEqual(first["generation"], 1)
        proc, second = h.run_cli(self.project, "report", "efficiency",
                                 "--task", "demo-task")
        self.assertEqual(second["generation"], 2)
        self.assertEqual(second["tokens_total"], "UNKNOWN")

    def test_delivery_after_acceptance(self):
        self.seal_and_accept()
        proc, payload = h.run_cli(self.project, "report", "delivery",
                                  "--task", "demo-task")
        self.assertTrue(payload["delivered"])

    def test_terminal_nonzero_writer_is_not_delivery(self):
        self.seal_and_accept()
        h.write_child(self.project, "late_fail.py",
                      "import sys\nsys.exit(3)\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "OTHER",
            "--argv-json", json.dumps([h.sys_executable(), "late_fail.py"]))
        self.assertEqual(run["exit_code"], 3)
        proc, payload = h.run_cli(self.project, "report", "delivery",
                                  "--task", "demo-task")
        self.assertTrue(payload["delivered"])
        self.assertEqual(payload["terminal_nonzero_runs"], 1)


if __name__ == "__main__":
    unittest.main()

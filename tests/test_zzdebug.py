"""CLI output contract: machine-readable JSON lines and stable exits.

The CLI is the only ingestion path for runtime events. Every command
prints exactly one JSON object on stdout, exits 0 on success and 2 with
stable refusal codes on fail-closed outcomes, even with no prior state
in the project.
"""
from __future__ import annotations

import json
import unittest

import _harness as h


class CliContractTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("clicontract", self)
        h.write_task(self.project)

    def test_validate_status_empty_ledger(self):
        h.write_config(self.project)
        proc, payload = h.run_cli(self.project, "validate", "status",
                                  "--task", "demo-task")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["occurrences"], 0)
        self.assertEqual(payload["evidence_state"], "MISSING")

    def test_claim_scan_empty_project(self):
        proc, payload = h.run_cli(self.project, "claim", "scan")
        self.assertEqual(payload["claims"], [])

    def test_missing_envelope_refuses_with_stable_code(self):
        h.write_config(self.project)
        h.expect_refusal(self.project, "envelope", "verify", "--task",
                         "demo-task", code="ENVELOPE_MISSING")

    def test_single_json_line_on_success(self):
        proc, payload = h.run_cli(self.project, "task-validate",
                                  "--task", "task.json")
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["ok"], True)


if __name__ == "__main__":
    unittest.main()

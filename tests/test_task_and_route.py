"""Preflight, task schema, footprint and route-availability regressions.

Source mapping: P08 (LIGHT/FULL + material clarification), P09 (conservative
actual footprint; facts never weaken the derived footprint), P04/P05 (route
bindings separate from roles; unavailable route stays honest), C01/C16.
"""
from __future__ import annotations

import json
import os
import unittest

import _harness as h


class TaskPreflightTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("preflight", self)

    def test_valid_full_task_preflights_ok(self):
        _, path = h.write_task(self.project)
        proc, payload = h.run_cli(self.project, "task-validate",
                                  "--task", "task.json")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "FULL")

    def test_unknown_schema_refused(self):
        _, path = h.write_task(self.project)
        task = json.loads(path.read_text(encoding="utf-8"))
        task["schema"] = "ual-task/9"
        path.write_text(json.dumps(task), encoding="utf-8")
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_SCHEMA_UNKNOWN")

    def test_missing_title_refused(self):
        h.write_task(self.project, title=None)
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_FIELD_MISSING:title")

    def test_bad_task_id_charset_refused(self):
        h.write_task(self.project, id="../escape")
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_ID_INVALID")

    def test_blocked_clarification_is_material_ambiguity(self):
        h.write_task(self.project, clarification_status="BLOCKED")
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="PREFLIGHT_MATERIAL_AMBIGUITY:"
                              "clarification_status_blocked")

    def test_open_clarification_ids_are_material_ambiguity(self):
        h.write_task(self.project, open_clarification_ids=["Q1"])
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="PREFLIGHT_MATERIAL_AMBIGUITY:open_clarification_ids")

    def test_full_mode_requires_requirement_coverage(self):
        h.write_task(self.project, requirements=[
            {"id": "R1", "criterion": 1, "command": 1, "evidence": "TEST_OUTPUT"},
        ])
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_COVERAGE_ROW_MISSING:R2")

    def test_full_coverage_criterion_out_of_range(self):
        h.write_task(self.project, requirements=[
            {"id": "R1", "criterion": 9, "command": 1, "evidence": "T"},
            {"id": "R2", "criterion": 2, "command": 1, "evidence": "T"},
        ])
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_COVERAGE_CRITERION_OUT_OF_RANGE:R1")

    def test_full_coverage_command_out_of_range(self):
        h.write_task(self.project, requirements=[
            {"id": "R1", "criterion": 1, "command": 4, "evidence": "T"},
            {"id": "R2", "criterion": 2, "command": 1, "evidence": "T"},
        ])
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_COVERAGE_COMMAND_OUT_OF_RANGE:R1")

    def test_duplicate_requirement_ids_refused(self):
        h.write_task(self.project, requirements=[
            {"id": "R1", "criterion": 1, "command": 1, "evidence": "T"},
            {"id": "R1", "criterion": 2, "command": 1, "evidence": "T"},
        ])
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_REQUIREMENT_ID_DUPLICATE:R1")

    def test_declared_facts_cannot_weaken_executable_footprint(self):
        h.write_task(self.project, work_kind="MECHANICAL")
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_FOOTPRINT_WEAKER_ROUTE")

    def test_governance_candidate_requires_restricted_authority(self):
        _, path = h.write_task(self.project)
        task = json.loads(path.read_text(encoding="utf-8"))
        task["candidate"]["allowlist"] = ["agent_loop_contract.py"]
        path.write_text(json.dumps(task), encoding="utf-8")
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_FOOTPRINT_GOVERNANCE_WITHOUT_RESTRICTED_AUTHORITY")

    def test_governance_with_restricted_authority_passes(self):
        _, path = h.write_task(self.project)
        task = json.loads(path.read_text(encoding="utf-8"))
        task["candidate"]["allowlist"] = ["agent_loop_contract.py"]
        task["authority_domains"] = ["SAFETY"]
        path.write_text(json.dumps(task), encoding="utf-8")
        proc, payload = h.run_cli(self.project, "task-validate",
                                  "--task", "task.json")
        self.assertTrue(payload["ok"])

    def test_light_mode_low_routine_clear_strong_ok(self):
        h.write_task(self.project, mode="LIGHT", risk="LOW", novelty="ROUTINE",
                     ambiguity="CLEAR", oracle_strength="STRONG",
                     requirements=[], success_criteria_count=0)
        proc, payload = h.run_cli(self.project, "task-validate",
                                  "--task", "task.json")
        self.assertEqual(payload["mode"], "LIGHT")

    def test_light_mode_high_risk_refused(self):
        h.write_task(self.project, mode="LIGHT", requirements=[],
                     success_criteria_count=0)
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_MODE_UNDERSTATED")

    def test_expected_outcome_vocabulary_enforced(self):
        h.write_task(self.project)
        _, path = h.write_task(self.project)
        task = json.loads(path.read_text(encoding="utf-8"))
        task["validation"]["commands"][0]["expected_outcomes"] = ["MAYBE"]
        path.write_text(json.dumps(task), encoding="utf-8")
        h.expect_refusal(self.project, "task-validate", "--task", "task.json",
                         code="TASK_EXPECTED_OUTCOME_INVALID")


class RouteBindingTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("route", self)

    def test_unconfigured_route_is_honestly_unavailable(self):
        proc, payload = h.run_cli(self.project, "route", "check",
                                  "--role", "ENGINEER_PRIMARY", expect=0)
        self.assertEqual(payload["decision"], "UNAVAILABLE")
        self.assertNotIn("binding", payload)

    def test_configured_route_is_available_and_recorded(self):
        (self.project / ".agent-loop").mkdir(exist_ok=True)
        (self.project / ".agent-loop" / "config.json").write_bytes(
            json.dumps({
                "schema": "ual-config/1",
                "owner_actor": "OWNER",
                "actors": {"OWNER": {"roles": ["OWNER"]}},
                "role_bindings": {
                    "ENGINEER_PRIMARY": {"transport": "command",
                                         "model": "synthetic-engineer/1",
                                         "argv": ["synthetic-engineer"]}},
            }).encode("utf-8"))
        proc, payload = h.run_cli(self.project, "route", "check",
                                  "--role", "ENGINEER_PRIMARY", expect=0)
        self.assertEqual(payload["decision"], "AVAILABLE")
        self.assertEqual(payload["binding"]["model"], "synthetic-engineer/1")
        self.assertEqual(payload.get("observed_identity"), "UNKNOWN")

    def test_unknown_role_refused(self):
        h.expect_refusal(self.project, "route", "check", "--role", "WIZARD",
                         code="ROUTE_ROLE_UNKNOWN")


if __name__ == "__main__":
    unittest.main()

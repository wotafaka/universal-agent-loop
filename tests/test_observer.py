"""Observer policy, receipts and terminal resnapshot regressions.

Source mapping: X10 (NONE/DEFERRED/IMMEDIATE by deterministic facts),
X11 (receipt identity/profile binding), X12 (raw inline evidence, never
paths alone), X13 (terminal receipt resnapshot even without heartbeat).
"""
from __future__ import annotations

import hashlib
import json
import unittest

import _harness as h


def span_digest(log_path, start_line, end_line):
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    chunk = "\n".join(lines[start_line - 1:end_line])
    return hashlib.sha256(chunk.encode("utf-8")).hexdigest()


class ObserverPolicyTests(unittest.TestCase):
    def policy(self, **facts):
        overrides = {"observer": {"policy": "AUTO"}}
        overrides.update(facts)
        project = h.fresh_project("obspol", self)
        h.write_task(project, **overrides)
        proc, payload = h.run_cli(project, "observer", "policy",
                                  "--task", "demo-task")
        return payload

    def test_low_routine_strong_clear_needs_no_observer(self):
        payload = self.policy(risk="LOW", novelty="ROUTINE",
                              ambiguity="CLEAR", oracle_strength="STRONG")
        self.assertEqual(payload["policy"], "NONE")

    def test_medium_routine_deferred(self):
        payload = self.policy()
        self.assertEqual(payload["policy"], "DEFERRED")

    def test_high_risk_immediate(self):
        payload = self.policy(risk="HIGH")
        self.assertEqual(payload["policy"], "IMMEDIATE")
        self.assertIn("HIGH_RISK", payload["reasons"])

    def test_weak_oracle_immediate(self):
        payload = self.policy(oracle_strength="WEAK")
        self.assertEqual(payload["policy"], "IMMEDIATE")

    def test_unknown_facts_fail_closed_to_immediate(self):
        project = h.fresh_project("obspol-bad", self)
        h.write_task(project, oracle_strength="UNKNOWN_VALUE")
        import json as _json
        task_path = project / "task.json"
        task = _json.loads(task_path.read_text("utf-8"))
        task_path.write_bytes(_json.dumps(task).encode("utf-8"))
        proc, payload = h.run_cli(project, "observer", "policy",
                                  "--task", "demo-task", expect=2)
        codes = payload.get("errors") or []
        self.assertTrue(any("OBSERVER_FACTS_UNKNOWN" in c
                            or "TASK_ORACLE_INVALID" in c for c in codes),
                        codes)


class ObserverGateTests(unittest.TestCase):
    def setUp(self):
        self.project = h.fresh_project("obsgate", self)
        h.write_task(self.project, observer={"policy": "IMMEDIATE"})
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)

    def engineer_run(self):
        h.write_child(self.project, "engineer.py", "print('engineering')\n")
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose", "ENGINEER",
            "--session-id", "sess-engineer")
        return run

    def reach_close_gate(self):
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task", "--purpose",
            "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
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
        eng = self.engineer_run()
        return eng

    def receipt_payload(self, run_id, log_path, state="ATTACHED"):
        payload = {
            "schema": "ual-observer-receipt/1",
            "task": "demo-task",
            "run_id": run_id,
            "state": state,
            "observed_identity": "UNKNOWN",
            "recorded_at": "2026-08-31T00:00:00+00:00",
            "evidence_spans": [],
            "reason": None,
        }
        if state == "ATTACHED":
            payload["evidence_spans"] = [{
                "source_run": run_id, "start_line": 1, "end_line": 1,
                "sha256": span_digest(log_path, 1, 1)}]
        else:
            payload["reason"] = "observer route not configured in fixture"
        return payload

    def write_receipt(self, payload, expect=0):
        path = self.project / "receipt.json"
        path.write_bytes(json.dumps(payload).encode("utf-8"))
        return h.run_cli(self.project, "observer", "record", "--task",
                         "demo-task", "--payload", "receipt.json",
                         expect=expect)

    def test_missing_receipt_refuses_close(self):
        self.reach_close_gate()
        h.expect_refusal(self.project, "close", "--task", "demo-task",
                         code="OBSERVER_RECEIPT_MISSING")

    def test_invalid_span_digest_refused(self):
        eng = self.reach_close_gate()
        log = (self.project / ".agent-loop" / "runs" / eng["run_id"]
               / "log.txt")
        payload = self.receipt_payload(eng["run_id"], log)
        payload["evidence_spans"][0]["sha256"] = "0" * 64
        self.write_receipt(payload)
        h.expect_refusal(self.project, "close", "--task", "demo-task",
                         code="OBSERVER_RECEIPT_INVALID")

    def test_duplicate_receipt_for_run_refused(self):
        eng = self.reach_close_gate()
        log = (self.project / ".agent-loop" / "runs" / eng["run_id"]
               / "log.txt")
        self.write_receipt(self.receipt_payload(eng["run_id"], log))
        self.write_receipt(self.receipt_payload(eng["run_id"], log), expect=2)

    def test_route_unavailable_is_honest_terminal_receipt(self):
        eng = self.reach_close_gate()
        payload = self.receipt_payload(eng["run_id"], None,
                                       state="ROUTE_UNAVAILABLE")
        self.write_receipt(payload)
        proc, payload = h.run_cli(self.project, "close", "--task", "demo-task")
        self.assertTrue(payload["ok"])

    def test_valid_receipt_with_raw_span_closes_and_resnapshots(self):
        eng = self.reach_close_gate()
        log = (self.project / ".agent-loop" / "runs" / eng["run_id"]
               / "log.txt")
        self.write_receipt(self.receipt_payload(eng["run_id"], log))
        proc, payload = h.run_cli(self.project, "close", "--task", "demo-task")
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["observer_receipts"])
        receipt_file = (self.project / ".agent-loop" / "tasks" / "demo-task"
                        / "attempts" / "attempt_00000001" / "receipts" /
                        "receipt_0001.json")
        original = receipt_file.read_bytes()
        receipt_file.write_bytes(original + b"tampered\n")
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        h.expect_refusal(self.project, "envelope", "verify", "--task",
                         "demo-task", code="OBSERVER_RECEIPT_DRIFT")
        receipt_file.write_bytes(original)

    def test_receipt_task_mismatch_refused(self):
        eng = self.reach_close_gate()
        payload = self.receipt_payload(eng["run_id"], None,
                                       state="ROUTE_UNAVAILABLE")
        payload["task"] = "other-task"
        self.write_receipt(payload, expect=2)


if __name__ == "__main__":
    unittest.main()

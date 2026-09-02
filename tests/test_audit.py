"""Audit package, verdict binding and fallback policy regressions.

Source mapping: X19 (audit package/result integrity; candidate identity
required), X20 (objective provider fallback; a valid FAIL is not an outage),
R5 (process exit zero is not audit PASS; missing observed provider identity
is UNKNOWN).
"""
from __future__ import annotations

import hashlib
import json
import unittest

import _harness as h


def sha_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AuditFlowBase(unittest.TestCase):
    def _build(self, name):
        self.project = h.fresh_project(name, self)
        h.write_task(self.project, audit={"required": True})
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)
        for argv_run in range(2):
            proc, run = h.run_cli(
                self.project, "run", "--task", "demo-task", "--purpose",
                "VALIDATION",
                "--argv-json", json.dumps(
                    [h.sys_executable(), "check_demo.py"]))
            h.run_cli(self.project, "validate", "record", "--task",
                      "demo-task", "--run", run["run_id"], "--ordinal", "1")
            if argv_run == 0:
                (self.project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")

    def build_package(self, iteration=1, expect=0):
        return h.run_cli(
            self.project, "audit", "package", "--task", "demo-task",
            "--iteration", str(iteration),
            *h.audit_cli_flags(h.audit_closure_flags(self.project)),
            expect=expect)

    def write_result(self, payload, name="audit_result.json"):
        path = self.project / name
        if isinstance(payload, (dict, list)):
            path.write_bytes(json.dumps(payload).encode("utf-8"))
        else:
            path.write_bytes(payload.encode("utf-8"))
        return name

    def route_log(self, exit_code=0, model=None, name="route_log.json"):
        path = self.project / name
        payload = {"exit_code": exit_code}
        if model:
            payload["model_observed"] = model
        path.write_bytes(json.dumps(payload).encode("utf-8"))
        return name

    def enable_fallback(self):
        config_dir = self.project / ".agent-loop"
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / "config.json"
        config = json.loads(config_path.read_text("utf-8")) \
            if config_path.is_file() else {
                "schema": "ual-config/1", "owner_actor": "OWNER",
                "actors": {"OWNER": {"roles": ["OWNER"]}}}
        config["audit_policy"] = {"fallback_enabled": True}
        config_path.write_bytes(json.dumps(config, indent=2).encode("utf-8"))


class AuditPackageTests(AuditFlowBase):
    def setUp(self):
        self._build("auditpkg")

    def test_package_builds_and_verifies(self):
        proc, payload = self.build_package()
        self.assertTrue(payload["ok"])
        proc, payload = h.run_cli(self.project, "audit", "verify", "--task",
                                  "demo-task", "--package", payload["package"])
        self.assertTrue(payload["ok"])

    def test_package_is_deterministic(self):
        _, first = self.build_package(iteration=1)
        _, second = self.build_package(iteration=2)
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        manifest_dir = self.project / second["package"]
        manifest = json.loads(
            (manifest_dir / "manifest.json").read_text("utf-8"))
        manifest.pop("iteration")
        manifest_one_dir = self.project / first["package"]
        manifest_one = json.loads(
            (manifest_one_dir / "manifest.json").read_text("utf-8"))
        manifest_one.pop("iteration")
        self.assertEqual(manifest_one, manifest)

    def test_secret_material_refused(self):
        project = h.fresh_project("auditsecret", self)
        h.write_task(project)
        h.write_child(project, "check_demo.py", h.check_script(True))
        h.authority(project)
        for argv_run in range(2):
            proc, run = h.run_cli(
                project, "run", "--task", "demo-task", "--purpose",
                "VALIDATION",
                "--argv-json", json.dumps(
                    [h.sys_executable(), "check_demo.py"]))
            h.run_cli(project, "validate", "record", "--task",
                      "demo-task", "--run", run["run_id"], "--ordinal",
                      "1")
            if argv_run == 0:
                (project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
        (project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(project, "refresh", "--task", "demo-task")
        h.run_cli(project, "report-check", "--task", "demo-task")
        h.run_cli(project, "close", "--task", "demo-task")
        h.run_cli(project, "envelope", "freeze", "--task", "demo-task")
        (project / "secretish.txt").write_bytes(
            b"api" + b"_key = deadbeef\n")
        h.expect_refusal(
            project, "audit", "package", "--task", "demo-task",
            "--iteration", "1", "--input", "secretish.txt",
            code="SECRET_MATERIAL_SUSPECTED")

    def test_tampered_package_refused(self):
        _, payload = self.build_package()
        package = self.project / payload["package"]
        (package / "audit_payload.bin").write_bytes(b"tampered\n")
        h.expect_refusal(self.project, "audit", "verify", "--task",
                         "demo-task", "--package", payload["package"],
                         code="AUDIT_PAYLOAD_IDENTITY_MISMATCH")


class AuditVerdictTests(AuditFlowBase):
    def setUp(self):
        self._build("auditverdict")
        _, payload = self.build_package()
        self.package = payload["package"]

    def audit_record(self, result, route_receipt=None, allow_fallback=False,
                     expect=0):
        args = ["audit", "record", "--task", "demo-task", "--package",
                self.package, "--result-file", result]
        if route_receipt:
            args += ["--route-receipt", route_receipt]
        if allow_fallback:
            args += ["--allow-fallback"]
        return h.run_cli(self.project, *args, expect=expect)

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

    def write_route_receipt(self, name="route_receipt.json", *,
                            kind="AUDIT_RESULT",
                            requested="synthetic-auditor/1",
                            observed="synthetic-auditor/1",
                            exit_code=0, result=None, raw=None,
                            provider_status=None, error_code=None,
                            terminal=None):
        args = ["audit", "route-receipt", "--task", "demo-task",
                "--package", self.package, "--kind", kind,
                "--requested-model", requested,
                "--model-observed", observed,
                "--exit-code", str(exit_code), "--out", name]
        if result:
            args += ["--result-file", result]
        if raw:
            args += ["--raw-error-file", raw]
        if provider_status is not None:
            args += ["--provider-status", str(provider_status)]
        if error_code is not None:
            args += ["--error-code", error_code]
        if terminal:
            args += ["--terminal"]
        h.run_cli(self.project, *args)
        return name

    def test_valid_pass_verdict_records(self):
        result = self.write_result({
            "verdict": "PASS", "findings": [],
            "requested_model": "synthetic-auditor/1"})
        receipt = self.write_route_receipt(result=result)
        proc, payload = self.audit_record(result, receipt)
        self.assertEqual(payload["disposition"], "AUDIT_RESULT")
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["observed_model"], "synthetic-auditor/1")

    def test_missing_route_receipt_observed_unknown(self):
        result = self.write_result({
            "verdict": "PASS", "findings": [],
            "requested_model": "synthetic-auditor/1"})
        proc, payload = self.audit_record(result)
        self.assertEqual(payload["observed_model"], "UNKNOWN")

    def test_exit_zero_without_verdict_is_not_pass(self):
        result = self.write_result("the provider said nice things in prose\n")
        self.audit_record(result, expect=2)
        proc, payload = h.run_cli(self.project, "audit", "status", "--task",
                                  "demo-task")
        self.assertIsNone(payload.get("latest_pass"))

    def test_valid_fail_is_real_result_not_outage(self):
        result = self.write_result({
            "verdict": "FAIL",
            "findings": [{"severity": "P1", "location": "src/demo.py",
                          "observed_evidence": "wrong value",
                          "impact": "correctness", "reproduction": "run",
                          "recommendation": "fix"}],
            "requested_model": "synthetic-auditor/1",
            "actual_model": "synthetic-auditor/1"})
        proc, payload = self.audit_record(result)
        self.assertEqual(payload["disposition"], "AUDIT_RESULT")
        self.assertEqual(payload["verdict"], "FAIL")

    def test_fallback_without_policy_refused(self):
        raw = self.write_raw()
        receipt = self.write_route_receipt(
            kind="PROVIDER_FAILURE", requested="m", observed="m",
            exit_code=1, raw=raw, provider_status=429, terminal=True)
        result = self.write_result("not json at all")
        self.audit_record(result, receipt, allow_fallback=True, expect=2)

    def test_audit_pass_satisfies_required_acceptance(self):
        result = self.write_result({
            "verdict": "PASS", "findings": [],
            "requested_model": "m", "actual_model": "m"})
        self.audit_record(result)
        self.write_review_file()
        proc, payload = h.run_cli(self.project, "review", "validate",
                                  "--task", "demo-task", "--review", "review.md")
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        proc, payload = h.run_cli(self.project, "accept", "--task",
                                  "demo-task", "--actor", "OWNER",
                                  "--decision", "ACCEPTED",
                                  "--review", "review.md")
        self.assertEqual(payload["decision"], "ACCEPTED")

    def test_stale_audit_cannot_accept_changed_candidate(self):
        result = self.write_result({
            "verdict": "PASS", "findings": [],
            "requested_model": "m", "actual_model": "m"})
        self.audit_record(result)
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 77\n")
        self.write_review_file()
        h.run_cli(self.project, "review", "validate", "--task", "demo-task",
                  "--review", "review.md", expect=2)

    def write_review_file(self, project=None):
        project = project or self.project
        (project / "proof_one.json").write_bytes(b'{"p": 1}\n')
        (project / "proof_two.json").write_bytes(b'{"p": 2}\n')
        p1 = sha_of(project / "proof_one.json")
        p2 = sha_of(project / "proof_two.json")
        envelope_dir = (project / ".agent-loop" / "tasks" / "demo-task" /
                        "attempts" / "attempt_00000001" / "envelope")
        envelope_sha = hashlib.sha256(
            sorted(envelope_dir.glob("envelope_*.json"))[-1]
            .read_bytes()).hexdigest()
        text = (
            "# Independent review — demo-task (synthetic fixture)\n\n"
            "## Contract compliance\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact `proof_one.json`"
            " sha256 `" + p1 + "` origin `REVIEWER_RECOMPUTED` action"
            " `recomputed fixture digests` candidate `demo-task`\n\n"
            "## Adversarial validity\n\n- Verdict: `PASS`\n"
            "- Evidence: `validation-review-proof/1` artifact `proof_two.json`"
            " sha256 `" + p2 + "` origin `REVIEWER_REEXECUTED` action"
            " `re-executed fixture checks` candidate `demo-task`\n\n"
            "## Findings\n\n- NONE\n\n## Durable correction\n\n"
            "- Mandated change: `NONE`\n\n"
            "## Convergence disposition\n\n"
            "- Disposition: `CONVERGED`\n"
            "- Covered requirement IDs: `R1,R2`\n"
            "- Remaining material requirement IDs: `NONE`\n\n"
            "## Frozen envelope binding\n\n"
            "- Frozen envelope sha256: `" + envelope_sha + "`\n")
        (project / "review.md").write_text(text, encoding="utf-8")
        return project / "review.md"


def sha_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()

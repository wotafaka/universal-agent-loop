"""Envelope freeze, bound review and manual acceptance regressions.

Source mapping: C04 (candidate/task/skill closure), C09/C10/C11 (two-pass
proof review, high-risk reviewer challenge, durable corrections), C14/C15
(audit binding at acceptance; role flip cannot bypass acceptance), C16
(git absence is not a clean diff), P10 (requirement convergence), R1
(re-verify all hashes at review AND acceptance).
"""
from __future__ import annotations

import hashlib
import json
import unittest

import _harness as h


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LifecycleFixture(unittest.TestCase):
    TASK_OVERRIDES = {}

    def _build(self, name, **task_overrides):
        self.project = h.fresh_project(name, self)
        self.task, _ = h.write_task(self.project, **{
            **self.TASK_OVERRIDES, **task_overrides})
        h.write_child(self.project, "check_demo.py", h.check_script(True))
        h.authority(self.project)
        run = self.run_check()
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
        run = self.run_check()
        h.run_cli(self.project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (self.project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(self.project, "refresh", "--task", "demo-task")
        h.run_cli(self.project, "report-check", "--task", "demo-task")
        h.run_cli(self.project, "close", "--task", "demo-task")

    def run_check(self):
        proc, run = h.run_cli(
            self.project, "run", "--task", "demo-task",
            "--purpose", "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        return run

    def proof_line(self, artifact, origin, action):
        data = (self.project / artifact).read_bytes()
        return ("`validation-review-proof/1` artifact `" + artifact
                + "` sha256 `" + sha(data) + "` origin `" + origin
                + "` action `" + action + "` candidate `demo-task`")

    def write_review(self, high_risk=False, findings_text="- NONE\n",
                     corrections="- Mandated change: `NONE`\n",
                     convergence=True, verdict="PASS", challenge=True):
        (self.project / "proof_one.json").write_bytes(
            json.dumps({"pass": 1}).encode("utf-8"))
        (self.project / "proof_two.json").write_bytes(
            json.dumps({"pass": 2}).encode("utf-8"))
        text = (
            "# Independent review — demo-task (synthetic fixture)\n\n"
            "## Contract compliance\n\n"
            "- Verdict: `" + verdict + "`\n"
            "- Evidence: " + self.proof_line(
                "proof_one.json", "REVIEWER_RECOMPUTED",
                "recomputed the fixture envelope digests") + "\n\n"
            "## Adversarial validity\n\n"
            "- Verdict: `" + verdict + "`\n"
            "- Evidence: " + self.proof_line(
                "proof_two.json", "REVIEWER_REEXECUTED",
                "re-executed the fixture checks") + "\n")
        if high_risk and challenge:
            (self.project / "challenge_artifact.json").write_bytes(
                b'{"counterexample": "empty-input"}\n')
            data = (self.project / "challenge_artifact.json").read_bytes()
            text += (
                "- Challenge type: `NEGATIVE_COUNTEREXAMPLE`\n"
                "- Challenge target: `src/demo.py`\n"
                "- Challenge artifact: `challenge_artifact.json`\n"
                "- Challenge artifact bytes: `" + str(len(data)) + "`\n"
                "- Challenge artifact sha256: `" + sha(data) + "`\n"
                "- Challenge result: `counterexample refused by candidate`\n")
        text += ("\n## Findings\n\n" + findings_text
                 + "\n## Durable correction\n\n" + corrections + "\n")
        if convergence:
            text += ("\n## Convergence disposition\n\n"
                     "- Disposition: `CONVERGED`\n"
                     "- Covered requirement IDs: `R1,R2`\n"
                     "- Remaining material requirement IDs: `NONE`\n")
        text += h.envelope_binding_section(self.project)
        path = self.project / "review.md"
        path.write_text(text, encoding="utf-8")
        return path

    def freeze_and_seal(self, review=None):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = review if review is not None else self.write_review(
            high_risk=self.task["risk"] == "HIGH")
        h.run_cli(self.project, "review", "validate", "--task", "demo-task",
                  "--review", "review.md")
        h.run_cli(self.project, "review", "seal", "--task", "demo-task",
                  "--review", "review.md", "--verdict", "PASS",
                  "--reviewer-session", "sess-reviewer")
        return review


class EnvelopeTests(LifecycleFixture):
    def setUp(self):
        self._build("envelope")

    def test_envelope_freeze_and_verify(self):
        proc, payload = h.run_cli(self.project, "envelope", "freeze",
                                  "--task", "demo-task")
        self.assertEqual(payload["members"][0]["path"], "src/demo.py")
        self.assertIn("report/IMPLEMENTATION.md",
                      [m["path"] for m in payload["members"]])
        proc, payload = h.run_cli(self.project, "envelope", "verify",
                                  "--task", "demo-task")
        self.assertTrue(payload["ok"])

    def test_candidate_drift_refuses_verify(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 99\n")
        h.expect_refusal(self.project, "envelope", "verify", "--task",
                         "demo-task", code="CANDIDATE_MEMBER_DRIFT")

    def test_skill_closure_missing_refused(self):
        skills = self.project / "skills" / "demo-skill"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("demo skill body\n", encoding="utf-8")
        project = h.fresh_project("envelope-skills", self)
        h.write_task(project, required_skills=["skills/demo-skill/SKILL.md"])
        h.write_child(project, "check_demo.py", h.check_script(True))
        h.write_config(project)
        h.register_sessions(project)
        proc, run = h.run_cli(
            project, "run", "--task", "demo-task", "--purpose", "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (project / "src" / "demo.py").write_bytes(b"VALUE = 2\n")
        proc, run = h.run_cli(
            project, "run", "--task", "demo-task", "--purpose", "VALIDATION",
            "--argv-json", json.dumps([h.sys_executable(), "check_demo.py"]))
        h.run_cli(project, "validate", "record", "--task", "demo-task",
                  "--run", run["run_id"], "--ordinal", "1")
        (project / "report" / "IMPLEMENTATION.md").write_text(
            "done\n", encoding="utf-8")
        h.run_cli(project, "refresh", "--task", "demo-task")
        h.run_cli(project, "report-check", "--task", "demo-task")
        h.run_cli(project, "close", "--task", "demo-task")
        h.expect_refusal(project, "envelope", "freeze", "--task", "demo-task",
                         code="CANDIDATE_SKILL_MISSING")

    def test_double_freeze_refused_write_once(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        h.expect_refusal(self.project, "envelope", "freeze", "--task",
                         "demo-task", code="ENVELOPE_EXISTS")


class ReviewGrammarTests(LifecycleFixture):
    def setUp(self):
        self._build("review")

    def test_valid_review_validates_and_seals(self):
        self.freeze_and_seal()

    def test_duplicate_verdict_refused(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review()
        text = review.read_text("utf-8").replace(
            "- Verdict: `PASS`", "- Verdict: `PASS`\n- Verdict: `FAIL`", 1)
        review.write_text(text, "utf-8")
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         code="REVIEW_DUPLICATE_VERDICT")

    def test_unknown_finding_needs_correction(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review(findings_text="- Bug7: crash on empty input\n")
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         code="REVIEW_FINDING_MALFORMED:- Bug7")

    def test_material_finding_requires_disposition(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review(findings_text="- M1: crash on empty input\n")
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         code="CORRECTION_DISPOSITION_MISSING:M1")

    def test_convergence_required_for_full_accepting_review(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review(convergence=False)
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         code="CONVERGENCE_DISPOSITION_SECTION_MISSING")

    def test_fail_pass_refused(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review(verdict="FAIL")
        proc, payload = h.run_cli(self.project, "review", "validate",
                                  "--task", "demo-task",
                                  "--review", "review.md")
        self.assertTrue(payload["ok"])
        h.expect_refusal(self.project, "review", "seal", "--task",
                         "demo-task", "--review", "review.md",
                         "--verdict", "PASS",
                         "--reviewer-session", "sess-reviewer",
                         code="REVIEW_TWO_PASS_FAIL_WITH_ACCEPTING_VERDICT")

    def test_proof_hash_drift_refused(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review()
        (self.project / "proof_one.json").write_bytes(b'{"pass": 1,"x":1}\n')
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         code="REVIEW_PROOF_HASH_MISMATCH")

    def test_reference_guard_composition(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review()
        proc, payload = h.run_cli(
            self.project, "review", "validate", "--task", "demo-task",
            "--review", "review.md",
            "--reference-root", str(h.CHECKOUT / "reference"))
        self.assertTrue(payload["ok"])
        bad = review.read_text("utf-8").replace(
            "- Verdict: `PASS`", "- Verdict: `PASS`\n- Verdict: `PASS`", 1)
        review.write_text(bad, "utf-8")
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         "--reference-root", str(h.CHECKOUT / "reference"),
                         code="REVIEW_GUARD_DUPLICATE_VERDICT")


class HighRiskReviewTests(LifecycleFixture):
    TASK_OVERRIDES = {"risk": "HIGH"}

    def setUp(self):
        self._build("review-high")

    def test_high_risk_requires_reviewer_challenge(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review(high_risk=False)
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         code="ADVERSARIAL_CHALLENGE_REQUIRED")
        review = self.write_review(high_risk=True)
        proc, payload = h.run_cli(self.project, "review", "validate",
                                  "--task", "demo-task", "--review", "review.md")
        self.assertTrue(payload["ok"])

    def test_challenge_artifact_drift_refused(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        review = self.write_review(high_risk=True)
        (self.project / "challenge_artifact.json").write_bytes(b'{"x": 2}\n')
        h.expect_refusal(self.project, "review", "validate", "--task",
                         "demo-task", "--review", "review.md",
                         code="ADVERSARIAL_CHALLENGE_ARTIFACT_SHA_MISMATCH")


class AcceptanceTests(LifecycleFixture):
    def setUp(self):
        self._build("accept")

    def test_acceptance_owner_only_and_bound(self):
        self.freeze_and_seal()
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "ENGINEER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="ACCEPTANCE_ACTOR_NOT_OWNER")
        proc, payload = h.run_cli(self.project, "accept", "--task",
                                  "demo-task", "--actor", "OWNER",
                                  "--decision", "ACCEPTED",
                                  "--review", "review.md")
        self.assertEqual(payload["decision"], "ACCEPTED")

    def test_acceptance_reverifies_hashes_after_seal(self):
        self.freeze_and_seal()
        (self.project / "src" / "demo.py").write_bytes(b"VALUE = 40\n")
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="CANDIDATE_MEMBER_DRIFT")

    def test_review_drift_refuses_acceptance(self):
        review = self.freeze_and_seal()
        review.write_text(
            review.read_text("utf-8") + "\ntampered\n", encoding="utf-8")
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="REVIEW_SEAL_ARTIFACT_DRIFT")

    def test_acceptance_without_seal_refused(self):
        h.run_cli(self.project, "envelope", "freeze", "--task", "demo-task")
        self.write_review()
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="REVIEW_SEAL_MISSING")


class AuditRequiredAcceptanceTests(LifecycleFixture):
    TASK_OVERRIDES = {"audit": {"required": True}}

    def setUp(self):
        self._build("accept-audit")

    def test_required_audit_blocks_acceptance_until_passed(self):
        self.freeze_and_seal()
        h.expect_refusal(self.project, "accept", "--task", "demo-task",
                         "--actor", "OWNER", "--decision", "ACCEPTED",
                         "--review", "review.md",
                         code="ACCEPTANCE_AUDIT_REQUIRED")


if __name__ == "__main__":
    unittest.main()

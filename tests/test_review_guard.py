"""Focused regressions for the hardened bound-review seam.

RED phase rule: while validation/review_guard.py does not exist, the helpers
below route to the unchanged legacy reference pair (parse_two_pass_review +
validate_correction_dispositions) so the observed failures are the reproduced
acceptance defects themselves — duplicate verdict declarations accepted and
unknown finding declarations silently ignored — never a missing import.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = PACKAGE_ROOT / "reference"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

_LEGACY_CONTRACT = None
_LEGACY_SMOKE = None


def _load_member(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(
        module_name, REFERENCE_DIR / name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _guard_module():
    try:
        from validation import review_guard as guard
    except ImportError:
        return None
    return guard


def _contract_module():
    global _LEGACY_CONTRACT
    guard = _guard_module()
    if guard is not None:
        return guard.load_verified_contract()
    if _LEGACY_CONTRACT is None:
        _LEGACY_CONTRACT = _load_member(
            "agent_loop_contract.py", "review_guard_tests.legacy_contract")
    return _LEGACY_CONTRACT


def _smoke_module():
    global _LEGACY_SMOKE
    guard = _guard_module()
    if guard is not None:
        guard.verify_reference_members()
    if _LEGACY_SMOKE is None:
        _LEGACY_SMOKE = _load_member("smoke.py",
                                     "review_guard_tests.reference_smoke")
    return _LEGACY_SMOKE


class BoundReviewGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="review-guard-tests-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.contract = _contract_module()
        self.smoke = _smoke_module()
        self.task_id = self.smoke.SYNTHETIC_TASK
        self.evidence = self.smoke.build_reference_evidence(
            self.tmp, self.contract)
        self.baseline = self.evidence["review_text"]
        self.decision = self.smoke.synthetic_owner_decision(
            self.evidence["candidate_sha256"])

    def guard_refusals(self, text, *, reference_root=None):
        guard = _guard_module()
        if guard is None:
            refusals = list(self.contract.parse_two_pass_review(
                text, root=self.tmp, task_id=self.task_id))
            refusals += list(self.contract.validate_correction_dispositions(
                text, root=self.tmp))
            return refusals
        return list(guard.validate_bound_review(
            text, root=self.tmp, task_id=self.task_id,
            reference_root=reference_root))

    def legacy_acceptance(self, evidence, decision):
        return self.smoke.reference_manual_acceptance(
            self.contract, self.tmp, evidence, decision)

    def assert_refusal_code(self, refusals, code):
        self.assertTrue(any(code in refusal for refusal in refusals),
                        refusals)

    def duplicate_fail_text(self):
        return self.baseline.replace(
            "- Verdict: `PASS`", "- Verdict: `PASS`\n- Verdict: `FAIL`", 1)

    def duplicate_pass_text(self):
        return self.baseline.replace(
            "- Verdict: `PASS`", "- Verdict: `PASS`\n- Verdict: `PASS`", 1)

    def duplicate_heading_text(self):
        return self.baseline + "\n## Contract compliance\n\n- Verdict: `PASS`\n"

    def unknown_finding_text(self):
        return self.baseline.replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\n- Bug7: crash on empty input\n\n"
            "## Durable correction")

    def uncorrected_finding_text(self):
        return self.baseline.replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\n- M1: crash on empty input\n\n"
            "## Durable correction")

    def indented_finding_text(self):
        return self.baseline.replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\n  - M1: crash on empty input\n\n"
            "## Durable correction")

    def star_bullet_finding_text(self):
        return self.baseline.replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\n* M1: crash on empty input\n\n"
            "## Durable correction")

    def table_finding_text(self):
        return self.baseline.replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\n| M1 | crash | evidence |\n\n"
            "## Durable correction")

    def prose_finding_text(self):
        return self.baseline.replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\nNotes: reviewed all findings\n\n"
            "## Durable correction")

    def none_findings_text(self):
        return self.baseline.replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\n- NONE\n\n## Durable correction")

    def renamed_findings_text(self):
        return self.baseline.replace("## Findings\n", "## Unrelated\n", 1)

    def indented_second_verdict_text(self):
        return self.baseline.replace(
            "- Verdict: `PASS`", "- Verdict: `PASS`\n    - Verdict: `FAIL`", 1)

    def noncanonical_second_verdict_text(self):
        return self.baseline.replace(
            "- Verdict: `PASS`", "- Verdict: `PASS`\n- Verdict: `MAYBE`", 1)

    def noncanonical_single_verdict_text(self):
        return self.baseline.replace(
            "- Verdict: `PASS`", "- Verdict: `MAYBE`", 1)

    def missing_verdict_text(self):
        return self.baseline.replace("- Verdict: `PASS`\n", "", 1)

    def star_fail_after_pass_text(self):
        return self.baseline.replace(
            "- Verdict: `PASS`", "- Verdict: `PASS`\n* Verdict: `FAIL`", 1)

    def malformed_verdict_text(self, line):
        return self.baseline.replace("- Verdict: `PASS`", line, 1)

    def mention_finding_text(self):
        return self.baseline.replace(
            "## Adversarial validity",
            "Note: the ## Findings section follows later.\n\n"
            "## Adversarial validity", 1).replace(
            "## Findings\n\n## Durable correction",
            "## Findings\n\n* M1: crash on empty input\n\n"
            "## Durable correction")

    def historical_pass_hides_fail_text(self):
        heading = "## Contract compliance"
        end = self.baseline.index("## Adversarial validity")
        historical = self.baseline[:end].replace(
            heading, heading + " (historical)")
        failed = self.baseline.replace("`PASS`", "`FAIL`", 1)
        return historical + "\n" + failed

    def historical_findings_hide_m1_text(self):
        end = self.baseline.index("## Durable correction")
        historical = self.baseline[:end].replace(
            "## Findings", "## Findings (historical)")
        return historical + "\n" + self.uncorrected_finding_text()

    def canonical_correction_text(self):
        (self.tmp / "finding_evidence.md").write_bytes(
            b"M1-reproduction: synthetic finding anchor\n")
        return self.uncorrected_finding_text().replace(
            "- Mandated change: `NONE`\n",
            "- Mandated change: `NONE`\n"
            "- M1: `NONE_REQUIRED` \u2014 rationale: reproduction recorded and "
            "refuted by the candidate bytes \u2014 evidence: "
            "`finding_evidence.md#M1-reproduction`\n")

    def test_valid_baseline_passes_guard_and_reference_gate(self):
        self.assertEqual([], self.guard_refusals(self.baseline))
        self.assertEqual([], self.legacy_acceptance(self.evidence, self.decision))

    def test_duplicate_fail_verdict_is_refused(self):
        self.assertEqual([], self.legacy_acceptance(
            dict(self.evidence, review_text=self.duplicate_fail_text()),
            self.decision))
        self.assert_refusal_code(
            self.guard_refusals(self.duplicate_fail_text()),
            "REVIEW_GUARD_DUPLICATE_VERDICT:## Contract compliance:PASS/FAIL")

    def test_duplicate_pass_verdict_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.duplicate_pass_text()),
            "REVIEW_GUARD_DUPLICATE_VERDICT:## Contract compliance:PASS/PASS")

    def test_duplicate_required_section_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.duplicate_heading_text()),
            "REVIEW_GUARD_DUPLICATE_SECTION:## Contract compliance")

    def test_unknown_finding_declaration_is_refused(self):
        self.assertEqual([], self.legacy_acceptance(
            dict(self.evidence, review_text=self.unknown_finding_text()),
            self.decision))
        self.assert_refusal_code(
            self.guard_refusals(self.unknown_finding_text()),
            "REVIEW_GUARD_FINDING_MALFORMED:- Bug7")

    def test_canonical_finding_without_correction_still_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.uncorrected_finding_text()),
            "CORRECTION_DISPOSITION_MISSING:M1")

    def test_valid_canonical_correction_passes(self):
        self.assertEqual([], self.guard_refusals(self.canonical_correction_text()))

    def test_missing_proof_artifact_is_refused(self):
        (self.tmp / "proof_contract_compliance.json").unlink()
        self.assert_refusal_code(
            self.guard_refusals(self.baseline),
            "REVIEW_TWO_PASS_EVIDENCE_ARTIFACT_MISSING")

    def test_unbound_root_never_accepts(self):
        guard = _guard_module()
        if guard is None:
            legacy = self.contract.parse_two_pass_review(
                self.baseline, root=None, task_id=self.task_id)
            self.fail("guard missing; legacy shape-only result for unbound "
                      "root: " + repr(legacy))
        self.assert_refusal_code(
            guard.validate_bound_review(self.baseline, root=None,
                                        task_id=self.task_id),
            "REVIEW_GUARD_ROOT_UNBOUND")

    def test_unbound_task_never_accepts(self):
        guard = _guard_module()
        if guard is None:
            legacy = self.contract.parse_two_pass_review(
                self.baseline, root=self.tmp, task_id=None)
            self.fail("guard missing; legacy shape-only result for unbound "
                      "task: " + repr(legacy))
        self.assert_refusal_code(
            guard.validate_bound_review(self.baseline, root=self.tmp,
                                        task_id=None),
            "REVIEW_GUARD_TASK_UNBOUND")

    def test_positional_binding_is_refused(self):
        guard = _guard_module()
        if guard is None:
            legacy = self.contract.parse_two_pass_review(
                self.baseline, self.tmp, self.task_id)
            self.assertEqual([], legacy)
            self.fail("guard missing; legacy pair accepts positional binding")
        with self.assertRaises(TypeError):
            guard.validate_bound_review(self.baseline, self.tmp, self.task_id)

    def test_pinned_reference_identity_is_verified(self):
        guard = _guard_module()
        if guard is None:
            self.assertEqual([], self.contract.parse_two_pass_review(
                self.baseline, root=self.tmp, task_id=self.task_id))
            return
        self.assertEqual(REFERENCE_DIR, guard.verify_reference_members())
        self.assertTrue(hasattr(guard.load_verified_contract(),
                                "parse_two_pass_review"))

    def test_tampered_core_member_denied_before_execution(self):
        tampered = self.tmp / "reference-tampered"
        shutil.copytree(REFERENCE_DIR, tampered)
        member = tampered / "agent_loop_contract.py"
        member.write_bytes(member.read_bytes()
                           + b"\nraise RuntimeError('CORRUPTED_CORE_EXECUTED')\n")
        guard = _guard_module()
        if guard is None:
            refusals = self.guard_refusals(self.baseline)
            self.fail("guard missing; legacy pair never checks reference "
                      "identity: " + repr(refusals))
        try:
            refusals = guard.validate_bound_review(
                self.baseline, root=self.tmp, task_id=self.task_id,
                reference_root=tampered)
        except RuntimeError as exc:
            self.fail("tampered core executed instead of being refused: "
                      + str(exc))
        self.assert_refusal_code(
            refusals, "MEMBER_IDENTITY_MISMATCH:agent_loop_contract.py")
        self.assertTrue(
            all("CORRUPTED_CORE_EXECUTED" not in refusal
                for refusal in refusals), refusals)

    def test_tampered_manifest_denied(self):
        tampered = self.tmp / "reference-manifest-tampered"
        shutil.copytree(REFERENCE_DIR, tampered)
        manifest = tampered / "manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b" ")
        guard = _guard_module()
        if guard is None:
            self.fail("guard missing; no manifest identity check exists in "
                      "the legacy pair")
        self.assert_refusal_code(
            guard.validate_bound_review(
                self.baseline, root=self.tmp, task_id=self.task_id,
                reference_root=tampered),
            "REVIEW_GUARD_REFERENCE_IDENTITY:MANIFEST_IDENTITY_MISMATCH")

    def test_hardened_reference_acceptance_composition(self):
        defect = dict(self.evidence, review_text=self.duplicate_fail_text())
        refusals = self.guard_refusals(self.duplicate_fail_text())
        refusals += self.legacy_acceptance(defect, self.decision)
        self.assert_refusal_code(refusals, "REVIEW_GUARD_DUPLICATE_VERDICT")
        self.assertEqual([], self.guard_refusals(self.baseline))
        self.assertEqual([], self.legacy_acceptance(self.evidence, self.decision))

    def test_unchanged_gates_still_refuse(self):
        self.assert_refusal_code(self.legacy_acceptance(self.evidence, None),
                                 "ACCEPTANCE_REFUSED_NO_EXPLICIT_DECISION")
        name, original = self.evidence["members"][0]
        (self.tmp / name).write_bytes(original + b"# tampered\n")
        self.assert_refusal_code(
            self.legacy_acceptance(self.evidence, self.decision),
            "ACCEPTANCE_REFUSED_CANDIDATE_DRIFT")
        (self.tmp / name).write_bytes(original)

    def test_indented_canonical_finding_is_refused(self):
        self.assertEqual([], self.legacy_acceptance(
            dict(self.evidence, review_text=self.indented_finding_text()),
            self.decision))
        self.assert_refusal_code(
            self.guard_refusals(self.indented_finding_text()),
            "REVIEW_GUARD_FINDING_MALFORMED:- M1")

    def test_star_bullet_finding_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.star_bullet_finding_text()),
            "REVIEW_GUARD_FINDING_MALFORMED:* M1")

    def test_noncanonical_findings_content_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.table_finding_text()),
            "REVIEW_GUARD_FINDING_MALFORMED:| M1")
        self.assert_refusal_code(
            self.guard_refusals(self.prose_finding_text()),
            "REVIEW_GUARD_FINDING_MALFORMED:Notes:")

    def test_explicit_none_findings_pass(self):
        self.assertEqual([], self.guard_refusals(self.none_findings_text()))
        self.assertEqual([], self.legacy_acceptance(
            dict(self.evidence, review_text=self.none_findings_text()),
            self.decision))

    def test_missing_findings_section_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.renamed_findings_text()),
            "REVIEW_GUARD_SECTION_MISSING:## Findings")

    def test_indented_second_verdict_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.indented_second_verdict_text()),
            "REVIEW_GUARD_DUPLICATE_VERDICT:## Contract compliance:PASS/FAIL")

    def test_noncanonical_second_verdict_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.noncanonical_second_verdict_text()),
            "REVIEW_GUARD_DUPLICATE_VERDICT:## Contract compliance:PASS/MAYBE")

    def test_noncanonical_single_verdict_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.noncanonical_single_verdict_text()),
            "REVIEW_GUARD_VERDICT_MALFORMED:## Contract compliance")

    def test_missing_verdict_is_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.missing_verdict_text()),
            "REVIEW_GUARD_VERDICT_MISSING:## Contract compliance")

    def test_star_fail_after_canonical_pass_is_refused(self):
        self.assertEqual([], self.legacy_acceptance(
            dict(self.evidence, review_text=self.star_fail_after_pass_text()),
            self.decision))
        self.assert_refusal_code(
            self.guard_refusals(self.star_fail_after_pass_text()),
            "REVIEW_GUARD_DUPLICATE_VERDICT:## Contract compliance:PASS/FAIL")

    def test_malformed_verdict_declarations_are_refused(self):
        cases = (
            "* Verdict: `FAIL`",
            "+ Verdict: FAIL",
            "1. Verdict: FAIL",
            "- Verdict : FAIL",
            "Verdict: FAIL",
            "verdict: FAIL",
        )
        for line in cases:
            with self.subTest(line=line):
                self.assert_refusal_code(
                    self.guard_refusals(self.malformed_verdict_text(line)),
                    "REVIEW_GUARD_VERDICT_MALFORMED:## Contract compliance")

    def test_two_verdict_fields_on_one_line_are_refused(self):
        self.assert_refusal_code(
            self.guard_refusals(self.malformed_verdict_text(
                "- Verdict: `PASS` verdict: `FAIL`")),
            "REVIEW_GUARD_VERDICT_MALFORMED:## Contract compliance")

    def test_inline_heading_mention_cannot_hide_findings(self):
        self.assertEqual([], self.legacy_acceptance(
            dict(self.evidence, review_text=self.mention_finding_text()),
            self.decision))
        refusals = self.guard_refusals(self.mention_finding_text())
        self.assert_refusal_code(
            refusals, "REVIEW_GUARD_HEADING_AMBIGUOUS:## Findings")
        self.assert_refusal_code(
            refusals, "REVIEW_GUARD_FINDING_MALFORMED:* M1")

    def test_historical_pass_cannot_hide_real_fail(self):
        self.assertEqual([], self.legacy_acceptance(
            dict(self.evidence,
                 review_text=self.historical_pass_hides_fail_text()),
            self.decision))
        self.assert_refusal_code(
            self.guard_refusals(self.historical_pass_hides_fail_text()),
            "REVIEW_GUARD_HEADING_AMBIGUOUS:## Contract compliance")

    def test_historical_empty_findings_cannot_hide_uncorrected_m1(self):
        text = self.historical_findings_hide_m1_text()
        refusals = self.guard_refusals(text)
        self.assert_refusal_code(
            refusals, "REVIEW_GUARD_HEADING_AMBIGUOUS:## Findings")
        self.assertTrue(
            all("REVIEW_GUARD_FINDING_MALFORMED" not in refusal
                for refusal in refusals), refusals)
        self.assert_refusal_code(
            self.guard_refusals(self.uncorrected_finding_text()),
            "CORRECTION_DISPOSITION_MISSING:M1")


if __name__ == "__main__":
    unittest.main()

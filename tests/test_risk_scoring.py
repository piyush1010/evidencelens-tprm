import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_models import VendorProfile  # noqa: E402
from risk_scoring import score_inherent_risk, summarize_residual_risk, tier_for_score  # noqa: E402


def profile(**overrides) -> VendorProfile:
    base = dict(vendor_name="Test Vendor", service_description="Test", business_owner="Owner")
    base.update(overrides)
    return VendorProfile(**base)


class InherentRiskTests(unittest.TestCase):
    def test_minimal_vendor_is_low_with_zero_score(self):
        result = score_inherent_risk(profile())
        self.assertEqual(result.score, 0)
        self.assertEqual(result.tier, "Low")
        self.assertTrue(all(f.points == 0 for f in result.factors))

    def test_tier_boundaries(self):
        self.assertEqual(tier_for_score(19), "Low")
        self.assertEqual(tier_for_score(20), "Medium")
        self.assertEqual(tier_for_score(44), "Medium")
        self.assertEqual(tier_for_score(45), "High")
        self.assertEqual(tier_for_score(69), "High")
        self.assertEqual(tier_for_score(70), "Critical")

    def test_maximum_profile_is_critical_and_score_is_sum_of_factors(self):
        result = score_inherent_risk(profile(
            personal_data=True, financial_or_health_data=True,
            record_volume="Over 100,000 records", production_access=True, privileged_access=True,
            business_criticality="High", operational_dependency="High", uses_subprocessors=True,
            regulatory_exposure=["GDPR", "PCI DSS", "SOX"], replaceability="Hard",
        ))
        self.assertEqual(result.score, sum(f.points for f in result.factors))
        self.assertEqual(result.score, 106)
        self.assertEqual(result.tier, "Critical")

    def test_regulatory_points_are_capped(self):
        two = score_inherent_risk(profile(regulatory_exposure=["GDPR", "HIPAA"]))
        four = score_inherent_risk(profile(regulatory_exposure=["GDPR", "HIPAA", "SOX", "GLBA"]))
        self.assertEqual(two.score, four.score)

    def test_privileged_access_to_sensitive_data_floors_at_high(self):
        result = score_inherent_risk(profile(privileged_access=True, financial_or_health_data=True))
        self.assertEqual(result.score, 30)  # Medium on points alone
        self.assertEqual(result.tier, "High")
        self.assertIsNotNone(result.floor_applied)

    def test_every_factor_is_reported(self):
        names = [f.factor for f in score_inherent_risk(profile()).factors]
        self.assertEqual(len(names), 10)
        self.assertIn("Privileged access", names)


class ValidationTests(unittest.TestCase):
    def test_required_fields(self):
        errors = VendorProfile(vendor_name=" ", service_description="", business_owner="").validate()
        self.assertEqual(len(errors), 3)

    def test_data_types_must_match_flags(self):
        errors = profile(data_types=["Health data"]).validate()
        self.assertTrue(any("financial or health" in e for e in errors))
        self.assertTrue(any("personal data" in e for e in errors))

    def test_valid_profile_has_no_errors(self):
        self.assertEqual(profile(data_types=["Source code"]).validate(), [])


def row(answer, status="Auto-ready", decision="Pending"):
    return {"answer": answer, "review_status": status, "reviewer_decision": decision}


class ResidualRiskTests(unittest.TestCase):
    def test_no_findings_returns_none(self):
        self.assertIsNone(summarize_residual_risk("High", []))

    def test_all_supported_lowers_one_tier_and_approves(self):
        result = summarize_residual_risk("High", [row("Yes")] * 4)
        self.assertEqual(result.residual_tier, "Medium")
        self.assertEqual(result.recommendation, "Approve")
        self.assertFalse(result.provisional)

    def test_low_never_goes_below_low(self):
        self.assertEqual(summarize_residual_risk("Low", [row("Yes")]).residual_tier, "Low")

    def test_gaps_on_medium_vendor_approve_with_conditions(self):
        result = summarize_residual_risk("Medium", [row("Yes"), row("Insufficient evidence", "Needs review", "Approve")])
        self.assertEqual(result.residual_tier, "Medium")
        self.assertEqual(result.recommendation, "Approve with conditions")

    def test_gaps_on_high_vendor_require_remediation(self):
        result = summarize_residual_risk("High", [row("Insufficient evidence", "Needs review", "Approve")])
        self.assertEqual(result.recommendation, "Remediation required")

    def test_contradicted_control_on_high_vendor_escalates(self):
        self.assertEqual(summarize_residual_risk("High", [row("No")]).recommendation,
                         "Escalate for risk acceptance")

    def test_two_contradictions_on_critical_vendor_reject(self):
        self.assertEqual(summarize_residual_risk("Critical", [row("No"), row("No")]).recommendation, "Reject")

    def test_pending_review_marks_result_provisional(self):
        result = summarize_residual_risk("Low", [row("Insufficient evidence", "Needs review")])
        self.assertTrue(result.provisional)
        self.assertEqual(result.counts["awaiting_review"], 1)

    def test_reviewer_rejection_of_no_is_treated_as_gap_not_failure(self):
        result = summarize_residual_risk("Medium", [row("No", "Needs review", "Reject")])
        self.assertEqual(result.counts["contradicted"], 0)
        self.assertEqual(result.recommendation, "Approve with conditions")


if __name__ == "__main__":
    unittest.main()

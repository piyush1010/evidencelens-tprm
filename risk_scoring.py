"""Deterministic, explainable vendor risk scoring.

Inherent risk is scored from the intake profile only, before any controls are considered.
Residual risk combines that tier with the reviewed assessment findings. Both produce
recommendations for a human risk owner; neither is a final decision.
"""

from typing import Iterable, List, Optional

from risk_models import TIERS, InherentRisk, ResidualRisk, RiskFactor, VendorProfile

LEVEL_POINTS = {"Low": 0, "Medium": 5, "High": 15}
DEPENDENCY_POINTS = {"Low": 0, "Medium": 3, "High": 8}
VOLUME_POINTS = {"Under 1,000 records": 0, "1,000–100,000 records": 5, "Over 100,000 records": 10}
REPLACEABILITY_POINTS = {"Easy": 0, "Moderate": 3, "Hard": 8}
REGULATION_POINTS_EACH = 5
REGULATION_POINTS_CAP = 10

# Upper bounds (inclusive) of each tier's score band; anything above the last is Critical.
TIER_BANDS = [("Low", 19), ("Medium", 44), ("High", 69)]


def tier_for_score(score: int) -> str:
    for tier, upper in TIER_BANDS:
        if score <= upper:
            return tier
    return "Critical"


def score_inherent_risk(profile: VendorProfile) -> InherentRisk:
    regs = profile.regulatory_exposure
    factors = [
        RiskFactor("Personal data", "Yes" if profile.personal_data else "No",
                   10 if profile.personal_data else 0),
        RiskFactor("Financial or health data", "Yes" if profile.financial_or_health_data else "No",
                   15 if profile.financial_or_health_data else 0),
        RiskFactor("Record volume", profile.record_volume, VOLUME_POINTS[profile.record_volume]),
        RiskFactor("Production-system access", "Yes" if profile.production_access else "No",
                   10 if profile.production_access else 0),
        RiskFactor("Privileged access", "Yes" if profile.privileged_access else "No",
                   15 if profile.privileged_access else 0),
        RiskFactor("Business criticality", profile.business_criticality,
                   LEVEL_POINTS[profile.business_criticality]),
        RiskFactor("Operational dependency", profile.operational_dependency,
                   DEPENDENCY_POINTS[profile.operational_dependency]),
        RiskFactor("Uses subprocessors", "Yes" if profile.uses_subprocessors else "No",
                   5 if profile.uses_subprocessors else 0),
        RiskFactor("Regulatory exposure", ", ".join(regs) if regs else "None",
                   min(len(regs) * REGULATION_POINTS_EACH, REGULATION_POINTS_CAP)),
        RiskFactor("Ease of replacement", profile.replaceability,
                   REPLACEABILITY_POINTS[profile.replaceability]),
    ]
    score = sum(f.points for f in factors)
    tier = tier_for_score(score)

    floor = None
    if profile.privileged_access and profile.financial_or_health_data and TIERS.index(tier) < TIERS.index("High"):
        tier = "High"
        floor = "Privileged access to financial or health data sets a minimum tier of High."
    return InherentRisk(score=score, tier=tier, factors=factors, floor_applied=floor)


def summarize_residual_risk(inherent_tier: str, findings: Iterable[dict]) -> Optional[ResidualRisk]:
    """Recommend a residual tier and next step from assessment rows.

    Each finding needs `answer`, and may have `review_status` and `reviewer_decision`.
    Returns None when there are no findings yet.
    """
    rows: List[dict] = list(findings)
    if not rows:
        return None

    failed = [r for r in rows if r["answer"] == "No" and r.get("reviewer_decision") != "Reject"]
    gaps = [r for r in rows if r["answer"] == "Insufficient evidence"
            or r.get("reviewer_decision") in ("Reject", "Request evidence")]
    pending = [r for r in rows if r.get("review_status") == "Needs review"
               and r.get("reviewer_decision", "Pending") == "Pending"]
    inherent_index = TIERS.index(inherent_tier)
    high_inherent = inherent_index >= TIERS.index("High")
    drivers = [f"Inherent tier is {inherent_tier}."]

    if not failed and not gaps:
        residual_index = max(inherent_index - 1, 0)
        recommendation = "Approve"
        drivers.append("All assessed controls are supported by cited evidence, lowering residual risk one tier.")
    elif not failed:
        residual_index = inherent_index
        recommendation = "Remediation required" if high_inherent else "Approve with conditions"
        drivers.append(f"{len(gaps)} control(s) lack sufficient evidence; residual risk stays at the inherent tier.")
    else:
        residual_index = inherent_index
        if inherent_tier == "Critical" and len(failed) >= 2:
            recommendation = "Reject"
        elif high_inherent:
            recommendation = "Escalate for risk acceptance"
        else:
            recommendation = "Remediation required"
        drivers.append(f"{len(failed)} control(s) are contradicted by the vendor's evidence.")
        if gaps:
            drivers.append(f"{len(gaps)} further control(s) lack sufficient evidence.")

    if pending:
        drivers.append(f"{len(pending)} finding(s) still await human review, so this is provisional.")

    return ResidualRisk(
        inherent_tier=inherent_tier,
        residual_tier=TIERS[residual_index],
        recommendation=recommendation,
        provisional=bool(pending),
        drivers=drivers,
        counts={"assessed": len(rows), "contradicted": len(failed),
                "insufficient_or_rejected": len(gaps), "awaiting_review": len(pending)},
    )

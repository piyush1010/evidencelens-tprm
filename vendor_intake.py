"""Streamlit UI for vendor intake, inherent risk and the residual-risk decision."""

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import streamlit as st

from risk_models import (
    DATA_TYPES, RECOMMENDATIONS, REGULATIONS, REPLACEABILITY, SENSITIVITY_LEVELS, TIERS,
    VOLUME_BANDS, VendorProfile,
)
from risk_scoring import score_inherent_risk, summarize_residual_risk

# Fictional vendor used by the one-click demo.
SAMPLE_VENDOR = VendorProfile(
    vendor_name="Northwind Payroll Cloud (synthetic)",
    service_description="Hosted payroll processing for all employees, including salary payments.",
    business_owner="Head of People Operations",
    data_types=["Employee data", "Bank account data"],
    personal_data=True,
    financial_or_health_data=True,
    record_volume="1,000–100,000 records",
    production_access=False,
    privileged_access=False,
    business_criticality="High",
    operational_dependency="Medium",
    uses_subprocessors=True,
    regulatory_exposure=["India DPDP Act", "GDPR"],
    replaceability="Moderate",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_vendor(profile: VendorProfile) -> None:
    inherent = score_inherent_risk(profile)
    st.session_state.vendor = profile.to_dict()
    st.session_state.inherent = inherent.to_dict()
    st.session_state.risk_decisions = []  # a decision applies to one vendor profile only
    st.session_state.audit.append({
        "timestamp_utc": _now(), "event": "vendor_profile_saved",
        "vendor_name": profile.vendor_name, "inherent_score": inherent.score,
        "inherent_tier": inherent.tier,
    })


def render_intake_form() -> None:
    current = VendorProfile(**st.session_state.vendor) if st.session_state.get("vendor") else SAMPLE_VENDOR
    with st.form("vendor_intake"):
        st.markdown("**1 · Vendor intake**")
        c1, c2 = st.columns(2)
        name = c1.text_input("Vendor name", current.vendor_name)
        owner = c2.text_input("Business owner", current.business_owner)
        description = st.text_area("Service description", current.service_description, height=68)
        data_types = st.multiselect("Data types processed", DATA_TYPES, current.data_types)
        c3, c4, c5 = st.columns(3)
        personal = c3.checkbox("Personal data", current.personal_data)
        sensitive = c4.checkbox("Financial or health data", current.financial_or_health_data)
        subprocessors = c5.checkbox("Uses subprocessors", current.uses_subprocessors)
        c6, c7 = st.columns(2)
        production = c6.checkbox("Access to production systems", current.production_access)
        privileged = c7.checkbox("Privileged / admin access", current.privileged_access)
        c8, c9 = st.columns(2)
        volume = c8.selectbox("Record volume", VOLUME_BANDS, VOLUME_BANDS.index(current.record_volume))
        replace = c9.selectbox("Ease of replacing the vendor", REPLACEABILITY,
                               REPLACEABILITY.index(current.replaceability))
        c10, c11 = st.columns(2)
        criticality = c10.selectbox("Business criticality", SENSITIVITY_LEVELS,
                                    SENSITIVITY_LEVELS.index(current.business_criticality))
        dependency = c11.selectbox("Operational dependency", SENSITIVITY_LEVELS,
                                   SENSITIVITY_LEVELS.index(current.operational_dependency))
        regs = st.multiselect("Regulatory exposure", REGULATIONS, current.regulatory_exposure)
        submitted = st.form_submit_button("Save profile and score inherent risk", type="primary")

    if submitted:
        profile = VendorProfile(
            vendor_name=name, service_description=description, business_owner=owner,
            data_types=data_types, personal_data=personal, financial_or_health_data=sensitive,
            record_volume=volume, production_access=production, privileged_access=privileged,
            business_criticality=criticality, operational_dependency=dependency,
            uses_subprocessors=subprocessors, regulatory_exposure=regs, replaceability=replace,
        )
        errors = profile.validate()
        if errors:
            for error in errors:
                st.error(error)
        else:
            save_vendor(profile)
            st.success("Vendor profile saved.")


def render_inherent_risk() -> None:
    inherent = st.session_state.get("inherent")
    if not inherent:
        st.info("Save the vendor profile to calculate inherent risk.")
        return
    st.markdown("**2 · Inherent risk** — before considering any vendor controls")
    m1, m2 = st.columns(2)
    m1.metric("Inherent tier", inherent["tier"])
    m2.metric("Score", f"{inherent['score']} / 106")
    if inherent.get("floor_applied"):
        st.warning(inherent["floor_applied"])
    factors = pd.DataFrame(inherent["factors"]).rename(
        columns={"factor": "Factor", "response": "Response", "points": "Points"})
    factors = factors.sort_values("Points", ascending=False)
    st.dataframe(factors, use_container_width=True, hide_index=True)
    st.caption("Bands: Low 0–19 · Medium 20–44 · High 45–69 · Critical 70+. Fixed, rule-based scoring; no AI involved.")


def current_residual() -> Optional[dict]:
    inherent = st.session_state.get("inherent")
    if not inherent or not st.session_state.rows:
        return None
    result = summarize_residual_risk(inherent["tier"], st.session_state.rows)
    return result.to_dict() if result else None


def render_residual_and_decision() -> None:
    st.markdown("**3 · Residual risk and decision**")
    residual = current_residual()
    if residual is None:
        st.info("Save a vendor profile and run an assessment to see the residual-risk recommendation.")
        return

    r1, r2, r3 = st.columns(3)
    r1.metric("Inherent tier", residual["inherent_tier"])
    r2.metric("Recommended residual tier", residual["residual_tier"])
    r3.metric("Recommendation", residual["recommendation"])
    for driver in residual["drivers"]:
        st.markdown(f"- {driver}")
    if residual["provisional"]:
        st.warning("Provisional: finish the review queue before recording a final decision.")
    st.caption("This is a workflow recommendation for a human risk owner, not a compliance determination.")

    with st.form("risk_decision"):
        d1, d2 = st.columns(2)
        final_tier = d1.selectbox("Final residual tier", TIERS, TIERS.index(residual["residual_tier"]))
        final_rec = d2.selectbox("Final decision", RECOMMENDATIONS,
                                 RECOMMENDATIONS.index(residual["recommendation"]))
        reviewer = st.text_input("Risk owner / reviewer")
        reason = st.text_area("Reason (required when overriding the recommendation)", height=68)
        record = st.form_submit_button("Record decision")

    if record:
        overridden = final_tier != residual["residual_tier"] or final_rec != residual["recommendation"]
        if not reviewer.strip():
            st.error("Enter the reviewer's name.")
        elif overridden and not reason.strip():
            st.error("Give a reason for overriding the recommendation.")
        else:
            decision = {
                "timestamp_utc": _now(),
                "event": "risk_override" if overridden else "risk_approved",
                "vendor_name": st.session_state.vendor["vendor_name"],
                "original_residual_tier": residual["residual_tier"],
                "original_recommendation": residual["recommendation"],
                "final_residual_tier": final_tier,
                "final_decision": final_rec,
                "reviewer": reviewer.strip(),
                "reason": reason.strip(),
                "provisional_at_decision": residual["provisional"],
            }
            st.session_state.risk_decisions.append(decision)
            st.session_state.audit.append(decision)
            st.success("Decision recorded in the audit trail.")

    if st.session_state.risk_decisions:
        st.dataframe(pd.DataFrame(st.session_state.risk_decisions)[[
            "timestamp_utc", "reviewer", "original_recommendation", "final_decision",
            "final_residual_tier", "reason"]], use_container_width=True, hide_index=True)

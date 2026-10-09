import io
import json
import os
from datetime import datetime, timezone
from typing import Literal

import pandas as pd
import streamlit as st
from pydantic import BaseModel, Field
from pypdf import PdfReader

from assessment import QUESTIONS, SAMPLE_TEXT, demo_assess
from gemini_evaluation import run_gemini_evaluation


class Assessment(BaseModel):
    question_id: str
    answer: Literal["Yes", "No", "Insufficient evidence"]
    confidence: int = Field(ge=0, le=100)
    evidence_quote: str
    rationale: str
    gap_or_follow_up: str


class AssessmentBatch(BaseModel):
    assessments: list[Assessment]


def extract_text(uploaded) -> str:
    if uploaded is None:
        return SAMPLE_TEXT
    if uploaded.type == "application/pdf":
        reader = PdfReader(io.BytesIO(uploaded.getvalue()))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded.getvalue().decode("utf-8", errors="replace")


def gemini_assess(text: str, api_key: str, model: str) -> list[dict]:
    from google import genai

    client = genai.Client(api_key=api_key)
    prompt = f"""You are a cautious third-party risk analyst. Assess every question against
the vendor evidence. Never infer a control that is not explicitly supported. Evidence quotes
must be short, exact excerpts from the supplied text. Use Insufficient evidence when the text
is ambiguous, incomplete, or lacks a required frequency/deadline. Confidence measures the
strength of the cited evidence, not general plausibility.

QUESTIONS AND ILLUSTRATIVE FRAMEWORK REFERENCES:
{json.dumps([{'id': q['id'], 'control_id': q['control_id'],
              'iso_27001_2022_annex_a_controls': q['iso_27001_2022_annex_a_controls'],
              'nist_csf_2_0_subcategories': q['nist_csf_2_0_subcategories'],
              'question': q['question']} for q in QUESTIONS], indent=2)}

VENDOR EVIDENCE:
{text[:100000]}
"""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": AssessmentBatch},
    )
    parsed = AssessmentBatch.model_validate_json(response.text)
    question_map = {q["id"]: q for q in QUESTIONS}
    return [
        {**item.model_dump(),
         "control_id": question_map[item.question_id]["control_id"],
         "iso_controls": " & ".join(question_map[item.question_id]["iso_27001_2022_annex_a_controls"]),
         "nist_csf_subcategories": " & ".join(question_map[item.question_id]["nist_csf_2_0_subcategories"]),
         "domain": question_map[item.question_id]["domain"],
         "question": question_map[item.question_id]["question"]}
        for item in parsed.assessments if item.question_id in question_map
    ]


st.set_page_config(page_title="EvidenceLens", page_icon="🛡️", layout="wide")
st.title("EvidenceLens")
st.caption("AI-assisted third-party security questionnaire review • Evidence first, human approved")

with st.sidebar:
    st.header("Assessment setup")
    mode = st.radio("Analysis mode", ["Transparent demo", "Gemini structured output"])
    api_key = st.text_input("Gemini API key", type="password", value=os.getenv("GEMINI_API_KEY", ""),
                            disabled=mode == "Transparent demo")
    model = st.selectbox(
        "Model",
        ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash"],
        disabled=mode == "Transparent demo",
        help="Use Flash-Lite for a lower-cost evaluation; compare with 3.8 Flash when capacity is available.",
    )
    threshold = st.slider("Human-review threshold", 50, 95, 75)
    upload = st.file_uploader("Vendor evidence", type=["pdf", "txt", "md"])
    st.caption("No file? The app uses a synthetic vendor policy so the demo always works.")
    run = st.button("Run assessment", type="primary", width="stretch")

if "rows" not in st.session_state:
    st.session_state.rows = []
if "audit" not in st.session_state:
    st.session_state.audit = []

if run:
    document = extract_text(upload)
    if not document.strip():
        st.error("No readable text was found in the document.")
    elif mode.startswith("Gemini") and not api_key:
        st.error("Add a Gemini API key or use Transparent demo mode.")
    else:
        with st.spinner("Mapping evidence to controls…"):
            try:
                rows = gemini_assess(document, api_key, model) if mode.startswith("Gemini") else demo_assess(document)
                for row in rows:
                    row["review_status"] = "Needs review" if row["confidence"] < threshold or row["answer"] == "Insufficient evidence" else "Auto-ready"
                    row["reviewer_decision"] = "Pending"
                st.session_state.rows = rows
                st.session_state.audit.append({
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "event": "assessment_completed",
                    "mode": mode, "questions": len(rows), "source": upload.name if upload else "synthetic_demo_policy",
                })
            except Exception as exc:
                error_text = str(exc)
                if "503" in error_text or "UNAVAILABLE" in error_text:
                    st.error(
                        "Gemini is temporarily at capacity. Retry later or select a different "
                        "approved model. Your document and settings are unchanged."
                    )
                elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                    st.error(
                        "The Gemini request or quota limit was reached. Wait before retrying "
                        "and check the Usage page in Google AI Studio."
                    )
                else:
                    st.error(f"Assessment failed: {error_text}")

if not st.session_state.rows:
    st.info("Upload a policy or run the included synthetic example to begin.")
    st.subheader("What this MVP demonstrates")
    st.markdown("- Evidence-grounded questionnaire completion\n- Structured AI output and explicit uncertainty\n- Confidence-based exception routing\n- Human approval and an exportable audit trail")
    with st.expander("Framework scope and content boundaries"):
        st.markdown(
            "- Questions are original demonstration content, not the proprietary Shared Assessments SIG questionnaire.\n"
            "- Shared Assessments SIG is represented as framework familiarity only; no SIG questions or IDs are bundled.\n"
            "- ISO 27001:2022 and NIST CSF 2.0 references are illustrative and require validation before production use."
        )
else:
    df = pd.DataFrame(st.session_state.rows)
    needs_review = ((df.review_status == "Needs review")).sum()
    supported = (df.answer == "Yes").sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Questions assessed", len(df))
    c2.metric("Supported", int(supported))
    c3.metric("Needs human review", int(needs_review))
    c4.metric("Average confidence", f"{df.confidence.mean():.0f}%")

    overview, review, evaluation, audit = st.tabs(
        ["Assessment", "Review queue", "Evaluation", "Audit & export"]
    )
    with overview:
        st.dataframe(df[["control_id", "iso_controls", "nist_csf_subcategories", "domain", "answer", "confidence", "review_status", "gap_or_follow_up"]],
                     width="stretch", hide_index=True)
        for row in st.session_state.rows:
            with st.expander(f"{row['question_id']} · {row['question']} — {row['answer']} ({row['confidence']}%)"):
                st.caption(
                    f"Demo control: {row['control_id']} · Illustrative ISO 27001:2022 Annex A: "
                    f"{row['iso_controls']} · Illustrative NIST CSF 2.0: {row['nist_csf_subcategories']}"
                )
                st.markdown(f"**Evidence:** “{row['evidence_quote']}”")
                st.write(row["rationale"])
                if row["gap_or_follow_up"]:
                    st.warning(row["gap_or_follow_up"])

    with review:
        review_rows = [r for r in st.session_state.rows if r["review_status"] == "Needs review"]
        if not review_rows:
            st.success("No exceptions require review at this threshold.")
        for row in review_rows:
            st.markdown(f"**{row['question_id']} — {row['question']}**")
            st.caption(
                f"Demo control: {row['control_id']} · Illustrative ISO 27001:2022 Annex A: "
                f"{row['iso_controls']} · Illustrative NIST CSF 2.0: {row['nist_csf_subcategories']}"
            )
            st.caption(f"AI answer: {row['answer']} · Confidence: {row['confidence']}%")
            st.write(f"Evidence: “{row['evidence_quote']}”")
            decision = st.selectbox("Reviewer decision", ["Pending", "Approve", "Reject", "Request evidence"],
                                    key=f"decision-{row['question_id']}")
            if decision != row["reviewer_decision"]:
                row["reviewer_decision"] = decision
                st.session_state.audit.append({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "event": "review_decision", "question_id": row["question_id"], "decision": decision})
            st.divider()

    with evaluation:
        st.subheader("Labelled 12-case synthetic evaluation")
        st.write(
            "Compare the selected Gemini model with human-labelled synthetic positive, negative, "
            "and insufficient-evidence cases. This controlled test is not a production-accuracy claim."
        )
        if mode != "Gemini structured output":
            st.info("Select Gemini structured output in the sidebar to run this evaluation.")
        elif not api_key:
            st.info("Enter your Gemini API key in the sidebar. The key is not written to the results file.")
        elif st.button("Run Gemini evaluation", type="primary"):
            with st.spinner("Evaluating 12 labelled synthetic cases in one structured request…"):
                try:
                    st.session_state.gemini_evaluation = run_gemini_evaluation(api_key, model)
                except Exception as exc:
                    error_text = str(exc)
                    if "503" in error_text or "UNAVAILABLE" in error_text:
                        st.error("Gemini is temporarily at capacity. Retry later or choose another model.")
                    elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                        st.error("The request or quota limit was reached. Wait and check AI Studio Usage.")
                    else:
                        st.error(f"Evaluation failed: {error_text}")

        if "gemini_evaluation" in st.session_state:
            evaluation_output = st.session_state.gemini_evaluation
            summary = evaluation_output["summary"]
            e1, e2, e3, e4 = st.columns(4)
            e1.metric("Answer agreement", f"{summary['answer_agreement_percent']}%")
            e2.metric("Citation existence", f"{summary['citation_existence_percent']}%")
            e3.metric("Review-routing recall", f"{summary['review_routing_recall_percent']}%")
            e4.metric("Unsupported definitive", f"{summary['unsupported_definitive_percent']}%")
            evaluation_df = pd.DataFrame(evaluation_output["cases"])
            st.dataframe(
                evaluation_df[[
                    "case_id", "expected_answer", "actual_answer", "answer_agrees",
                    "citation_exists", "evidence_quote"
                ]],
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "Download Gemini evaluation JSON",
                json.dumps(evaluation_output, indent=2),
                "gemini_evaluation_results.json",
                "application/json",
            )

    with audit:
        export_df = pd.DataFrame(st.session_state.rows)
        st.download_button("Download assessment CSV", export_df.to_csv(index=False),
                           "vendor_assessment.csv", "text/csv")
        st.download_button("Download audit log JSON", json.dumps(st.session_state.audit, indent=2),
                           "audit_log.json", "application/json")
        st.json(st.session_state.audit)

st.divider()
st.caption(
    "Questions are original demo content and do not reproduce the proprietary Shared Assessments SIG questionnaire. "
    "ISO 27001:2022 and NIST CSF 2.0 references are illustrative and require validation before production use. "
    "AI output requires human validation."
)

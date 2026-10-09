import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
import streamlit as st
from pydantic import BaseModel, Field
from pypdf import PdfReader

from assessment import (
    QUESTIONS,
    SAMPLE_POLICIES,
    SAMPLE_TEXT,
    demo_assess,
    enrich_framework_metadata,
)
from gemini_evaluation import run_gemini_evaluation


ROOT = Path(__file__).parent
SAVED_GEMINI_EVALUATION = json.loads(
    (ROOT / "gemini_evaluation_results.json").read_text()
)
SAVED_BASELINE_EVALUATION = json.loads(
    (ROOT / "evaluation_results.json").read_text()
)


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


def prepare_rows(rows: list[dict], threshold: int) -> list[dict]:
    """Add current metadata and workflow fields to assessment results."""
    rows = enrich_framework_metadata(rows)
    for row in rows:
        row["review_status"] = (
            "Needs review"
            if row["confidence"] < threshold
            or row["answer"] == "Insufficient evidence"
            else "Auto-ready"
        )
        row["reviewer_decision"] = "Pending"
    return rows


def store_assessment(rows: list[dict], mode: str, source: str) -> None:
    """Persist one assessment and its completion event for this browser session."""
    st.session_state.rows = rows
    st.session_state.last_assessment_mode = mode
    st.session_state.audit.append(
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": "assessment_completed",
            "mode": mode,
            "questions": len(rows),
            "source": source,
        }
    )


def render_sample_picker(key_prefix: str) -> tuple[bool, dict]:
    """Render the public sample library and return the selected run action."""
    sample_ids = list(SAMPLE_POLICIES)
    selected_id = st.selectbox(
        "Choose a sample policy",
        sample_ids,
        format_func=lambda sample_id: SAMPLE_POLICIES[sample_id]["title"],
        key=f"{key_prefix}-sample-policy",
    )
    selected = SAMPLE_POLICIES[selected_id]
    st.caption(selected["description"])
    run_column, download_column = st.columns(2)
    run_sample = run_column.button(
        "Run selected sample",
        type="primary",
        width="stretch",
        key=f"{key_prefix}-run-sample",
    )
    download_column.download_button(
        "Download sample policy",
        selected["text"],
        file_name=selected["file"],
        mime="text/plain",
        width="stretch",
        key=f"{key_prefix}-download-sample",
    )
    return run_sample, selected


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
if "last_assessment_mode" not in st.session_state:
    st.session_state.last_assessment_mode = None

# A Streamlit session can survive a deployment. Enrich cached rows so results
# created by an older app version remain compatible with the current schema.
st.session_state.rows = enrich_framework_metadata(st.session_state.rows)

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
                rows = prepare_rows(rows, threshold)
                store_assessment(
                    rows,
                    mode,
                    upload.name if upload else "synthetic_demo_policy",
                )
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
    st.subheader("Try a sample vendor policy")
    run_sample, selected_sample = render_sample_picker("landing")
    if run_sample:
        rows = prepare_rows(demo_assess(selected_sample["text"]), threshold)
        store_assessment(
            rows,
            "Transparent demo",
            f"sample:{selected_sample['id']}",
        )
        st.rerun()
    st.caption(
        "The included no-key demo uses a transparent keyword baseline—not Gemini. "
        "Gemini analysis is optional."
    )
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
    assessment_mode = st.session_state.last_assessment_mode or "Transparent demo"
    if assessment_mode == "Transparent demo":
        st.info(
            "Analysis engine: transparent keyword baseline (not Gemini). It surfaces the "
            "closest matching text and routes incomplete evidence to human review."
        )
    else:
        st.info(f"Analysis engine: {model} with Gemini structured output.")
    with st.expander("Try another sample policy"):
        run_sample, selected_sample = render_sample_picker("results")
        if run_sample:
            rows = prepare_rows(demo_assess(selected_sample["text"]), threshold)
            store_assessment(
                rows,
                "Transparent demo",
                f"sample:{selected_sample['id']}",
            )
            st.rerun()
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
                quote_label = (
                    "Closest text found (not sufficient)"
                    if row["answer"] == "Insufficient evidence"
                    else "Supporting evidence"
                )
                st.markdown(f"**{quote_label}:** “{row['evidence_quote']}”")
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
            quote_label = (
                "Closest text found (not sufficient)"
                if row["answer"] == "Insufficient evidence"
                else "Supporting evidence"
            )
            st.markdown(f"**{quote_label}:** “{row['evidence_quote']}”")
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
            "The saved benchmark below compares Gemini with the transparent keyword baseline on "
            "human-labelled synthetic positive, negative, and insufficient-evidence cases. This "
            "controlled test is not a production-accuracy claim."
        )
        evaluation_output = st.session_state.get(
            "gemini_evaluation", SAVED_GEMINI_EVALUATION
        )
        summary = evaluation_output["summary"]
        baseline_summary = SAVED_BASELINE_EVALUATION["summary"]
        baseline_agreements = sum(
            case["answer_agrees"] for case in SAVED_BASELINE_EVALUATION["cases"]
        )
        gemini_agreements = sum(
            case["answer_agrees"] for case in evaluation_output["cases"]
        )

        st.caption(
            f"Saved result: {summary['engine']} • {summary['cases']} synthetic cases • "
            "case-level outputs included below"
        )
        e1, e2, e3, e4 = st.columns(4)
        e1.metric(
            "Answer agreement",
            f"{gemini_agreements}/{summary['cases']}",
            f"+{gemini_agreements - baseline_agreements} vs baseline "
            f"({baseline_agreements}/{baseline_summary['cases']})",
        )
        e2.metric("Citation existence", f"{summary['citation_existence_percent']}%")
        e3.metric("Review-routing recall", f"{summary['review_routing_recall_percent']}%")
        e4.metric("Unsupported definitive", f"{summary['unsupported_definitive_percent']}%")

        comparison_df = pd.DataFrame(
            [
                {
                    "engine": "Transparent keyword baseline",
                    "answer_agreement": f"{baseline_summary['answer_agreement_percent']}% ({baseline_agreements}/12)",
                    "review_routing_recall": f"{baseline_summary['review_routing_recall_percent']}%",
                    "unsupported_definitive": f"{baseline_summary['unsupported_definitive_percent']}%",
                },
                {
                    "engine": summary["engine"],
                    "answer_agreement": f"{summary['answer_agreement_percent']}% ({gemini_agreements}/12)",
                    "review_routing_recall": f"{summary['review_routing_recall_percent']}%",
                    "unsupported_definitive": f"{summary['unsupported_definitive_percent']}%",
                },
            ]
        )
        st.dataframe(comparison_df, width="stretch", hide_index=True)

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
            "Download saved evaluation JSON",
            json.dumps(evaluation_output, indent=2),
            "gemini_evaluation_results.json",
            "application/json",
        )

        with st.expander("Rerun the benchmark with Gemini (optional)"):
            if mode != "Gemini structured output":
                st.info("Select Gemini structured output in the sidebar to rerun the benchmark.")
            elif not api_key:
                st.info("Enter your Gemini API key in the sidebar. The key is not written to the results file.")
            elif st.button("Run Gemini evaluation", type="primary"):
                with st.spinner("Evaluating 12 labelled synthetic cases in one structured request…"):
                    try:
                        st.session_state.gemini_evaluation = run_gemini_evaluation(api_key, model)
                        st.rerun()
                    except Exception as exc:
                        error_text = str(exc)
                        if "503" in error_text or "UNAVAILABLE" in error_text:
                            st.error("Gemini is temporarily at capacity. Retry later or choose another model.")
                        elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                            st.error("The request or quota limit was reached. Wait and check AI Studio Usage.")
                        else:
                            st.error(f"Evaluation failed: {error_text}")

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

import io
import json
import os
from datetime import datetime, timezone
from typing import Literal, Optional

import pandas as pd
import streamlit as st
from pydantic import BaseModel, Field
from pypdf import PdfReader

from assessment import QUESTIONS, SAMPLE_TEXT, demo_assess
from gemini_evaluation import run_gemini_evaluation
from vendor_intake import (
    SAMPLE_VENDOR, current_residual, render_inherent_risk, render_intake_form,
    render_residual_and_decision, save_vendor,
)

ROOT = os.path.dirname(os.path.abspath(__file__))


@st.cache_data
def load_recorded_results(filename: str) -> Optional[dict]:
    path = os.path.join(ROOT, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


METRICS = [
    ("answer_agreement_percent", "Answer agreement"),
    ("citation_existence_percent", "Citation exists in source"),
    ("review_routing_recall_percent", "Review-routing recall"),
    ("unsupported_definitive_percent", "Unsupported definitive answers (lower is better)"),
]


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

QUESTIONS AND ILLUSTRATIVE FRAMEWORK MAPPINGS:
{json.dumps([{'id': q['id'], 'control_id': q['control_id'],
              'iso_27001_2022_annex_a_controls': q['iso_27001_2022_annex_a_controls'],
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
    answers = {item.question_id: item.model_dump() for item in parsed.assessments}
    rows = []
    for q in QUESTIONS:  # one row per question, in order, even if the model skipped one
        answer = answers.get(q["id"]) or {
            "question_id": q["id"], "answer": "Insufficient evidence", "confidence": 0,
            "evidence_quote": "", "rationale": "The model returned no answer for this question.",
            "gap_or_follow_up": "Re-run the assessment or answer this question manually.",
        }
        rows.append({**answer, "control_id": q["control_id"],
                     "iso_controls": " & ".join(q["iso_27001_2022_annex_a_controls"]),
                     "domain": q["domain"], "question": q["question"]})
    return rows


def quote_in_source(quote: str, document: str) -> bool:
    normalize = lambda text: " ".join(text.lower().split())
    return bool(quote.strip()) and normalize(quote) in normalize(document)


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
    run = st.button("Run assessment", type="primary", use_container_width=True)

if "rows" not in st.session_state:
    st.session_state.rows = []
if "audit" not in st.session_state:
    st.session_state.audit = []
for key, default in (("vendor", None), ("inherent", None), ("risk_decisions", [])):
    if key not in st.session_state:
        st.session_state[key] = default

def run_assessment(document: str, use_gemini: bool, source: str) -> None:
    if not document.strip():
        st.error("No readable text was found in the document.")
        return
    if use_gemini and not api_key:
        st.error("Add a Gemini API key or use Transparent demo mode.")
        return
    with st.spinner("Mapping evidence to controls…"):
        try:
            rows = gemini_assess(document, api_key, model) if use_gemini else demo_assess(document)
            for row in rows:
                cited = row["answer"] == "Insufficient evidence" or quote_in_source(row["evidence_quote"], document)
                row["citation_verified"] = cited
                if not cited:
                    row["gap_or_follow_up"] = ("Cited quote was not found verbatim in the document; verify it. "
                                               + row["gap_or_follow_up"]).strip()
                needs_review = row["confidence"] < threshold or row["answer"] == "Insufficient evidence" or not cited
                row["review_status"] = "Needs review" if needs_review else "Auto-ready"
                row["reviewer_decision"] = "Pending"
            st.session_state.rows = rows
            for key in [k for k in st.session_state if str(k).startswith("decision-")]:
                del st.session_state[key]  # fresh assessment, fresh review decisions
            st.session_state.risk_decisions = []  # earlier risk decisions were based on the old findings
            st.session_state.audit.append({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(), "event": "assessment_completed",
                "mode": "Gemini structured output" if use_gemini else "Transparent demo",
                "questions": len(rows), "source": source,
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
    hero_text, hero_button = st.columns([3, 1], vertical_alignment="center")
    hero_text.markdown(
        "**See it in one click.** Runs the transparent baseline on a synthetic vendor policy — "
        "no upload or API key needed."
    )
    demo_clicked = hero_button.button("▶ Run demo", type="primary", use_container_width=True)
else:
    demo_clicked = False

if demo_clicked:
    if not st.session_state.vendor:
        save_vendor(SAMPLE_VENDOR)
    run_assessment(SAMPLE_TEXT, use_gemini=False, source="synthetic_demo_policy")
    if st.session_state.rows:
        st.rerun()  # redraw without the one-click banner
elif run:
    run_assessment(extract_text(upload), use_gemini=mode.startswith("Gemini"),
                   source=upload.name if upload else "synthetic_demo_policy")

# Apply review-queue decisions before any tab renders, so the residual-risk summary is current.
for row in st.session_state.rows:
    decision = st.session_state.get(f"decision-{row['question_id']}")
    if decision is not None and decision != row["reviewer_decision"]:
        row["reviewer_decision"] = decision
        st.session_state.audit.append({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": "review_decision", "question_id": row["question_id"], "decision": decision,
            "reviewer": st.session_state.get("reviewer_name", "").strip() or "unnamed"})

has_rows = bool(st.session_state.rows)
if has_rows:
    df = pd.DataFrame(st.session_state.rows)
    needs_review = ((df.review_status == "Needs review")).sum()
    supported = (df.answer == "Yes").sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Questions assessed", len(df))
    c2.metric("Supported", int(supported))
    c3.metric("Needs human review", int(needs_review))
    c4.metric("Average confidence", f"{df.confidence.mean():.0f}%")

vendor_tab, overview, review, evaluation, audit = st.tabs(
    ["Vendor & risk", "Assessment", "Review queue", "Evaluation", "Audit & export"]
)

with vendor_tab:
    render_intake_form()
    st.divider()
    render_inherent_risk()
    st.divider()
    render_residual_and_decision()

with overview:
    if not has_rows:
        st.info("Click **Run demo** above, or upload a policy in the sidebar, to begin.")
        st.subheader("What this MVP demonstrates")
        st.markdown("- Evidence-grounded questionnaire completion\n- Structured AI output and explicit uncertainty\n- Confidence-based exception routing\n- Human approval and an exportable audit trail")
        st.caption("Want the numbers first? Open the **Evaluation** tab for the recorded baseline-vs-Gemini results.")
    else:
        st.dataframe(df[["control_id", "iso_controls", "domain", "answer", "confidence", "review_status", "gap_or_follow_up"]],
                     use_container_width=True, hide_index=True)
        for row in st.session_state.rows:
            with st.expander(f"{row['question_id']} · {row['question']} — {row['answer']} ({row['confidence']}%)"):
                st.caption(f"Demo control: {row['control_id']} · Illustrative ISO 27001:2022 Annex A mapping: {row['iso_controls']}")
                st.markdown(f"**Evidence:** “{row['evidence_quote']}”")
                st.write(row["rationale"])
                if row["gap_or_follow_up"]:
                    st.warning(row["gap_or_follow_up"])

with review:
    if not has_rows:
        st.info("Run an assessment to populate the review queue.")
    else:
        reviewer_name = st.text_input("Your name (recorded with each decision)", key="reviewer_name")
    review_rows = [r for r in st.session_state.rows if r["review_status"] == "Needs review"]
    if has_rows and not review_rows:
        st.success("No exceptions require review at this threshold.")
    for row in review_rows:
        st.markdown(f"**{row['question_id']} — {row['question']}**")
        st.caption(f"Demo control: {row['control_id']} · Illustrative ISO 27001:2022 Annex A mapping: {row['iso_controls']}")
        st.caption(f"AI answer: {row['answer']} · Confidence: {row['confidence']}%")
        st.write(f"Evidence: “{row['evidence_quote']}”")
        decision = st.selectbox("Reviewer decision", ["Pending", "Approve", "Reject", "Request evidence"],
                                key=f"decision-{row['question_id']}")
        st.divider()

with evaluation:
    st.subheader("Labelled 12-case evaluation")
    st.write(
        "Twelve hand-labelled cases — a positive, a negative and an insufficient-evidence case "
        "for each of four controls — designed to catch negation, missing deadlines and scope gaps."
    )
    baseline = load_recorded_results("evaluation_results.json")
    gemini_recorded = load_recorded_results("gemini_evaluation_results.json")

    if baseline and gemini_recorded:
        gemini_engine = gemini_recorded["summary"]["engine"]
        st.markdown(f"**Recorded results** · keyword baseline vs `{gemini_engine}`")
        summary_rows = [
            {
                "Metric": label,
                "Keyword baseline": f"{baseline['summary'][key]}%",
                f"Gemini ({gemini_engine})": f"{gemini_recorded['summary'][key]}%",
            }
            for key, label in METRICS
        ]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        baseline_cases = {c["case_id"]: c for c in baseline["cases"]}
        case_rows = []
        for case in gemini_recorded["cases"]:
            base = baseline_cases.get(case["case_id"], {})
            case_rows.append({
                "Case": case["case_id"],
                "Expected": case["expected_answer"],
                "Baseline": base.get("actual_answer", "—"),
                "Baseline ✓": "✅" if base.get("answer_agrees") else "❌",
                "Gemini": case["actual_answer"],
                "Gemini ✓": "✅" if case["answer_agrees"] else "❌",
            })
        with st.expander("Case-by-case results", expanded=True):
            st.dataframe(pd.DataFrame(case_rows), use_container_width=True, hide_index=True)
        st.caption(
            "A small, controlled engineering test on synthetic evidence — not a general "
            "model-accuracy or production-readiness claim. The keyword baseline mostly fails on "
            "negated statements (\"does not encrypt…\"), which it reads as support."
        )
    else:
        st.warning("Recorded evaluation files were not found in this deployment.")

    with st.expander("Re-run the Gemini evaluation with your own API key"):
        st.write(
            "Sends the same 12 cases to the model selected in the sidebar in one structured "
            "request. Your key stays in this browser session and is not saved."
        )
        live_key = st.text_input("Gemini API key", type="password", key="eval_api_key",
                                 value=api_key or "")
        if st.button("Run Gemini evaluation", disabled=not live_key):
            with st.spinner("Evaluating 12 labelled cases in one structured request…"):
                try:
                    st.session_state.gemini_evaluation = run_gemini_evaluation(live_key, model, save=False)
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
            st.markdown(f"**Your run** · `{summary['engine']}`")
            if summary.get("latency_seconds") is not None:
                st.caption(
                    f"{summary['latency_seconds']} s for {summary['cases']} cases · "
                    f"{summary.get('input_tokens') or '?'} input / {summary.get('output_tokens') or '?'} output tokens"
                )
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
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download Gemini evaluation JSON",
                json.dumps(evaluation_output, indent=2),
                "gemini_evaluation_results.json",
                "application/json",
            )

with audit:
    if not has_rows:
        st.info("Run an assessment to export results and the audit log.")
    else:
        export_df = pd.DataFrame(st.session_state.rows)
        residual = current_residual()
        latest_decision = st.session_state.risk_decisions[-1] if st.session_state.risk_decisions else {}
        if st.session_state.vendor:
            export_df.insert(0, "vendor_name", st.session_state.vendor["vendor_name"])
            export_df["inherent_tier"] = st.session_state.inherent["tier"]
            export_df["inherent_score"] = st.session_state.inherent["score"]
        if residual:
            export_df["recommended_residual_tier"] = residual["residual_tier"]
            export_df["recommendation"] = residual["recommendation"]
        if latest_decision:
            export_df["final_decision"] = latest_decision["final_decision"]
            export_df["final_residual_tier"] = latest_decision["final_residual_tier"]
        st.download_button("Download assessment CSV", export_df.to_csv(index=False),
                           "vendor_assessment.csv", "text/csv")
        st.download_button("Download audit log JSON", json.dumps(st.session_state.audit, indent=2),
                           "audit_log.json", "application/json")
        st.download_button("Download vendor risk summary JSON", json.dumps({
            "vendor": st.session_state.vendor, "inherent_risk": st.session_state.inherent,
            "residual_risk_recommendation": residual, "decisions": st.session_state.risk_decisions,
        }, indent=2), "vendor_risk_summary.json", "application/json")
        st.json(st.session_state.audit)

st.divider()
st.caption("Questions are original demo content. ISO mappings are illustrative and should be validated against an authoritative licensed source. AI output requires human validation.")

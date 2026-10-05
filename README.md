# EvidenceLens — one-day TPRM AI MVP

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://evidencelens-tprm.streamlit.app/)

**Live demo:** [evidencelens-tprm.streamlit.app](https://evidencelens-tprm.streamlit.app/)

## Try it in 30 seconds

1. Open the live demo; no account or API key is required.
2. Keep **Transparent demo** selected.
3. Leave the upload empty to use the included synthetic vendor policy.
4. Click **Run assessment**.
5. Inspect the evidence citations and open the **Review queue** for ambiguous controls.

Gemini mode is optional and requires visitors to supply their own API key for that browser
session. No project-owner key is embedded in the public deployment.

EvidenceLens converts vendor security documentation into a reviewable questionnaire
assessment. It emphasizes evidence traceability and human approval rather than pretending
that an LLM can make final risk decisions autonomously.

For the complete problem statement, product decisions, success metrics, limitations, and
interview preparation, see [PROJECT_BRIEF.md](PROJECT_BRIEF.md).

## What the demo proves

- Upload PDF/TXT/Markdown vendor evidence.
- Map evidence to four original demo controls with illustrative ISO 27001:2022 Annex A references.
- Return a structured answer, exact evidence quote, rationale, confidence and follow-up.
- Route ambiguous or low-confidence answers to a human review queue.
- Capture reviewer decisions in an audit log and export the assessment as CSV.
- Run without an API key using a transparent keyword baseline, or use Gemini structured output.

## Run locally

The project is tested with Python 3.9. Use Python 3.11 when selecting a cloud
deployment runtime unless you have a reason to choose another supported version.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Optionally set `GEMINI_API_KEY`, or paste the key into the sidebar. The default evaluation
model is `gemini-3.5-flash-lite`; the UI also offers `gemini-3.8-flash` and
`gemini-3.7-flash`. Keeping this configurable supports model lifecycle and capacity changes.

## Suggested five-minute demo

1. Explain the problem: analysts repeatedly search policies to answer vendor questionnaires.
2. Run the included synthetic policy in Transparent demo mode.
3. Open a supported answer and show its evidence quote.
4. Open the review queue and highlight the deliberately ambiguous breach-notification and
   subprocessor-reassessment controls.
5. Make a reviewer decision and export the audit log.
6. Explain success metrics: evidence acceptance rate, unsupported-answer rate, analyst time
   per questionnaire, review-queue precision, latency and cost per assessment.

## Honest limitations

- The sample question set is original demo content and is not the proprietary SIG questionnaire.
- The displayed ISO mappings are illustrative and must be validated against an
  authoritative licensed framework source before production use.
- PDF text extraction may not handle scanned documents; production would add OCR.
- The demo baseline is keyword-based, not semantic retrieval.
- No authentication, persistent database, tenant isolation or production security controls.
- LLM answers are decision support and require review; they are not compliance determinations.

## One-day build sequence

1. **Hours 1–2:** finalize problem statement, user flow and sample evidence.
2. **Hours 3–5:** implement document parsing, structured assessment and citations.
3. **Hours 6–7:** add confidence routing, human review and audit export.
4. **Hour 8:** run an evaluation set, record a short demo and publish the repository.

## Evaluation sheet to add before sharing

Create 20–30 manually labelled question/evidence pairs. Report:

- Answer agreement with the human label.
- Citation validity: whether the quoted passage exists and supports the answer.
- Unsupported-answer rate.
- Percentage correctly routed to human review.
- Median latency and estimated cost per questionnaire.

The repository includes an initial 12-case adversarial test set for the transparent
baseline. Run it with:

```bash
python evaluate.py
```

The generated `evaluation_results.json` records both the summary and case-level failures.
Treat this as an engineering smoke test; expand it before making portfolio-quality claims.

After running a normal Gemini assessment in the app, open the **Evaluation** tab and click
**Run Gemini evaluation**. The app evaluates the same 12 cases in one structured request,
displays a baseline comparison, and writes `gemini_evaluation_results.json` without storing
the API key.

### Initial measured comparison

On the included 12-case synthetic test, the keyword baseline reached 58.3% answer agreement
and 62.5% review-routing recall. A recorded `gemini-3.5-flash-lite` run reached 100% on both,
with exact source quotes for every case and no unsupported definitive answers. This is a small,
controlled engineering test—not a general model-accuracy or production-readiness claim. See
`evaluation_results.json` and `gemini_evaluation_results.json` for case-level evidence.

# EvidenceLens Project Brief and Interview Guide

## 1. One-sentence description

EvidenceLens is an AI-assisted vendor security assessment prototype that turns
unstructured policy documents into evidence-backed control assessments and routes
uncertain answers to a human reviewer.

## 2. Beginner glossary

- **Third party:** An outside company that provides software, services, data, or another
  business capability.
- **TPRM:** Third-Party Risk Management—the process of identifying, assessing, treating,
  monitoring, and eventually closing risks created by third parties.
- **Vendor due diligence:** Checks performed before or during a vendor relationship to
  determine whether the vendor meets security, privacy, legal, and operational expectations.
- **Security questionnaire:** A list of control questions a vendor answers, often with
  supporting policies, reports, or certificates.
- **Control:** A safeguard intended to reduce risk, such as multi-factor authentication or
  encryption.
- **Evidence:** A document passage or artifact supporting a control claim.
- **Human in the loop:** A workflow in which AI assists, but a person reviews uncertain or
  consequential outputs before a decision is made.
- **Structured output:** Predictable fields such as answer, confidence, evidence, rationale,
  and follow-up, rather than a free-form chatbot response.
- **Audit trail:** A record of what the system and reviewer did, and when they did it.

## 3. Problem statement

Risk analysts often receive long vendor policies and must manually search them to answer
repetitive security questions. The work is slow and inconsistent, and an answer may be copied
without preserving the source passage that supports it. A generative AI system can accelerate
the first review, but an unsupported or overconfident answer can create compliance and security
risk. The product therefore needs to automate evidence discovery while preserving citations,
uncertainty, reviewer control, and an audit trail.

## 4. Purpose

The purpose is not to replace a risk analyst or certify a vendor. It is to:

1. Reduce the time spent locating relevant evidence.
2. Produce a consistent first-pass assessment.
3. Make every generated answer traceable to vendor evidence.
4. Send ambiguous or unsupported answers to a reviewer.
5. Record decisions for later review and export.

## 5. Target users

- Primary: vendor-risk and information-security analysts.
- Secondary: procurement, privacy, compliance, and vendor-management teams.
- External participant in a larger product: the vendor supplying documents and follow-up evidence.

## 6. Current solution

The current MVP allows a user to:

1. Upload a PDF, TXT, or Markdown vendor document, or use a synthetic example.
2. Choose a transparent keyword baseline or optional Gemini analysis.
3. Assess the evidence against four original demo controls.
4. Receive a structured answer, confidence score, exact evidence quote, rationale, and follow-up.
5. Route insufficient or low-confidence results to a human-review queue.
6. Record reviewer decisions.
7. Export the assessment as CSV and the audit history as JSON.

The questions are original demo content. Displayed ISO mappings are illustrative and are not a
claim of ISO certification or official framework validation.

## 7. Product workflow

```text
Vendor document
      ↓
Text extraction
      ↓
Original control-question schema
      ↓
Assessment engine
  ├── Transparent keyword baseline
  └── Gemini structured output
      ↓
Answer + evidence + confidence + rationale + follow-up
      ↓
Confidence and exception rules
  ├── Supported / auto-ready
  └── Needs human review
      ↓
Reviewer decision
      ↓
CSV assessment + JSON audit trail
```

## 8. How it was built

- **Streamlit:** Builds the browser interface and dashboard using Python.
- **Python:** Implements document processing, assessment logic, review routing, and exports.
- **PyPDF:** Extracts text from text-based PDF documents.
- **JSON question schema:** Keeps questions and framework metadata separate from application code,
  making the assessment configurable.
- **Pydantic:** Defines and validates the structure expected from Gemini.
- **Google GenAI SDK:** Optionally sends evidence and questions to Gemini and requests structured
  JSON output.
- **Session state:** Temporarily retains results and reviewer choices while the app is open.
- **Pandas:** Displays assessment tables and creates CSV exports.

## 9. Important product decisions

### Why require evidence quotes?

An answer without a source is difficult to verify. Quotes let reviewers determine whether the
document actually supports the answer and help detect hallucinations.

### Why use `Insufficient evidence` instead of forcing Yes or No?

A missing statement does not necessarily mean the vendor lacks the control. It means the supplied
evidence does not establish the control. The correct next action is often to request evidence.

### Why include a human-review threshold?

TPRM decisions can affect security, compliance, and procurement. Confidence-based routing allows
automation for clear cases while escalating uncertainty.

### Why keep a transparent baseline?

It makes the demo usable without an API key and provides a simple comparison point for evaluating
whether the LLM produces enough improvement to justify its cost and complexity.

### Why not automatically approve or reject a vendor?

Four security controls cannot represent the vendor's total inherent and residual risk. A real
decision also requires privacy, legal, financial, operational, geographic, and business-criticality
context.

## 10. Success metrics

An initial 12-case synthetic evaluation has been run against both the transparent keyword baseline
and `gemini-3.5-flash-lite`. It deliberately includes positive, negative, and
insufficient-evidence wording. The test is useful for engineering comparison but is too small and
controlled to support production-quality or general accuracy claims.

| Metric | Meaning | Keyword baseline | Gemini result | Initial target |
|---|---|---:|---:|---:|
| Citation existence | Percentage of selected quotes found verbatim in the document | 100.0% | 100.0% | 100% |
| Citation validity | Percentage of quotes that genuinely support the answer | Not human-scored | Not human-scored | ≥95% |
| Answer agreement | Percentage of answers matching a human-labelled reference answer | 58.3% | 100.0% | ≥85% |
| Unsupported definitive answers | Definitive `Yes` answers when the expected result was not `Yes` | 50.0% | 0.0% | ≤5% |
| Review-routing recall | Percentage of negative or ambiguous cases sent to human review | 62.5% | 100.0% | ≥90% |
| Analyst time per question | Median time required to produce and verify one answer | Not measured | Not measured | ≥50% reduction |
| Assessment latency | Time from submission to displayed results for the demo set | Not measured | Not measured | <30 seconds |
| Cost per assessment | Estimated Gemini cost for one representative document/question set | Not measured | Not measured | Record baseline |
| Reviewer acceptance | Percentage of AI answers approved without correction | Not measured | Not measured | ≥80% |

The baseline's weak answer agreement is expected: keyword matching detects the presence of terms
but does not reliably understand negation or requirement mismatches such as TLS 1.2 versus TLS 1.3.
Gemini correctly handled all 12 synthetic cases in the recorded run. This indicates that semantic
reasoning improved this small test, not that the system has 100% accuracy on real vendor documents.

### How to measure them

Expand the current 12 cases to 20–30 question/evidence examples and manually label the correct
answer and valid supporting passage. Run both the keyword baseline and Gemini path. Compare each
output with the labels, record elapsed time, and inspect whether uncertain cases entered the review
queue.

## 11. Current limitations

- Only four original demo controls are included.
- The system is not an official SIG implementation and has not been certified against ISO 27001.
- Scanned PDFs may require OCR because PyPDF primarily extracts embedded text.
- Results are stored only in the current browser session; there is no persistent database.
- There is no authentication, tenant isolation, role-based access, or production security model.
- Framework mappings are illustrative and need validation against authoritative licensed sources.
- The Gemini path still needs a labelled evaluation before quality claims can be made.
- It supports an assessment step, not the entire TPRM lifecycle.

## 12. Sensible next iterations

1. Build and label an evaluation dataset.
2. Add question criticality and evidence-quality fields.
3. Add a limited control-gap summary without claiming to approve the vendor.
4. Add privacy and operational due-diligence domains.
5. Add OCR for scanned documents.
6. Persist vendors, assessments, findings, and audit events in a database.
7. Add authentication and reviewer roles.
8. Add remediation owners, due dates, status, and continuous-monitoring events.

## 13. Interview introduction (60–90 seconds)

> I built EvidenceLens to explore a common TPRM problem: analysts repeatedly search long vendor
> policies to answer security questionnaires, but using an LLM without traceability can introduce
> unsupported answers. The prototype accepts vendor documentation and produces structured control
> assessments containing an answer, an exact evidence quote, confidence, rationale, and a follow-up.
> Clear answers can be marked auto-ready, while ambiguous or insufficient evidence is routed to a
> human reviewer. Reviewer actions are recorded and the assessment can be exported. I deliberately
> kept the scope narrow and added a transparent baseline so I can evaluate whether Gemini improves
> citation validity and analyst time. My next step is a labelled test set measuring answer agreement,
> unsupported-answer rate, and review-routing quality.

## 14. Interview questions and model answers

### What user problem are you solving?

Risk analysts spend time locating, copying, and validating evidence across vendor documents. The
product accelerates the first pass while preserving source traceability and reviewer control.

### Why is this a product rather than just an LLM demo?

The LLM is only one component. The product defines a repeatable user workflow: document intake,
structured assessment, evidence presentation, uncertainty routing, reviewer decisions, and audit
export. It also defines users, risks, success metrics, and boundaries.

### Why did you choose this MVP scope?

The highest-risk assumption was whether AI could produce evidence-grounded answers that a reviewer
could efficiently verify. Four controls were sufficient to test the complete workflow before adding
framework breadth or production infrastructure.

### How do you reduce hallucinations?

The prompt prohibits unsupported inference, requires exact quotes, offers `Insufficient evidence`,
validates output structure, and routes uncertainty to a reviewer. The next improvement is automated
quote-existence checking and a labelled citation-validity evaluation.

### What does confidence mean?

It represents the strength and completeness of evidence for that specific answer. It is not the
probability that the vendor is safe and should not be used alone as a vendor-risk score.

### Why not call missing evidence non-compliance?

Absence of evidence is not proof that a control is absent. It creates an evidence gap requiring a
follow-up, whereas a confirmed negative statement can support a `No` answer.

### How would you prioritize the roadmap?

First evaluate accuracy and citations because they determine trust. Next add control criticality and
remediation workflows. Then add privacy and operational domains. Persistent storage, authentication,
integrations, and continuous monitoring follow once the workflow demonstrates value.

### What are the biggest risks?

Unsupported answers, misleading confidence, exposure of sensitive vendor documents, outdated
framework mappings, and users treating decision support as automatic approval. Mitigations include
citations, review gates, access control, encryption, retention policies, evaluation, and clear scope.

### How would this work at enterprise scale?

Documents would be stored securely by tenant, processed asynchronously, split into retrievable
sections, and assessed through versioned prompts and schemas. Results, reviewer actions, model
versions, and evidence locations would be persisted. Role-based access, encryption, monitoring,
retention, and integrations would be required.

### What would you do with more time?

Build the labelled evaluation set first, compare the baseline with Gemini, add quote verification,
then implement control criticality, findings, remediation ownership, and a persistent audit model.

### What did you deliberately not build?

A full TPRM lifecycle, official framework content, automated vendor approval, authentication, and a
production database. Those additions would not be credible until the evidence-assessment workflow
is evaluated.

### How does the project relate to Certa?

It explores document-driven due diligence, configurable workflows, AI-assisted assessments,
exception routing, and human oversight—themes relevant to an AI-powered third-party-risk platform—
while remaining a small independent prototype rather than a recreation of Certa's product.

## 15. Honest resume statement before evaluation

> Built EvidenceLens, a Gemini-assisted vendor security-assessment prototype that extracts cited
> evidence from documents, produces structured control assessments, and routes uncertain answers
> for human review with an exportable audit trail.

After evaluation, add metrics only if they are measured and reproducible.

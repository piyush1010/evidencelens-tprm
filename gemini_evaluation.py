import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

ROOT = Path(__file__).parent
CASES = json.loads((ROOT / "evaluation_cases.json").read_text())


class EvaluationPrediction(BaseModel):
    case_id: str
    answer: Literal["Yes", "No", "Insufficient evidence"]
    evidence_quote: str
    rationale: str


class EvaluationBatch(BaseModel):
    predictions: list[EvaluationPrediction]


def run_gemini_evaluation(api_key: str, model: str) -> dict:
    from google import genai

    client = genai.Client(api_key=api_key)
    prompt = f"""You are evaluating vendor security evidence. For every case below, answer only
the associated question using only that case's evidence. Pay close attention to negation and exact
requirements such as protocol versions, time limits, scope, and frequency.

Use Yes only when every material part is explicitly supported. Use No when the evidence explicitly
contradicts the requirement. Use Insufficient evidence when relevant information is missing or
ambiguous. The evidence_quote must be an exact excerpt from the case evidence.

EVALUATION CASES:
{json.dumps(CASES, indent=2)}
"""
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": EvaluationBatch,
        },
    )
    batch = EvaluationBatch.model_validate_json(response.text)
    predictions = {item.case_id: item for item in batch.predictions}
    results = []

    for case in CASES:
        prediction = predictions.get(case["case_id"])
        if prediction is None:
            actual_answer = "Missing prediction"
            quote = ""
            rationale = "The model did not return this case."
        else:
            actual_answer = prediction.answer
            quote = prediction.evidence_quote
            rationale = prediction.rationale

        agrees = actual_answer == case["expected_answer"]
        quote_exists = bool(quote) and quote.lower() in case["evidence"].lower()
        should_review = case["expected_answer"] != "Yes"
        routed_to_review = actual_answer != "Yes"
        unsupported_definitive = actual_answer == "Yes" and should_review
        results.append(
            {
                **case,
                "actual_answer": actual_answer,
                "evidence_quote": quote,
                "rationale": rationale,
                "answer_agrees": agrees,
                "citation_exists": quote_exists,
                "should_review": should_review,
                "routed_to_review": routed_to_review,
                "unsupported_definitive": unsupported_definitive,
            }
        )

    total = len(results)
    review_cases = [row for row in results if row["should_review"]]
    definitive = [row for row in results if row["actual_answer"] == "Yes"]
    summary = {
        "engine": model,
        "cases": total,
        "answer_agreement_percent": round(
            100 * sum(row["answer_agrees"] for row in results) / total, 1
        ),
        "citation_existence_percent": round(
            100 * sum(row["citation_exists"] for row in results) / total, 1
        ),
        "review_routing_recall_percent": round(
            100 * sum(row["routed_to_review"] for row in review_cases) / len(review_cases),
            1,
        ),
        "unsupported_definitive_percent": round(
            100
            * sum(row["unsupported_definitive"] for row in definitive)
            / len(definitive),
            1,
        )
        if definitive
        else 0.0,
    }
    output = {"summary": summary, "cases": results}
    (ROOT / "gemini_evaluation_results.json").write_text(
        json.dumps(output, indent=2) + "\n"
    )
    return output


import json
from pathlib import Path

from assessment import demo_assess

ROOT = Path(__file__).parent


def main() -> None:
    cases = json.loads((ROOT / "evaluation_cases.json").read_text())
    results = []

    for case in cases:
        assessment = next(
            row
            for row in demo_assess(case["evidence"])
            if row["question_id"] == case["question_id"]
        )
        quote_exists = (
            assessment["evidence_quote"] != "No supporting passage found."
            and assessment["evidence_quote"].lower() in case["evidence"].lower()
        )
        agrees = assessment["answer"] == case["expected_answer"]
        should_review = case["expected_answer"] != "Yes"
        routed_to_review = (
            assessment["answer"] == "Insufficient evidence"
            or assessment["confidence"] < 75
        )
        unsupported_definitive = (
            assessment["answer"] == "Yes" and case["expected_answer"] != "Yes"
        )
        results.append(
            {
                **case,
                "actual_answer": assessment["answer"],
                "confidence": assessment["confidence"],
                "evidence_quote": assessment["evidence_quote"],
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
        "engine": "transparent_keyword_baseline",
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
    (ROOT / "evaluation_results.json").write_text(json.dumps(output, indent=2) + "\n")

    print("Transparent baseline evaluation")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()


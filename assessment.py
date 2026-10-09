import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
QUESTIONS = json.loads((ROOT / "questions.json").read_text())
SAMPLE_TEXT = (ROOT / "sample_vendor_policy.txt").read_text()


def enrich_framework_metadata(rows: list[dict]) -> list[dict]:
    """Attach current framework metadata to new or cached assessment rows."""
    question_map = {question["id"]: question for question in QUESTIONS}
    for row in rows:
        question = question_map.get(row.get("question_id"))
        if not question:
            continue
        row["control_id"] = question["control_id"]
        row["iso_controls"] = " & ".join(
            question["iso_27001_2022_annex_a_controls"]
        )
        row["nist_csf_subcategories"] = " & ".join(
            question["nist_csf_2_0_subcategories"]
        )
        row["domain"] = question["domain"]
        row["question"] = question["question"]
    return rows


def sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
        if len(sentence.strip()) > 20
    ]


def demo_assess(text: str) -> list[dict]:
    """Transparent baseline; deliberately sends weak matches to human review."""
    rows = []
    text_lower = text.lower()
    chunks = sentences(text)

    for question in QUESTIONS:
        matched_terms = [
            keyword for keyword in question["keywords"] if keyword in text_lower
        ]
        ranked = sorted(
            chunks,
            key=lambda sentence: sum(
                keyword in sentence.lower() for keyword in question["keywords"]
            ),
            reverse=True,
        )
        quote = ranked[0] if ranked and matched_terms else "No supporting passage found."
        coverage = len(matched_terms) / len(question["keywords"])
        confidence = min(94, round(35 + coverage * 60)) if matched_terms else 18
        answer = "Yes" if coverage >= 0.75 else "Insufficient evidence"
        gap = (
            ""
            if answer == "Yes"
            else "Request policy details or supporting evidence from the vendor."
        )

        if question["id"] == "DEMO-IR-01" and "without undue delay" in text_lower:
            answer, confidence = "Insufficient evidence", 72
            gap = "Request a specific notification timeframe and contractual commitment."

        if question["id"] == "DEMO-VR-01" and "does not state how often" in text_lower:
            answer, confidence = "Insufficient evidence", 91
            gap = "Confirm the reassessment frequency for existing subprocessors."

        rows.append(
            {
                "question_id": question["id"],
                "control_id": question["control_id"],
                "iso_controls": " & ".join(
                    question["iso_27001_2022_annex_a_controls"]
                ),
                "nist_csf_subcategories": " & ".join(
                    question["nist_csf_2_0_subcategories"]
                ),
                "domain": question["domain"],
                "question": question["question"],
                "answer": answer,
                "confidence": confidence,
                "evidence_quote": quote,
                "rationale": (
                    f"Matched {len(matched_terms)} of "
                    f"{len(question['keywords'])} expected evidence signals."
                ),
                "gap_or_follow_up": gap,
            }
        )

    return rows

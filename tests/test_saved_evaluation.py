import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SavedEvaluationTests(unittest.TestCase):
    def test_saved_comparison_matches_case_level_results(self) -> None:
        baseline = json.loads((ROOT / "evaluation_results.json").read_text())
        gemini = json.loads((ROOT / "gemini_evaluation_results.json").read_text())

        self.assertEqual(len(baseline["cases"]), 12)
        self.assertEqual(len(gemini["cases"]), 12)
        self.assertEqual(sum(case["answer_agrees"] for case in baseline["cases"]), 7)
        self.assertEqual(sum(case["answer_agrees"] for case in gemini["cases"]), 12)
        self.assertEqual(gemini["summary"]["unsupported_definitive_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()

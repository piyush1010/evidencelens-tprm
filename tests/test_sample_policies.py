import unittest

from assessment import SAMPLE_POLICIES, demo_assess


class SamplePolicyTests(unittest.TestCase):
    def test_library_contains_three_distinct_scenarios(self) -> None:
        self.assertEqual(
            set(SAMPLE_POLICIES),
            {"mixed-evidence", "strong-controls", "evidence-gaps"},
        )

    def test_sample_scenarios_produce_expected_demo_shape(self) -> None:
        expected_answers = {
            "mixed-evidence": ["Yes", "Yes", "Insufficient evidence", "Insufficient evidence"],
            "strong-controls": ["Yes", "Yes", "Yes", "Yes"],
            "evidence-gaps": [
                "Insufficient evidence",
                "Insufficient evidence",
                "Insufficient evidence",
                "Insufficient evidence",
            ],
        }

        for sample_id, answers in expected_answers.items():
            with self.subTest(sample_id=sample_id):
                results = demo_assess(SAMPLE_POLICIES[sample_id]["text"])
                self.assertEqual([row["answer"] for row in results], answers)

    def test_every_sample_is_clearly_synthetic(self) -> None:
        for sample in SAMPLE_POLICIES.values():
            self.assertIn("fictional", sample["text"].lower())
            self.assertIn("synthetic demo", sample["text"].lower())


if __name__ == "__main__":
    unittest.main()

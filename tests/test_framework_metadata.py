import unittest

from assessment import QUESTIONS, SAMPLE_TEXT, demo_assess


class FrameworkMetadataTests(unittest.TestCase):
    def test_every_question_has_iso_and_nist_references(self) -> None:
        for question in QUESTIONS:
            self.assertTrue(question["iso_27001_2022_annex_a_controls"])
            self.assertTrue(question["nist_csf_2_0_subcategories"])

    def test_demo_results_export_nist_references(self) -> None:
        results = demo_assess(SAMPLE_TEXT)

        self.assertEqual(len(results), len(QUESTIONS))
        for result in results:
            self.assertTrue(result["nist_csf_subcategories"])


if __name__ == "__main__":
    unittest.main()

import unittest

from assessment import (
    QUESTIONS,
    SAMPLE_TEXT,
    demo_assess,
    enrich_framework_metadata,
)


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

    def test_cached_rows_are_enriched_for_new_framework_fields(self) -> None:
        cached_rows = [{"question_id": "DEMO-AC-01", "answer": "Yes"}]

        enriched = enrich_framework_metadata(cached_rows)

        self.assertEqual(enriched[0]["nist_csf_subcategories"], "PR.AA-03")
        self.assertEqual(enriched[0]["iso_controls"], "A.5.15 & A.8.2")


if __name__ == "__main__":
    unittest.main()

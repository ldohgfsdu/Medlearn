import unittest

from scripts.textbook_pipeline.subject_hints import route_subject_hints


class SubjectHintsRoutingTests(unittest.TestCase):
    def test_routes_physiology_and_pharmacology_to_different_schemas(self):
        physiology = route_subject_hints(textbook_title="生理学（第10版）")
        pharmacology = route_subject_hints(textbook_title="药理学（第9版）")
        self.assertEqual(physiology.hints.id, "physiology")
        self.assertEqual(pharmacology.hints.id, "pharmacology")
        self.assertIn("调节", physiology.hints.aspect_candidates)
        self.assertIn("药代动力学", pharmacology.hints.aspect_candidates)
        self.assertNotEqual(
            physiology.hints.aspect_candidates,
            pharmacology.hints.aspect_candidates,
        )

    def test_manifest_override_has_highest_authority(self):
        decision = route_subject_hints(
            textbook_title="综合医学教材",
            explicit_hints="anatomy",
        )
        self.assertEqual(decision.hints.id, "anatomy")
        self.assertEqual(decision.basis, "manifest")
        self.assertEqual(decision.confidence, 1.0)

    def test_ambiguous_signals_fall_back_instead_of_guessing(self):
        decision = route_subject_hints(
            textbook_title="生理学与药理学联合教程"
        )
        self.assertEqual(decision.hints.id, "generic_textbook")
        self.assertEqual(decision.basis, "fallback")

    def test_unknown_subject_preserves_source_heading_profile(self):
        decision = route_subject_hints(textbook_title="医学人文导论")
        self.assertEqual(decision.hints.id, "generic_textbook")
        self.assertEqual(
            decision.hints.summary_style,
            "source-heading-preserving outline",
        )

    def test_hints_do_not_define_document_tree_parentage(self):
        decision = route_subject_hints(textbook_title="药理学")
        self.assertFalse(hasattr(decision.hints, "parent_id"))
        self.assertFalse(hasattr(decision.hints, "heading_rules"))

    def test_hints_do_not_carry_high_risk_aspects(self):
        """Risk aspects live in the standalone RiskRuleSet, not on hints."""
        decision = route_subject_hints(textbook_title="药理学")
        self.assertFalse(hasattr(decision.hints, "high_risk_aspects"))
        self.assertTrue(decision.hints.default_risk_rule_set_id)

    def test_hints_reference_risk_rule_set_by_id_and_version(self):
        decision = route_subject_hints(textbook_title="内科学（第10版）")
        self.assertEqual(
            decision.hints.default_risk_rule_set_id, "clinical_medicine_default"
        )
        self.assertEqual(decision.hints.default_risk_rule_set_version, "1")


if __name__ == "__main__":
    unittest.main()

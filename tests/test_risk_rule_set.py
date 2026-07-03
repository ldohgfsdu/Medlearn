import unittest

from scripts.textbook_pipeline.risk_rule_set import (
    RiskRuleSet,
    load_all_risk_rule_sets,
    load_risk_rule_set,
)


class RiskRuleSetTests(unittest.TestCase):
    def test_load_clinical_medicine_default(self):
        rule_set = load_risk_rule_set("clinical_medicine_default")
        self.assertEqual(rule_set.id, "clinical_medicine_default")
        self.assertEqual(rule_set.version, "1")
        self.assertIn("剂量", rule_set.high_risk_aspects)
        self.assertIn("禁忌", rule_set.high_risk_aspects)

    def test_load_pharmacology_default(self):
        rule_set = load_risk_rule_set("pharmacology_default")
        self.assertIn("相互作用", rule_set.high_risk_aspects)
        self.assertIn("中毒", rule_set.high_risk_aspects)

    def test_generic_textbook_default_has_empty_risks(self):
        rule_set = load_risk_rule_set("generic_textbook_default")
        self.assertEqual(rule_set.high_risk_aspects, ())

    def test_unknown_rule_set_raises_key_error(self):
        with self.assertRaises(KeyError):
            load_risk_rule_set("nonexistent_rule_set")

    def test_version_mismatch_raises_value_error(self):
        with self.assertRaises(ValueError):
            load_risk_rule_set("clinical_medicine_default", version="999")

    def test_load_all_rule_sets_returns_dict(self):
        all_sets = load_all_risk_rule_sets()
        self.assertIn("clinical_medicine_default", all_sets)
        self.assertIn("pharmacology_default", all_sets)
        self.assertIsInstance(all_sets["clinical_medicine_default"], RiskRuleSet)

    def test_rule_set_is_frozen_and_hashable(self):
        rule_set = load_risk_rule_set("clinical_medicine_default")
        with self.assertRaises(Exception):
            rule_set.high_risk_aspects = ("new",)  # type: ignore[misc]
        hash(rule_set)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = ROOT / "scripts" / "orchestrator.py"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location("medlearn_orchestrator", ORCHESTRATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OrchestratorTests(unittest.TestCase):
    def test_audit_app_knowledge_quality_exports_source_qa_then_runs_strict_audit(self):
        orchestrator = load_orchestrator()
        calls = []

        def fake_call(args):
            calls.append(args)
            return 0

        with patch.object(orchestrator, "_call", side_effect=fake_call), patch.object(
            sys,
            "argv",
            ["orchestrator.py", "audit-app-knowledge-quality"],
        ):
            self.assertEqual(orchestrator.main(), 0)

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "node")
        self.assertTrue(str(calls[0][1]).endswith("export-ev1-source-qa-queue.mjs"))
        self.assertIn("--all", calls[0])
        self.assertIn("--pretty", calls[0])
        self.assertEqual(calls[1][0], "node")
        self.assertTrue(str(calls[1][1]).endswith("audit-ev1-knowledge-quality.mjs"))
        self.assertIn("--pretty", calls[1])
        self.assertIn("--strict", calls[1])

    def test_audit_app_knowledge_quality_is_listed_as_supported_command(self):
        orchestrator = load_orchestrator()

        self.assertIn("audit-app-knowledge-quality", orchestrator.SUPPORTED_COMMANDS)

    def test_reverify_app_knowledge_bundle_reverifies_then_rebuilds_and_audits(self):
        orchestrator = load_orchestrator()
        calls = []

        def fake_call(args):
            calls.append(args)
            return 0

        with patch.object(orchestrator, "_call", side_effect=fake_call), patch.object(
            sys,
            "argv",
            ["orchestrator.py", "reverify-app-knowledge-bundle"],
        ):
            self.assertEqual(orchestrator.main(), 0)

        self.assertEqual(len(calls), 9)
        self.assertEqual(calls[0][0], sys.executable)
        self.assertTrue(str(calls[0][1]).endswith("ingest_knowledge.py"))
        self.assertEqual(calls[0][2], "ev1-reverify-candidates")
        self.assertEqual(calls[1][2], "ev1-candidate-quality-report")
        self.assertIn("--strict", calls[1])
        self.assertEqual(calls[2][2], "ev1-convert-ready")
        self.assertIn("--continue-on-error", calls[2])
        self.assertEqual(calls[3][2], "ev1-release-gate")
        self.assertEqual(calls[4][2], "ev1-display-contract")
        self.assertEqual(calls[5][2], "ev1-display-quality-report")
        self.assertIn("--strict", calls[5])
        self.assertTrue(str(calls[6][1]).endswith("export_ev1_display_contracts_ts.py"))
        self.assertEqual(calls[7][0], "node")
        self.assertTrue(str(calls[7][1]).endswith("export-ev1-source-qa-queue.mjs"))
        self.assertIn("--all", calls[7])
        self.assertEqual(calls[8][0], "node")
        self.assertTrue(str(calls[8][1]).endswith("audit-ev1-knowledge-quality.mjs"))
        self.assertIn("--strict", calls[8])

    def test_reverify_commands_are_listed_as_supported_commands(self):
        orchestrator = load_orchestrator()

        self.assertIn("ev1-reverify-candidates", orchestrator.SUPPORTED_COMMANDS)
        self.assertIn("ev1-candidate-quality-report", orchestrator.SUPPORTED_COMMANDS)
        self.assertIn("ev1-display-quality-report", orchestrator.SUPPORTED_COMMANDS)
        self.assertIn("reverify-app-knowledge-bundle", orchestrator.SUPPORTED_COMMANDS)


if __name__ == "__main__":
    unittest.main()

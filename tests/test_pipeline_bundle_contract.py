import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_pipeline_closure import check_app_bundle_contract  # noqa: E402


class PipelineBundleContractTests(unittest.TestCase):
    def test_app_bundle_contract_has_no_path_drift(self):
        report = check_app_bundle_contract()

        self.assertEqual(report["issues"], [])
        self.assertGreater(report["fixture_chunks"], 0)
        self.assertEqual(Path(report["normalized_root"]).parts, ("generated", "knowledge_nodes", "internal-medicine-10"))
        self.assertEqual(Path(report["display_root"]).parts, ("generated", "display_contracts", "internal-medicine-10"))


if __name__ == "__main__":
    unittest.main()

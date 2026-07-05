from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_p0_smoke  # noqa: E402
import verify_pipeline_closure  # noqa: E402


class VerificationModeTests(unittest.TestCase):
    def test_p0_defaults_to_local_only(self) -> None:
        with patch.object(
            verify_p0_smoke,
            "check_remote_db",
            side_effect=AssertionError("remote check must be opt-in"),
        ):
            report = verify_p0_smoke.build_report()

        self.assertTrue(report["remote_db"]["skipped"])
        self.assertIn("--remote", report["remote_db"]["reason"])

    def test_p0_remote_mode_calls_remote_check(self) -> None:
        expected = {"skipped": False, "issues": []}
        with patch.object(
            verify_p0_smoke,
            "check_remote_db",
            return_value=expected,
        ) as remote:
            report = verify_p0_smoke.build_report(include_remote=True)

        remote.assert_called_once_with()
        self.assertEqual(report["remote_db"], expected)

    def test_closure_defaults_to_local_only(self) -> None:
        with patch.object(
            verify_pipeline_closure,
            "build_p0_report",
            return_value={
                "remote_db": {
                    "skipped": True,
                    "reason": "remote verification not requested",
                },
                "passed": True,
                "issue_count": 0,
            },
        ) as p0:
            report = verify_pipeline_closure.build_report()

        p0.assert_called_once_with(include_remote=False)
        self.assertTrue(report["p0_smoke"]["remote_db"]["skipped"])

    def test_remote_connection_error_is_structured(self) -> None:
        with (
            patch.dict(
                verify_p0_smoke.os.environ,
                {
                    "SUPABASE_URL": "https://invalid.example",
                    "SUPABASE_SERVICE_ROLE_KEY": "test-key",
                },
                clear=True,
            ),
            patch("supabase.create_client", side_effect=RuntimeError("offline")),
        ):
            result = verify_p0_smoke.check_remote_db()

        self.assertFalse(result["skipped"])
        self.assertEqual(
            result["issues"],
            ["remote DB verification failed: RuntimeError: offline"],
        )


if __name__ == "__main__":
    unittest.main()

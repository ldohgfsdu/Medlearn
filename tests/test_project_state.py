from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_current_state import render_current_state
from validate_project_state import ProjectStateError, validate_repository


class ProjectStateTests(unittest.TestCase):
    def test_repository_state_is_valid_and_renderable(self) -> None:
        validated = validate_repository(ROOT)
        rendered = render_current_state(validated)
        self.assertIn("Phase: `mvp_alpha_readiness`", rendered)
        self.assertIn("local_demo_recovery", rendered)
        self.assertIn("remote_supabase_validation", rendered)

    def test_duplicate_object_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._copy_governance_files(root)

            completed_path = root / "state" / "completed_objects.yaml"
            completed = yaml.safe_load(completed_path.read_text(encoding="utf-8"))
            duplicate = copy.deepcopy(completed["objects"][0])
            duplicate["status"] = "blocked"
            duplicate["frozen"] = False
            duplicate["completed_at"] = None
            duplicate["blocked_reason"] = "Test duplicate."

            blocked_path = root / "state" / "blocked_objects.yaml"
            blocked = yaml.safe_load(blocked_path.read_text(encoding="utf-8"))
            blocked["objects"].append(duplicate)
            blocked_path.write_text(
                yaml.safe_dump(blocked, sort_keys=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectStateError, "Duplicate object id"):
                validate_repository(root)

    def test_blocked_object_requires_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._copy_governance_files(root)

            blocked_path = root / "state" / "blocked_objects.yaml"
            blocked = yaml.safe_load(blocked_path.read_text(encoding="utf-8"))
            blocked["objects"][0]["blocked_reason"] = None
            blocked_path.write_text(
                yaml.safe_dump(blocked, sort_keys=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectStateError, "requires blocked_reason"):
                validate_repository(root)

    def test_generator_does_not_overwrite_when_state_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._copy_governance_files(root)

            blocked_path = root / "state" / "blocked_objects.yaml"
            blocked = yaml.safe_load(blocked_path.read_text(encoding="utf-8"))
            blocked["objects"][0]["blocked_reason"] = None
            blocked_path.write_text(
                yaml.safe_dump(blocked, sort_keys=False),
                encoding="utf-8",
            )

            output = root / "docs" / "CURRENT_STATE.md"
            sentinel = "do not overwrite\n"
            output.write_text(sentinel, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "generate_current_state.py"),
                    "--root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), sentinel)

    def test_unknown_dependency_requires_external_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._copy_governance_files(root)

            blocked_path = root / "state" / "blocked_objects.yaml"
            blocked = yaml.safe_load(blocked_path.read_text(encoding="utf-8"))
            blocked["objects"][0]["dependencies"] = ["missing_object"]
            blocked_path.write_text(
                yaml.safe_dump(blocked, sort_keys=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ProjectStateError, "unknown object"):
                validate_repository(root)

    def _copy_governance_files(self, target: Path) -> None:
        for relative in (
            "state/active_object.yaml",
            "state/completed_objects.yaml",
            "state/blocked_objects.yaml",
            "docs/ADR_INDEX.yaml",
            "scripts/textbook_pipeline/ADR-004-display-graph-separation.md",
        ):
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

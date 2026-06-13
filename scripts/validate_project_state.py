#!/usr/bin/env python3
"""Validate MedLearn's machine-readable governance state."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required. Install it with: pip install -r scripts/requirements.txt"
    ) from exc


SCHEMA_VERSION = 1
OBJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ADR_ID_PATTERN = re.compile(r"^ADR-\d{3}$")
ADR_STATUSES = {"proposed", "accepted", "superseded", "deprecated", "rejected"}
FILE_STATUSES = {
    "active_object.yaml": {"active"},
    "completed_objects.yaml": {"completed", "archived"},
    "blocked_objects.yaml": {"blocked", "paused"},
}


class ProjectStateError(ValueError):
    """Raised when project governance state is invalid."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProjectStateError(f"Missing required file: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProjectStateError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectStateError(f"{path} must contain a YAML mapping")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ProjectStateError(
            f"{path} must declare schema_version: {SCHEMA_VERSION}"
        )
    return data


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectStateError(f"{label} must be a non-empty string")
    return value.strip()


def _require_string_list(
    value: Any,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        raise ProjectStateError(f"{label} must be a list")
    if not allow_empty and not value:
        raise ProjectStateError(f"{label} must not be empty")
    result = []
    for index, item in enumerate(value):
        result.append(_require_text(item, f"{label}[{index}]"))
    if len(result) != len(set(result)):
        raise ProjectStateError(f"{label} must not contain duplicates")
    return result


def _validate_timestamp(value: Any, label: str, *, required: bool = False) -> None:
    if value is None:
        if required:
            raise ProjectStateError(f"{label} is required")
        return
    if isinstance(value, (date, datetime)):
        return
    text = _require_text(value, label)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise ProjectStateError(
                f"{label} must be an ISO date or datetime"
            ) from exc


def _validate_object(
    obj: Any,
    *,
    source: Path,
    allowed_statuses: set[str],
) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ProjectStateError(f"Object in {source} must be a mapping")

    object_id = _require_text(obj.get("id"), f"{source}: object id")
    if not OBJECT_ID_PATTERN.fullmatch(object_id):
        raise ProjectStateError(
            f"{source}: invalid object id {object_id!r}; use lowercase letters, "
            "numbers, underscores, or hyphens"
        )

    _require_text(obj.get("title"), f"{object_id}.title")
    _require_text(obj.get("objective"), f"{object_id}.objective")
    status = _require_text(obj.get("status"), f"{object_id}.status")
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        raise ProjectStateError(
            f"{object_id}.status must be one of [{allowed}] in {source.name}"
        )

    _require_string_list(obj.get("scope"), f"{object_id}.scope")
    _require_string_list(
        obj.get("acceptance_criteria"),
        f"{object_id}.acceptance_criteria",
    )
    _require_string_list(
        obj.get("dependencies"),
        f"{object_id}.dependencies",
        allow_empty=True,
    )
    if "adr_tags" in obj:
        _require_string_list(
            obj.get("adr_tags"),
            f"{object_id}.adr_tags",
            allow_empty=True,
        )
    if "evidence" in obj:
        _require_string_list(
            obj.get("evidence"),
            f"{object_id}.evidence",
            allow_empty=True,
        )

    if not isinstance(obj.get("frozen"), bool):
        raise ProjectStateError(f"{object_id}.frozen must be true or false")

    _validate_timestamp(
        obj.get("activated_at"),
        f"{object_id}.activated_at",
        required=True,
    )
    _validate_timestamp(obj.get("completed_at"), f"{object_id}.completed_at")
    _validate_timestamp(obj.get("archived_at"), f"{object_id}.archived_at")
    _validate_timestamp(obj.get("reactivated_at"), f"{object_id}.reactivated_at")

    blocked_reason = obj.get("blocked_reason")
    if blocked_reason is not None:
        _require_text(blocked_reason, f"{object_id}.blocked_reason")

    reactivated_at = obj.get("reactivated_at")
    reactivation_reason = obj.get("reactivation_reason")
    if reactivation_reason is not None:
        _require_text(reactivation_reason, f"{object_id}.reactivation_reason")
    if bool(reactivated_at) != bool(reactivation_reason):
        raise ProjectStateError(
            f"{object_id} must set reactivated_at and reactivation_reason together"
        )

    if status == "active":
        if obj.get("completed_at") is not None:
            raise ProjectStateError(f"{object_id}: active object cannot be completed")
        if blocked_reason is not None:
            raise ProjectStateError(f"{object_id}: active object cannot be blocked")
        if obj["frozen"]:
            raise ProjectStateError(f"{object_id}: active object cannot be frozen")
    elif status == "completed":
        _validate_timestamp(
            obj.get("completed_at"),
            f"{object_id}.completed_at",
            required=True,
        )
        if not obj["frozen"]:
            raise ProjectStateError(
                f"{object_id}: completed object must default to frozen: true"
            )
    elif status == "archived":
        _validate_timestamp(
            obj.get("archived_at"),
            f"{object_id}.archived_at",
            required=True,
        )
        if not obj["frozen"]:
            raise ProjectStateError(
                f"{object_id}: archived object must be frozen"
            )
    elif status in {"blocked", "paused"}:
        if blocked_reason is None:
            raise ProjectStateError(
                f"{object_id}: {status} object requires blocked_reason"
            )
        if obj.get("completed_at") is not None:
            raise ProjectStateError(
                f"{object_id}: {status} object cannot be completed"
            )

    return obj


def _load_state(root: Path) -> dict[str, Any]:
    state_dir = root / "state"
    active_path = state_dir / "active_object.yaml"
    completed_path = state_dir / "completed_objects.yaml"
    blocked_path = state_dir / "blocked_objects.yaml"

    active_data = _load_yaml(active_path)
    completed_data = _load_yaml(completed_path)
    blocked_data = _load_yaml(blocked_path)

    project = active_data.get("project")
    if not isinstance(project, dict):
        raise ProjectStateError(f"{active_path}: project must be a mapping")
    _require_text(project.get("name"), "project.name")
    _require_text(project.get("phase"), "project.phase")

    active = active_data.get("active_object")
    active_objects: list[dict[str, Any]] = []
    if active is not None:
        active_objects.append(
            _validate_object(
                active,
                source=active_path,
                allowed_statuses=FILE_STATUSES[active_path.name],
            )
        )

    def load_object_list(path: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
        objects = data.get("objects")
        if not isinstance(objects, list):
            raise ProjectStateError(f"{path}: objects must be a list")
        return [
            _validate_object(
                obj,
                source=path,
                allowed_statuses=FILE_STATUSES[path.name],
            )
            for obj in objects
        ]

    completed = load_object_list(completed_path, completed_data)
    blocked = load_object_list(blocked_path, blocked_data)
    all_objects = active_objects + completed + blocked

    seen: dict[str, str] = {}
    for obj in all_objects:
        object_id = obj["id"]
        location = obj["status"]
        if object_id in seen:
            raise ProjectStateError(
                f"Duplicate object id {object_id!r} in statuses "
                f"{seen[object_id]!r} and {location!r}"
            )
        seen[object_id] = location

    objects_by_id = {obj["id"]: obj for obj in all_objects}
    for obj in all_objects:
        for dependency in obj["dependencies"]:
            if dependency.startswith("external:"):
                external_id = dependency.removeprefix("external:")
                if not external_id:
                    raise ProjectStateError(
                        f"{obj['id']} has an empty external dependency"
                    )
                continue
            if dependency not in objects_by_id:
                raise ProjectStateError(
                    f"{obj['id']} depends on unknown object {dependency!r}; "
                    "register it or prefix it with external:"
                )
            if dependency == obj["id"]:
                raise ProjectStateError(
                    f"{obj['id']} cannot depend on itself"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(object_id: str, trail: list[str]) -> None:
        if object_id in visiting:
            cycle = " -> ".join([*trail, object_id])
            raise ProjectStateError(f"Dependency cycle detected: {cycle}")
        if object_id in visited:
            return
        visiting.add(object_id)
        obj = objects_by_id[object_id]
        for dependency in obj["dependencies"]:
            if not dependency.startswith("external:"):
                visit(dependency, [*trail, object_id])
        visiting.remove(object_id)
        visited.add(object_id)

    for object_id in objects_by_id:
        visit(object_id, [])

    return {
        "project": project,
        "active": active_objects[0] if active_objects else None,
        "completed": completed,
        "blocked": blocked,
        "objects_by_id": objects_by_id,
    }


def _load_adr_index(root: Path) -> dict[str, Any]:
    index_path = root / "docs" / "ADR_INDEX.yaml"
    data = _load_yaml(index_path)
    adrs = data.get("adrs")
    if not isinstance(adrs, list):
        raise ProjectStateError(f"{index_path}: adrs must be a list")

    by_id: dict[str, dict[str, Any]] = {}
    for index, adr in enumerate(adrs):
        if not isinstance(adr, dict):
            raise ProjectStateError(f"{index_path}: adrs[{index}] must be a mapping")
        adr_id = _require_text(adr.get("id"), f"adrs[{index}].id")
        if not ADR_ID_PATTERN.fullmatch(adr_id):
            raise ProjectStateError(f"Invalid ADR id: {adr_id!r}")
        if adr_id in by_id:
            raise ProjectStateError(f"Duplicate ADR id: {adr_id}")
        _require_text(adr.get("title"), f"{adr_id}.title")
        status = _require_text(adr.get("status"), f"{adr_id}.status")
        if status not in ADR_STATUSES:
            raise ProjectStateError(
                f"{adr_id}.status must be one of {sorted(ADR_STATUSES)}"
            )
        applies_to = _require_string_list(
            adr.get("applies_to"),
            f"{adr_id}.applies_to",
        )
        supersedes = _require_string_list(
            adr.get("supersedes"),
            f"{adr_id}.supersedes",
            allow_empty=True,
        )
        if adr_id in supersedes:
            raise ProjectStateError(f"{adr_id} cannot supersede itself")

        relative_path = Path(_require_text(adr.get("path"), f"{adr_id}.path"))
        resolved_path = (root / relative_path).resolve()
        try:
            resolved_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ProjectStateError(
                f"{adr_id}.path must stay inside the repository"
            ) from exc
        if not resolved_path.is_file():
            raise ProjectStateError(
                f"{adr_id}.path does not exist: {relative_path.as_posix()}"
            )

        adr["applies_to"] = applies_to
        adr["supersedes"] = supersedes
        by_id[adr_id] = adr

    for adr_id, adr in by_id.items():
        for superseded_id in adr["supersedes"]:
            if superseded_id not in by_id:
                raise ProjectStateError(
                    f"{adr_id} supersedes unknown ADR {superseded_id}"
                )

    return {"adrs": adrs, "by_id": by_id}


def validate_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    state = _load_state(root)
    adr_index = _load_adr_index(root)
    return {"root": root, "state": state, "adr_index": adr_index}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args()

    try:
        result = validate_repository(args.root)
    except ProjectStateError as exc:
        print(f"Project state validation failed: {exc}", file=sys.stderr)
        return 1

    state = result["state"]
    active_count = 1 if state["active"] else 0
    print(
        "Project state is valid: "
        f"{active_count} active, "
        f"{len(state['blocked'])} blocked/paused, "
        f"{len(state['completed'])} completed/archived, "
        f"{len(result['adr_index']['adrs'])} indexed ADRs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

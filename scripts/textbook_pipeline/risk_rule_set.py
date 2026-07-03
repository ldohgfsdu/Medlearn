"""Versioned, standalone risk rule sets.

RiskRuleSet is intentionally decoupled from SubjectHints. Subject hints reference
a default risk rule set by id + version (string fields only); this module never
imports subject_hints and never determines Document Tree parentage or publication
approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REGISTRY_DIR = Path(__file__).resolve().parent.parent.parent / "registry" / "risk_rule_sets"


@dataclass(frozen=True)
class RiskRuleSet:
    id: str
    version: str
    high_risk_aspects: tuple[str, ...]


def load_risk_rule_set(
    rule_set_id: str,
    *,
    version: str = "1",
    registry_version: str = "1",
) -> RiskRuleSet:
    """Load a single risk rule set from the versioned YAML registry."""
    path = REGISTRY_DIR / f"registry.v{registry_version}.yaml"
    with path.open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    rule_sets = data.get("rule_sets", {})
    if rule_set_id not in rule_sets:
        raise KeyError(f"risk rule set '{rule_set_id}' not found in {path}")
    entry = rule_sets[rule_set_id]
    if entry.get("version") != version:
        raise ValueError(
            f"risk rule set '{rule_set_id}' version mismatch: requested {version}, "
            f"found {entry.get('version')}"
        )
    return RiskRuleSet(
        id=rule_set_id,
        version=version,
        high_risk_aspects=tuple(entry.get("high_risk_aspects", [])),
    )


def load_all_risk_rule_sets(*, registry_version: str = "1") -> dict[str, RiskRuleSet]:
    """Load every risk rule set in the given registry version."""
    path = REGISTRY_DIR / f"registry.v{registry_version}.yaml"
    with path.open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    rule_sets = data.get("rule_sets", {})
    return {
        rule_set_id: RiskRuleSet(
            id=rule_set_id,
            version=entry.get("version", "1"),
            high_risk_aspects=tuple(entry.get("high_risk_aspects", [])),
        )
        for rule_set_id, entry in rule_sets.items()
    }

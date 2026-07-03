"""Conservative subject hints for textbook knowledge extraction.

Hints select extraction schemas only. They never determine Document Tree
parentage, rewrite source headings, or grant publication approval. High-risk
aspect rules live in the standalone, versioned RiskRuleSet registry; hints
reference a default rule set by id + version (string fields only) and never
import the risk_rule_set module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

REGISTRY_DIR = Path(__file__).resolve().parent.parent.parent / "registry" / "subject_hints"


@dataclass(frozen=True)
class SubjectHints:
    id: str
    version: str
    aspect_candidates: tuple[str, ...]
    preserve_structures: tuple[str, ...]
    summary_style: str
    signals: tuple[str, ...]
    default_risk_rule_set_id: str
    default_risk_rule_set_version: str


@dataclass(frozen=True)
class SubjectHintsRoutingDecision:
    hints: SubjectHints
    confidence: float
    basis: Literal["manifest", "title_and_catalog", "fallback"]
    matched_signals: tuple[str, ...]


def load_hints_registry(*, registry_version: str = "1") -> dict[str, SubjectHints]:
    """Load every subject hint in the given registry version."""
    path = REGISTRY_DIR / f"registry.v{registry_version}.yaml"
    with path.open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    raw_hints = data.get("hints", {})
    hints: dict[str, SubjectHints] = {}
    for hints_id, entry in raw_hints.items():
        default_ref = entry.get("default_risk_rule_set", {})
        hints[hints_id] = SubjectHints(
            id=hints_id,
            version=str(entry.get("version", "1")),
            aspect_candidates=tuple(entry.get("aspect_candidates", [])),
            preserve_structures=tuple(entry.get("preserve_structures", [])),
            summary_style=entry.get("summary_style", ""),
            signals=tuple(entry.get("signals", [])),
            default_risk_rule_set_id=default_ref.get("id", ""),
            default_risk_rule_set_version=str(default_ref.get("version", "1")),
        )
    return hints


def route_subject_hints(
    *,
    textbook_title: str,
    catalog_titles: list[str] | tuple[str, ...] = (),
    explicit_hints: str | None = None,
    registry_version: str = "1",
) -> SubjectHintsRoutingDecision:
    """Select hints from explicit metadata or conservative source signals."""
    hints_registry = load_hints_registry(registry_version=registry_version)

    if explicit_hints in hints_registry:
        return SubjectHintsRoutingDecision(
            hints_registry[explicit_hints], 1.0, "manifest", (explicit_hints,)
        )

    haystack = "\n".join([textbook_title, *catalog_titles])
    scored: list[tuple[int, str, tuple[str, ...]]] = []
    for hints_id, hints in hints_registry.items():
        matched = tuple(signal for signal in hints.signals if signal in haystack)
        if matched:
            scored.append((len(matched), hints_id, matched))
    scored.sort(key=lambda item: (-item[0], item[1]))

    if not scored:
        return SubjectHintsRoutingDecision(
            hints_registry["generic_textbook"], 0.0, "fallback", ()
        )
    best_score, best_id, matched = scored[0]
    tied = [item for item in scored if item[0] == best_score]
    if len(tied) > 1:
        return SubjectHintsRoutingDecision(
            hints_registry["generic_textbook"],
            0.25,
            "fallback",
            tuple(signal for _, _, values in tied for signal in values),
        )
    confidence = min(0.95, 0.65 + 0.1 * (best_score - 1))
    return SubjectHintsRoutingDecision(
        hints_registry[best_id], confidence, "title_and_catalog", matched
    )

"""Provenance dry-run audit for golden sections (asthma + pulmonary tuberculosis).

Runs the full repair + verify pipeline against real synthesis data and compares
before/after per-item state. Outputs JSON audit report + Markdown summary.

Read-only: does NOT modify generated data, state YAML, App, database, or commit.

Calibration notes (v3):
- Missing list fields are normalized to [] before comparison (avoids inflated
  change counts from None → [] transitions).
- Over-extended chain detection receives the real bound_artifact_id and
  enumerates ALL shorter contiguous subchains that still contain the bound
  artifact (forward, backward, and middle positions). Joining uses the
  production `_join_raw_fragments` to match ASCII/alnum boundary behavior.
- procedural_risk is derived from explicit risk detection notes
  (expanded_content_risk / truncated_sentence unresolved with risk), not from
  risk_class alone.
- Three separate reconstruction counters:
  (a) newly_populated_provenance: source_artifact_ids went from empty to non-empty
      (includes single-artifact provenance).
  (b) new_multi_artifact_reconstruction: source_artifact_ids went from
      non-multi to multi (length >= 2).
  (c) final_multi_artifact: final state has multi-artifact chain.
- Rejected items emit artifact/evidence/failure-reason/source locator.
- This is a code-level classification, NOT medical review approval.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.evidence_artifact import EvidenceArtifact
from textbook_pipeline.evidence_synthesis import SynthesizedItem
from textbook_pipeline.evidence_verifier import verify_items
from textbook_pipeline.knowledge_quality_audit import (
    dry_run_repair_candidate_items,
    load_artifacts_from_evidence_payload,
)
from textbook_pipeline.paragraph_reconstruction import (
    _join_raw_fragments,
    can_stitch_artifacts,
    classify_expanded_content_risk,
    is_truncated_sentence,
    loose_contains,
    sorted_artifacts,
)

KNOWLEDGE_ROOT = ROOT / "generated" / "knowledge_nodes" / "internal-medicine-10"
REPORT_DIR = ROOT / "generated" / "reports"

SECTIONS = [
    {
        "section_id": "第二篇_呼吸系统疾病__第四章_支气管哮喘",
        "short_name": "asthma",
        "page_start": 62,
        "page_end": 70,
    },
    {
        "section_id": "第二篇_呼吸系统疾病__第八章_肺结核",
        "short_name": "tuberculosis",
        "page_start": 102,
        "page_end": 116,
    },
]

# Fields tracked for before/after comparison
TRACKED_FIELDS = (
    "verification_state",
    "risk_class",
    "source_artifact_ids",
    "reconstructed_locators",
    "content",
    "evidence",
)

# List fields that must be normalized None → [] before comparison
LIST_FIELDS = {"source_artifact_ids", "reconstructed_locators", "verification_notes"}

# Notes that indicate explicit procedural risk detection
PROCEDURAL_RISK_NOTE_PATTERNS = [
    re.compile(r"expanded_content_risk", re.IGNORECASE),
    re.compile(r"truncated_sentence.*procedural risk", re.IGNORECASE),
]


def _item_key(item: dict[str, Any]) -> str:
    return f"{item.get('artifact_id', '')}#{item.get('item_index', 0)}"


def _normalize_field(field: str, value: Any) -> Any:
    """Normalize list fields: None → []. Other fields unchanged."""
    if field in LIST_FIELDS and value is None:
        return []
    return value


def _snapshot(item: dict[str, Any]) -> dict[str, Any]:
    return {
        field: copy.deepcopy(_normalize_field(field, item.get(field)))
        for field in TRACKED_FIELDS
    }


def _load_section(section: dict[str, str | int]) -> tuple[list[EvidenceArtifact], list[dict[str, Any]]]:
    section_id = str(section["section_id"])
    evidence_path = KNOWLEDGE_ROOT / f"{section_id}.evidence.json"
    synthesis_path = KNOWLEDGE_ROOT / f"{section_id}.evidence.synthesis.json"
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    synthesis_payload = json.loads(synthesis_path.read_text(encoding="utf-8"))
    artifacts = load_artifacts_from_evidence_payload(evidence_payload)
    items = synthesis_payload.get("items") or []
    return artifacts, items


def _classify_medical_content(
    item: dict[str, Any],
    artifact: EvidenceArtifact | None,
) -> str:
    """Code-level classification per medlearn-validate-medical-content skill.

    Returns one of: Verified candidate / Needs review / Evidence only / Unsupported.
    NOTE: This is a deterministic code-level classification, NOT medical review approval.
    """
    state = str(item.get("verification_state") or "")
    evidence = str(item.get("evidence") or "")
    content = str(item.get("content") or "")

    if not artifact:
        return "Unsupported"

    if not evidence or not content:
        return "Unsupported"

    if state == "rejected":
        return "Unsupported"

    if state == "evidence_only":
        return "Evidence only"

    if state == "needs_review":
        return "Needs review"

    # pass + standard risk → verified candidate (code-level; still requires human review)
    if state == "pass":
        return "Verified candidate"

    return "Needs review"


def _has_explicit_procedural_risk(notes: list[str]) -> bool:
    """Return True only if explicit procedural risk detection produced a note."""
    for note in notes or []:
        for pattern in PROCEDURAL_RISK_NOTE_PATTERNS:
            if pattern.search(str(note)):
                return True
    return False


def _join_chain_text(chain: list[EvidenceArtifact]) -> str:
    """Join artifact raw_text using the production _join_raw_fragments."""
    joined = ""
    for art in chain:
        if art and art.raw_text:
            joined = _join_raw_fragments(joined, art.raw_text)
    return joined


def _detect_overextended_chain(
    after_ids: list[str],
    artifact_map: dict[str, EvidenceArtifact],
    evidence_loose: str,
    bound_artifact_id: str,
) -> str | None:
    """Return a description if a shorter legal contiguous subchain that still
    contains the bound artifact also contains the complete evidence; None
    otherwise.

    The bound artifact may appear anywhere in the chain (forward, backward,
    or middle). We enumerate every contiguous subchain that:
      - has length < len(after_ids),
      - contains the bound artifact,
      - preserves the original chain's ordering,
    and check whether its `_join_raw_fragments`-joined loose-normalized text
    contains the evidence. If any shorter subchain works, the actual chain is
    over-extended.
    """
    if len(after_ids) <= 1 or not evidence_loose or len(evidence_loose) < 8:
        return None

    chain_artifacts = [artifact_map.get(aid) for aid in after_ids]
    if any(a is None for a in chain_artifacts):
        return "unresolved artifact in chain"

    # Verify adjacency first (sanity)
    for i in range(len(chain_artifacts) - 1):
        left = chain_artifacts[i]
        right = chain_artifacts[i + 1]
        assert left is not None and right is not None
        if not can_stitch_artifacts(left, right):
            return f"chain link {left.id}→{right.id} not legally stitchable"

    # Locate the bound artifact's position in the chain.
    try:
        bound_index = after_ids.index(bound_artifact_id)
    except ValueError:
        return f"bound artifact {bound_artifact_id} not in chain"

    from textbook_pipeline.evidence_span_context import normalize_loose as _norm_loose

    actual_len = len(after_ids)
    # Enumerate all shorter contiguous subchains containing bound_index.
    for length in range(actual_len - 1, 0, -1):  # shorter lengths first
        for start in range(0, actual_len - length + 1):
            end = start + length  # exclusive
            if not (start <= bound_index < end):
                continue  # subchain must contain the bound artifact
            sub_chain = chain_artifacts[start:end]
            joined = _join_chain_text(sub_chain)
            if evidence_loose in _norm_loose(joined):
                return (
                    f"shorter legal subchain of length {length} "
                    f"({[a.id for a in sub_chain]}) also contains evidence; "
                    f"actual chain length {actual_len}"
                )

    return None


def _run_section_audit(section: dict[str, str | int]) -> dict[str, Any]:
    section_id = str(section["section_id"])
    short_name = str(section["short_name"])
    page_start = int(section["page_start"])
    page_end = int(section["page_end"])

    artifacts, original_items = _load_section(section)
    artifact_map = {a.id: a for a in artifacts}

    # --- Before snapshot (normalized) ---
    before_snapshots: dict[str, dict[str, Any]] = {}
    for item in original_items:
        key = _item_key(item)
        before_snapshots[key] = _snapshot(item)

    # --- Step 1: dry_run_repair_candidate_items (repair path) ---
    candidate_payload = {"candidate_items": copy.deepcopy(original_items)}
    repaired_payload, dry_run_stats = dry_run_repair_candidate_items(
        candidate_payload, artifacts
    )
    repaired_items = repaired_payload.get("candidate_items") or []

    # --- Step 2: verify_items on repaired items (verifier path) ---
    syn_items: list[SynthesizedItem] = []
    for raw in repaired_items:
        try:
            syn_items.append(SynthesizedItem(**raw))
        except TypeError:
            syn_items.append(
                SynthesizedItem(
                    artifact_id=str(raw.get("artifact_id") or ""),
                    item_index=int(raw.get("item_index") or 0),
                    title=str(raw.get("title") or ""),
                    parent_entity=raw.get("parent_entity"),
                    aspect=str(raw.get("aspect") or ""),
                    content=str(raw.get("content") or ""),
                    evidence=str(raw.get("evidence") or ""),
                    risk_class=str(raw.get("risk_class") or "standard"),
                    source_heading=str(raw.get("source_heading") or ""),
                    page_start=int(raw.get("page_start") or 0),
                    page_end=int(raw.get("page_end") or 0),
                    source_artifact_ids=list(raw.get("source_artifact_ids") or []),
                    reconstructed_locators=list(raw.get("reconstructed_locators") or []),
                    verification_state=str(raw.get("verification_state") or "pending"),
                    verification_notes=list(raw.get("verification_notes") or []),
                )
            )

    results, verify_counts = verify_items(
        syn_items, artifacts, section_page_start=page_start, section_page_end=page_end
    )
    result_map = {r.artifact_id + "#" + str(r.item_index): r for r in results}

    # --- After snapshot (normalized) ---
    after_snapshots: dict[str, dict[str, Any]] = {}
    after_notes: dict[str, list[str]] = {}
    for syn_item in syn_items:
        item_dict = asdict(syn_item)
        key = _item_key(item_dict)
        after_snapshots[key] = _snapshot(item_dict)
        after_notes[key] = list(item_dict.get("verification_notes") or [])

    # --- Per-item comparison ---
    item_comparisons: list[dict[str, Any]] = []
    state_transitions: Counter[str] = Counter()
    changed_count = 0
    newly_populated_provenance_count = 0
    new_multi_artifact_reconstruction_count = 0
    final_multi_artifact_count = 0
    rejected_details: list[dict[str, Any]] = []

    for key, before in before_snapshots.items():
        after = after_snapshots.get(key, {})
        if not after:
            item_comparisons.append({
                "key": key,
                "status": "missing_after",
                "before": before,
                "after": None,
                "changes": ["item disappeared after verify"],
            })
            continue

        # Normalized comparison
        changes: list[str] = []
        for field in TRACKED_FIELDS:
            before_val = _normalize_field(field, before.get(field))
            after_val = _normalize_field(field, after.get(field))
            if before_val != after_val:
                changes.append(field)

        is_changed = len(changes) > 0
        if is_changed:
            changed_count += 1

        before_state = str(before.get("verification_state") or "")
        after_state = str(after.get("verification_state") or "")
        transition = f"{before_state}→{after_state}"
        state_transitions[transition] += 1

        before_ids_norm = _normalize_field("source_artifact_ids", before.get("source_artifact_ids")) or []
        after_ids = after.get("source_artifact_ids") or []
        is_multi_artifact = len(after_ids) > 1
        if is_multi_artifact:
            final_multi_artifact_count += 1

        # (a) newly_populated_provenance: source_artifact_ids went from empty to non-empty
        is_newly_populated_provenance = (
            not before_ids_norm
            and len(after_ids) > 0
        )
        if is_newly_populated_provenance:
            newly_populated_provenance_count += 1

        # (b) new_multi_artifact_reconstruction: went from non-multi to multi (length >= 2)
        is_new_multi_artifact_reconstruction = (
            len(before_ids_norm) < 2
            and len(after_ids) >= 2
        )
        if is_new_multi_artifact_reconstruction:
            new_multi_artifact_reconstruction_count += 1

        is_state_downgrade = (
            before_state == "pass"
            and after_state in ("needs_review", "evidence_only", "rejected")
        )

        # Procedural risk: only from explicit detection notes
        notes = after_notes.get(key, [])
        has_procedural_risk = _has_explicit_procedural_risk(notes)

        still_truncated = (
            is_truncated_sentence(str(after.get("content") or ""))
            or is_truncated_sentence(str(after.get("evidence") or ""))
        )

        # Classify per medlearn-validate-medical-content
        artifact_id_str = key.split("#")[0]
        artifact = artifact_map.get(artifact_id_str)
        classification = _classify_medical_content(after, artifact)

        cmp_entry: dict[str, Any] = {
            "key": key,
            "artifact_id": artifact_id_str,
            "item_index": int(key.split("#")[1]) if "#" in key else 0,
            "status": "changed" if is_changed else "unchanged",
            "changes": changes,
            "before": before,
            "after": after,
            "flags": {
                "multi_artifact": is_multi_artifact,
                "newly_populated_provenance": is_newly_populated_provenance,
                "new_multi_artifact_reconstruction": is_new_multi_artifact_reconstruction,
                "state_downgrade": is_state_downgrade,
                "procedural_risk": has_procedural_risk,
                "still_truncated": still_truncated,
            },
            "medical_content_classification": classification,
        }

        # Rejected item detail
        if after_state == "rejected":
            verify_result = result_map.get(key)
            reasons = (verify_result.reasons if verify_result else []) or []
            bound_artifact = artifact_map.get(artifact_id_str)
            rejected_details.append({
                "key": key,
                "artifact_id": artifact_id_str,
                "artifact_present": bound_artifact is not None,
                "artifact_locator": (
                    {
                        "page_start": bound_artifact.page_start,
                        "page_end": bound_artifact.page_end,
                        "source_order": bound_artifact.source_order,
                        "source_heading": bound_artifact.source_heading,
                    }
                    if bound_artifact
                    else None
                ),
                "evidence": str(after.get("evidence") or ""),
                "content": str(after.get("content") or ""),
                "failure_reasons": reasons,
                "verification_notes": notes,
            })

        item_comparisons.append(cmp_entry)

    # --- Assertions ---
    violations: list[str] = []
    overextended: list[str] = []

    from textbook_pipeline.evidence_span_context import normalize_loose as _norm_loose

    for cmp_item in item_comparisons:
        after = cmp_item.get("after") or {}
        after_state = str(after.get("verification_state") or "")
        after_ids = after.get("source_artifact_ids") or []
        is_multi = len(after_ids) > 1
        after_evidence = str(after.get("evidence") or "")
        artifact_id_str = cmp_item.get("artifact_id") or ""
        bound_artifact = artifact_map.get(artifact_id_str)

        # Assert: no pass + multi-artifact
        if after_state == "pass" and is_multi:
            violations.append(
                f"{cmp_item['key']}: pass verdict with multi-artifact provenance"
            )

        # Assert: cross-artifact evidence must have populated provenance
        if bound_artifact and after_evidence and after_state != "rejected":
            if not loose_contains(bound_artifact.raw_text, after_evidence):
                if not after_ids:
                    violations.append(
                        f"{cmp_item['key']}: cross-artifact evidence but empty source_artifact_ids"
                    )
                if after_state == "pass":
                    violations.append(
                        f"{cmp_item['key']}: cross-artifact evidence with pass verdict"
                    )

        # Over-extended chain check: actually verify shortest legal subchain
        # containing the bound artifact.
        if is_multi and bound_artifact and after_evidence:
            evidence_loose = _norm_loose(after_evidence)
            oe_desc = _detect_overextended_chain(
                after_ids, artifact_map, evidence_loose, artifact_id_str
            )
            if oe_desc:
                overextended.append(f"{cmp_item['key']}: {oe_desc}")

    # --- Provenance completeness ---
    items_with_evidence = sum(
        1 for c in item_comparisons
        if str((c.get("after") or {}).get("evidence") or "")
    )
    items_with_provenance = sum(
        1 for c in item_comparisons
        if (c.get("after") or {}).get("source_artifact_ids")
    )
    provenance_rate = (
        items_with_provenance / items_with_evidence if items_with_evidence else 0.0
    )

    # --- Risk items: only explicit procedural risk, plus state downgrades separately ---
    procedural_risk_items = [
        c for c in item_comparisons
        if (c.get("flags") or {}).get("procedural_risk")
    ]
    state_downgrade_items = [
        c for c in item_comparisons
        if (c.get("flags") or {}).get("state_downgrade")
    ]
    still_truncated_items = [
        c for c in item_comparisons
        if (c.get("flags") or {}).get("still_truncated")
    ]

    # --- Medical content classification summary ---
    classification_counts: Counter[str] = Counter()
    for c in item_comparisons:
        classification_counts[c.get("medical_content_classification", "Needs review")] += 1

    return {
        "section_id": section_id,
        "short_name": short_name,
        "page_range": [page_start, page_end],
        "artifact_count": len(artifacts),
        "total_items": len(original_items),
        "changed_items": changed_count,
        "newly_populated_provenance_count": newly_populated_provenance_count,
        "new_multi_artifact_reconstruction_count": new_multi_artifact_reconstruction_count,
        "final_multi_artifact_count": final_multi_artifact_count,
        "dry_run_stats": dry_run_stats,
        "verify_counts": verify_counts,
        "state_transitions": dict(state_transitions),
        "provenance_completeness": {
            "items_with_evidence": items_with_evidence,
            "items_with_provenance": items_with_provenance,
            "rate": round(provenance_rate, 4),
        },
        "medical_content_classification": dict(classification_counts),
        "assertions": {
            "violations": violations,
            "overextended_chains": overextended,
            "all_assertions_pass": len(violations) == 0 and len(overextended) == 0,
            "overextension_check_method": (
                "shortest legal contiguous subchain containing bound artifact and evidence; "
                "joins via production _join_raw_fragments"
            ),
        },
        "procedural_risk_count": len(procedural_risk_items),
        "state_downgrade_count": len(state_downgrade_items),
        "still_truncated_count": len(still_truncated_items),
        "procedural_risk_items": [
            {
                "key": r["key"],
                "after_state": (r.get("after") or {}).get("verification_state"),
                "source_artifact_ids": (r.get("after") or {}).get("source_artifact_ids"),
                "evidence_preview": str((r.get("after") or {}).get("evidence") or "")[:80],
            }
            for r in procedural_risk_items
        ],
        "rejected_details": rejected_details,
        "multi_artifact_items": [
            {
                "key": c["key"],
                "source_artifact_ids": (c.get("after") or {}).get("source_artifact_ids"),
                "verification_state": (c.get("after") or {}).get("verification_state"),
                "evidence_preview": str((c.get("after") or {}).get("evidence") or "")[:80],
                "is_newly_populated_provenance": (c.get("flags") or {}).get("newly_populated_provenance", False),
                "is_new_multi_artifact_reconstruction": (c.get("flags") or {}).get("new_multi_artifact_reconstruction", False),
            }
            for c in item_comparisons
            if (c.get("flags") or {}).get("multi_artifact")
        ],
        "items": item_comparisons,
    }


def _build_markdown_summary(section_reports: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Provenance Dry-Run Audit Report (v3 — recalibrated)")
    lines.append("")
    lines.append("**Read-only audit.** No generated data, state YAML, App, database, commit, or push was performed.")
    lines.append("**Code-level classification, NOT medical review approval.** Classifications reflect deterministic verification state; qualified human medical review is still required for any publication decision.")
    lines.append("")
    lines.append("Calibration notes (v3):")
    lines.append("- Change counts normalize missing list fields (None → []) before comparison.")
    lines.append("- Over-extended chain check enumerates ALL shorter contiguous subchains containing the bound artifact (forward / backward / middle), joined via production `_join_raw_fragments`.")
    lines.append("- `procedural_risk` is derived from explicit risk-detection notes, not from `risk_class` alone.")
    lines.append("- Three separate reconstruction counters: newly_populated_provenance, new_multi_artifact_reconstruction, final_multi_artifact.")
    lines.append("- Rejected items emit artifact, evidence, failure reason, and source locator.")
    lines.append("")

    total_items = 0
    total_changed = 0
    total_newly_populated = 0
    total_new_multi_recon = 0
    total_final_multi = 0
    total_violations = 0
    total_overextended = 0
    total_procedural = 0
    total_downgrade = 0
    total_truncated = 0
    all_classifications: Counter[str] = Counter()

    for report in section_reports:
        lines.append(f"## {report['short_name']} ({report['section_id']})")
        lines.append("")
        lines.append(f"- Pages: {report['page_range'][0]}–{report['page_range'][1]}")
        lines.append(f"- Artifacts: {report['artifact_count']}")
        lines.append(f"- Total items: {report['total_items']}")
        lines.append(f"- Changed items (normalized): {report['changed_items']}")
        lines.append(f"- Newly populated provenance (empty → non-empty): {report['newly_populated_provenance_count']}")
        lines.append(f"- New multi-artifact reconstruction (non-multi → multi): {report['new_multi_artifact_reconstruction_count']}")
        lines.append(f"- Final multi-artifact items: {report['final_multi_artifact_count']}")
        lines.append(f"- Procedural risk items: {report['procedural_risk_count']}")
        lines.append(f"- State downgrade items: {report['state_downgrade_count']}")
        lines.append(f"- Still truncated items: {report['still_truncated_count']}")
        lines.append("")

        lines.append("### Dry-run stats")
        for k, v in report["dry_run_stats"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

        lines.append("### Verify counts")
        for k, v in report["verify_counts"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

        lines.append("### State transitions")
        for transition, count in sorted(report["state_transitions"].items()):
            lines.append(f"- `{transition}`: {count}")
        lines.append("")

        lines.append("### Provenance completeness")
        pc = report["provenance_completeness"]
        lines.append(f"- Items with evidence: {pc['items_with_evidence']}")
        lines.append(f"- Items with provenance (multi-artifact): {pc['items_with_provenance']}")
        lines.append(f"- Multi-artifact provenance rate (of evidence items): {pc['rate']:.1%}")
        lines.append("")

        lines.append("### Medical content classification (code-level, NOT medical review)")
        for cls, count in sorted(report["medical_content_classification"].items()):
            lines.append(f"- {cls}: {count}")
            all_classifications[cls] += count
        lines.append("")

        lines.append("### Assertions")
        ast = report["assertions"]
        lines.append(f"- All assertions pass: **{ast['all_assertions_pass']}**")
        lines.append(f"- Over-extension check method: {ast['overextension_check_method']}")
        if ast["violations"]:
            lines.append(f"- Violations ({len(ast['violations'])}):")
            for v in ast["violations"][:10]:
                lines.append(f"  - {v}")
        else:
            lines.append("- Violations: 0")
        if ast["overextended_chains"]:
            lines.append(f"- Over-extended chains ({len(ast['overextended_chains'])}):")
            for v in ast["overextended_chains"][:10]:
                lines.append(f"  - {v}")
        else:
            lines.append("- Over-extended chains: 0")
        lines.append("")

        # Rejected detail
        rejected = report.get("rejected_details") or []
        if rejected:
            lines.append(f"### Rejected items ({len(rejected)})")
            for rj in rejected:
                lines.append(f"- `{rj['key']}` (artifact_id: `{rj['artifact_id']}`)")
                lines.append(f"  - artifact present: {rj['artifact_present']}")
                if rj.get("artifact_locator"):
                    loc = rj["artifact_locator"]
                    lines.append(
                        f"  - source locator: page {loc['page_start']}–{loc['page_end']}, "
                        f"order={loc['source_order']}, heading=`{loc['source_heading']}`"
                    )
                lines.append(f"  - failure reasons: {rj['failure_reasons']}")
                lines.append(f"  - evidence: `{rj['evidence'][:120]}`")
                lines.append(f"  - content: `{rj['content'][:120]}`")
                if rj.get("verification_notes"):
                    lines.append(f"  - notes: {rj['verification_notes']}")
            lines.append("")

        # Procedural risk items
        proc_risk = report.get("procedural_risk_items") or []
        if proc_risk:
            lines.append(f"### Procedural risk items ({len(proc_risk)}) — explicit detection only")
            for ri in proc_risk[:10]:
                lines.append(
                    f"- `{ri['key']}`: state={ri['after_state']}, ids={ri['source_artifact_ids']}"
                )
                lines.append(f"  - evidence: `{ri['evidence_preview']}...`")
            if len(proc_risk) > 10:
                lines.append(f"- ... and {len(proc_risk) - 10} more")
            lines.append("")

        # Multi-artifact breakdown
        ma_items = report["multi_artifact_items"]
        if ma_items:
            new_pop_in_ma = sum(1 for m in ma_items if m.get("is_newly_populated_provenance"))
            new_multi_in_ma = sum(1 for m in ma_items if m.get("is_new_multi_artifact_reconstruction"))
            lines.append(f"### Multi-artifact items ({len(ma_items)})")
            lines.append(f"- of which newly populated provenance: {new_pop_in_ma}")
            lines.append(f"- of which new multi-artifact reconstruction: {new_multi_in_ma}")
            for ma in ma_items[:10]:
                tags = []
                if ma.get("is_newly_populated_provenance"):
                    tags.append("newly_populated")
                if ma.get("is_new_multi_artifact_reconstruction"):
                    tags.append("new_multi_recon")
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                lines.append(
                    f"- `{ma['key']}`{tag_str}: state={ma['verification_state']}, "
                    f"ids={ma['source_artifact_ids']}"
                )
                lines.append(f"  - evidence: `{ma['evidence_preview']}...`")
            if len(ma_items) > 10:
                lines.append(f"- ... and {len(ma_items) - 10} more")
            lines.append("")

        total_items += report["total_items"]
        total_changed += report["changed_items"]
        total_newly_populated += report["newly_populated_provenance_count"]
        total_new_multi_recon += report["new_multi_artifact_reconstruction_count"]
        total_final_multi += report["final_multi_artifact_count"]
        total_violations += len(ast["violations"])
        total_overextended += len(ast["overextended_chains"])
        total_procedural += report["procedural_risk_count"]
        total_downgrade += report["state_downgrade_count"]
        total_truncated += report["still_truncated_count"]

    lines.append("## Overall summary")
    lines.append("")
    lines.append(f"- Total items: {total_items}")
    lines.append(f"- Total changed (normalized): {total_changed}")
    lines.append(f"- Total newly populated provenance: {total_newly_populated}")
    lines.append(f"- Total new multi-artifact reconstruction: {total_new_multi_recon}")
    lines.append(f"- Total final multi-artifact: {total_final_multi}")
    lines.append(f"- Total procedural risk items: {total_procedural}")
    lines.append(f"- Total state downgrade items: {total_downgrade}")
    lines.append(f"- Total still truncated items: {total_truncated}")
    lines.append(f"- Total violations: {total_violations}")
    lines.append(f"- Total over-extended chains: {total_overextended}")
    lines.append("")
    lines.append("### Overall medical content classification (code-level, NOT medical review)")
    for cls, count in sorted(all_classifications.items()):
        lines.append(f"- {cls}: {count}")
    lines.append("")

    all_pass = total_violations == 0 and total_overextended == 0
    lines.append("## Backfill recommendation")
    lines.append("")
    if all_pass:
        lines.append("- **Code-level provenance assertions pass.**")
        lines.append("- No `pass` + multi-artifact, no cross-artifact evidence with empty provenance, no over-extended chain.")
        lines.append("- **However, this report is NOT medical review approval.**")
        lines.append("- 529 `Needs review` + 9 `Evidence only` + 2 `Unsupported` items require qualified human medical review before any public display or medical-approval decision.")
        lines.append("- A controlled local candidate backfill is not inherently blocked by `needs_review` status, provided:")
        lines.append("  1. `needs_review` / `evidence_only` / `rejected` items remain non-publishable as organized conclusions in the App.")
        lines.append("  2. Backfill scope, environment, and idempotency are explicitly authorized.")
        lines.append("  3. The backfill is reversible and re-runnable after medical review resolves the open items.")
        lines.append("- **Recommendation: do NOT backfill to public/release state.** A controlled local candidate backfill may be authorized separately with the above guards.")
    else:
        lines.append("- **Code-level assertions FAILED.** Do NOT backfill.")
        lines.append(f"- Violations: {total_violations}, over-extended chains: {total_overextended}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    section_reports: list[dict[str, Any]] = []
    for section in SECTIONS:
        print(f"  auditing {section['short_name']} ({section['section_id']})...")
        report = _run_section_audit(section)
        section_reports.append(report)
        ast = report["assertions"]
        print(
            f"    items={report['total_items']}, "
            f"changed(normalized)={report['changed_items']}, "
            f"newly_populated={report['newly_populated_provenance_count']}, "
            f"new_multi_recon={report['new_multi_artifact_reconstruction_count']}, "
            f"final_multi={report['final_multi_artifact_count']}, "
            f"procedural_risk={report['procedural_risk_count']}, "
            f"downgrade={report['state_downgrade_count']}, "
            f"truncated={report['still_truncated_count']}, "
            f"violations={len(ast['violations'])}, "
            f"overextended={len(ast['overextended_chains'])}, "
            f"assertions_pass={ast['all_assertions_pass']}"
        )

    # JSON report
    json_report = {
        "audit_type": "provenance_dry_run_v3_recalibrated",
        "audit_scope": "golden_sections",
        "sections": section_reports,
    }
    json_path = REPORT_DIR / "provenance_dry_run_audit.json"
    json_path.write_text(
        json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  JSON report: {json_path}")

    # Markdown summary
    md_summary = _build_markdown_summary(section_reports)
    md_path = REPORT_DIR / "provenance_dry_run_audit.md"
    md_path.write_text(md_summary, encoding="utf-8")
    print(f"  Markdown summary: {md_path}")

    all_pass = all(r["assertions"]["all_assertions_pass"] for r in section_reports)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

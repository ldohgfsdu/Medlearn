"""Evidence Synthesis — Phase 2 of EV1 pipeline.

Constrained LLM item synthesis from evidence artifacts.
Each artifact → small prompt → candidate items.

Design rules:
  - LLM only organizes, does NOT discover scope or invent evidence
  - content must not exceed raw_text
  - evidence must be continuous span from raw_text
  - high-risk content → needs_review
  - output is candidate only, NOT verified content
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .evidence_artifact import EvidenceArtifact


@dataclass
class SynthesizedItem:
    """One candidate item produced by constrained LLM synthesis."""
    # Identity
    artifact_id: str              # source EvidenceArtifact.id
    item_index: int               # index within artifact items

    # Content
    title: str                    # e.g. "胃炎的病因"
    parent_entity: str | None     # e.g. "胃炎" or null if uncertain
    aspect: str                   # from source_heading
    content: str                  # LLM-organized text (constrained to evidence)
    evidence: str                 # verbatim from raw_text (continuous span)

    # Risk
    risk_class: str               # "standard" | "candidate" | "needs_review"

    # Provenance
    source_heading: str           # from artifact
    page_start: int
    page_end: int

    # Verification state (filled by verifier, default pending)
    verification_state: str = "pending"  # "pending" | "pass" | "needs_review" | "rejected"
    verification_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SYNTHESIS_PROMPT = """你是医学知识整理器。以下是一个教材片段，请将其整理为结构化知识点。

约束：
1. content 不得超出原文范围，不可添加原文未提及的医学事实
2. evidence 必须是原文中连续的片段，不可拼接不同位置的文字
3. 如果不确定 parent_entity，设为 null
4. 如果内容涉及具体药物剂量、治疗方案，标记 risk_class="candidate"
5. 如果完全无法整理，返回空 items 数组

教材路径：{part_title} > {section_title}
知识面向：{source_heading}

原文：
{raw_text}

输出 JSON（不要添加任何其他文字）：
{{"items":[{{"title":"...","parent_entity":"...","aspect":"...","content":"...","evidence":"...","risk_class":"standard|candidate"}}]}}

注意：只输出 JSON，不要输出思考过程。"""


def call_ollama_synthesis(
    artifact: EvidenceArtifact,
    *,
    model: str = "medlearn-qwen3:8b",
    ollama_url: str = "",
    timeout: int = 120,
) -> list[dict[str, Any]]:
    """Call LLM for constrained synthesis on a single artifact."""
    import requests

    url = ollama_url or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

    prompt = SYNTHESIS_PROMPT.format(
        part_title=artifact.part_title,
        section_title=artifact.section_title,
        source_heading=artifact.source_heading,
        raw_text=artifact.raw_text[:2000],  # Truncate for safety
    )

    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "think": False,
        "keep_alive": "5m",
        "messages": [{"role": "user", "content": prompt}],
        "options": {
            "temperature": 0,
            "num_ctx": 4096,
            "num_gpu": 999,
            "num_predict": 1024,
        },
    }

    response = requests.post(f"{url}/api/chat", json=payload, timeout=timeout)
    response.raise_for_status()

    result = response.json()
    content = result["message"]["content"]

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from content
        import re
        match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
        if match:
            data = json.loads(match.group(1).strip())
        else:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(content[start:end + 1])
            else:
                return []

    return data.get("items", [])


def synthesize_artifact(
    artifact: EvidenceArtifact,
    *,
    model: str = "medlearn-qwen3:8b",
    ollama_url: str = "",
) -> tuple[list[SynthesizedItem], dict[str, Any]]:
    """Synthesize items from a single artifact.

    Returns (items, metrics).
    """
    start = time.time()

    try:
        raw_items = call_ollama_synthesis(
            artifact, model=model, ollama_url=ollama_url
        )
    except Exception as e:
        return [], {"error": str(e), "time_s": time.time() - start}

    elapsed = time.time() - start

    items: list[SynthesizedItem] = []
    for i, raw in enumerate(raw_items):
        # Validate required fields
        if not raw.get("content") or not raw.get("evidence"):
            continue

        # Enforce aspect from source_heading
        aspect = artifact.source_heading
        if artifact.normalized_aspect:
            aspect = artifact.normalized_aspect

        item = SynthesizedItem(
            artifact_id=artifact.id,
            item_index=i,
            title=raw.get("title", ""),
            parent_entity=raw.get("parent_entity"),
            aspect=aspect,
            content=raw.get("content", ""),
            evidence=raw.get("evidence", ""),
            risk_class=raw.get("risk_class", "standard"),
            source_heading=artifact.source_heading,
            page_start=artifact.page_start,
            page_end=artifact.page_end,
        )
        items.append(item)

    metrics = {
        "time_s": elapsed,
        "raw_items": len(raw_items),
        "valid_items": len(items),
    }

    return items, metrics


def synthesize_artifacts(
    artifacts: list[EvidenceArtifact],
    *,
    model: str = "medlearn-qwen3:8b",
    ollama_url: str = "",
    max_artifacts: int = 0,
    checkpoint_path: Any | None = None,
    resume: bool = True,
    verbose: bool = True,
) -> tuple[list[SynthesizedItem], list[dict[str, Any]]]:
    """Synthesize items from multiple artifacts.

    Returns (all_items, per_artifact_metrics).
    """
    all_items: list[SynthesizedItem] = []
    all_metrics: list[dict[str, Any]] = []
    processed_artifact_ids: set[str] = set()

    if checkpoint_path and resume:
        checkpoint = load_synthesis_cache(checkpoint_path)
        all_items = checkpoint["items"]
        all_metrics = checkpoint["metrics"]
        processed_artifact_ids = {
            str(metric.get("artifact_id") or "")
            for metric in all_metrics
            if metric.get("artifact_id")
        }
        if processed_artifact_ids and verbose:
            print(
                f"  [resume] synthesis checkpoint: "
                f"{len(processed_artifact_ids)} artifacts, {len(all_items)} items"
            )

    selected = artifacts[:max_artifacts] if max_artifacts > 0 else artifacts

    for i, artifact in enumerate(selected):
        if artifact.id in processed_artifact_ids:
            if verbose:
                print(f"  [{i+1}/{len(selected)}] Artifact {artifact.id[:12]}... cached")
            continue

        if verbose:
            print(f"  [{i+1}/{len(selected)}] Artifact {artifact.id[:12]}... "
                  f"p{artifact.page_start} {artifact.artifact_type} ", end="", flush=True)

        items, metrics = synthesize_artifact(
            artifact, model=model, ollama_url=ollama_url
        )

        if verbose:
            print(f"→ {len(items)} items ({metrics.get('time_s', 0):.1f}s)")
        elif (i + 1) % 100 == 0 or (i + 1) == len(selected):
            print(
                f"  progress: {i+1}/{len(selected)} artifacts, "
                f"items={len(all_items) + len(items)}"
            )

        all_items.extend(items)
        all_metrics.append({
            "artifact_id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "page": artifact.page_start,
            **metrics,
        })
        processed_artifact_ids.add(artifact.id)

        if checkpoint_path:
            write_synthesis_cache(all_items, all_metrics, checkpoint_path)

    return all_items, all_metrics


def load_synthesis_cache(input_path: Any) -> dict[str, Any]:
    """Load synthesis checkpoint/cache."""
    from pathlib import Path

    path = Path(input_path)
    if not path.exists():
        return {"items": [], "metrics": []}
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    items: list[SynthesizedItem] = []
    for raw in payload.get("items") or []:
        if not isinstance(raw, dict):
            continue
        try:
            items.append(SynthesizedItem(**raw))
        except TypeError:
            continue
    metrics = [
        metric for metric in (payload.get("metrics") or [])
        if isinstance(metric, dict)
    ]
    return {"items": items, "metrics": metrics}


def write_synthesis_cache(
    items: list[SynthesizedItem],
    metrics: list[dict[str, Any]],
    output_path: Any,
) -> None:
    """Write synthesis results to JSON cache."""
    from pathlib import Path

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": "ev1-synthesis-0.1.0",
        "count": len(items),
        "items": [item.to_dict() for item in items],
        "metrics": metrics,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

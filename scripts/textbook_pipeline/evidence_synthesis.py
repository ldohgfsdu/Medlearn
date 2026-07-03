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
import unicodedata
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
    risk_class: str               # "standard" | "needs_review"; legacy "candidate" is downgraded by verifier

    # Provenance
    source_heading: str           # from artifact
    page_start: int
    page_end: int
    source_artifact_ids: list[str] = field(default_factory=list)
    reconstructed_locators: list[dict[str, Any]] = field(default_factory=list)

    # Verification state (filled by verifier, default pending)
    verification_state: str = "pending"  # "pending" | "pass" | "needs_review" | "rejected" | "evidence_only"
    verification_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SYNTHESIS_PROMPT = """你是医学教材知识抽取器。任务是把下面的教材片段整理成可查阅的候选知识点。

总原则：
1. 只根据“原文”抽取，不补充、不解释、不改写教材没有明说的内容。
2. evidence 必须是原文中的连续原文片段，不能拼接不同位置的文字。
3. content 必须被 evidence 直接支持；优先写成 evidence 中的连续短句或极小幅度去标点整理。
4. 禁止把标题、上位疾病名、知识面向、表头、图题、单位说明补进 content，除非这些文字也连续出现在 evidence 中。
5. 禁止把表格/图注压缩成推断性句子；如果表格行列关系不清，返回空 items，让系统展示原始证据。
6. 如果只能概括、同义改写、跨句合并、补全省略主语，返回空 items。
7. risk_class 判定规则：
    a) 标记为 "needs_review"：涉及治疗剂量、给药方案、手术/操作步骤、适应证、禁忌证、首选/优先级推荐——这些直接影响临床决策。
    b) 标记为 "standard"：涉及教材中的诊断标准阈值（如 FEV1/FVC<70%、PEF 变异率>10%）、分级分度数值（轻/中/重度标准）、参考范围、分类截断值——这些属于教材知识陈述，不构成临床处方。
    c) 无法判断时默认 "standard"。
8. 如果不确定 parent_entity，设为 null。

字段要求：
- title：简短名词短语，可概括该条内容，但不能伪造教材结构。
- parent_entity：原文明确指向的疾病/概念；不确定则 null。
- aspect：由系统填充，模型输出会被忽略。
- content：可用于学习卡片的精确内容，不能超过 evidence。
- evidence：原文连续片段，必须足以支持 content。
- risk_class："standard" 或 "needs_review"。

教材路径：{part_title} > {section_title}
知识面向：{source_heading}

原文：
{raw_text}

输出 JSON（不要添加任何其他文字）：
{{"items":[{{"title":"...","parent_entity":"...","aspect":"...","content":"...","evidence":"...","risk_class":"standard|needs_review"}}]}}

注意：只输出 JSON，不要输出思考过程。"""


def _normalize_loose(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    return "".join(
        char.lower()
        for char in normalized
        if unicodedata.category(char)[0] not in {"C", "P", "Z"}
    )


def _loose_contains(haystack: str, needle: str) -> bool:
    normalized_needle = _normalize_loose(needle)
    if not normalized_needle:
        return False
    return normalized_needle in _normalize_loose(haystack)


def raw_item_is_source_supported(raw: dict[str, Any], artifact: EvidenceArtifact) -> tuple[bool, str]:
    """Reject LLM items that exceed their declared source span."""
    content = str(raw.get("content") or "")
    evidence = str(raw.get("evidence") or "")
    if not content or not evidence:
        return False, "missing_content_or_evidence"
    if not _loose_contains(artifact.raw_text, evidence):
        return False, "evidence_not_in_source"
    if not _loose_contains(evidence, content):
        return False, "content_not_supported_by_evidence"
    return True, ""


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
    skipped_reasons: dict[str, int] = {}
    for i, raw in enumerate(raw_items):
        # Validate required fields
        supported, reason = raw_item_is_source_supported(raw, artifact)
        if not supported:
            skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
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
        "skipped_items": sum(skipped_reasons.values()),
        "skipped_reasons": skipped_reasons,
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

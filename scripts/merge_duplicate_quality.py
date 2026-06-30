"""Quality gates for duplicate disease-aspect merge plans."""

from __future__ import annotations

import re
from typing import Any

ASPECT_TITLE_CONFLICTS: dict[str, tuple[str, ...]] = {
    "临床表现": ("影像学", "影像表现", "危险因素", "病史", "诊断", "治疗", "预防", "检查"),
    "临床特征": ("影像学", "危险因素", "病史", "诊断", "治疗", "预防"),
    "诊断": ("鉴别诊断", "治疗", "预防"),
    "诊断方法": ("鉴别诊断", "治疗", "预防"),
    "病因": ("预防", "治疗", "诊断"),
    "病因和发病机制": ("预防", "治疗"),
    "发病机制": ("治疗", "诊断", "预防"),
    "治疗": ("诊断", "预防", "病因"),
    "治疗方案": ("诊断", "预防", "病因"),
}

TRUNCATED_TAIL_RE = re.compile(
    r"(?:或|和|及|以及|包括|如|为|是|有|伴|并|但|而|且|与|在|对|从|向|把|被|将|要|可|应|需|待)\s*$"
)


def strip_redundant_title_prefix(title: str, content: str) -> str:
    title = title.strip()
    content = content.strip()
    if not title or not content:
        return content
    for separator in ("：", ":"):
        prefix = f"{title}{separator}"
        if content.startswith(prefix):
            return content[len(prefix) :].strip()
    if content.startswith(title):
        remainder = content[len(title) :].lstrip()
        for lead in ("：", ":", "包含", "包括", "是为", "为", "是"):
            if remainder.startswith(lead):
                return remainder[len(lead) :].lstrip()
    return content


def normalize_body_text(title: str, content: str) -> str:
    return re.sub(r"\s+", "", strip_redundant_title_prefix(title, content))


def is_truncated_content(content: str) -> bool:
    text = content.strip()
    if not text:
        return False
    if text[-1] in "。！？；.!?;」』\"”%％）)":
        return False
    if TRUNCATED_TAIL_RE.search(text):
        return True
    return False


def aspect_title_conflicts(group_aspect: str, section_title: str) -> list[str]:
    markers = ASPECT_TITLE_CONFLICTS.get(group_aspect, ())
    hits = [marker for marker in markers if marker in section_title]
    if "鉴别诊断" in section_title and group_aspect in {"诊断", "诊断方法", "诊断与鉴别诊断"}:
        if "鉴别诊断" not in hits:
            hits.append("鉴别诊断")
    return hits


def read_parent_entity(node: dict[str, Any]) -> str:
    source_span = node.get("source_span") or {}
    if not isinstance(source_span, dict):
        return ""
    return str(source_span.get("parent_entity") or "").strip()


def section_entity_from_title(title: str) -> str:
    title = title.strip()
    if "的" in title:
        return title.split("的", 1)[0].strip()
    return title


def entities_compatible(left: str, right: str) -> bool:
    if not left or not right:
        return True
    if left == right:
        return True
    return left in right or right in left


def entity_attribution_conflicts(
    group_parent: str,
    members: list[dict[str, Any]],
    sections: list[dict[str, str]] | None = None,
    *,
    group_aspect: str = "",
) -> list[str]:
    if not group_parent:
        return []
    issues: list[str] = []
    for node in members:
        parent_entity = read_parent_entity(node)
        if not parent_entity or parent_entity == group_parent:
            continue
        if entities_compatible(parent_entity, group_parent):
            continue
        issues.append(f"{node.get('id')}: parent_entity={parent_entity}")

    if group_aspect == "鉴别诊断":
        return list(dict.fromkeys(issues))

    for section in sections or []:
        title = str(section.get("title") or "").strip()
        if "的" not in title or title.endswith("的鉴别诊断"):
            continue
        section_entity = section_entity_from_title(title)
        if entities_compatible(section_entity, group_parent):
            continue
        issues.append(f"section_title:{title}: entity={section_entity}")
    return list(dict.fromkeys(issues))


def duplicate_body_conflicts(sections: list[dict[str, str]]) -> list[str]:
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for section in sections:
        title = str(section.get("title") or "").strip()
        content = str(section.get("content") or "").strip()
        normalized = normalize_body_text(title, content)
        if not normalized:
            continue
        previous = seen.get(normalized)
        if previous:
            conflicts.append(f"{previous} == {title}")
        seen[normalized] = title
    return conflicts


def sanitize_sections(sections: list[dict[str, str]]) -> list[dict[str, str]]:
    sanitized: list[dict[str, str]] = []
    for section in sections:
        title = str(section.get("title") or "").strip()
        content = strip_redundant_title_prefix(title, str(section.get("content") or "").strip())
        sanitized.append({"title": title, "content": content})
    return sanitized


def render_merged_content(sections: list[dict[str, str]]) -> str:
    return "\n\n".join(
        f"{index}. {section['title']}\n{section['content']}"
        for index, section in enumerate(sections, start=1)
    )


def assess_merge_group(
    *,
    group_aspect: str,
    group_parent: str,
    members: list[dict[str, Any]],
    sections: list[dict[str, str]],
) -> list[str]:
    blockers: list[str] = []

    for section in sections:
        title = str(section.get("title") or "").strip()
        content = str(section.get("content") or "").strip()
        for marker in aspect_title_conflicts(group_aspect, title):
            blockers.append(f"aspect_title_conflict:{title}:{marker}")
        if is_truncated_content(content):
            blockers.append(f"truncated_sentence:{title}")

    for issue in entity_attribution_conflicts(
        group_parent,
        members,
        sections,
        group_aspect=group_aspect,
    ):
        blockers.append(f"entity_attribution_conflict:{issue}")

    for issue in duplicate_body_conflicts(sections):
        blockers.append(f"duplicate_body:{issue}")

    return list(dict.fromkeys(blockers))
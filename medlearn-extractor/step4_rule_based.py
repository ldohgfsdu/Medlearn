"""Step 4 (Rule-based): Structurize knowledge points using regex rules.

Replaces LLM structurization with pattern-based extraction.
Chinese medical textbooks use consistent headings:
  【病因和发病机制】【病理】【临床表现】
  【实验室和其他检查】【诊断与鉴别诊断】【治疗】【预后】

Zero API cost, instant processing.
"""

import json
import re
import sys

from rich.console import Console
from rich.panel import Panel

import config

console = Console()

# ── Dimension section markers ──────────────────────────────────────
# Ordered by expected appearance in textbook text
SECTION_PATTERNS = [
    ("etiology_pathogenesis", re.compile(
        r"【病因和发病机制】|【病因】|【病因与发病机制】|【病因及发病机制】"
    )),
    ("pathology", re.compile(
        r"【病理】|【病理解剖】|【病理生理】|【病理改变】|【病理学】"
    )),
    ("manifestation", re.compile(
        r"【临床表现】|【临床特点】|【临床症状】|【症状与体征】"
    )),
    ("examination", re.compile(
        r"【实验室[和与及]?[特殊辅助其他]*检查】|【辅助检查】|【实验室检查】|【影像学检查】"
    )),
    ("diagnosis", re.compile(
        r"【诊断[与和及]?[鉴别]*[诊断]*】|【诊断标准】|【诊断要点】|【鉴别诊断】"
    )),
    ("treatment", re.compile(
        r"【治疗】|【治疗原则】|【治疗方案】|【处理】"
    )),
    ("prognosis", re.compile(
        r"【预后】|【转归】|【病程与预后】|【预防】"
    )),
]

VINDICATE_CATEGORIES = [
    ("vascular", ["血管", "动脉", "静脉", "血栓", "栓塞", "梗死", "缺血", "出血", "高血压"]),
    ("infectious", ["感染", "细菌", "病毒", "真菌", "结核", "寄生虫", "脓肿", "脓", "炎症"]),
    ("neoplastic", ["肿瘤", "癌", "瘤", "恶性", "转移", "占位", "淋巴瘤", "白血病"]),
    ("drug", ["药物", "中毒", "过敏", "药", "毒素", "化学"]),
    ("inflammatory", ["炎症", "自身免疫", "免疫", "风湿", "红斑狼疮", "结节病", "过敏"]),
    ("congenital", ["先天", "遗传", "基因", "家族", "发育异常", "畸形"]),
    ("autoimmune", ["自身抗体", "自身免疫", "免疫复合物", "补体", "狼疮", "类风湿"]),
    ("traumatic", ["外伤", "创伤", "损伤", "手术", "骨折", "撞击"]),
    ("endocrine", ["内分泌", "激素", "甲状腺", "肾上腺", "垂体", "糖尿病", "代谢"]),
]

DEFINITION_RE = re.compile(
    r"(?:【定义】|定义[：:]?\s*)?"
    r"((?:.{2,40}?(?:简称|又称|也称|俗称).{2,40}?)?"
    r".{2,40}?(?:是指|是一种|是|指|称为|即为|定义为|指的就是|主要指)"
    r".{10,500}?[。])"
)

CLEANUP_RES = [
    re.compile(r"^第[一二三四五六七八九十百零0-9]+[章节篇]\s*.*$", re.MULTILINE),
    re.compile(r"^本章数字资源\s*$", re.MULTILINE),
    re.compile(r"^思考题[：:]?\s*$", re.MULTILINE),
    re.compile(r"^本章思维导图\s*$", re.MULTILINE),
    re.compile(r"^图\d+[-–—].*$", re.MULTILINE),
    re.compile(r"^表\d+[-–—].*$", re.MULTILINE),
]

KEYWORD_STOP_WORDS = {
    "病人", "患者", "疾病", "治疗", "诊断", "检查", "症状", "表现",
    "发生", "包括", "主要", "一般", "常见", "用于", "其中", "可以",
    "可能", "相关", "引起", "出现", "具有", "进行", "通过", "作用",
    "一种", "目前", "临床", "研究", "方法", "显著", "明显",
    "的", "和", "与", "或", "等", "及", "在", "为", "中",
}

def _clean_text(text: str) -> str:
    """Remove noise: page markers, chapter headers, figure/table captions."""
    text = re.sub(r"--- Page \d+ ---", "", text)
    for pattern in CLEANUP_RES:
        text = pattern.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_sections(text: str) -> tuple[str, dict[str, str]]:
    """Split text into pre-section intro and dimension sections.

    Returns (intro_text, {dimension_name: section_text})
    """
    sections: dict[str, str] = {}
    matches = []
    for dim_name, pattern in SECTION_PATTERNS:
        for m in pattern.finditer(text):
            matches.append((m.start(), dim_name))

    if not matches:
        return text, sections

    matches.sort(key=lambda x: x[0])

    before = text[:matches[0][0]]
    for i, (pos, dim_name) in enumerate(matches):
        end_pos = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        section_text = text[pos:end_pos]
        # Remove the heading itself
        section_text = SECTION_PATTERNS[0][1].sub("", section_text, count=1)
        for _, pat in SECTION_PATTERNS:
            section_text = pat.sub("", section_text, count=1)
        section_text = section_text.strip()
        if section_text:
            if dim_name in sections:
                sections[dim_name] += "\n" + section_text
            else:
                sections[dim_name] = section_text

    return before.strip(), sections


def _extract_definition(text: str, name: str) -> str:
    """Extract definition sentence from text."""
    flat_text = text.replace("\n", "")
    escaped_name = re.escape(name)
    patterns = [
        re.compile(rf"{escaped_name}\s*(?:[（(][^)）]*[)）])?\s*(?:简称\S+)?[，,。]*\s*(?:是指|是一种|是|指|即|为一|为一组|为一类)(.{{10,500}}?)[。]"),
        re.compile(rf"{escaped_name}\s*(?:又称|亦称|也称|又名)\s*\S+?[，,。]*\s*(?:是指|是一种|是|指|即)(.{{10,500}}?)[。]"),
    ]
    for pat in patterns:
        m = pat.search(flat_text[:2500])
        if m:
            matched = m.group(0).strip()
            return f"{name}{matched[len(name):]}" if matched.startswith(name) else matched

    m = DEFINITION_RE.search(flat_text[:2500])
    if m:
        return m.group(1).strip()

    for line in flat_text[:500].split("\n"):
        line = line.strip()
        if len(line) > 20 and any(kw in line for kw in ["是指", "是一种", "是", "指", "称为", "即"]):
            return line[:300]
    return "教材中未详细展开"


def _extract_keywords(text: str, name: str, sections: dict[str, str]) -> list[str]:
    """Extract medical keywords from the text.

    Focuses on high-quality, precise terms:
    1. English abbreviations (e.g. COPD, IgE, GWAS)
    2. Medical terms with English equivalents (e.g. 气道高反应性（AHR）)
    3. Named diseases/syndromes with clear boundaries
    """
    keywords = []
    seen = set()

    def add(kw):
        kw = kw.strip()
        if len(kw) < 2 or len(kw) > 25:
            return
        if kw in KEYWORD_STOP_WORDS:
            return
        if kw in seen:
            return
        seen.add(kw)
        keywords.append(kw)

    # 1. Terms with English abbreviations in parentheses
    for m in re.finditer(r"([\u4e00-\u9fff]{2,15})[（(]([A-Z]{2,10})[)）]", text[:5000]):
        add(m.group(1))
        add(m.group(2))

    # 2. Well-formed disease names: prefix + body part/descriptor + suffix
    well_formed_disease = re.compile(
        r"(?:^|[，,。；;、\s（(])"
        r"((?:慢性|急性|原发性|继发性|特发性|先天性|获得性|遗传性|"
        r"弥漫性|局灶性|系统性|进行性|发作性|过敏性|化脓性|感染性)?"
        r"[\u4e00-\u9fff]{3,8}"
        r"(?:综合征|梗死|栓塞|衰竭|坏死|水肿|中毒|哮喘|气胸|贫血|结核|休克|昏迷))"
    )
    for m in well_formed_disease.finditer(text[:3000]):
        term = m.group(1)
        if len(term) >= 5:
            add(term)

    # 3. Medical biomarkers, receptors, genes
    bio_term = re.compile(
        r"(?:^|[，,。；;、\s（(])"
        r"([\u4e00-\u9fff]{3,8}(?:因子|蛋白|基因|受体|通道|抗体|抗原|激素|酶|细胞))"
    )
    for m in bio_term.finditer(text[:3000]):
        term = m.group(1)
        add(term)

    return keywords[:15]


def _extract_aliases(text: str, name: str) -> list[str]:
    """Extract aliases/alternative names from text."""
    aliases = []
    patterns = [
        re.compile(rf"{re.escape(name)}\s*简称\s*(\S+?)[，,。\s]"),
        re.compile(rf"{re.escape(name)}\s*又称\s*(\S+?)[，,。\s]"),
        re.compile(r"简称\s*(\S+?)[，,。\s]"),
        re.compile(r"又称\s*(\S+?)[，,。\s]"),
        re.compile(r"亦称\s*(\S+?)[，,。\s]"),
    ]
    for pat in patterns:
        for m in pat.finditer(text[:2000]):
            alias = m.group(1).strip()
            alias = re.sub(r"[（(][^)）]*[)）]", "", alias)
            if alias and len(alias) > 1 and alias != name:
                aliases.append(alias)
    return list(dict.fromkeys(aliases))[:5]


def _extract_key_points(text: str, sections: dict[str, str]) -> list[str]:
    """Extract key learning points from bulleted/numbered lists."""
    points = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩]", line):
            points.append(re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*", "", line))
        elif re.match(r"^[（(]\d+[）)]\s+", line):
            points.append(re.sub(r"^[（(]\d+[）)]\s+", "", line))
        elif re.match(r"^\d+[.、,．]\s+", line) and len(line) > 10:
            points.append(re.sub(r"^\d+[.、,．]\s+", "", line))
    if not points:
        for line in lines[:20]:
            line = line.strip()
            if len(line) > 15 and len(line) < 200:
                if any(kw in line for kw in ["特点", "特征", "重要", "关键", "必须", "注意", "主要"]):
                    points.append(line)
                    if len(points) >= 3:
                        break
    return points[:8]


def _build_vindicate(text: str, sections: dict[str, str], name: str) -> dict[str, str]:
    """Build VINDICATE differential diagnosis from text."""
    dd_text = sections.get("diagnosis", "")
    if not dd_text:
        dd_text = text

    result = {}
    for category, tokens in VINDICATE_CATEGORIES:
        candidates = []
        for token in tokens:
            if token in dd_text:
                idx = dd_text.find(token)
                start = max(0, idx - 30)
                end = min(len(dd_text), idx + 80)
                snippet = dd_text[start:end].replace("\n", " ").strip()
                candidates.append(snippet)

        # Try to find disease names in the diagnosis text
        disease_names = re.findall(
            r"(?:慢性|急性|原发性|继发性|特发性|先天性)?"
            r"[\u4e00-\u9fff]{2,4}"
            r"(?:病|炎|癌|瘤|症|综合征|衰竭|梗死|栓塞|中毒|肿)(?!.*\d)",
            dd_text[:3000]
        )
        relevant_diseases = []
        for d in disease_names:
            for token in tokens:
                if token in dd_text and abs(dd_text.find(d) - dd_text.find(token)) < 200:
                    relevant_diseases.append(d)
                    break

        if relevant_diseases:
            result[category] = f"需与以下疾病鉴别：{'、'.join(relevant_diseases[:5])}"
        elif candidates:
            result[category] = candidates[0][:100]
        else:
            result[category] = "教材中未详细展开"

    return result


def _extract_common_misconceptions(text: str, name: str) -> list[str]:
    """Extract potential common misconceptions from text."""
    misconceptions = []
    patterns = [
        re.compile(r"注意.{5,80}[。；]"),
        re.compile(r"容易误诊.{5,80}[。；]"),
        re.compile(r"需与.{5,80}鉴别[。；]"),
        re.compile(r"不应.{5,80}[。；]"),
        re.compile(r"并非.{5,80}[。；]"),
        re.compile(r"临床上.{5,30}误区.{5,80}[。；]"),
    ]
    for pat in patterns:
        for m in pat.finditer(text[:3000]):
            mc = m.group(0).strip()
            if len(mc) > 10:
                misconceptions.append(mc)
    if not misconceptions:
        misconceptions = ["教材中未明确提及常见误区"]
    return misconceptions[:3]


def structurize_one(kp: dict) -> dict:
    """Structurize a single knowledge point using regex rules."""
    name = kp["name"]
    kp_type = kp.get("type", "disease")
    text = kp.get("extracted_text", "")

    if not text or kp.get("status") != "success":
        kp["structured"] = None
        kp["structurize_status"] = "skipped: no text"
        return kp

    cleaned = _clean_text(text)
    if len(cleaned) < 50:
        kp["structured"] = None
        kp["structurize_status"] = "skipped: text too short"
        return kp

    intro, sections = _split_sections(cleaned)

    aliases = _extract_aliases(cleaned, name)
    keywords = _extract_keywords(cleaned, name, sections)
    key_points = _extract_key_points(cleaned, sections)
    definition = _extract_definition(intro + "\n" + cleaned[:500], name)
    common_misconceptions = _extract_common_misconceptions(cleaned, name)
    vindicate = _build_vindicate(cleaned, sections, name)

    etiology_pathogenesis_text = sections.get("etiology_pathogenesis", "教材中未详细展开")
    if etiology_pathogenesis_text == "教材中未详细展开":
        etiology_text = "教材中未详细展开"
        pathogenesis_text = "教材中未详细展开"
    else:
        etiology_text = etiology_pathogenesis_text[:2000]
        pathogenesis_text = etiology_pathogenesis_text[2000:4000] if len(etiology_pathogenesis_text) > 2000 else "教材中未详细展开"

    structured = {
        "definition": definition,
        "etiology": etiology_text,
        "pathogenesis": pathogenesis_text,
        "pathology": sections.get("pathology", "教材中未详细展开")[:2000],
        "manifestation": sections.get("manifestation", "教材中未详细展开")[:2000],
        "examination": sections.get("examination", "教材中未详细展开")[:2000],
        "diagnosis": sections.get("diagnosis", "教材中未详细展开")[:2000],
        "treatment": sections.get("treatment", "教材中未详细展开")[:2000],
        "prognosis": sections.get("prognosis", "教材中未详细展开")[:2000],
        "aliases": aliases,
        "keywords": keywords,
        "vindicate": vindicate,
        "key_points": key_points,
        "common_misconceptions": common_misconceptions,
    }

    kp["structured"] = structured
    kp["structurize_status"] = "success"
    return kp


def structurize_knowledge(blocks_path: str, output_path: str) -> None:
    """Read blocks and structurize each knowledge point."""
    console.rule("[bold blue]Step 4: Structurize Knowledge (Rule-based)")

    with open(blocks_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])
    console.print(f"📝 Total knowledge points to structurize: {len(kps)}")
    console.print(f"⚡ Using regex rule engine (zero API cost, instant processing)")

    results = []
    success = 0
    skipped = 0
    failed = 0

    for i, kp in enumerate(kps):
        result = structurize_one(kp)
        results.append(result)

        status = result.get("structurize_status", "")
        if status == "success":
            success += 1
        elif "skipped" in status:
            skipped += 1
        else:
            failed += 1

        if (i + 1) % 50 == 0:
            console.print(f"   Progress: {i + 1}/{len(kps)} (success: {success}, skipped: {skipped})")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"knowledge_points": results}, f, ensure_ascii=False, indent=2)

    # Dimension coverage stats
    dim_coverage = {}
    for dim in ["definition", "etiology", "pathogenesis", "pathology", "manifestation",
                "examination", "diagnosis", "treatment", "prognosis"]:
        filled = sum(
            1 for r in results
            if r.get("structured") and r["structured"].get(dim, "") not in ("", "教材中未详细展开")
        )
        dim_coverage[dim] = filled

    console.print(Panel.fit(
        f"[green]✓[/green] Structured saved to: {output_path}\n"
        f"[green]✓[/green] Success: {success}\n"
        f"[yellow]⊘[/yellow] Skipped: {skipped}\n"
        f"[red]✗[/red] Failed: {failed}\n\n"
        + "Dimension coverage:\n" +
        "\n".join(f"  {dim}: {count}/{success} ({count/success*100:.0f}%)" if success else f"  {dim}: 0"
                   for dim, count in dim_coverage.items()),
        title="Structurize Complete (Rule-based)",
        border_style="green" if failed == 0 else "yellow",
    ))


if __name__ == "__main__":
    structurize_knowledge(str(config.BLOCKS_JSON), str(config.STRUCTURED_JSON))

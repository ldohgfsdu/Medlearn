#!/usr/bin/env python3
"""Audit display contracts for OCR-fragment pollution in top-level titles.

Scans generated/display_contracts/internal-medicine-10/*.json and flags
top-level titles (part_title, section_title, and each node's display.title)
that look like OCR fragments: empty titles, single-character / over-short
titles, titles containing characters outside the legitimate medical-text
character set (e.g. U+FFFD, private-use area, control chars, box-drawing /
geometric symbols), or pure-symbol titles.

The allowed character set for a title is: Chinese (CJK), Greek letters (used
in medical terms such as β2 / γ-干扰素), Latin letters including accented ones
(used in medical eponyms such as Sézary / Ménétrier), any Unicode number
(Nd/Nl/No — includes Roman numerals Ⅰ Ⅱ and circled digits), any punctuation
(P*), math symbols (Sm — covers +, ±, ×, ≥), separators, and a small
whitelist of scientific symbols (°, ℃, ℉). These are legitimate scientific /
medical notation, not OCR fragments. True garbage — replacement chars,
private-use glyphs, control chars, box-drawing / dingbats, exotic-script
letters, etc. — is still flagged.

Output: a summary is printed to stdout and a markdown report is written to
generated/reports/display_contract_ocr_pollution_audit.md.

Exit code: 1 if any pollution is found, 0 otherwise. (Parse errors are
reported but do not by themselves flip the exit code, per the task spec.)

Optional CLI args: one or more display-contract file paths (absolute or
repo-relative). When omitted, the whole default directory is scanned.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DC_DIR = ROOT / "generated/display_contracts/internal-medicine-10"
REPORT_PATH = ROOT / "generated/reports/display_contract_ocr_pollution_audit.md"

# Titles whose stripped length is <= this are treated as OCR fragments.
SHORT_TITLE_MAX_LEN = 1

# Golden-path validation targets, surfaced explicitly in the report.
GOLDEN_PATH_KEYWORDS = ("哮喘", "肺结核")


def is_chinese_char(c: str) -> bool:
    cp = ord(c)
    return (
        0x4E00 <= cp <= 0x9FFF       # CJK Unified Ideographs
        or 0x3400 <= cp <= 0x4DBF    # CJK Unified Ideographs Extension A
        or 0xF900 <= cp <= 0xFAFF    # CJK Compatibility Ideographs
        or 0x20000 <= cp <= 0x2A6DF  # CJK Unified Ideographs Extension B
    )


def is_greek_char(c: str) -> bool:
    # Greek and Coptic (α β γ δ …) — legitimate in medical terms.
    return 0x0370 <= ord(c) <= 0x03FF


def is_latin_letter(c: str) -> bool:
    # ASCII letters + Latin-1 Supplement (À..ÿ, covers é/è/ü/ö/ñ…) + Latin
    # Extended-A/B (Ā..ɏ). Accented Latin letters appear in medical eponyms
    # such as Sézary 综合征 and Ménétrier 病 and are not OCR pollution.
    if ("a" <= c <= "z") or ("A" <= c <= "Z"):
        return True
    cp = ord(c)
    return (0x00C0 <= cp <= 0x00FF) or (0x0100 <= cp <= 0x024F)


def is_number(c: str) -> bool:
    # Nd (decimal), Nl (Roman numerals Ⅰ Ⅱ), No (circled digits ① ②, ½, ²).
    return unicodedata.category(c).startswith("N")


def is_punctuation(c: str) -> bool:
    return unicodedata.category(c).startswith("P")


def is_math_symbol(c: str) -> bool:
    # Sm covers +, ±, ×, ÷, ≥, ≤, =, ≠, ≈, →, … — scientific notation.
    return unicodedata.category(c) == "Sm"


def is_separator(c: str) -> bool:
    return c.isspace() or unicodedata.category(c).startswith("Z")


# Symbol-other chars that are legitimate in medical text but are category So
# (not P/Sm). Box-drawing, geometric shapes, dingbats, U+FFFD, etc. are NOT
# whitelisted and will still be flagged.
ALLOWED_SO_WHITELIST = frozenset({0x00B0, 0x2103, 0x2109})  # °, ℃, ℉


def is_allowed_char(c: str) -> bool:
    return (
        is_chinese_char(c)
        or is_greek_char(c)
        or is_latin_letter(c)
        or is_number(c)
        or is_punctuation(c)
        or is_math_symbol(c)
        or is_separator(c)
        or ord(c) in ALLOWED_SO_WHITELIST
    )


def has_text_content(c: str) -> bool:
    # Letters or numbers count as textual content (not pure symbols).
    return (
        is_chinese_char(c)
        or is_greek_char(c)
        or is_latin_letter(c)
        or is_number(c)
    )


def char_name(c: str) -> str:
    try:
        return unicodedata.name(c)
    except ValueError:
        return "<no name>"


def audit_title(title: str) -> list[dict]:
    """Return a list of pollution issues for the given title."""
    issues: list[dict] = []
    stripped = (title or "").strip()
    if not stripped:
        issues.append({"rule": "empty", "detail": "标题为空或仅空白"})
        return issues
    if len(stripped) <= SHORT_TITLE_MAX_LEN:
        issues.append(
            {"rule": "too_short", "detail": f"单字/过短标题（长度={len(stripped)}）"}
        )
    bad = [c for c in stripped if not is_allowed_char(c)]
    if bad:
        uniq = sorted(set(bad))
        desc = ", ".join(f"U+{ord(c):04X} '{c}' ({char_name(c)})" for c in uniq)
        issues.append(
            {"rule": "disallowed_chars", "detail": f"含非中文/英文/数字/标点字符: {desc}"}
        )
    if not any(has_text_content(c) for c in stripped):
        issues.append({"rule": "pure_symbols", "detail": "标题仅由符号/标点构成"})
    return issues


def collect_titles(contract: dict) -> list[tuple[str, str, str]]:
    """Return (scope, locator, title) tuples for top-level titles.

    scope:   'part_title' | 'section_title' | 'node_title'
    locator: node id for node titles, '' for root-level titles
    """
    items: list[tuple[str, str, str]] = []
    part = contract.get("part_title")
    if isinstance(part, str):
        items.append(("part_title", "", part))
    sec = contract.get("section_title")
    if isinstance(sec, str):
        items.append(("section_title", "", sec))
    for node in contract.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        display = node.get("display")
        if not isinstance(display, dict):
            continue
        title = display.get("title")
        if title is None:
            continue
        node_id = node.get("id", "?")
        items.append(("node_title", str(node_id), str(title)))
    return items


def audit_file(path: Path) -> dict:
    result = {
        "file": path.name,
        "path": str(path.relative_to(ROOT)) if __relative(path, ROOT) else str(path),
        "parse_error": None,
        "titles_checked": 0,
        "findings": [],
    }
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # report any parse failure instead of crashing
        result["parse_error"] = f"{type(exc).__name__}: {exc}"
        return result
    for scope, locator, title in collect_titles(contract):
        result["titles_checked"] += 1
        issues = audit_title(title)
        if issues:
            result["findings"].append(
                {"scope": scope, "locator": locator, "title": title, "issues": issues}
            )
    return result


def __relative(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def render_stdout(results: list[dict]) -> None:
    files = len(results)
    parse_errors = [r for r in results if r["parse_error"]]
    polluted = [r for r in results if r["findings"]]
    titles_checked = sum(r["titles_checked"] for r in results)
    finding_count = sum(len(r["findings"]) for r in results)

    print("=" * 64)
    print("Display Contract OCR 碎片污染审计")
    print("=" * 64)
    print(f"扫描目录: generated/display_contracts/internal-medicine-10/")
    print(f"扫描文件数: {files}")
    print(f"解析失败文件数: {len(parse_errors)}")
    print(f"检查顶层标题数: {titles_checked}")
    print(f"污染标题数: {finding_count}")
    print(f"有污染的文件数: {len(polluted)}")
    print(f"结论: {'❌ 发现 OCR 碎片污染' if polluted else '✅ 未发现 OCR 碎片污染'}")

    if parse_errors:
        print("\n--- 解析失败 ---")
        for r in parse_errors:
            print(f"  · {r['file']}: {r['parse_error']}")

    if polluted:
        print("\n--- 污染明细（按文件） ---")
        for r in polluted:
            print(f"\n[{r['file']}]")
            for f in r["findings"]:
                loc = (
                    f"[{f['scope']}]"
                    if not f["locator"]
                    else f"[{f['scope']} id={f['locator']}]"
                )
                rules = ", ".join(i["rule"] for i in f["issues"])
                print(f'  · {loc} "{f["title"]}" -> {rules}')
                for i in f["issues"]:
                    print(f"      - {i['rule']}: {i['detail']}")

    print("\n--- Golden Path 验证目标 ---")
    for r in results:
        if any(k in r["file"] for k in GOLDEN_PATH_KEYWORDS):
            ok = not r["findings"] and not r["parse_error"]
            status = "✅ 无顶层污染" if ok else "❌ 有顶层污染/异常"
            print(f"  · {r['file']}: {status} (检查 {r['titles_checked']} 个顶层标题)")


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_markdown(results: list[dict]) -> str:
    files = len(results)
    parse_errors = [r for r in results if r["parse_error"]]
    polluted = [r for r in results if r["findings"]]
    titles_checked = sum(r["titles_checked"] for r in results)
    finding_count = sum(len(r["findings"]) for r in results)
    verdict = "❌ 发现 OCR 碎片污染" if polluted else "✅ 未发现 OCR 碎片污染"

    lines: list[str] = []
    lines.append("# Display Contract OCR 碎片污染审计报告")
    lines.append("")
    lines.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("- 扫描目录: `generated/display_contracts/internal-medicine-10/`")
    lines.append("- 检测范围: 顶层标题（`part_title`、`section_title`、各节点 `display.title`）")
    lines.append("")
    lines.append("## 检测规则")
    lines.append("")
    lines.append("| 规则 | 说明 |")
    lines.append("|------|------|")
    lines.append("| `empty` | 标题为空或仅空白 |")
    lines.append("| `too_short` | 去空白后长度 ≤ 1 的标题（单字标题，疑似 OCR 碎片） |")
    lines.append(
        "| `disallowed_chars` | 含合法医学字符集以外的字符"
        "（合法集合：中文、希腊字母、拉丁字母含变音符号、数字 N*、标点 P*、"
        "数学符号 Sm、空白，以及 °/℃/℉；会捕获 U+FFFD、私有区、控制符、"
        "制表/几何/装饰符号及异国脚本字母等） |"
    )
    lines.append("| `pure_symbols` | 标题仅由标点/符号构成，无中文、英文字母或数字 |")
    lines.append("")
    lines.append("## 摘要")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|----|")
    lines.append(f"| 扫描文件数 | {files} |")
    lines.append(f"| 解析失败文件数 | {len(parse_errors)} |")
    lines.append(f"| 检查顶层标题数 | {titles_checked} |")
    lines.append(f"| 污染标题数 | {finding_count} |")
    lines.append(f"| 有污染的文件数 | {len(polluted)} |")
    lines.append(f"| 结论 | {verdict} |")
    lines.append("")

    if parse_errors:
        lines.append("## 解析失败")
        lines.append("")
        for r in parse_errors:
            lines.append(f"- `{r['file']}`: {r['parse_error']}")
        lines.append("")

    lines.append("## 污染明细")
    lines.append("")
    if not polluted:
        lines.append("未发现顶层 OCR 碎片污染。")
        lines.append("")
    else:
        for r in polluted:
            lines.append(f"### `{r['file']}`")
            lines.append("")
            lines.append("| 范围 | 定位 | 标题 | 问题明细 |")
            lines.append("|------|------|------|---------|")
            for f in r["findings"]:
                loc = "—" if not f["locator"] else f"`{f['locator']}`"
                detail = "; ".join(f"`{i['rule']}`: {i['detail']}" for i in f["issues"])
                lines.append(
                    f"| {f['scope']} | {loc} | {_md_escape(f['title'])} | {_md_escape(detail)} |"
                )
            lines.append("")

    lines.append("## Golden Path 验证目标")
    lines.append("")
    any_target = False
    for r in results:
        if any(k in r["file"] for k in GOLDEN_PATH_KEYWORDS):
            any_target = True
            ok = not r["findings"] and not r["parse_error"]
            status = "✅ 无顶层污染" if ok else "❌ 有顶层污染/异常"
            lines.append(
                f"- `{r['file']}`: {status}（检查 {r['titles_checked']} 个顶层标题）"
            )
    if not any_target:
        lines.append("（未在扫描范围内找到哮喘/肺结核 display contract。）")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = argv[1:]
    if args:
        files: list[Path] = []
        for a in args:
            p = Path(a)
            if not p.is_absolute():
                p = (ROOT / a).resolve()
            if p.is_file():
                files.append(p)
        files = sorted(set(files))
    else:
        files = sorted(DEFAULT_DC_DIR.glob("*.json"))

    if not files:
        print(f"未找到 display contract 文件: {DEFAULT_DC_DIR}")
        return 2

    results = [audit_file(f) for f in files]
    render_stdout(results)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_markdown(results), encoding="utf-8")
    print(f"\n报告已写入: {REPORT_PATH.relative_to(ROOT)}")

    has_pollution = any(r["findings"] for r in results)
    return 1 if has_pollution else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

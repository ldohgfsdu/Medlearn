#!/usr/bin/env python
"""Validate agent contract consistency across skills, router, and checklists.

Checks (errors by default; warnings only fail under --strict):
  ERROR  1. Every SKILL.md has valid YAML frontmatter (name + description).
  ERROR  2. Skill `name` matches its directory name.
  ERROR  3. All paths referenced in SKILL.md backticks exist.
  ERROR  4. Every skill referenced in TASK_ROUTER.yaml exists.
  ERROR  5. Every checklist referenced in TASK_ROUTER.yaml and SKILL.md exists.
  ERROR  6. Router routes have required fields (skill, triggers).
  ERROR  7. `also_apply` skills exist.
  ERROR  8. Training evaluator command examples include required --base-model/--adapter.
  ERROR  9. Checklists do not embed drift-prone counts (regex: N refs / N locators).
  ERROR 10. No skill hardcodes RGBA in component guidance (should reference tokens).
  ERROR 11. All paths in TASK_ROUTER.yaml `read` lists exist.
  ERROR 12. All paths in TASK_ROUTER.yaml `default.read` list exist.
  ERROR 13. All backtick paths in checklists/*.md exist.
  WARN  14. Router routes should declare `priority` explicitly (defaults to 50).
  WARN  15. Router routes should declare `inherits_default` explicitly (defaults to true).

Exit codes: 0 = clean; 1 = violations; 2 = environment error.

Run:
    python scripts/validate_agent_contracts.py
    python scripts/validate_agent_contracts.py --strict  # warnings become errors
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = PROJECT_ROOT / ".agents" / "skills"
ROUTER_PATH = PROJECT_ROOT / "context" / "TASK_ROUTER.yaml"
CHECKLISTS_DIR = PROJECT_ROOT / "checklists"


def find_skills() -> dict[str, Path]:
    """Return {skill_name: skill_md_path} for every SKILL.md under .agents/skills/."""
    skills: dict[str, Path] = {}
    if not SKILLS_DIR.is_dir():
        return skills
    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        skill_dir = skill_md.parent.name
        skills[skill_dir] = skill_md
    return skills


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    """Parse YAML frontmatter from a markdown file. Returns None if absent."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    frontmatter_text = text[3:end]
    try:
        result = yaml.safe_load(frontmatter_text)
        return result if isinstance(result, dict) else None
    except yaml.YAMLError:
        return None


def extract_backtick_paths(text: str) -> list[str]:
    """Extract backtick-wrapped paths that look like file references."""
    paths: list[str] = []
    for match in re.finditer(r"`((?:[\w./-]+/)+[\w.-]+)`", text):
        paths.append(match.group(1))
    return paths


def path_exists(rel_path: str) -> bool:
    """Check if a relative path exists from project root."""
    # Skip paths with template placeholders or obvious non-file patterns
    if "<" in rel_path or ">" in rel_path or "$" in rel_path:
        return True
    # Skip ellipsis paths (e.g., "knowledge_nodes/.../file.json")
    if "..." in rel_path:
        return True
    # Skip token lists (e.g., "Typography.numberXL/Large/Medium" — multiple
    # capitalized segments with no file extension, separated by /)
    if "/" in rel_path and "." not in rel_path.split("/")[-1]:
        if re.search(r"[A-Z]", rel_path.split("/")[-1]):
            return True
    # Skip paths that are clearly config keys, not file paths (must contain
    # a path separator or a file extension to be considered a file reference)
    if "/" not in rel_path and "." not in rel_path:
        return True
    return (PROJECT_ROOT / rel_path).exists()


def check_skill_frontmatter(skills: dict[str, Path]) -> list[str]:
    """Check 1 & 2: frontmatter validity and name/dir match."""
    violations: list[str] = []
    for name, path in sorted(skills.items()):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            violations.append(f"{path}: missing or invalid YAML frontmatter")
            continue
        if "name" not in fm or "description" not in fm:
            violations.append(f"{path}: frontmatter missing name or description")
            continue
        if fm["name"] != name:
            violations.append(
                f"{path}: name '{fm['name']}' != directory '{name}'"
            )
    return violations


def check_referenced_paths(skills: dict[str, Path]) -> list[str]:
    """Check 3: paths referenced in backticks exist."""
    violations: list[str] = []
    for name, path in sorted(skills.items()):
        text = path.read_text(encoding="utf-8")
        for ref in extract_backtick_paths(text):
            if not path_exists(ref):
                violations.append(f"{path}: referenced path '{ref}' not found")
    return violations


def check_router_skills_exist(skills: dict[str, Path]) -> list[str]:
    """Check 4 & 7: every skill in TASK_ROUTER.yaml exists."""
    violations: list[str] = []
    if not ROUTER_PATH.is_file():
        violations.append(f"{ROUTER_PATH}: TASK_ROUTER.yaml not found")
        return violations
    router = yaml.safe_load(ROUTER_PATH.read_text(encoding="utf-8"))
    if not isinstance(router, dict):
        violations.append(f"{ROUTER_PATH}: not a YAML mapping")
        return violations

    # Default skill
    default_skill = router.get("default", {}).get("skill")
    if default_skill and default_skill not in skills:
        violations.append(
            f"{ROUTER_PATH}: default skill '{default_skill}' not found in {SKILLS_DIR}"
        )

    # Route skills + also_apply
    routes = router.get("routes", {})
    for route_name, route in routes.items():
        if not isinstance(route, dict):
            continue
        skill = route.get("skill")
        if not skill:
            violations.append(f"{ROUTER_PATH}: route '{route_name}' missing 'skill'")
        elif skill not in skills:
            violations.append(
                f"{ROUTER_PATH}: route '{route_name}' skill '{skill}' not found"
            )
        also_apply = route.get("also_apply", []) or []
        if not isinstance(also_apply, list):
            violations.append(
                f"{ROUTER_PATH}: route '{route_name}' also_apply must be a list"
            )
            continue
        for s in also_apply:
            if s not in skills:
                violations.append(
                    f"{ROUTER_PATH}: route '{route_name}' also_apply skill '{s}' not found"
                )
    return violations


def check_router_checklists_exist() -> list[str]:
    """Check 5: every checklist referenced in router exists."""
    violations: list[str] = []
    if not ROUTER_PATH.is_file():
        return violations
    router = yaml.safe_load(ROUTER_PATH.read_text(encoding="utf-8"))

    def check_checklist_list(checks: list, context: str) -> None:
        if not isinstance(checks, list):
            return
        for c in checks:
            if not isinstance(c, str):
                continue
            if not c.startswith("checklists/"):
                continue
            if not (PROJECT_ROOT / c).is_file():
                violations.append(f"{ROUTER_PATH}: {context} references missing '{c}'")

    default_checks = router.get("default", {}).get("checks", [])
    check_checklist_list(default_checks, "default")
    for route_name, route in (router.get("routes") or {}).items():
        if isinstance(route, dict):
            check_checklist_list(route.get("checks", []), f"route '{route_name}'")
    return violations


def check_skill_checklists_exist(skills: dict[str, Path]) -> list[str]:
    """Check 5: every checklist referenced in SKILL.md exists."""
    violations: list[str] = []
    pattern = re.compile(r"`(checklists/[\w.-]+\.md)`")
    for name, path in sorted(skills.items()):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            cl = match.group(1)
            if not (PROJECT_ROOT / cl).is_file():
                violations.append(f"{path}: references missing checklist '{cl}'")
    return violations


def check_router_required_fields() -> tuple[list[str], list[str]]:
    """Check 6 (error) + 14/15 (warnings): route required fields + explicit defaults."""
    violations: list[str] = []
    warnings: list[str] = []
    if not ROUTER_PATH.is_file():
        return violations, warnings
    router = yaml.safe_load(ROUTER_PATH.read_text(encoding="utf-8"))
    routes = router.get("routes", {}) if isinstance(router, dict) else {}
    for route_name, route in routes.items():
        if not isinstance(route, dict):
            continue
        if "skill" not in route:
            violations.append(f"{ROUTER_PATH}: route '{route_name}' missing 'skill'")
        if "triggers" not in route or not route["triggers"]:
            violations.append(
                f"{ROUTER_PATH}: route '{route_name}' missing or empty 'triggers'"
            )
        # Warnings (only fail under --strict)
        if "priority" not in route:
            warnings.append(
                f"{ROUTER_PATH}: route '{route_name}' missing 'priority' (defaults to 50)"
            )
        if "inherits_default" not in route:
            warnings.append(
                f"{ROUTER_PATH}: route '{route_name}' missing 'inherits_default' "
                "(defaults to true)"
            )
    return violations, warnings


def check_training_evaluator_params(skills: dict[str, Path]) -> list[str]:
    """Check 8: training evaluator command examples include required params."""
    violations: list[str] = []
    training_skill = skills.get("medlearn-evaluate-training-stage")
    if not training_skill:
        return violations
    text = training_skill.read_text(encoding="utf-8")
    # Find powershell code blocks that invoke evaluate_*
    for match in re.finditer(
        r"evaluate_(?:stage\d|sft_adapter)\w*\.py", text
    ):
        # Find the enclosing code block
        start = text.rfind("```", 0, match.start())
        end = text.find("```", match.end())
        if start == -1 or end == -1:
            continue
        block = text[start:end]
        if "--base-model" not in block or "--adapter" not in block:
            violations.append(
                f"{training_skill}: evaluator command block missing --base-model/--adapter"
            )
    return violations


def check_checklists_no_drift_counts() -> list[str]:
    """Check 9: checklists must not embed drift-prone counts."""
    violations: list[str] = []
    # Match patterns like "275 refs", "238 locators", "281 references"
    pattern = re.compile(r"\b\d{2,}\s+(?:refs?|locators?|references?)\b", re.IGNORECASE)
    if not CHECKLISTS_DIR.is_dir():
        return violations
    for cl in CHECKLISTS_DIR.glob("*.md"):
        text = cl.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            violations.append(
                f"{cl}: drift-prone count '{match.group(0)}' — move to generated report"
            )
    return violations


def check_no_hardcoded_rgba(skills: dict[str, Path]) -> list[str]:
    """Check 10: skills must not hardcode RGBA in component guidance."""
    violations: list[str] = []
    # Only flag in component-guidance context (PageViewer / overlay / fill)
    pattern = re.compile(r"rgba?\(\s*\d+", re.IGNORECASE)
    for name, path in sorted(skills.items()):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            # Allow if the line explicitly says "use token" / "see constants"
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start:line_end] if line_end != -1 else text[line_start:]
            if "token" in line.lower() or "constants/" in line:
                continue
            violations.append(
                f"{path}: hardcoded RGBA '{match.group(0)}...' — use TextbookEditorial token"
            )
    return violations


def check_router_read_paths() -> list[str]:
    """Check 11 & 12: all paths in TASK_ROUTER.yaml `read` lists exist."""
    violations: list[str] = []
    if not ROUTER_PATH.is_file():
        return violations
    router = yaml.safe_load(ROUTER_PATH.read_text(encoding="utf-8"))
    if not isinstance(router, dict):
        return violations

    def check_read_list(reads: list, context: str) -> None:
        if not isinstance(reads, list):
            return
        for r in reads:
            if not isinstance(r, str):
                continue
            if not path_exists(r):
                violations.append(
                    f"{ROUTER_PATH}: {context} read path '{r}' not found"
                )

    # default.read (check 12)
    check_read_list(router.get("default", {}).get("read", []), "default")

    # routes[].read (check 11)
    for route_name, route in (router.get("routes") or {}).items():
        if isinstance(route, dict):
            check_read_list(route.get("read", []), f"route '{route_name}'")
    return violations


def check_checklist_paths() -> list[str]:
    """Check 13: all backtick paths in checklists/*.md exist."""
    violations: list[str] = []
    if not CHECKLISTS_DIR.is_dir():
        return violations
    for cl in CHECKLISTS_DIR.glob("*.md"):
        text = cl.read_text(encoding="utf-8")
        for ref in extract_backtick_paths(text):
            if not path_exists(ref):
                violations.append(f"{cl}: referenced path '{ref}' not found")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as errors (warnings fail the check)",
    )
    args = parser.parse_args()

    skills = find_skills()
    if not skills:
        print(f"No skills found under {SKILLS_DIR}", file=sys.stderr)
        return 2

    violations: list[str] = []
    warnings: list[str] = []

    # Error checks
    violations.extend(check_skill_frontmatter(skills))
    violations.extend(check_referenced_paths(skills))
    violations.extend(check_router_skills_exist(skills))
    violations.extend(check_router_checklists_exist())
    violations.extend(check_skill_checklists_exist(skills))
    router_violations, router_warnings = check_router_required_fields()
    violations.extend(router_violations)
    warnings.extend(router_warnings)
    violations.extend(check_training_evaluator_params(skills))
    violations.extend(check_checklists_no_drift_counts())
    violations.extend(check_no_hardcoded_rgba(skills))
    violations.extend(check_router_read_paths())
    violations.extend(check_checklist_paths())

    # Under --strict, warnings become violations
    if args.strict:
        violations.extend(warnings)
        warnings = []

    if not violations and not warnings:
        print(
            f"OK: {len(skills)} skills, router, and checklists consistent.",
            file=sys.stdout,
        )
        return 0

    if warnings and not args.strict:
        print(f"WARN: {len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    if violations:
        print(f"FAIL: {len(violations)} violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    # Only warnings, non-strict mode
    return 0


if __name__ == "__main__":
    sys.exit(main())

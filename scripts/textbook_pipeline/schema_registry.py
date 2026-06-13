"""V4 Schema Registry - Step 5 of optimized pipeline.
Fulfills all 4 responsibilities:
1. Return schema by type/suggested_schema
2. Validate schema existence
3. Return prompt instructions
4. Return required/optional fields

Unknown schema falls back to concept_schema with report recording.
"""
from __future__ import annotations
import importlib
from pathlib import Path
from typing import Dict, Any

def _load_schema_module(schema_name: str):
    """Dynamically load schema module."""
    try:
        module_name = f"schemas.{schema_name}_schema"
        return importlib.import_module(module_name, package="textbook_pipeline")
    except ImportError:
        return importlib.import_module("schemas.concept_schema", package="textbook_pipeline")

def validate_schema_name(schema_name: str) -> bool:
    """Check if schema exists."""
    try:
        _load_schema_module(schema_name)
        return True
    except Exception:
        return False

def get_schema(schema_name: str) -> Dict:
    """Return full schema definition."""
    if not validate_schema_name(schema_name):
        schema_name = "concept"
    module = _load_schema_module(schema_name)
    return {
        "name": getattr(module, "SCHEMA_NAME", "concept"),
        "required_fields": getattr(module, "REQUIRED_FIELDS", []),
        "optional_fields": getattr(module, "OPTIONAL_FIELDS", []),
        "prompt_instructions": getattr(module, "PROMPT_INSTRUCTIONS", ""),
        "json_schema": getattr(module, "JSON_SCHEMA", {})
    }

def get_required_fields(schema_name: str) -> List[str]:
    module = _load_schema_module(schema_name if validate_schema_name(schema_name) else "concept")
    return getattr(module, "REQUIRED_FIELDS", ["definition"])

def get_optional_fields(schema_name: str) -> List[str]:
    module = _load_schema_module(schema_name if validate_schema_name(schema_name) else "concept")
    return getattr(module, "OPTIONAL_FIELDS", [])

def get_prompt_instructions(schema_name: str) -> str:
    module = _load_schema_module(schema_name if validate_schema_name(schema_name) else "concept")
    return getattr(module, "PROMPT_INSTRUCTIONS", "只提取原文信息，不要补充教材外内容。")

def get_fallback_report(original_schema: str) -> Dict:
    """Record fallback in extraction_report."""
    return {
        "schema_fallback": True,
        "original_schema": original_schema,
        "fallback_schema": "concept"
    }

# CLI for testing
if __name__ == "__main__":
    print("Schema Registry loaded.")
    print("Available schemas:", ["disease", "drug", "test", "concept"])
    print("Test get_schema('disease'):", get_schema("disease")["name"])

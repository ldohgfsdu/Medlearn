"""Configuration for MedLearn PDF knowledge extractor.

All sensitive settings are loaded from environment variables.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

PDF_PATH = os.getenv("MEDLEARN_PDF_PATH", "内科学.pdf")
if not Path(PDF_PATH).is_absolute():
    PDF_PATH = str(BASE_DIR / PDF_PATH)

TEXT_MD = OUTPUT_DIR / "text.md"
TOC_JSON = OUTPUT_DIR / "toc.json"
BLOCKS_JSON = OUTPUT_DIR / "blocks.json"
STRUCTURED_JSON = OUTPUT_DIR / "structured.json"
REVIEW_SAMPLE_JSON = OUTPUT_DIR / "review_sample.json"
KNOWLEDGE_NODES_JSON = OUTPUT_DIR / "knowledge_nodes.json"
REPORT_MD = OUTPUT_DIR / "REPORT.md"

# ── LLM Provider ───────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("MEDLEARN_LLM_PROVIDER", "openai").lower().strip()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "tp-c7b6myjwusbxag596cpwcofy5jseovx1psorro1y8oquq1v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "mimo-v2.5-pro")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")

# ── Concurrency & Batching ─────────────────────────────────────────
MAX_CONCURRENCY = int(os.getenv("MEDLEARN_MAX_CONCURRENCY", "5"))
BATCH_SIZE = int(os.getenv("MEDLEARN_BATCH_SIZE", "50"))

# ── Validation ─────────────────────────────────────────────────────
MIN_KEYWORDS = int(os.getenv("MEDLEARN_MIN_KEYWORDS", "3"))
MIN_KEY_POINTS = int(os.getenv("MEDLEARN_MIN_KEY_POINTS", "2"))
REVIEW_SAMPLE_RATE = float(os.getenv("MEDLEARN_REVIEW_SAMPLE_RATE", "0.1"))

# ── Runtime ────────────────────────────────────────────────────────
REQUEST_TIMEOUT = int(os.getenv("MEDLEARN_REQUEST_TIMEOUT", "120"))

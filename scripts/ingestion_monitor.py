#!/usr/bin/env python
"""
V4.7 Ingestion Monitor
Tracks full textbook ingestion with checkpoint and summary.
"""
import json
from pathlib import Path
from datetime import datetime

STATE_FILE = Path("ingestion_state.json")
FAILED_DIR = Path("failed_nodes")
PILOT_REPORTS_DIR = Path("pilot_reports")

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"status": "ready", "current_chapter": "呼吸系统疾病", "current_chunk_index": 0}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def log_failure(node, reason, raw_text):
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    path = FAILED_DIR / f"{node.get('title', 'unknown').replace('/', '_')}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            "title": node.get("title"),
            "type": node.get("type"),
            "reason": reason,
            "raw_text_sample": raw_text[:300],
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

def print_status():
    state = load_state()
    print(f"\n📊 Ingestion Status - {state['book']}")
    print("=" * 60)
    print(f"Status           : {state['status']}")
    print(f"Current Chapter  : {state['current_chapter']}")
    print(f"Current Chunk    : {state['current_chunk_index']}")
    print(f"Success Rate     : {state.get('success_rate', 0):.1f}%")
    print(f"Written          : {state.get('total_written', 0)}")
    print(f"Failed           : {state.get('total_failed', 0)}")
    print(f"Estimated Time   : {state.get('estimated_remaining_minutes', 0)} min")
    print("=" * 60)

if __name__ == "__main__":
    print_status()
    print("\nUse: python ingestion_monitor.py to check status.")
    print("This is the production monitoring system for V4.7.")

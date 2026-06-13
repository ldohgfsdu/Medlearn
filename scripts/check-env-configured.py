#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

KEYS = [
    "EXPO_PUBLIC_SUPABASE_URL",
    "EXPO_PUBLIC_SUPABASE_ANON_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "AI_API_KEY",
]


def main() -> int:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        print("missing .env")
        return 1

    text = env_path.read_text(encoding="utf-8")
    ok = True
    for key in KEYS:
        match = re.search(rf"^{re.escape(key)}=(.*)$", text, re.M)
        value = match.group(1).strip().strip('"').strip("'") if match else ""
        placeholder = (not value) or value.startswith("your_") or value.endswith("_here")
        print(f"{key}: configured={not placeholder}")
        if placeholder:
            ok = False
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
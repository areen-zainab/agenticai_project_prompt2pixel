"""
backend/utils.py
────────────────────────────────────────────────────────────────────────────
Utility functions for the backend.
"""

import json
from pathlib import Path
from typing import Any, Optional


def load_json_file(path: Path) -> Any:
    """Safely load a JSON file."""
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def save_json_file(path: Path, data: Any) -> bool:
    """Safely save data to a JSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

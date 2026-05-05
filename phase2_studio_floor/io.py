"""Load Phase 1 outputs for Phase 2."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_scene_manifest(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict) or "scenes" not in data:
        raise ValueError("scene_manifest.json must contain a 'scenes' array")
    return data


def load_character_db(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict) or "characters" not in data:
        raise ValueError("character_db.json must contain a 'characters' array")
    return data

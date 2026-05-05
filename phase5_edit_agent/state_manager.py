"""SQLite-backed version history for Phase 5 edits.

Each snapshot stores a JSON state payload plus copies of any generated
assets so the UI can show history and revert a prior version.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.config.config import BASE_DIR

DB_PATH = BASE_DIR / "outputs" / "state_versions.db"
SNAPSHOTS_DIR = BASE_DIR / "outputs" / "snapshots"
_LOCK = threading.Lock()


@dataclass
class VersionRecord:
    version: int
    timestamp: str
    description: str
    state_json: dict[str, Any]
    asset_paths: list[str]


class StateManager:
    def __init__(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS versions (
                    version     INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    description TEXT NOT NULL,
                    state_json  TEXT NOT NULL,
                    asset_paths TEXT NOT NULL
                )
                """
            )

    def snapshot(self, state_json: dict[str, Any], description: str, asset_paths: list[str]) -> int:
        """Save a new version and copy the referenced assets."""
        timestamp = datetime.now().isoformat(timespec="seconds")
        with _LOCK, sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "INSERT INTO versions (timestamp, description, state_json, asset_paths) VALUES (?,?,?,?)",
                (timestamp, description, json.dumps(state_json), json.dumps(asset_paths)),
            )
            version = int(cursor.lastrowid)

        snap_dir = SNAPSHOTS_DIR / f"v{version}"
        snap_dir.mkdir(parents=True, exist_ok=True)
        for src in asset_paths:
            path = Path(src)
            if path.is_file():
                shutil.copy2(path, snap_dir / path.name)

        return version

    def history(self) -> list[dict[str, Any]]:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT version, timestamp, description FROM versions ORDER BY version DESC"
            ).fetchall()
        return [
            {"version": row[0], "timestamp": row[1], "description": row[2]}
            for row in rows
        ]

    def revert(self, version: int) -> VersionRecord:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT version, timestamp, description, state_json, asset_paths FROM versions WHERE version=?",
                (version,),
            ).fetchone()

        if not row:
            raise ValueError(f"Version {version} not found")

        record = VersionRecord(
            version=int(row[0]),
            timestamp=str(row[1]),
            description=str(row[2]),
            state_json=json.loads(row[3]),
            asset_paths=json.loads(row[4]),
        )

        snap_dir = SNAPSHOTS_DIR / f"v{version}"
        for asset_path in record.asset_paths:
            path = Path(asset_path)
            snap_file = snap_dir / path.name
            if snap_file.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snap_file, path)

        return record

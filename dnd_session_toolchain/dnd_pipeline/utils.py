"""General helpers shared by the pipeline modules."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_DIRS = [
    "audio",
    "transcripts",
    "sessions",
    "characters",
    "locations",
    "factions",
    "events",
]


def ensure_project_structure(base_dir: Path) -> None:
    """Create expected project folders and index file if missing."""
    for folder in PROJECT_DIRS:
        (base_dir / folder).mkdir(parents=True, exist_ok=True)

    index_path = base_dir / "index.json"
    if not index_path.exists():
        default_index: dict[str, Any] = {
            "sessions": [],
            "characters": {},
            "locations": {},
            "factions": {},
            "events": {},
            "unresolved_hooks": [],
            "updated_at": "",
        }
        index_path.write_text(json.dumps(default_index, indent=2), encoding="utf-8")


def slugify(value: str) -> str:
    """Convert a user-facing string into a safe filename slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    cleaned = cleaned.strip("-")
    return cleaned or "untitled"


def safe_filename(value: str) -> str:
    """Build a stable filename from entity title text."""
    return f"{slugify(value)}.md"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON with consistent formatting."""
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

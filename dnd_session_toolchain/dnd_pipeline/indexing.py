"""Campaign index maintenance."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import SessionSummary


def _default_index() -> dict[str, Any]:
    """Return empty index structure."""
    return {
        "sessions": [],
        "characters": {},
        "locations": {},
        "factions": {},
        "events": {},
        "unresolved_hooks": [],
        "updated_at": "",
    }


def load_index(index_path: Path) -> dict[str, Any]:
    """Load index file if present; otherwise return default structure."""
    if not index_path.exists():
        return _default_index()
    return json.loads(index_path.read_text(encoding="utf-8"))


def _add_entity(index: dict[str, Any], bucket: str, entity_name: str, session_title: str) -> None:
    """Track entity occurrences by session title."""
    entries = index.setdefault(bucket, {})
    sessions = entries.setdefault(entity_name, [])
    if session_title not in sessions:
        sessions.append(session_title)


def update_index(
    index_path: Path,
    summary: SessionSummary,
    session_markdown_path: Path,
    transcript_path: Path,
) -> None:
    """Update campaign index with one newly processed session."""
    index = load_index(index_path)

    session_record = {
        "title": summary.session_title,
        "date": summary.session_date,
        "note_file": str(session_markdown_path.as_posix()),
        "transcript_file": str(transcript_path.as_posix()),
    }
    if session_record not in index["sessions"]:
        index["sessions"].append(session_record)

    for name in summary.characters:
        _add_entity(index, "characters", name, summary.session_title)
    for name in summary.locations:
        _add_entity(index, "locations", name, summary.session_title)
    for name in summary.factions:
        _add_entity(index, "factions", name, summary.session_title)
    for name in summary.events:
        _add_entity(index, "events", name, summary.session_title)
    for hook in summary.unresolved_hooks:
        if hook not in index["unresolved_hooks"]:
            index["unresolved_hooks"].append(hook)

    index["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

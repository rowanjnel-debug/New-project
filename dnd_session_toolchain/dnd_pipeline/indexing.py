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


def _resolve_index_path(index_path: Path, value: str) -> Path:
    """Resolve absolute or index-relative path entries."""
    raw = Path(value)
    if raw.is_absolute():
        return raw
    return (index_path.parent / raw).resolve()


def _path_key(path: Path) -> str:
    """Build normalized comparison key for file paths."""
    return str(path.resolve().as_posix()).casefold()


def get_previous_session_context(
    index_path: Path,
    current_transcript_path: Path,
) -> dict[str, Any] | None:
    """Load context from the most recent session before current transcript.

    Context is sourced from the prior session's summary JSON (if present) and
    falls back to index metadata when needed.
    """
    index = load_index(index_path)
    sessions = index.get("sessions", [])
    current_key = _path_key(current_transcript_path)

    for record in reversed(sessions):
        transcript_value = str(record.get("transcript_file", "")).strip()
        if not transcript_value:
            continue

        transcript_path = _resolve_index_path(index_path, transcript_value)
        if _path_key(transcript_path) == current_key:
            continue

        summary_payload: dict[str, Any] = {}
        summary_path = transcript_path.with_suffix(".summary.json")
        if summary_path.exists():
            try:
                summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                summary_payload = {}

        context = {
            "session_title": str(record.get("title", "")).strip(),
            "session_date": str(record.get("date", "")).strip(),
            "previously_on": str(summary_payload.get("previously_on", "")).strip(),
            "last_session_narrative": str(summary_payload.get("last_session_narrative", "")).strip(),
            "plain_text_summary": str(summary_payload.get("plain_text_summary", "")).strip(),
            "unresolved_hooks": [str(v) for v in summary_payload.get("unresolved_hooks", [])],
            "characters": [str(v) for v in summary_payload.get("characters", [])],
            "locations": [str(v) for v in summary_payload.get("locations", [])],
            "factions": [str(v) for v in summary_payload.get("factions", [])],
            "events": [str(v) for v in summary_payload.get("events", [])],
        }

        if not context["unresolved_hooks"]:
            # Fallback to global unresolved hooks if per-session hooks unavailable.
            context["unresolved_hooks"] = [str(v) for v in index.get("unresolved_hooks", [])[:8]]

        if (
            context["session_title"]
            or context["previously_on"]
            or context["last_session_narrative"]
            or context["plain_text_summary"]
            or context["unresolved_hooks"]
        ):
            return context

    return None


def _trim_list(values: list[str], limit: int, max_chars: int = 120) -> list[str]:
    """Return a trimmed list of non-empty unique strings preserving order."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value).strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        if len(clean) > max_chars:
            clean = clean[: max_chars - 3].rstrip() + "..."
        out.append(clean)
        if len(out) >= limit:
            break
    return out


def get_campaign_memory_context(
    index_path: Path,
    current_transcript_path: Path,
) -> dict[str, Any]:
    """Build campaign-wide memory snapshot to improve cross-session continuity."""
    index = load_index(index_path)
    sessions = index.get("sessions", [])
    current_key = _path_key(current_transcript_path)

    historical_sessions: list[dict[str, str]] = []
    for record in sessions:
        transcript_value = str(record.get("transcript_file", "")).strip()
        if not transcript_value:
            continue
        transcript_path = _resolve_index_path(index_path, transcript_value)
        if _path_key(transcript_path) == current_key:
            continue
        historical_sessions.append(
            {
                "title": str(record.get("title", "")).strip(),
                "date": str(record.get("date", "")).strip(),
            }
        )

    recent_sessions = historical_sessions[-5:]
    known_characters = _trim_list(list(index.get("characters", {}).keys()), 30, max_chars=80)
    known_locations = _trim_list(list(index.get("locations", {}).keys()), 30, max_chars=80)
    known_factions = _trim_list(list(index.get("factions", {}).keys()), 30, max_chars=80)
    known_events = _trim_list(list(index.get("events", {}).keys()), 15, max_chars=100)
    open_hooks = _trim_list([str(v) for v in index.get("unresolved_hooks", [])], 10, max_chars=120)

    return {
        "historical_session_count": len(historical_sessions),
        "recent_sessions": recent_sessions,
        "known_characters": known_characters,
        "known_locations": known_locations,
        "known_factions": known_factions,
        "known_events": known_events,
        "open_hooks": open_hooks,
    }


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

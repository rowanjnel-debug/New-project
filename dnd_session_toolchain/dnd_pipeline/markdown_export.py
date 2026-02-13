"""Markdown rendering and entity page maintenance for Obsidian."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import SessionSummary
from .utils import safe_filename


def render_session_markdown(summary: SessionSummary, transcript_file: str, audio_file: str) -> str:
    """Render a session note in Obsidian-friendly markdown."""
    hook_lines = "\n".join(f"- {item}" for item in summary.unresolved_hooks) or "- None"
    char_links = " ".join(f"[[{name}]]" for name in summary.characters)
    loc_links = " ".join(f"[[{name}]]" for name in summary.locations)
    fac_links = " ".join(f"[[{name}]]" for name in summary.factions)
    event_links = " ".join(f"[[{name}]]" for name in summary.events)

    return f"""# {summary.session_title}

Date: {summary.session_date}
Transcript: `{transcript_file}`
Audio: `{audio_file}`
Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC

## Last Session Narrative
{summary.last_session_narrative or "No narrative available."}

## Plain Text Summary
{summary.plain_text_summary or "No summary available."}

## Unresolved Hooks
{hook_lines}

## Linked Entities
Characters: {char_links}
Locations: {loc_links}
Factions: {fac_links}
Events: {event_links}

## Backlinks
{summary.backlink_block}
"""


def _append_session_reference(path: Path, session_title: str, session_date: str) -> None:
    """Append a session reference to an entity file if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            f"# {path.stem.replace('-', ' ').title()}\n\n## Mentions\n",
            encoding="utf-8",
        )

    marker = f"- [[{session_title}]] ({session_date})"
    body = path.read_text(encoding="utf-8")
    if marker not in body:
        if not body.endswith("\n"):
            body += "\n"
        body += marker + "\n"
        path.write_text(body, encoding="utf-8")


def update_entity_pages(base_dir: Path, summary: SessionSummary) -> None:
    """Update character/location/event/faction files with backlinks to session."""
    entity_map = {
        "characters": summary.characters,
        "locations": summary.locations,
        "events": summary.events,
        "factions": summary.factions,
    }
    for folder, names in entity_map.items():
        for name in names:
            target = base_dir / folder / safe_filename(name)
            _append_session_reference(target, summary.session_title, summary.session_date)

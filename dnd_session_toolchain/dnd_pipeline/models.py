"""Data models used by the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _normalize_list(values: list[str]) -> list[str]:
    """Return unique, stripped values while preserving input order."""
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = value.strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(clean)
    return output


@dataclass
class SessionSummary:
    """Canonical model of LLM output for one session."""

    session_title: str
    session_date: str
    characters: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    factions: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    unresolved_hooks: list[str] = field(default_factory=list)
    last_session_narrative: str = ""
    plain_text_summary: str = ""
    backlink_block: str = ""

    def normalize(self) -> "SessionSummary":
        """Normalize list fields and trim scalar text."""
        self.session_title = self.session_title.strip()
        self.session_date = self.session_date.strip()
        self.characters = _normalize_list(self.characters)
        self.locations = _normalize_list(self.locations)
        self.factions = _normalize_list(self.factions)
        self.events = _normalize_list(self.events)
        self.unresolved_hooks = _normalize_list(self.unresolved_hooks)
        self.last_session_narrative = self.last_session_narrative.strip()
        self.plain_text_summary = self.plain_text_summary.strip()
        self.backlink_block = self.backlink_block.strip()
        return self

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SessionSummary":
        """Build a summary model from parsed JSON payload."""
        required = [
            "session_title",
            "session_date",
            "characters",
            "locations",
            "events",
            "unresolved_hooks",
        ]
        missing = [key for key in required if key not in payload]
        if missing:
            missing_csv = ", ".join(missing)
            raise ValueError(f"Missing keys in summarizer JSON: {missing_csv}")

        summary = cls(
            session_title=str(payload["session_title"]),
            session_date=str(payload["session_date"]),
            characters=[str(v) for v in payload.get("characters", [])],
            locations=[str(v) for v in payload.get("locations", [])],
            factions=[str(v) for v in payload.get("factions", [])],
            events=[str(v) for v in payload.get("events", [])],
            unresolved_hooks=[str(v) for v in payload.get("unresolved_hooks", [])],
            last_session_narrative=str(payload.get("last_session_narrative", "")),
            plain_text_summary=str(payload.get("plain_text_summary", "")),
            backlink_block=str(payload.get("backlink_block", "")),
        )
        return summary.normalize()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the summary to a JSON-safe dictionary."""
        return {
            "session_title": self.session_title,
            "session_date": self.session_date,
            "characters": self.characters,
            "locations": self.locations,
            "factions": self.factions,
            "events": self.events,
            "unresolved_hooks": self.unresolved_hooks,
            "last_session_narrative": self.last_session_narrative,
            "plain_text_summary": self.plain_text_summary,
            "backlink_block": self.backlink_block,
        }

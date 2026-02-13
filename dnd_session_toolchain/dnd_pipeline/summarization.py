"""Session summarization and structured extraction."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .config import ModelConfig
from .models import SessionSummary


SYSTEM_PROMPT = """You are a D&D campaign archivist.
Return ONLY valid JSON.

Required fields:
- session_title: string
- session_date: YYYY-MM-DD string
- characters: string[]
- locations: string[]
- factions: string[]
- events: string[]
- unresolved_hooks: string[]
- last_session_narrative: string
- plain_text_summary: string
- backlink_block: string with Obsidian links like [[Name]]

Rules:
- Keep names consistent with transcript wording.
- Extract only information supported by transcript text.
- If information is missing, return empty list or concise fallback text.
"""


def _extract_json_blob(raw_text: str) -> str:
    """Extract a JSON object from model text, even if wrapped in markdown."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response did not contain JSON.")
    return raw_text[start : end + 1]


def _build_backlink_block(summary: SessionSummary) -> str:
    """Create a clean backlink section for Obsidian."""
    links: list[str] = []
    for name in summary.characters + summary.locations + summary.factions + summary.events:
        links.append(f"[[{name}]]")

    seen: set[str] = set()
    unique_links: list[str] = []
    for link in links:
        key = link.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_links.append(link)
    return "\n".join(unique_links)


def _build_user_prompt(transcript: str, session_date: str) -> str:
    """Create user prompt for model inference."""
    return (
        f"Session date: {session_date}\n\n"
        "Transcript:\n"
        f"{transcript}\n\n"
        "Generate structured campaign notes as specified."
    )


def build_manual_chatgpt_prompt(transcript: str, session_date: str) -> str:
    """Build a copy/paste prompt for manual use on chatgpt.com."""
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "Return only JSON. Do not include markdown fences.\n\n"
        f"{_build_user_prompt(transcript, session_date)}\n"
    )


def _summarize_with_ollama(transcript: str, session_date: str, config: ModelConfig) -> str:
    """Run summarization against a local Ollama model."""
    import requests

    payload = {
        "model": config.model,
        "stream": False,
        "prompt": f"{SYSTEM_PROMPT}\n\n{_build_user_prompt(transcript, session_date)}",
        "options": {"temperature": config.temperature},
    }
    response = requests.post(
        f"{config.ollama_base_url}/api/generate",
        json=payload,
        timeout=240,
    )
    response.raise_for_status()
    body = response.json()
    return str(body.get("response", "")).strip()


def _summarize_with_openai_compatible(transcript: str, session_date: str, config: ModelConfig) -> str:
    """Run summarization against an OpenAI-compatible chat endpoint."""
    import requests

    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set.")

    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(transcript, session_date)},
        ],
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        f"{config.openai_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=240,
    )
    response.raise_for_status()
    body = response.json()
    return str(body["choices"][0]["message"]["content"]).strip()


def _heuristic_fallback(transcript: str, session_date: str) -> SessionSummary:
    """Create an offline summary when no model endpoint is available."""
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    plain = " ".join(lines[:8])[:1200]

    # Lightweight candidate extraction based on capitalized terms.
    tokens = re.findall(r"\b[A-Z][a-zA-Z'\-]+\b(?:\s+[A-Z][a-zA-Z'\-]+\b)?", transcript)
    counts = Counter(token.strip() for token in tokens if len(token.strip()) > 2)
    most_common = [name for name, _ in counts.most_common(8)]

    characters = most_common[:4]
    locations = most_common[4:6]
    events = [f"Session recap for {session_date}"]

    summary = SessionSummary(
        session_title=f"Session Notes {session_date}",
        session_date=session_date,
        characters=characters,
        locations=locations,
        factions=[],
        events=events,
        unresolved_hooks=["Review full transcript for unresolved hooks."],
        last_session_narrative=plain or "No narrative extracted from transcript.",
        plain_text_summary=plain or "No summary extracted from transcript.",
    ).normalize()
    summary.backlink_block = _build_backlink_block(summary)
    return summary


def summarize_transcript(transcript: str, session_date: str, config: ModelConfig) -> SessionSummary:
    """Generate structured summary from transcript using configured provider."""
    provider = config.provider.strip().lower()

    try:
        if provider == "ollama":
            raw = _summarize_with_ollama(transcript, session_date, config)
        elif provider in {"openai", "openai_compatible"}:
            raw = _summarize_with_openai_compatible(transcript, session_date, config)
        elif provider in {"heuristic", "offline"}:
            return _heuristic_fallback(transcript, session_date)
        else:
            raise ValueError(f"Unsupported provider '{config.provider}'.")

        payload = json.loads(_extract_json_blob(raw))
        summary = SessionSummary.from_payload(payload)
        if not summary.backlink_block:
            summary.backlink_block = _build_backlink_block(summary)
        return summary.normalize()
    except Exception:
        # Keep the tool runnable even if model server is unavailable.
        return _heuristic_fallback(transcript, session_date)


def write_summary_json(summary: SessionSummary, summary_json_path: Path) -> None:
    """Persist structured summary JSON to disk."""
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_json_path.write_text(
        json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_summary_json_text(raw_json: str) -> SessionSummary:
    """Parse user-provided JSON text into a normalized session summary."""
    payload = json.loads(_extract_json_blob(raw_json))
    summary = SessionSummary.from_payload(payload)
    if not summary.backlink_block:
        summary.backlink_block = _build_backlink_block(summary)
    return summary.normalize()

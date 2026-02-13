"""Audio transcription module using local Faster-Whisper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Segment:
    """Single timestamped text segment from Whisper."""

    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """Transcription output container."""

    text: str
    language: str
    duration: float
    segments: list[Segment]


def transcribe_audio(
    audio_path: Path,
    model_size: str = "base",
    language: str | None = None,
    device: str = "auto",
    compute_type: str = "int8",
) -> TranscriptionResult:
    """Transcribe an audio file into plain text and timestamped segments."""
    # Import lazily so non-transcription commands can run without Whisper installed.
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size_or_path=model_size, device=device, compute_type=compute_type)
    raw_segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
    )

    parsed_segments: list[Segment] = []
    parts: list[str] = []
    for item in raw_segments:
        text = item.text.strip()
        parsed_segments.append(Segment(start=float(item.start), end=float(item.end), text=text))
        parts.append(text)

    full_text = "\n".join(parts).strip()
    return TranscriptionResult(
        text=full_text,
        language=getattr(info, "language", ""),
        duration=float(getattr(info, "duration", 0.0)),
        segments=parsed_segments,
    )


def write_transcription_files(result: TranscriptionResult, transcript_path: Path) -> Path:
    """Write transcript text and adjacent segments JSON file."""
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(result.text + "\n", encoding="utf-8")

    segments_payload = [
        {"start": s.start, "end": s.end, "text": s.text}
        for s in result.segments
    ]
    segments_path = transcript_path.with_suffix(".segments.json")
    segments_path.write_text(json.dumps(segments_payload, indent=2), encoding="utf-8")
    return segments_path

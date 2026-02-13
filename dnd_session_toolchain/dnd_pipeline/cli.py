"""Command line interface for the D&D session notes pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_model_config
from .indexing import update_index
from .markdown_export import render_session_markdown, update_entity_pages
from .summarization import (
    build_manual_chatgpt_prompt,
    parse_summary_json_text,
    summarize_transcript,
    write_summary_json,
)
from .transcription import transcribe_audio, write_transcription_files
from .utils import ensure_project_structure, slugify


def _add_project_root_arg(parser: argparse.ArgumentParser) -> None:
    """Attach project root argument to a subcommand parser."""
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root containing audio/transcripts/sessions folders.",
    )


def _resolve_path(base_dir: Path, user_path: str) -> Path:
    """Resolve relative path against project root."""
    path = Path(user_path)
    if path.is_absolute():
        return path
    return base_dir / path


def _finalize_outputs(base_dir: Path, summary, transcript_path: Path, audio_path: Path) -> Path:
    """Write session markdown, entity pages, and campaign index."""
    slug = slugify(summary.session_title)
    session_file = base_dir / "sessions" / f"{summary.session_date}-{slug}.md"
    markdown = render_session_markdown(
        summary,
        transcript_file=str(transcript_path.relative_to(base_dir).as_posix()),
        audio_file=str(audio_path.relative_to(base_dir).as_posix()),
    )
    session_file.write_text(markdown, encoding="utf-8")
    update_entity_pages(base_dir, summary)
    update_index(
        index_path=base_dir / "index.json",
        summary=summary,
        session_markdown_path=session_file,
        transcript_path=transcript_path,
    )
    return session_file


def cmd_transcribe(args: argparse.Namespace) -> None:
    """Transcribe an audio file into /transcripts."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    audio_path = _resolve_path(base_dir, args.audio)
    transcript_path = base_dir / "transcripts" / f"{audio_path.stem}.txt"
    result = transcribe_audio(
        audio_path=audio_path,
        model_size=args.whisper_model,
        language=args.language,
    )
    segments_path = write_transcription_files(result, transcript_path)
    print(f"Transcript written: {transcript_path}")
    print(f"Segments written: {segments_path}")


def cmd_prepare_prompt(args: argparse.Namespace) -> None:
    """Generate a paste-ready prompt for ChatGPT website workflow."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)
    transcript_path = _resolve_path(base_dir, args.transcript)
    transcript = transcript_path.read_text(encoding="utf-8")
    prompt = build_manual_chatgpt_prompt(transcript, args.session_date)
    prompt_path = transcript_path.with_suffix(".chatgpt_prompt.txt")
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"Prompt written: {prompt_path}")


def cmd_apply_json(args: argparse.Namespace) -> None:
    """Consume JSON response from ChatGPT website and export notes/index."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    transcript_path = _resolve_path(base_dir, args.transcript)
    json_path = _resolve_path(base_dir, args.summary_json)
    audio_path = _resolve_path(base_dir, args.audio)

    summary = parse_summary_json_text(json_path.read_text(encoding="utf-8"))
    write_summary_json(summary, transcript_path.with_suffix(".summary.json"))
    session_file = _finalize_outputs(base_dir, summary, transcript_path, audio_path)
    print(f"Session note written: {session_file}")


def cmd_summarize(args: argparse.Namespace) -> None:
    """Summarize transcript using configured model provider."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    transcript_path = _resolve_path(base_dir, args.transcript)
    audio_path = _resolve_path(base_dir, args.audio)
    config = load_model_config(_resolve_path(base_dir, args.config))
    transcript = transcript_path.read_text(encoding="utf-8")

    summary = summarize_transcript(transcript, args.session_date, config)
    write_summary_json(summary, transcript_path.with_suffix(".summary.json"))
    session_file = _finalize_outputs(base_dir, summary, transcript_path, audio_path)
    print(f"Session note written: {session_file}")


def cmd_run(args: argparse.Namespace) -> None:
    """Full one-command pipeline: transcribe + summarize + export."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    audio_path = _resolve_path(base_dir, args.audio)
    transcript_path = base_dir / "transcripts" / f"{audio_path.stem}.txt"
    result = transcribe_audio(
        audio_path=audio_path,
        model_size=args.whisper_model,
        language=args.language,
    )
    write_transcription_files(result, transcript_path)

    config = load_model_config(_resolve_path(base_dir, args.config))
    summary = summarize_transcript(result.text, args.session_date, config)
    write_summary_json(summary, transcript_path.with_suffix(".summary.json"))
    session_file = _finalize_outputs(base_dir, summary, transcript_path, audio_path)

    print(f"Transcript written: {transcript_path}")
    print(f"Session note written: {session_file}")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser and subcommands."""
    parser = argparse.ArgumentParser(description="D&D session capture and indexing pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe = subparsers.add_parser("transcribe", help="Transcribe an audio file.")
    _add_project_root_arg(transcribe)
    transcribe.add_argument("--audio", required=True, help="Path to MP3/WAV audio file.")
    transcribe.add_argument("--whisper-model", default="base", help="Whisper model size.")
    transcribe.add_argument("--language", default=None, help="Optional language code.")
    transcribe.set_defaults(func=cmd_transcribe)

    summarize = subparsers.add_parser("summarize", help="Summarize an existing transcript.")
    _add_project_root_arg(summarize)
    summarize.add_argument("--transcript", required=True, help="Path to transcript text file.")
    summarize.add_argument("--audio", required=True, help="Original audio file path.")
    summarize.add_argument("--session-date", required=True, help="Session date YYYY-MM-DD.")
    summarize.add_argument("--config", default="model_config.json", help="Model config path.")
    summarize.set_defaults(func=cmd_summarize)

    run = subparsers.add_parser("run", help="Run transcription + summarization in one command.")
    _add_project_root_arg(run)
    run.add_argument("--audio", required=True, help="Path to MP3/WAV audio file.")
    run.add_argument("--session-date", required=True, help="Session date YYYY-MM-DD.")
    run.add_argument("--whisper-model", default="base", help="Whisper model size.")
    run.add_argument("--language", default=None, help="Optional language code.")
    run.add_argument("--config", default="model_config.json", help="Model config path.")
    run.set_defaults(func=cmd_run)

    prompt = subparsers.add_parser(
        "prepare-prompt",
        help="Create a prompt file you can paste into ChatGPT website.",
    )
    _add_project_root_arg(prompt)
    prompt.add_argument("--transcript", required=True, help="Path to transcript text file.")
    prompt.add_argument("--session-date", required=True, help="Session date YYYY-MM-DD.")
    prompt.set_defaults(func=cmd_prepare_prompt)

    apply_json = subparsers.add_parser(
        "apply-json",
        help="Apply JSON response from ChatGPT website and export notes/index.",
    )
    _add_project_root_arg(apply_json)
    apply_json.add_argument("--transcript", required=True, help="Path to transcript text file.")
    apply_json.add_argument("--summary-json", required=True, help="Path to JSON text file.")
    apply_json.add_argument("--audio", required=True, help="Original audio file path.")
    apply_json.set_defaults(func=cmd_apply_json)

    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

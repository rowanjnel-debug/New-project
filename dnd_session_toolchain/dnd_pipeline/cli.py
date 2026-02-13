"""Command line interface for the D&D session notes pipeline."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .cleanup import choose_prompt_source, clean_transcript_text
from .config import load_model_config
from .health import assert_transcription_ready, print_health_report, run_health_checks, run_setup
from .indexing import get_campaign_memory_context, get_previous_session_context, update_index
from .markdown_export import render_session_markdown, update_entity_pages
from .summarization import (
    build_previously_on_text,
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


def _display_path(path: Path, base_dir: Path) -> str:
    """Render a path relative to base_dir when possible, otherwise absolute."""
    try:
        return str(path.relative_to(base_dir).as_posix())
    except ValueError:
        return str(path.as_posix())


def _ensure_file_exists(path: Path, label: str) -> None:
    """Raise a clear error when required input file is missing."""
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def _require_transcription_ready(base_dir: Path) -> None:
    """Exit with user-friendly message if transcription tools are missing."""
    try:
        assert_transcription_ready(base_dir)
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(2)


def _generate_prompt_file(
    base_dir: Path,
    transcript_path: Path,
    session_date: str,
    use_cleaned: str,
) -> Path:
    """Generate manual ChatGPT prompt file for a transcript."""
    source_path = choose_prompt_source(transcript_path, use_cleaned)
    previous_context = get_previous_session_context(
        base_dir / "index.json",
        transcript_path,
    )
    campaign_memory = get_campaign_memory_context(
        base_dir / "index.json",
        transcript_path,
    )
    transcript = source_path.read_text(encoding="utf-8")
    prompt = build_manual_chatgpt_prompt(
        transcript,
        session_date,
        previous_context=previous_context,
        campaign_memory=campaign_memory,
    )
    prompt_path = transcript_path.with_suffix(".chatgpt_prompt.txt")
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"Prompt source transcript: {source_path}")
    if previous_context:
        title = str(previous_context.get("session_title", "")).strip()
        date_value = str(previous_context.get("session_date", "")).strip()
        print(f"Prompt previous context: {title} ({date_value})".strip())
    else:
        print("Prompt previous context: none found")
    print(
        "Prompt campaign memory: "
        f"{int(campaign_memory.get('historical_session_count', 0))} prior sessions, "
        f"{len(campaign_memory.get('known_characters', []))} characters, "
        f"{len(campaign_memory.get('known_locations', []))} locations, "
        f"{len(campaign_memory.get('known_factions', []))} factions"
    )
    print(f"Prompt written: {prompt_path}")
    return prompt_path


def _finalize_outputs(base_dir: Path, summary, transcript_path: Path, audio_path: Path) -> Path:
    """Write session markdown, entity pages, and campaign index."""
    slug = slugify(summary.session_title)
    session_file = base_dir / "sessions" / f"{summary.session_date}-{slug}.md"
    markdown = render_session_markdown(
        summary,
        transcript_file=_display_path(transcript_path, base_dir),
        audio_file=_display_path(audio_path, base_dir),
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
    _require_transcription_ready(base_dir)

    audio_path = _resolve_path(base_dir, args.audio)
    _ensure_file_exists(audio_path, "Audio file")
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
    _ensure_file_exists(transcript_path, "Transcript file")
    _generate_prompt_file(
        base_dir=base_dir,
        transcript_path=transcript_path,
        session_date=args.session_date,
        use_cleaned=args.use_cleaned,
    )


def cmd_clean_transcript(args: argparse.Namespace) -> None:
    """Clean a transcript by removing stutters and repeated fragments."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    transcript_path = _resolve_path(base_dir, args.transcript)
    _ensure_file_exists(transcript_path, "Transcript file")
    raw_text = transcript_path.read_text(encoding="utf-8")
    cleaned_text, stats = clean_transcript_text(raw_text)

    if args.in_place:
        output_path = transcript_path
    elif args.output:
        output_path = _resolve_path(base_dir, args.output)
    else:
        output_path = transcript_path.with_suffix(".cleaned.txt")

    output_path.write_text(cleaned_text, encoding="utf-8")
    print(f"Cleaned transcript written: {output_path}")
    print(
        "Cleanup stats: "
        f"lines {stats.lines_in}->{stats.lines_out}, words {stats.words_in}->{stats.words_out}"
    )


def cmd_apply_json(args: argparse.Namespace) -> None:
    """Consume JSON response from ChatGPT website and export notes/index."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    transcript_path = _resolve_path(base_dir, args.transcript)
    json_path = _resolve_path(base_dir, args.summary_json)
    audio_path = _resolve_path(base_dir, args.audio)
    _ensure_file_exists(transcript_path, "Transcript file")
    _ensure_file_exists(json_path, "Summary JSON")
    _ensure_file_exists(audio_path, "Audio file")
    previous_context = get_previous_session_context(
        base_dir / "index.json",
        transcript_path,
    )

    summary = parse_summary_json_text(json_path.read_text(encoding="utf-8"))
    if not summary.previously_on:
        summary.previously_on = build_previously_on_text(previous_context, summary.session_date)
    write_summary_json(summary, transcript_path.with_suffix(".summary.json"))
    session_file = _finalize_outputs(base_dir, summary, transcript_path, audio_path)
    print(f"Session note written: {session_file}")


def cmd_summarize(args: argparse.Namespace) -> None:
    """Summarize transcript using configured model provider."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    transcript_path = _resolve_path(base_dir, args.transcript)
    audio_path = _resolve_path(base_dir, args.audio)
    _ensure_file_exists(transcript_path, "Transcript file")
    _ensure_file_exists(audio_path, "Audio file")
    config = load_model_config(_resolve_path(base_dir, args.config))
    previous_context = get_previous_session_context(
        base_dir / "index.json",
        transcript_path,
    )
    campaign_memory = get_campaign_memory_context(
        base_dir / "index.json",
        transcript_path,
    )
    transcript = transcript_path.read_text(encoding="utf-8")

    summary = summarize_transcript(
        transcript,
        args.session_date,
        config,
        previous_context=previous_context,
        campaign_memory=campaign_memory,
    )
    write_summary_json(summary, transcript_path.with_suffix(".summary.json"))
    session_file = _finalize_outputs(base_dir, summary, transcript_path, audio_path)
    print(f"Session note written: {session_file}")


def cmd_run(args: argparse.Namespace) -> None:
    """Full one-command pipeline: transcribe + summarize + export."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)
    _require_transcription_ready(base_dir)

    audio_path = _resolve_path(base_dir, args.audio)
    _ensure_file_exists(audio_path, "Audio file")
    transcript_path = base_dir / "transcripts" / f"{audio_path.stem}.txt"
    result = transcribe_audio(
        audio_path=audio_path,
        model_size=args.whisper_model,
        language=args.language,
    )
    write_transcription_files(result, transcript_path)

    config = load_model_config(_resolve_path(base_dir, args.config))
    previous_context = get_previous_session_context(
        base_dir / "index.json",
        transcript_path,
    )
    campaign_memory = get_campaign_memory_context(
        base_dir / "index.json",
        transcript_path,
    )
    summary = summarize_transcript(
        result.text,
        args.session_date,
        config,
        previous_context=previous_context,
        campaign_memory=campaign_memory,
    )
    write_summary_json(summary, transcript_path.with_suffix(".summary.json"))
    session_file = _finalize_outputs(base_dir, summary, transcript_path, audio_path)

    print(f"Transcript written: {transcript_path}")
    print(f"Session note written: {session_file}")


def cmd_health_check(args: argparse.Namespace) -> None:
    """Run user-friendly environment checks."""
    base_dir = Path(args.project_root).resolve()
    checks = run_health_checks(base_dir, require_whisper=args.require_whisper)
    print_health_report(checks)
    failed = [c for c in checks if not c.ok]
    if failed:
        raise SystemExit(1)


def cmd_setup(args: argparse.Namespace) -> None:
    """Create local venv, install dependencies, and print health summary."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)
    run_setup(base_dir, upgrade_pip=not args.skip_pip_upgrade)
    checks = run_health_checks(base_dir, require_whisper=False)
    print_health_report(checks)
    if any(not c.ok for c in checks):
        print("Setup completed with issues. Review the failed checks above.")
    else:
        print("Setup complete. Environment is ready.")


def cmd_process_session(args: argparse.Namespace) -> None:
    """One command for manual workflow: transcribe -> clean -> prompt -> optional apply JSON."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)
    _require_transcription_ready(base_dir)

    audio_path = _resolve_path(base_dir, args.audio)
    _ensure_file_exists(audio_path, "Audio file")
    transcript_path = base_dir / "transcripts" / f"{audio_path.stem}.txt"

    result = transcribe_audio(
        audio_path=audio_path,
        model_size=args.whisper_model,
        language=args.language,
    )
    segments_path = write_transcription_files(result, transcript_path)
    print(f"Transcript written: {transcript_path}")
    print(f"Segments written: {segments_path}")

    cleaned_text, stats = clean_transcript_text(result.text)
    cleaned_path = transcript_path.with_suffix(".cleaned.txt")
    cleaned_path.write_text(cleaned_text, encoding="utf-8")
    print(f"Cleaned transcript written: {cleaned_path}")
    print(
        "Cleanup stats: "
        f"lines {stats.lines_in}->{stats.lines_out}, words {stats.words_in}->{stats.words_out}"
    )

    _generate_prompt_file(
        base_dir=base_dir,
        transcript_path=transcript_path,
        session_date=args.session_date,
        use_cleaned=args.use_cleaned,
    )

    manual_json_path = (
        _resolve_path(base_dir, args.summary_json)
        if args.summary_json
        else transcript_path.with_suffix(".manual.json")
    )

    if manual_json_path.exists():
        previous_context = get_previous_session_context(
            base_dir / "index.json",
            transcript_path,
        )
        summary = parse_summary_json_text(manual_json_path.read_text(encoding="utf-8"))
        if not summary.previously_on:
            summary.previously_on = build_previously_on_text(previous_context, summary.session_date)
        write_summary_json(summary, transcript_path.with_suffix(".summary.json"))
        session_file = _finalize_outputs(base_dir, summary, transcript_path, audio_path)
        print(f"Manual JSON found and applied: {manual_json_path}")
        print(f"Session note written: {session_file}")
    else:
        print("No manual JSON found yet.")
        print(f"Next step: save ChatGPT JSON to {manual_json_path}")
        print(
            "Then run: "
            f"python run_pipeline.py apply-json --project-root . --transcript \"{_display_path(transcript_path, base_dir)}\" "
            f"--summary-json \"{_display_path(manual_json_path, base_dir)}\" --audio \"{audio_path}\""
        )


def _ask(prompt: str, default: str = "") -> str:
    """Prompt user for input with optional default."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def cmd_wizard(args: argparse.Namespace) -> None:
    """Interactive assistant for non-technical users."""
    base_dir = Path(args.project_root).resolve()
    ensure_project_structure(base_dir)

    print("D&D Session Toolchain Wizard")
    print("1) Setup environment")
    print("2) Process new session (transcribe, clean, prompt, optional apply-json)")
    print("3) Apply existing manual JSON")
    print("4) Health check")

    choice = _ask("Choose an option", "2")

    if choice == "1":
        cmd_setup(
            argparse.Namespace(
                project_root=str(base_dir),
                skip_pip_upgrade=False,
            )
        )
        return

    if choice == "2":
        audio = _ask("Audio path (mp3/wav/mp4)")
        session_date = _ask("Session date (YYYY-MM-DD)", date.today().isoformat())
        whisper_model = _ask("Whisper model", "tiny")
        language = _ask("Language code (blank = auto)", "")
        use_cleaned = _ask("Prompt source mode: auto/always/never", "auto")
        summary_json = _ask("Manual JSON path (blank = auto)", "")
        cmd_process_session(
            argparse.Namespace(
                project_root=str(base_dir),
                audio=audio,
                session_date=session_date,
                whisper_model=whisper_model,
                language=language or None,
                use_cleaned=use_cleaned,
                summary_json=summary_json or None,
            )
        )
        return

    if choice == "3":
        transcript = _ask("Transcript path")
        summary_json = _ask("Manual JSON path")
        audio = _ask("Audio path")
        cmd_apply_json(
            argparse.Namespace(
                project_root=str(base_dir),
                transcript=transcript,
                summary_json=summary_json,
                audio=audio,
            )
        )
        return

    if choice == "4":
        cmd_health_check(
            argparse.Namespace(
                project_root=str(base_dir),
                require_whisper=True,
            )
        )
        return

    print("Unknown option. Please rerun wizard and choose 1-4.")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser and subcommands."""
    parser = argparse.ArgumentParser(description="D&D session capture and indexing pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup = subparsers.add_parser(
        "setup",
        help="Create .venv, install dependencies, and run health checks.",
    )
    _add_project_root_arg(setup)
    setup.add_argument(
        "--skip-pip-upgrade",
        action="store_true",
        help="Skip pip self-upgrade during setup.",
    )
    setup.set_defaults(func=cmd_setup)

    health = subparsers.add_parser(
        "health-check",
        help="Check environment readiness with plain-English fixes.",
    )
    _add_project_root_arg(health)
    health.add_argument(
        "--require-whisper",
        action="store_true",
        help="Also verify faster-whisper availability for transcription.",
    )
    health.set_defaults(func=cmd_health_check)

    wizard = subparsers.add_parser(
        "wizard",
        help="Interactive guided workflow for non-technical users.",
    )
    _add_project_root_arg(wizard)
    wizard.set_defaults(func=cmd_wizard)

    transcribe = subparsers.add_parser("transcribe", help="Transcribe an audio file.")
    _add_project_root_arg(transcribe)
    transcribe.add_argument("--audio", required=True, help="Path to MP3/WAV audio file.")
    transcribe.add_argument("--whisper-model", default="base", help="Whisper model size.")
    transcribe.add_argument("--language", default=None, help="Optional language code.")
    transcribe.set_defaults(func=cmd_transcribe)

    clean = subparsers.add_parser(
        "clean-transcript",
        help="Remove transcript stutters/repeats and write cleaned text.",
    )
    _add_project_root_arg(clean)
    clean.add_argument("--transcript", required=True, help="Path to transcript text file.")
    clean.add_argument(
        "--output",
        default=None,
        help="Output path for cleaned transcript (default: <transcript>.cleaned.txt).",
    )
    clean.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the original transcript file.",
    )
    clean.set_defaults(func=cmd_clean_transcript)

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

    process = subparsers.add_parser(
        "process-session",
        help="Transcribe, clean, generate prompt, and optionally apply manual JSON.",
    )
    _add_project_root_arg(process)
    process.add_argument("--audio", required=True, help="Path to MP3/WAV/MP4 audio file.")
    process.add_argument("--session-date", required=True, help="Session date YYYY-MM-DD.")
    process.add_argument("--whisper-model", default="tiny", help="Whisper model size.")
    process.add_argument("--language", default=None, help="Optional language code.")
    process.add_argument(
        "--use-cleaned",
        choices=["auto", "always", "never"],
        default="auto",
        help="Choose whether to use <transcript>.cleaned.txt as prompt source.",
    )
    process.add_argument(
        "--summary-json",
        default=None,
        help="Optional manual JSON path. If omitted, auto-looks for <transcript>.manual.json.",
    )
    process.set_defaults(func=cmd_process_session)

    prompt = subparsers.add_parser(
        "prepare-prompt",
        help="Create a prompt file you can paste into ChatGPT website.",
    )
    _add_project_root_arg(prompt)
    prompt.add_argument("--transcript", required=True, help="Path to transcript text file.")
    prompt.add_argument("--session-date", required=True, help="Session date YYYY-MM-DD.")
    prompt.add_argument(
        "--use-cleaned",
        choices=["auto", "always", "never"],
        default="auto",
        help="Choose whether to use <transcript>.cleaned.txt as prompt source.",
    )
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

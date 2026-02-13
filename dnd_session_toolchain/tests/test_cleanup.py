"""Unit tests for transcript cleanup and prompt source selection."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dnd_pipeline.cleanup import (  # noqa: E402
    choose_prompt_source,
    clean_line,
    clean_transcript_text,
)


class CleanupTests(unittest.TestCase):
    """Behavior tests for stutter/repeat cleanup."""

    def test_clean_line_collapses_repeated_words(self) -> None:
        self.assertEqual(clean_line("yeah yeah yeah that's that's true"), "yeah that's true")

    def test_clean_line_collapses_repeated_ngrams(self) -> None:
        self.assertEqual(
            clean_line("we can do that we can do that we can do that"),
            "we can do that",
        )

    def test_clean_line_removes_filler_only(self) -> None:
        self.assertEqual(clean_line("um uh erm"), "")

    def test_clean_transcript_removes_adjacent_duplicate_lines(self) -> None:
        raw = "hello there\nhello there\nhello there\nnext line\n"
        cleaned, stats = clean_transcript_text(raw)
        self.assertEqual(cleaned, "hello there\nnext line\n")
        self.assertEqual(stats.lines_in, 4)
        self.assertEqual(stats.lines_out, 2)


class PromptSourceTests(unittest.TestCase):
    """Behavior tests for choosing cleaned/original prompt source."""

    def test_choose_prompt_source_auto_prefers_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            transcript = base / "session.txt"
            cleaned = base / "session.cleaned.txt"
            transcript.write_text("raw", encoding="utf-8")
            cleaned.write_text("clean", encoding="utf-8")

            chosen = choose_prompt_source(transcript, "auto")
            self.assertEqual(chosen, cleaned)

    def test_choose_prompt_source_auto_falls_back_to_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            transcript = base / "session.txt"
            transcript.write_text("raw", encoding="utf-8")

            chosen = choose_prompt_source(transcript, "auto")
            self.assertEqual(chosen, transcript)

    def test_choose_prompt_source_always_requires_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            transcript = base / "session.txt"
            transcript.write_text("raw", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                choose_prompt_source(transcript, "always")

    def test_choose_prompt_source_invalid_mode_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            transcript = base / "session.txt"
            transcript.write_text("raw", encoding="utf-8")

            with self.assertRaises(ValueError):
                choose_prompt_source(transcript, "badmode")


if __name__ == "__main__":
    unittest.main()

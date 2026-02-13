"""Unit tests for previous-session context and prompt composition."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dnd_pipeline.indexing import get_previous_session_context  # noqa: E402
from dnd_pipeline.models import SessionSummary  # noqa: E402
from dnd_pipeline.summarization import (  # noqa: E402
    build_manual_chatgpt_prompt,
    build_previously_on_text,
)


class PreviousContextTests(unittest.TestCase):
    """Tests for loading prior-session context from index + summary files."""

    def test_get_previous_session_context_skips_current_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            transcripts = base / "transcripts"
            transcripts.mkdir(parents=True, exist_ok=True)

            prev_transcript = transcripts / "session-1.txt"
            curr_transcript = transcripts / "session-2.txt"
            prev_transcript.write_text("previous", encoding="utf-8")
            curr_transcript.write_text("current", encoding="utf-8")

            prev_summary = {
                "session_title": "Session One",
                "session_date": "2026-02-10",
                "characters": ["A"],
                "locations": ["B"],
                "factions": [],
                "events": ["E1"],
                "unresolved_hooks": ["Hook 1"],
                "previously_on": "Earlier recap.",
                "last_session_narrative": "Narrative one.",
                "plain_text_summary": "Summary one.",
                "backlink_block": "[[A]]",
            }
            prev_transcript.with_suffix(".summary.json").write_text(
                json.dumps(prev_summary),
                encoding="utf-8",
            )

            index_payload = {
                "sessions": [
                    {
                        "title": "Session One",
                        "date": "2026-02-10",
                        "note_file": "sessions/session-1.md",
                        "transcript_file": "transcripts/session-1.txt",
                    },
                    {
                        "title": "Session Two",
                        "date": "2026-02-11",
                        "note_file": "sessions/session-2.md",
                        "transcript_file": "transcripts/session-2.txt",
                    },
                ],
                "characters": {},
                "locations": {},
                "factions": {},
                "events": {},
                "unresolved_hooks": [],
                "updated_at": "",
            }
            index_path = base / "index.json"
            index_path.write_text(json.dumps(index_payload), encoding="utf-8")

            context = get_previous_session_context(index_path, curr_transcript)
            self.assertIsNotNone(context)
            assert context is not None
            self.assertEqual(context["session_title"], "Session One")
            self.assertEqual(context["previously_on"], "Earlier recap.")
            self.assertEqual(context["unresolved_hooks"], ["Hook 1"])


class PreviouslyOnPromptTests(unittest.TestCase):
    """Tests for previously_on construction and prompt inclusion."""

    def test_build_previously_on_prefers_explicit_prior_value(self) -> None:
        context = {"previously_on": "Already summarized."}
        value = build_previously_on_text(context, "2026-02-13")
        self.assertEqual(value, "Already summarized.")

    def test_build_manual_prompt_contains_previous_context(self) -> None:
        context = {
            "session_title": "Session Zero",
            "session_date": "2026-02-01",
            "last_session_narrative": "The party escaped.",
            "unresolved_hooks": ["Who betrayed the group?"],
        }
        prompt = build_manual_chatgpt_prompt("New transcript here", "2026-02-13", context)
        self.assertIn("Previous session context:", prompt)
        self.assertIn("Who betrayed the group?", prompt)

    def test_markdown_uses_previously_on(self) -> None:
        summary = SessionSummary(
            session_title="S",
            session_date="2026-02-13",
            previously_on="Previously recap text.",
        ).normalize()
        from dnd_pipeline.markdown_export import render_session_markdown  # local import for test speed

        markdown = render_session_markdown(summary, "transcripts/s.txt", "audio/s.mp3")
        self.assertIn("## Previously On", markdown)
        self.assertIn("Previously recap text.", markdown)


if __name__ == "__main__":
    unittest.main()

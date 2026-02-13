# D&D Session Voice Capture Toolchain

End-to-end local workflow for converting Discord D&D recordings into:
- transcripts
- structured session notes
- linked campaign index files for Obsidian

The project supports three summarization modes:
- `offline` (no LLM, heuristic fallback)
- `ollama` (local LLM, optional)
- `openai_compatible` (remote API, optional)

## Project Layout

```text
dnd_session_toolchain/
|- audio/
|- transcripts/
|- sessions/
|- characters/
|- locations/
|- factions/
|- events/
|- index.json
|- model_config.json
|- run_pipeline.py
|- requirements.txt
|- scripts/
`- dnd_pipeline/
```

## 1) Beginner-Friendly Quick Start (Recommended)

Run these in order:

```bash
cd dnd_session_toolchain
python run_pipeline.py setup --project-root .
python run_pipeline.py health-check --project-root . --require-whisper
python run_pipeline.py wizard --project-root .
```

If you prefer a non-interactive single command for a new session:

```bash
python run_pipeline.py process-session --project-root . --audio audio\session_12.mp3 --session-date 2026-02-13
```

What these do:
- `setup`: creates `.venv`, installs dependencies, and prepares local environment.
- `health-check`: gives plain-English pass/fail checks and fixes.
- `wizard`: guided interactive flow for setup, processing, and applying manual JSON.
- `process-session`: transcribes audio, cleans stutters/repeats, writes a ChatGPT prompt, and auto-applies JSON if `<transcript>.manual.json` exists.

## 2) Manual Dependency Install (Advanced)

```bash
cd dnd_session_toolchain
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

You also need `ffmpeg` available on your system path for audio decoding.

## 3) Configure Summarization Mode

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Edit `model_config.json`:
- No LLM (default-safe): set `"provider": "offline"`
- Local LLM (optional): set `"provider": "ollama"` and install/run Ollama
- Remote API (optional): set `"provider": "openai_compatible"` and provide `OPENAI_API_KEY`

Example `offline` config:

```json
{
  "provider": "offline",
  "model": "llama3.1:8b",
  "temperature": 0.2,
  "max_tokens": 1800,
  "ollama_base_url": "http://127.0.0.1:11434",
  "openai_base_url": "https://api.openai.com/v1"
}
```

## 4) One-Command Full Run

Place an audio file in `audio/`, then run:

```bash
python run_pipeline.py run --project-root . --audio audio\session_12.mp3 --session-date 2026-02-13
```

Outputs:
- `transcripts/session_12.txt`
- `transcripts/session_12.segments.json`
- `transcripts/session_12.summary.json`
- `sessions/YYYY-MM-DD-session-title.md`
- updated entity files in `characters/`, `locations/`, `factions/`, `events/`
- updated `index.json`

## 5) Manual ChatGPT Website Option (No API Integration)

This mode lets you use chatgpt.com manually and paste the response back.
For best continuity, keep one ongoing chat thread for your campaign and paste each new prompt into that same thread.

1. Transcribe only:

```bash
python run_pipeline.py transcribe --project-root . --audio audio\session_12.mp3
```

2. Optional: clean stutters/repeats in transcript:

```bash
python run_pipeline.py clean-transcript --project-root . --transcript transcripts\session_12.txt
```

3. Generate a paste-ready prompt:

```bash
python run_pipeline.py prepare-prompt --project-root . --transcript transcripts\session_12.txt --session-date 2026-02-13
```
By default, this uses `transcripts\session_12.cleaned.txt` if it exists.
Use `--use-cleaned never` to force the original transcript, or `--use-cleaned always` to require the cleaned file.
The prompt also automatically includes context from the most recent prior session in `index.json` to produce a "Previously On" recap.
It also includes a campaign-memory snapshot (recent sessions, known entities, open hooks) so the model can maintain long-running story continuity.

4. Paste `transcripts/session_12.chatgpt_prompt.txt` into chatgpt.com.
5. Save the returned JSON to `transcripts/session_12.manual.json`.
6. Apply JSON and export notes:

```bash
python run_pipeline.py apply-json --project-root . --transcript transcripts\session_12.txt --summary-json transcripts\session_12.manual.json --audio audio\session_12.mp3
```

## 6) Script Shortcuts

- `python scripts\run_full_pipeline.py --project-root . --audio audio\session_12.mp3 --session-date 2026-02-13`
- `python scripts\transcribe_session.py --project-root . --audio audio\session_12.mp3`
- `python scripts\clean_transcript.py --project-root . --transcript transcripts\session_12.txt`
- `python scripts\summarize_session.py --project-root . --transcript transcripts\session_12.txt --audio audio\session_12.mp3 --session-date 2026-02-13`
- `python scripts\export_markdown.py --project-root . --transcript transcripts\session_12.txt --summary-json transcripts\session_12.manual.json --audio audio\session_12.mp3`
- `python scripts\setup_toolchain.py --project-root .`
- `python scripts\wizard.py --project-root .`
- `python scripts\process_session.py --project-root . --audio audio\session_12.mp3 --session-date 2026-02-13`

## 7) Run Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## 8) JSON Schema Produced by Summarizer

```json
{
  "session_title": "string",
  "session_date": "YYYY-MM-DD",
  "characters": ["string"],
  "locations": ["string"],
  "factions": ["string"],
  "events": ["string"],
  "unresolved_hooks": ["string"],
  "previously_on": "string",
  "last_session_narrative": "string",
  "plain_text_summary": "string",
  "backlink_block": "[[Link One]]\\n[[Link Two]]"
}
```

Note: `events[]` are prompted to use tags for better structure:
`[IN_WORLD]`, `[RULES]`, `[TABLE_TALK]`, `[META]`.

## 9) Obsidian Import

1. Open Obsidian vault.
2. Copy or move this folder's generated note directories:
- `sessions/`
- `characters/`
- `locations/`
- `factions/`
- `events/`
3. Keep `index.json` in vault root or in a `meta/` folder for query tooling.

## 10) Example Outputs Included

- `transcripts/example_session.txt`
- `transcripts/example_session.summary.json`
- `sessions/2026-02-13-example-session-title.md`
- `characters/template-character.md`
- `locations/template-location.md`
- `factions/template-faction.md`
- `events/template-event.md`
- `index.json`

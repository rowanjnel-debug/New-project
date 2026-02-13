"""Wrapper script for manual ChatGPT JSON -> Markdown export mode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dnd_pipeline.cli import main


if __name__ == "__main__":
    sys.argv.insert(1, "apply-json")
    main()

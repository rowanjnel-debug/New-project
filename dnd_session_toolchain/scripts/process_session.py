"""Wrapper script for process-session mode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dnd_pipeline.cli import main


if __name__ == "__main__":
    project_root = str(Path(__file__).resolve().parents[1])
    sys.argv.insert(1, "process-session")
    if "--project-root" not in sys.argv:
        sys.argv.extend(["--project-root", project_root])
    main()

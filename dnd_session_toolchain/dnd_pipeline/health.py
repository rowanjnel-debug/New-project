"""Environment checks and setup helpers for user-friendly CLI flows."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HealthCheck:
    """Single health-check result."""

    name: str
    ok: bool
    details: str
    fix: str = ""


def get_venv_python(venv_dir: Path) -> Path:
    """Return interpreter path inside a venv for current platform."""
    if sys.platform.startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _module_available(module_name: str) -> bool:
    """Return True if a Python module can be discovered."""
    return importlib.util.find_spec(module_name) is not None


def run_health_checks(base_dir: Path, require_whisper: bool = False) -> list[HealthCheck]:
    """Run environment checks and return results."""
    checks: list[HealthCheck] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append(
        HealthCheck(
            name="python_version",
            ok=py_ok,
            details=f"Using Python {sys.version.split()[0]}",
            fix="Install Python 3.10+ and rerun.",
        )
    )

    venv_dir = base_dir / ".venv"
    venv_python = get_venv_python(venv_dir)
    checks.append(
        HealthCheck(
            name="virtualenv",
            ok=venv_python.exists(),
            details=f"Expected venv interpreter at {venv_python}",
            fix="Run: python run_pipeline.py setup --project-root .",
        )
    )

    ffmpeg_path = shutil.which("ffmpeg")
    checks.append(
        HealthCheck(
            name="ffmpeg",
            ok=bool(ffmpeg_path),
            details=f"ffmpeg path: {ffmpeg_path or 'not found'}",
            fix="Install ffmpeg and ensure it is available on PATH.",
        )
    )

    if require_whisper:
        whisper_ok = _module_available("faster_whisper")
        checks.append(
            HealthCheck(
                name="faster_whisper",
                ok=whisper_ok,
                details="faster_whisper import check",
                fix="Install dependencies: pip install -r requirements.txt",
            )
        )

    return checks


def print_health_report(checks: list[HealthCheck]) -> None:
    """Print readable health report with fixes."""
    print("Health check report:")
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        print(f"- {check.name}: {status} - {check.details}")
        if not check.ok and check.fix:
            print(f"  Fix: {check.fix}")


def assert_transcription_ready(base_dir: Path) -> None:
    """Raise a helpful error if transcription prerequisites are missing."""
    checks = run_health_checks(base_dir, require_whisper=True)
    failed = [c for c in checks if not c.ok]
    if failed:
        lines = ["Transcription prerequisites are not ready:"]
        for check in failed:
            lines.append(f"- {check.name}: {check.details}")
            if check.fix:
                lines.append(f"  Fix: {check.fix}")
        raise RuntimeError("\n".join(lines))


def run_setup(base_dir: Path, upgrade_pip: bool = True) -> None:
    """Create local venv and install dependencies into it."""
    venv_dir = base_dir / ".venv"
    venv_python = get_venv_python(venv_dir)

    if not venv_python.exists():
        print(f"Creating virtual environment at {venv_dir} ...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
        )
    else:
        print(f"Using existing virtual environment at {venv_dir}")

    pip_cmd = [str(venv_python), "-m", "pip"]
    if upgrade_pip:
        print("Upgrading pip ...")
        subprocess.run(pip_cmd + ["install", "--upgrade", "pip"], check=True)

    requirements = base_dir / "requirements.txt"
    print("Installing dependencies ...")
    subprocess.run(pip_cmd + ["install", "-r", str(requirements)], check=True)

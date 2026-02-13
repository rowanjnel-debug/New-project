"""Configuration loading for model and runtime options."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        """Fallback no-op when python-dotenv is not installed."""
        return False


@dataclass
class ModelConfig:
    """Runtime settings for summarization model routing."""

    provider: str = "offline"
    model: str = "llama3.1:8b"
    temperature: float = 0.2
    max_tokens: int = 1800
    ollama_base_url: str = "http://127.0.0.1:11434"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""


def load_model_config(path: Path) -> ModelConfig:
    """Load model configuration from JSON file and environment variables."""
    load_dotenv()
    payload = json.loads(path.read_text(encoding="utf-8"))

    return ModelConfig(
        provider=str(payload.get("provider", "offline")).strip().lower(),
        model=str(payload.get("model", "llama3.1:8b")).strip(),
        temperature=float(payload.get("temperature", 0.2)),
        max_tokens=int(payload.get("max_tokens", 1800)),
        ollama_base_url=str(
            payload.get("ollama_base_url", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
        ).rstrip("/"),
        openai_base_url=str(
            payload.get("openai_base_url", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        ).rstrip("/"),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
    )

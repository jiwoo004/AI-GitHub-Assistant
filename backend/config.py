"""Configuration management for AI Git Assistant.

Stores settings in ~/.ai-git-assistant/config.json
"""
import json
from pathlib import Path
from typing import Dict, Any
import shutil


def get_config_dir() -> Path:
    """Get config directory, create if not exists."""
    config_dir = Path.home() / ".ai-git-assistant"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get config file path."""
    return get_config_dir() / "config.json"


def load_config() -> Dict[str, Any]:
    """Load config from file or return defaults."""
    config_file = get_config_file()
    defaults = {
        "max_diff_bytes": 2_000_000,  # Default: 2 MB
        "ai_timeout_seconds": 30.0,
        # Preferred git executable path; default to `which git` or 'git'
        "git_executable": shutil.which("git") or "git",
        # Ollama settings
        "ollama_host": "http://localhost:11434",
        "ollama_model": "exaone3.5:2.4b",
    }
    if not config_file.exists():
        return defaults
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        # Merge user config with defaults
        result = defaults.copy()
        result.update(user_config)
        return result
    except Exception as e:
        print(f"Error loading config: {e}, using defaults")
        return defaults


def save_config(config: Dict[str, Any]) -> None:
    """Save config to file."""
    config_file = get_config_file()
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")


def validate_max_diff_bytes(value: int) -> bool:
    """Validate max_diff_bytes is in acceptable range."""
    return 100_000 <= value <= 100_000_000  # 100 KB to 100 MB


def validate_ai_timeout(value: float) -> bool:
    """Validate ai_timeout_seconds is in acceptable range."""
    return 5.0 <= value <= 300.0  # 5s to 5 minutes

"""Shared pytest fixtures for PromptManager tests."""

import json
from pathlib import Path

import pytest

from prompt_manager import PromptManager


@pytest.fixture()
def sample_prompts_data() -> dict:
    """Return a known test prompts configuration."""
    return {
        "settings": {
            "auto_close": False,
            "show_notifications": True,
        },
        "categories": [
            {
                "name": "Meetings",
                "prompts": [
                    {
                        "title": "Clean transcript",
                        "text": "Fix grammar and punctuation in transcripts.",
                    },
                    {
                        "title": "Summarize meeting",
                        "text": "Create a structured meeting summary with action items.",
                    },
                ],
            },
            {
                "name": "Git",
                "prompts": [
                    {
                        "title": "Create and push feature branch",
                        "text": "Create a new feature branch and push to remote.",
                    },
                ],
            },
            {
                "name": "Project Management",
                "prompts": [
                    {
                        "title": "Break Down the Big Picture",
                        "text": "Break down the project into phases.",
                    },
                    {
                        "title": "Create Full Project Plan",
                        "text": "Build a full project plan with deliverables.",
                    },
                    {
                        "title": "RACI Chart Generator",
                        "text": "Create a RACI chart for the project.",
                    },
                ],
            },
        ],
    }


@pytest.fixture()
def tmp_json_config(tmp_path: Path, sample_prompts_data: dict) -> Path:
    """Create a temporary prompts.json file with test data and return its path."""
    config_path = tmp_path / "prompts.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(sample_prompts_data, f, indent=2)
    return config_path


@pytest.fixture()
def prompt_manager(tmp_json_config: Path) -> PromptManager:
    """Create a PromptManager pointed at a temporary test config file."""
    return PromptManager(config_path=tmp_json_config)

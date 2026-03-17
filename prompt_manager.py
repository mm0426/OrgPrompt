"""Prompt management - loading, caching, and searching prompts."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class Prompt:
    """Represents a single prompt."""
    title: str
    text: str
    category: str


class PromptManager:
    """Manages prompt loading and searching."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent / "prompts.json"
        self._data: dict = {}
        self._prompts: list[Prompt] = []
        self._categories: list[str] = []
        self._load()

    def _load(self) -> None:
        """Load prompts from JSON file."""
        if not self.config_path.exists():
            self._create_default_config()
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

        self._prompts = []
        self._categories = []

        for category in self._data.get("categories", []):
            cat_name = category.get("name", "Uncategorized")
            self._categories.append(cat_name)
            for prompt in category.get("prompts", []):
                self._prompts.append(Prompt(
                    title=prompt.get("title", "Untitled"),
                    text=prompt.get("text", ""),
                    category=cat_name
                ))

    def _create_default_config(self) -> None:
        """Create a default configuration file."""
        default = {
            "settings": {"auto_close": True, "show_notifications": True},
            "categories": [{
                "name": "General",
                "prompts": [{
                    "title": "Example Prompt",
                    "text": "This is an example prompt. Edit prompts.json to add your own!"
                }]
            }]
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2)
        self._load()

    def reload(self) -> None:
        """Reload prompts from file."""
        self._load()

    @property
    def settings(self) -> dict:
        """Get settings from config."""
        return self._data.get("settings", {"auto_close": True, "show_notifications": True})

    @property
    def categories(self) -> list[str]:
        """Get list of category names."""
        return self._categories

    def get_prompts_by_category(self, category: str) -> list[Prompt]:
        """Get all prompts in a category."""
        return [p for p in self._prompts if p.category == category]

    def get_all_prompts(self) -> list[Prompt]:
        """Get all prompts."""
        return self._prompts

    def search(self, query: str) -> list[Prompt]:
        """Search prompts by title or text."""
        if not query:
            return self._prompts

        query_lower = query.lower()
        return [
            p for p in self._prompts
            if query_lower in p.title.lower() or query_lower in p.text.lower()
        ]

    def get_category_prompt_count(self, category: str) -> int:
        """Get number of prompts in a category."""
        return len([p for p in self._prompts if p.category == category])

"""Prompt management - loading, caching, and searching prompts."""

import json
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
        self._builtin_cache: list[Prompt] | None = None
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
        self._builtin_cache = None
        self._load()

    @property
    def settings(self) -> dict:
        """Get settings from config."""
        return self._data.get("settings", {"auto_close": True, "show_notifications": True})

    # --- Workflow support methods ---

    def get_workflow_file_paths(self) -> dict[str, str]:
        """Get workflow file paths from settings.

        Returns dict with 'design_spec_path' and 'questions_file_path' keys.
        Defaults to empty strings if workflow_files key is missing.
        """
        wf = self.settings.get("workflow_files", {})
        return {
            "design_spec_path": wf.get("design_spec_path", ""),
            "questions_file_path": wf.get("questions_file_path", ""),
        }

    def set_workflow_file_paths(
        self, design_spec_path: str, questions_file_path: str
    ) -> bool:
        """Save workflow file paths to prompts.json.

        Uses atomic write: read -> modify -> write to temp -> rename.
        Returns True on success, False on failure.
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "settings" not in data:
                data["settings"] = {}
            data["settings"]["workflow_files"] = {
                "design_spec_path": design_spec_path,
                "questions_file_path": questions_file_path,
            }

            tmp_path = self.config_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp_path.replace(self.config_path)

            self._data = data
            self._builtin_cache = None
            self._load()
            return True
        except Exception:
            logger.exception(
                "Failed to save workflow file paths to %s", self.config_path
            )
            return False

    def get_built_in_prompts(self) -> list[Prompt]:
        """Get built-in workflow prompts with placeholders substituted.

        Returns cached prompts when available. Returns empty list if
        standard-prompts.txt is missing or malformed.
        """
        if self._builtin_cache is not None:
            return self._builtin_cache

        from workflow_prompt_templates import load_builtin_prompts

        paths = self.get_workflow_file_paths()
        config_dir = self.config_path.parent
        try:
            self._builtin_cache = load_builtin_prompts(
                config_dir, paths["design_spec_path"], paths["questions_file_path"]
            )
            return self._builtin_cache
        except (FileNotFoundError, ValueError):
            self._builtin_cache = []
            return []

    def get_built_in_category_name(self) -> str | None:
        """Return 'Built-in Workflow' if built-in prompts are available, else None."""
        from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

        return BUILT_IN_CATEGORY_NAME if self.get_built_in_prompts() else None

    def get_prompt_availability_for(self, prompt_index: int) -> tuple[bool, str]:
        """Get availability for a built-in prompt by index."""
        from workflow_availability import get_prompt_availability

        paths = self.get_workflow_file_paths()
        return get_prompt_availability(
            prompt_index, paths["design_spec_path"], paths["questions_file_path"]
        )

    def get_built_in_prompt_count(self) -> int:
        """Get number of built-in prompts."""
        return len(self.get_built_in_prompts())

    # --- Existing properties/methods (modified) ---

    @property
    def categories(self) -> list[str]:
        """Get list of category names.

        Built-in workflow category appears first when built-in prompts are
        available.
        """
        built_in = self.get_built_in_category_name()
        if built_in:
            return [built_in] + self._categories
        return self._categories

    def get_prompts_by_category(self, category: str) -> list[Prompt]:
        """Get all prompts in a category."""
        return [p for p in self._prompts if p.category == category]

    def get_all_prompts(self) -> list[Prompt]:
        """Get all prompts."""
        return self._prompts

    def search(self, query: str) -> list[Prompt]:
        """Search prompts by title or text, including built-in workflow prompts."""
        all_prompts = self._prompts + self.get_built_in_prompts()

        if not query:
            return all_prompts

        query_lower = query.lower()
        return [
            p for p in all_prompts
            if query_lower in p.title.lower() or query_lower in p.text.lower()
        ]

    def get_category_prompt_count(self, category: str) -> int:
        """Get number of prompts in a category, including built-in prompts."""
        from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

        count = len([p for p in self._prompts if p.category == category])
        if category == BUILT_IN_CATEGORY_NAME:
            count += len(self.get_built_in_prompts())
        return count

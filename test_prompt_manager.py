"""Regression tests for PromptManager."""

import json
from pathlib import Path

from prompt_manager import Prompt, PromptManager


def test_load_prompts_from_json(prompt_manager: PromptManager) -> None:
    """Verifies prompts load correctly from a test prompts.json."""
    prompts = prompt_manager.get_all_prompts()

    assert len(prompts) == 6

    titles = {p.title for p in prompts}
    assert "Clean transcript" in titles
    assert "Summarize meeting" in titles
    assert "Create and push feature branch" in titles
    assert "Break Down the Big Picture" in titles
    assert "Create Full Project Plan" in titles
    assert "RACI Chart Generator" in titles


def test_categories_order(prompt_manager: PromptManager) -> None:
    """Verifies category list matches JSON order."""
    categories = prompt_manager.categories

    assert categories == ["Meetings", "Git", "Project Management"]


def test_search_by_title(prompt_manager: PromptManager) -> None:
    """Verifies case-insensitive title search."""
    results = prompt_manager.search("clean transcript")

    assert len(results) == 1
    assert results[0].title == "Clean transcript"

    # Case-insensitive check
    results_upper = prompt_manager.search("CLEAN TRANSCRIPT")
    assert len(results_upper) == 1
    assert results_upper[0].title == "Clean transcript"


def test_search_by_text(prompt_manager: PromptManager) -> None:
    """Verifies case-insensitive text search."""
    results = prompt_manager.search("action items")

    assert len(results) == 1
    assert results[0].title == "Summarize meeting"

    # Case-insensitive check
    results_upper = prompt_manager.search("ACTION ITEMS")
    assert len(results_upper) == 1


def test_get_prompts_by_category(prompt_manager: PromptManager) -> None:
    """Verifies category filtering returns correct prompts."""
    meetings = prompt_manager.get_prompts_by_category("Meetings")

    assert len(meetings) == 2
    assert all(p.category == "Meetings" for p in meetings)

    titles = {p.title for p in meetings}
    assert titles == {"Clean transcript", "Summarize meeting"}


def test_get_prompts_by_category_empty(prompt_manager: PromptManager) -> None:
    """Returns empty list for non-existent category."""
    results = prompt_manager.get_prompts_by_category("NonExistent")

    assert results == []


def test_search_empty_query(prompt_manager: PromptManager) -> None:
    """Returns all prompts when query is empty."""
    results = prompt_manager.search("")

    assert len(results) == 6


def test_search_no_results(prompt_manager: PromptManager) -> None:
    """Returns empty list when nothing matches."""
    results = prompt_manager.search("xyznonexistent123")

    assert results == []


def test_reload_refreshes_data(
    prompt_manager: PromptManager, tmp_json_config: Path
) -> None:
    """Verifies reload picks up file changes."""
    # Initially 6 prompts
    assert len(prompt_manager.get_all_prompts()) == 6

    # Overwrite the config file with a new category
    new_data = {
        "settings": {"auto_close": True, "show_notifications": False},
        "categories": [
            {
                "name": "Testing",
                "prompts": [
                    {"title": "Unit test", "text": "Write unit tests."},
                    {"title": "Integration test", "text": "Write integration tests."},
                    {"title": "E2E test", "text": "Write end-to-end tests."},
                ],
            }
        ],
    }
    with open(tmp_json_config, "w", encoding="utf-8") as f:
        json.dump(new_data, f, indent=2)

    # Reload and verify new data
    prompt_manager.reload()

    prompts = prompt_manager.get_all_prompts()
    assert len(prompts) == 3
    assert prompt_manager.categories == ["Testing"]
    titles = {p.title for p in prompts}
    assert titles == {"Unit test", "Integration test", "E2E test"}

    # Verify settings also updated
    assert prompt_manager.settings["show_notifications"] is False


def test_missing_json_creates_default(tmp_path: Path) -> None:
    """Verifies default config creation on missing file."""
    missing_path = tmp_path / "nonexistent.json"

    manager = PromptManager(config_path=missing_path)

    # The file should now exist
    assert missing_path.exists()

    # Verify default content
    assert manager.categories == ["General"]
    prompts = manager.get_prompts_by_category("General")
    assert len(prompts) == 1
    assert prompts[0].title == "Example Prompt"


def test_settings_property(prompt_manager: PromptManager) -> None:
    """Verifies settings access returns dict with expected keys."""
    settings = prompt_manager.settings

    assert isinstance(settings, dict)
    assert "auto_close" in settings
    assert "show_notifications" in settings
    assert settings["auto_close"] is False
    assert settings["show_notifications"] is True


def test_get_all_prompts(prompt_manager: PromptManager) -> None:
    """Returns all prompts across categories."""
    prompts = prompt_manager.get_all_prompts()

    assert len(prompts) == 6
    assert all(isinstance(p, Prompt) for p in prompts)

    categories = {p.category for p in prompts}
    assert categories == {"Meetings", "Git", "Project Management"}


def test_get_category_prompt_count(prompt_manager: PromptManager) -> None:
    """Returns correct count per category."""
    assert prompt_manager.get_category_prompt_count("Meetings") == 2
    assert prompt_manager.get_category_prompt_count("Git") == 1
    assert prompt_manager.get_category_prompt_count("Project Management") == 3
    assert prompt_manager.get_category_prompt_count("NonExistent") == 0

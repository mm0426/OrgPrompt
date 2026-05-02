"""Unit tests for PromptManager workflow integration (WU-2b).

Tests the workflow methods added to PromptManager:
- get_workflow_file_paths / set_workflow_file_paths
- get_built_in_prompts / get_built_in_category_name
- get_prompt_availability_for / get_built_in_prompt_count
- Modified categories, search, get_category_prompt_count
"""

import json
from pathlib import Path

import pytest

from prompt_manager import Prompt, PromptManager

# ---------------------------------------------------------------------------
# Minimal standard-prompts.txt content used across tests.
# Three blocks matching the real file structure.
# ---------------------------------------------------------------------------
STANDARD_PROMPTS_TEMPLATE = (
    "## Critical Questions\n"
    "Review this project summary - ____. Identify any unclear, missing, or "
    "risky elements I should address before we start. Frame your response as "
    "a series of critical questions I need to answer and write those questions "
    "to a new file in md format.\n"
    "\n"
    "## Update Spec from Answers\n"
    "update ____ with details that answer all of the questions in #### (while "
    "keeping all details that don't contradict the answers and also keeping "
    "the design spec format).  Ask me if you are not sure about high level "
    "decisions.\n"
    "\n"
    "## RFC Pipeline\n"
    "I have an RFC at ____.  Use the ralphinho-rfc-pipeline pattern:  1. "
    "Decompose it into work units with a dependency DAG  2. For each layer, "
    "run units in parallel using the Task tool  3. Each unit gets: research "
    "→ plan → implement → test → review  4. Use separate agents for each "
    "stage (author-bias elimination)  5. Land via merge queue with conflict "
    "recovery\n"
)


def _write_json_config(
    path: Path,
    *,
    auto_close: bool = True,
    show_notifications: bool = True,
    categories: list | None = None,
    workflow_files: dict | None = None,
) -> Path:
    """Write a prompts.json to *path* and return it."""
    data: dict = {
        "settings": {
            "auto_close": auto_close,
            "show_notifications": show_notifications,
        },
        "categories": categories or [],
    }
    if workflow_files is not None:
        data["settings"]["workflow_files"] = workflow_files
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workflow_prompt_manager(tmp_path: Path) -> PromptManager:
    """Create a PromptManager with both prompts.json and standard-prompts.txt."""
    config = tmp_path / "prompts.json"
    _write_json_config(config)

    template = tmp_path / "standard-prompts.txt"
    template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")

    return PromptManager(config_path=config)


@pytest.fixture()
def workflow_prompt_manager_with_categories(tmp_path: Path) -> PromptManager:
    """PromptManager with user categories AND standard-prompts.txt."""
    config = tmp_path / "prompts.json"
    _write_json_config(
        config,
        categories=[
            {
                "name": "Meetings",
                "prompts": [
                    {"title": "Summarize", "text": "Summarize the meeting."},
                ],
            },
        ],
    )

    template = tmp_path / "standard-prompts.txt"
    template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")

    return PromptManager(config_path=config)


@pytest.fixture()
def workflow_prompt_manager_no_template(tmp_path: Path) -> PromptManager:
    """PromptManager with prompts.json but NO standard-prompts.txt."""
    config = tmp_path / "prompts.json"
    _write_json_config(config)
    return PromptManager(config_path=config)


@pytest.fixture()
def workflow_prompt_manager_with_paths(tmp_path: Path) -> PromptManager:
    """PromptManager with workflow_file_paths already saved."""
    config = tmp_path / "prompts.json"
    _write_json_config(
        config,
        workflow_files={
            "design_spec_path": "d:\\specs\\my-design.md",
            "questions_file_path": "d:\\specs\\questions.md",
        },
    )

    template = tmp_path / "standard-prompts.txt"
    template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")

    return PromptManager(config_path=config)


# ===========================================================================
# Workflow File Paths
# ===========================================================================


class TestGetWorkflowFilePaths:
    """Tests for get_workflow_file_paths()."""

    def test_get_workflow_file_paths_defaults_empty(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """When no workflow_files in JSON, returns empty strings."""
        paths = workflow_prompt_manager.get_workflow_file_paths()
        assert paths["design_spec_path"] == ""
        assert paths["questions_file_path"] == ""

    def test_get_workflow_file_paths_returns_saved(
        self, workflow_prompt_manager_with_paths: PromptManager
    ) -> None:
        """When workflow_files saved, returns those values."""
        paths = workflow_prompt_manager_with_paths.get_workflow_file_paths()
        assert paths["design_spec_path"] == "d:\\specs\\my-design.md"
        assert paths["questions_file_path"] == "d:\\specs\\questions.md"

    def test_get_workflow_file_paths_partial(self, tmp_path: Path) -> None:
        """When only design_spec_path is set, questions_file_path defaults to empty."""
        config = tmp_path / "prompts.json"
        _write_json_config(
            config,
            workflow_files={"design_spec_path": "d:\\specs\\partial.md"},
        )

        template = tmp_path / "standard-prompts.txt"
        template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")

        manager = PromptManager(config_path=config)
        paths = manager.get_workflow_file_paths()
        assert paths["design_spec_path"] == "d:\\specs\\partial.md"
        assert paths["questions_file_path"] == ""


# ===========================================================================
# Settings Round-Trip
# ===========================================================================


class TestSetWorkflowFilePaths:
    """Tests for set_workflow_file_paths()."""

    def test_set_workflow_file_paths_round_trip(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """Set then get returns same values."""
        workflow_prompt_manager.set_workflow_file_paths(
            design_spec_path="d:\\projects\\spec.md",
            questions_file_path="d:\\projects\\questions.md",
        )
        paths = workflow_prompt_manager.get_workflow_file_paths()
        assert paths["design_spec_path"] == "d:\\projects\\spec.md"
        assert paths["questions_file_path"] == "d:\\projects\\questions.md"

    def test_set_workflow_file_paths_preserves_categories(
        self, workflow_prompt_manager_with_categories: PromptManager
    ) -> None:
        """Existing categories/prompts not lost after write."""
        manager = workflow_prompt_manager_with_categories

        # Verify pre-existing data
        user_prompts = [
            p for p in manager.get_all_prompts() if p.category == "Meetings"
        ]
        assert len(user_prompts) == 1
        assert user_prompts[0].title == "Summarize"

        # Write workflow paths
        manager.set_workflow_file_paths(
            design_spec_path="d:\\specs\\new.md",
            questions_file_path="d:\\specs\\q.md",
        )

        # Reload from disk to verify persistence
        manager.reload()

        # User categories still intact
        assert "Meetings" in manager.categories
        meetings = manager.get_prompts_by_category("Meetings")
        assert len(meetings) == 1
        assert meetings[0].title == "Summarize"

    def test_set_workflow_file_paths_preserves_settings(
        self, tmp_path: Path
    ) -> None:
        """Existing settings (auto_close, etc.) not lost."""
        config = tmp_path / "prompts.json"
        _write_json_config(
            config,
            auto_close=False,
            show_notifications=False,
            categories=[
                {
                    "name": "Dev",
                    "prompts": [
                        {"title": "Test", "text": "text"},
                    ],
                },
            ],
        )

        template = tmp_path / "standard-prompts.txt"
        template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")

        manager = PromptManager(config_path=config)
        assert manager.settings["auto_close"] is False
        assert manager.settings["show_notifications"] is False

        manager.set_workflow_file_paths(
            design_spec_path="d:\\new\\spec.md",
            questions_file_path="d:\\new\\q.md",
        )

        # Reload and verify settings survived
        manager.reload()
        assert manager.settings["auto_close"] is False
        assert manager.settings["show_notifications"] is False

    def test_set_workflow_file_paths_atomic_write(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """File is valid JSON after write (no corruption)."""
        workflow_prompt_manager.set_workflow_file_paths(
            design_spec_path="d:\\atomic\\spec.md",
            questions_file_path="d:\\atomic\\q.md",
        )

        # Read the file directly and verify it is valid JSON
        raw = workflow_prompt_manager.config_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)  # Will raise if not valid JSON

        assert "settings" in parsed
        assert "workflow_files" in parsed["settings"]
        assert parsed["settings"]["workflow_files"]["design_spec_path"] == "d:\\atomic\\spec.md"
        assert parsed["settings"]["workflow_files"]["questions_file_path"] == "d:\\atomic\\q.md"


# ===========================================================================
# Built-in Prompts
# ===========================================================================


class TestGetBuiltInPrompts:
    """Tests for get_built_in_prompts()."""

    def test_get_built_in_prompts_returns_prompts(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """With standard-prompts.txt present, returns 3 Prompt objects."""
        prompts = workflow_prompt_manager.get_built_in_prompts()
        assert len(prompts) == 3
        assert all(isinstance(p, Prompt) for p in prompts)

    def test_get_built_in_prompts_category(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """All prompts have category 'Built-in Workflow'."""
        prompts = workflow_prompt_manager.get_built_in_prompts()
        assert all(p.category == "Built-in Workflow" for p in prompts)

    def test_get_built_in_prompts_missing_file(
        self, workflow_prompt_manager_no_template: PromptManager
    ) -> None:
        """Returns empty list when standard-prompts.txt missing."""
        prompts = workflow_prompt_manager_no_template.get_built_in_prompts()
        assert prompts == []

    def test_get_built_in_prompts_substitution(
        self, workflow_prompt_manager_with_paths: PromptManager
    ) -> None:
        """With design_spec_path set, ____ is replaced in text."""
        prompts = workflow_prompt_manager_with_paths.get_built_in_prompts()

        # Prompt 0 (Critical Questions) uses ____
        assert "____" not in prompts[0].text
        assert "d:\\specs\\my-design.md" in prompts[0].text

        # Prompt 1 (Update Spec from Answers) uses ____ and ####
        assert "____" not in prompts[1].text
        assert "####" not in prompts[1].text
        assert "d:\\specs\\my-design.md" in prompts[1].text
        assert "d:\\specs\\questions.md" in prompts[1].text

        # Prompt 2 (RFC Pipeline) uses ____
        assert "____" not in prompts[2].text
        assert "d:\\specs\\my-design.md" in prompts[2].text

    def test_get_built_in_prompts_no_substitution_when_empty(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """With empty paths, tokens remain raw."""
        prompts = workflow_prompt_manager.get_built_in_prompts()

        # All three prompts should still contain ____ since design_spec_path is empty
        assert all("____" in p.text for p in prompts)

        # Prompt 1 should still contain #### since questions_file_path is empty
        assert "####" in prompts[1].text


# ===========================================================================
# Built-in Category
# ===========================================================================


class TestGetBuiltinCategoryName:
    """Tests for get_built_in_category_name()."""

    def test_get_built_in_category_name_available(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """Returns 'Built-in Workflow' when template file exists."""
        name = workflow_prompt_manager.get_built_in_category_name()
        assert name == "Built-in Workflow"

    def test_get_built_in_category_name_unavailable(
        self, workflow_prompt_manager_no_template: PromptManager
    ) -> None:
        """Returns None when template file missing."""
        name = workflow_prompt_manager_no_template.get_built_in_category_name()
        assert name is None


class TestCategoriesProperty:
    """Tests for the modified categories property."""

    def test_categories_prepends_builtin(
        self, workflow_prompt_manager_with_categories: PromptManager
    ) -> None:
        """Categories list has 'Built-in Workflow' first."""
        cats = workflow_prompt_manager_with_categories.categories
        assert cats[0] == "Built-in Workflow"
        assert "Meetings" in cats

    def test_categories_no_builtin_when_missing(
        self, workflow_prompt_manager_no_template: PromptManager
    ) -> None:
        """Categories unchanged when no template file."""
        cats = workflow_prompt_manager_no_template.categories
        assert "Built-in Workflow" not in cats


# ===========================================================================
# Availability
# ===========================================================================


class TestGetPromptAvailabilityFor:
    """Tests for get_prompt_availability_for()."""

    def test_get_prompt_availability_for_prompt_0_ready(
        self, workflow_prompt_manager_with_paths: PromptManager
    ) -> None:
        """Returns (True, '') when design_spec_path set (Prompt 0 needs only design spec)."""
        available, reason = workflow_prompt_manager_with_paths.get_prompt_availability_for(0)
        assert available is True
        assert reason == ""

    def test_get_prompt_availability_for_prompt_1_needs_questions(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """Returns (False, 'Missing questions file path') when only design_spec_path set."""
        # workflow_prompt_manager has empty paths, so Prompt 1 is not available.
        # First, set only the design_spec_path.
        workflow_prompt_manager.set_workflow_file_paths(
            design_spec_path="d:\\specs\\design.md",
            questions_file_path="",
        )
        available, reason = workflow_prompt_manager.get_prompt_availability_for(1)
        assert available is False
        assert reason == "Missing questions file path"

    def test_get_prompt_availability_for_prompt_2_ready(
        self, workflow_prompt_manager_with_paths: PromptManager
    ) -> None:
        """Returns (True, '') when design_spec_path set (Prompt 2 needs only design spec)."""
        available, reason = workflow_prompt_manager_with_paths.get_prompt_availability_for(2)
        assert available is True
        assert reason == ""


# ===========================================================================
# Search
# ===========================================================================


class TestSearchIncludesBuiltin:
    """Tests that search includes built-in prompts."""

    def test_search_includes_builtin_prompts(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """Built-in prompts appear in search results."""
        results = workflow_prompt_manager.search("Critical Questions")
        assert len(results) >= 1
        assert any(p.title == "Critical Questions" for p in results)

    def test_search_all_returns_builtin(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """Empty search returns all prompts including built-in."""
        results = workflow_prompt_manager.search("")
        titles = [p.title for p in results]
        assert "Critical Questions" in titles
        assert "Update Spec from Answers" in titles
        assert "RFC Pipeline" in titles


# ===========================================================================
# Category Count
# ===========================================================================


class TestGetCategoryPromptCountBuiltin:
    """Tests that get_category_prompt_count works for built-in category."""

    def test_get_category_prompt_count_builtin(
        self, workflow_prompt_manager: PromptManager
    ) -> None:
        """Returns correct count for 'Built-in Workflow'."""
        count = workflow_prompt_manager.get_category_prompt_count("Built-in Workflow")
        assert count == 3

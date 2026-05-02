"""Integration tests for WU-4a: UI tests (mocked Tk) and regression tests.

WorkflowFilesDialog tests verify validation and action methods using a hidden Tk
root so that tk StringVars work correctly.

PromptWindow integration tests mock PromptManager to verify button visibility
logic without creating a full UI.

Regression tests use real file I/O with tmp_path to verify the full integration
between PromptManager, workflow templates, and availability computation.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prompt_manager import Prompt, PromptManager
from workflow_files_dialog import WorkflowFilesDialog
from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME


# ---------------------------------------------------------------------------
# Standard prompts template used across tests (matches real file structure).
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
    "-> plan -> implement -> test -> review  4. Use separate agents for each "
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


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="module")
def hidden_root():
    """Create a hidden Tk root for testing tk-dependent widgets.

    Uses module scope to avoid Tcl/Tk initialization issues when multiple
    tests create and destroy Tk instances.
    """
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture()
def workflow_manager(tmp_path: Path) -> PromptManager:
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
            {
                "name": "Git",
                "prompts": [
                    {
                        "title": "Create branch",
                        "text": "Create and push a feature branch.",
                    },
                ],
            },
        ],
    )
    template = tmp_path / "standard-prompts.txt"
    template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")
    return PromptManager(config_path=config)


@pytest.fixture()
def manager_no_template(tmp_path: Path) -> PromptManager:
    """PromptManager with user categories but NO standard-prompts.txt."""
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
    return PromptManager(config_path=config)


@pytest.fixture()
def manager_with_paths(tmp_path: Path) -> PromptManager:
    """PromptManager with workflow_file_paths already saved."""
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
        workflow_files={
            "design_spec_path": "d:\\specs\\my-design.md",
            "questions_file_path": "d:\\specs\\questions.md",
        },
    )
    template = tmp_path / "standard-prompts.txt"
    template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")
    return PromptManager(config_path=config)


# ===========================================================================
# WorkflowFilesDialog Tests
# ===========================================================================


class TestWorkflowFilesDialog:
    """Tests for WorkflowFilesDialog validation and action methods."""

    def test_dialog_populates_fields_from_manager(self, hidden_root, workflow_manager):
        """Dialog pre-populates fields from prompt_manager on creation."""
        workflow_manager.set_workflow_file_paths(
            design_spec_path="d:\\projects\\spec.md",
            questions_file_path="d:\\projects\\questions.md",
        )

        dialog = WorkflowFilesDialog(
            parent=hidden_root,
            prompt_manager=workflow_manager,
        )
        # Build the dialog (creates StringVars and widgets) but don't show modally
        dialog._build_dialog()
        dialog._populate_fields()

        assert dialog.design_spec_var.get() == "d:\\projects\\spec.md"
        assert dialog.questions_file_var.get() == "d:\\projects\\questions.md"

        dialog._destroy_dialog()

    def test_dialog_validate_blocks_empty_design_spec(self, hidden_root, workflow_manager):
        """Empty design spec path returns False from _validate."""
        dialog = WorkflowFilesDialog(
            parent=hidden_root,
            prompt_manager=workflow_manager,
        )
        dialog._build_dialog()
        dialog.design_spec_var.set("")
        dialog.questions_file_var.set("")

        result = dialog._validate()

        assert result is False
        assert "required" in dialog.message_var.get().lower()

        dialog._destroy_dialog()

    def test_dialog_validate_allows_empty_questions(self, hidden_root, workflow_manager):
        """Empty questions path is allowed when design spec is set."""
        dialog = WorkflowFilesDialog(
            parent=hidden_root,
            prompt_manager=workflow_manager,
        )
        dialog._build_dialog()

        # Set a valid design spec path and empty questions
        dialog.design_spec_var.set("d:\\specs\\design.md")
        dialog.questions_file_var.set("")

        result = dialog._validate()

        # Should return True - questions path is optional
        assert result is True

        dialog._destroy_dialog()

    def test_dialog_validate_warns_nonexistent_file(self, hidden_root, workflow_manager):
        """Non-existent design spec shows warning but still allows save."""
        dialog = WorkflowFilesDialog(
            parent=hidden_root,
            prompt_manager=workflow_manager,
        )
        dialog._build_dialog()

        dialog.design_spec_var.set("d:\\nonexistent\\file-that-does-not-exist.md")
        dialog.questions_file_var.set("")

        result = dialog._validate()

        # _validate returns True (allows save) but sets a warning message
        assert result is True
        assert "does not exist" in dialog.message_var.get().lower()

        dialog._destroy_dialog()

    def test_dialog_clear_questions_saves_immediately(self, hidden_root, workflow_manager):
        """Calling _clear_questions triggers set_workflow_file_paths with empty questions."""
        # First set some paths so there is something to clear
        workflow_manager.set_workflow_file_paths(
            design_spec_path="d:\\specs\\existing.md",
            questions_file_path="d:\\specs\\old-questions.md",
        )

        dialog = WorkflowFilesDialog(
            parent=hidden_root,
            prompt_manager=workflow_manager,
        )
        dialog._build_dialog()
        dialog._populate_fields()

        # Verify pre-populated state
        assert dialog.questions_file_var.get() == "d:\\specs\\old-questions.md"

        # Clear the questions path
        dialog._clear_questions()

        # The questions var should now be empty
        assert dialog.questions_file_var.get() == ""

        # The prompt_manager should have been called with empty questions
        paths = workflow_manager.get_workflow_file_paths()
        assert paths["questions_file_path"] == ""
        assert paths["design_spec_path"] == "d:\\specs\\existing.md"

        dialog._destroy_dialog()


# ===========================================================================
# PromptWindow Integration Tests
# ===========================================================================


class TestPromptWindowIntegration:
    """Tests for PromptWindow workflow button visibility logic."""

    def test_workflow_button_visible_when_builtin_available(self, hidden_root, workflow_manager):
        """When built-in category is available, Workflow Files button should be packed."""
        # Verify the precondition: built-in category is available
        assert workflow_manager.get_built_in_category_name() == BUILT_IN_CATEGORY_NAME

        from prompt_window import PromptWindow

        on_close_mock = MagicMock()
        pw = PromptWindow(
            prompt_manager=workflow_manager,
            on_close=on_close_mock,
        )
        # show() creates the real Toplevel and calls _setup_ui
        pw.show()

        # The workflow_btn should exist and be packed
        pack_info = pw.workflow_btn.pack_info()
        assert pack_info != {}, "Workflow Files button should be packed when built-in available"

        pw._close()

    def test_workflow_button_hidden_when_builtin_unavailable(self, hidden_root, manager_no_template):
        """When built-in category is None, Workflow Files button should NOT be packed."""
        # Verify the precondition: no built-in category
        assert manager_no_template.get_built_in_category_name() is None

        from prompt_window import PromptWindow

        pw = PromptWindow(
            prompt_manager=manager_no_template,
        )
        pw.show()

        # The workflow_btn should exist but NOT be packed
        # pack_info() raises TclError when the widget isn't packed
        import tkinter as tk
        try:
            pack_info = pw.workflow_btn.pack_info()
            is_packed = pack_info != {}
        except tk.TclError:
            is_packed = False
        assert not is_packed, "Workflow Files button should not be packed when built-in unavailable"

        pw._close()


# ===========================================================================
# Regression Tests
# ===========================================================================


class TestRegressionExistingPromptsLoad:
    """Existing user prompts load unchanged when built-in prompts are added."""

    def test_existing_prompts_load_unchanged(self, workflow_manager):
        """User prompts from prompts.json load correctly with no interference from built-in."""
        all_prompts = workflow_manager.get_all_prompts()

        # Only user prompts from JSON (built-in are separate)
        assert len(all_prompts) == 2
        titles = {p.title for p in all_prompts}
        assert "Summarize" in titles
        assert "Create branch" in titles

        # Verify user category prompts are accessible
        meetings = workflow_manager.get_prompts_by_category("Meetings")
        assert len(meetings) == 1
        assert meetings[0].title == "Summarize"
        assert meetings[0].text == "Summarize the meeting."

        git = workflow_manager.get_prompts_by_category("Git")
        assert len(git) == 1
        assert git[0].title == "Create branch"


class TestRegressionLegacyJson:
    """Legacy prompts.json without workflow_files key works fine."""

    def test_legacy_prompts_json_no_workflow_files(self, tmp_path):
        """prompts.json without workflow_files key defaults to empty strings."""
        config = tmp_path / "prompts.json"
        _write_json_config(
            config,
            categories=[
                {
                    "name": "Dev",
                    "prompts": [
                        {"title": "Refactor", "text": "Refactor the code."},
                    ],
                },
            ],
        )

        manager = PromptManager(config_path=config)
        paths = manager.get_workflow_file_paths()

        assert paths["design_spec_path"] == ""
        assert paths["questions_file_path"] == ""

        # User prompts still load fine
        assert len(manager.get_all_prompts()) == 1
        assert manager.get_all_prompts()[0].title == "Refactor"


class TestRegressionAppStarts:
    """App starts correctly when standard-prompts.txt is missing."""

    def test_app_starts_when_standard_prompts_missing(self, manager_no_template):
        """PromptManager with no standard-prompts.txt: built-in category is None."""
        assert manager_no_template.get_built_in_category_name() is None
        assert manager_no_template.get_built_in_prompts() == []

        # Only user categories shown
        assert manager_no_template.categories == ["Meetings"]
        assert len(manager_no_template.get_all_prompts()) == 1


class TestRegressionSearch:
    """Search includes both user and built-in prompts."""

    def test_search_includes_user_and_builtin(self, workflow_manager):
        """Search query matches both user and built-in prompts."""
        # Search for a built-in prompt title
        results = workflow_manager.search("Critical Questions")
        assert any(p.title == "Critical Questions" for p in results)

        # Search for a user prompt title
        results = workflow_manager.search("Summarize")
        assert any(p.title == "Summarize" for p in results)

    def test_copy_user_prompt_unchanged(self, workflow_manager):
        """Copying a non-builtin prompt still works with the standard flow."""
        user_prompts = workflow_manager.get_prompts_by_category("Meetings")
        assert len(user_prompts) == 1
        prompt = user_prompts[0]

        assert prompt.title == "Summarize"
        assert prompt.text == "Summarize the meeting."
        assert prompt.category == "Meetings"
        # No availability check needed for user prompts - they are always available


class TestRegressionCategoryOrder:
    """Built-in category appears first when available."""

    def test_categories_order_builtin_first(self, workflow_manager):
        """When both built-in and user categories exist, built-in is first."""
        cats = workflow_manager.categories
        assert cats[0] == BUILT_IN_CATEGORY_NAME
        assert "Meetings" in cats
        assert "Git" in cats
        # Built-in is prepended, not replacing user categories
        assert len(cats) == 3  # Built-in + Meetings + Git


class TestRegressionReload:
    """Reload refreshes built-in prompts from current template file."""

    def test_reload_refreshes_builtin_prompts(self, tmp_path):
        """After reload, built-in prompts reflect current template file."""
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

        # Start with a template that has 3 prompts
        template = tmp_path / "standard-prompts.txt"
        template.write_text(STANDARD_PROMPTS_TEMPLATE, encoding="utf-8")

        manager = PromptManager(config_path=config)
        assert len(manager.get_built_in_prompts()) == 3
        assert manager.get_built_in_category_name() == BUILT_IN_CATEGORY_NAME

        # Replace template with a single-block file
        template.write_text("## Only Prompt\nSingle prompt body ____. \n", encoding="utf-8")

        # Reload
        manager.reload()

        # Built-in prompts should now reflect the new file
        builtin = manager.get_built_in_prompts()
        assert len(builtin) == 1
        assert builtin[0].title == "Only Prompt"

        # User prompts still intact
        meetings = manager.get_prompts_by_category("Meetings")
        assert len(meetings) == 1
        assert meetings[0].title == "Summarize"


class TestRegressionWorkflowPathsPreserveUserPrompts:
    """Saving workflow paths does not touch user prompt text in JSON."""

    def test_set_workflow_paths_preserves_user_prompts(self, workflow_manager):
        """Saving workflow paths does not modify user prompt text."""
        # Capture original user prompts
        original_user_prompts = workflow_manager.get_all_prompts()
        assert len(original_user_prompts) == 2

        original_meetings = workflow_manager.get_prompts_by_category("Meetings")
        assert original_meetings[0].text == "Summarize the meeting."

        # Save workflow paths
        workflow_manager.set_workflow_file_paths(
            design_spec_path="d:\\new\\spec.md",
            questions_file_path="d:\\new\\questions.md",
        )

        # Reload from disk to verify persistence
        workflow_manager.reload()

        # User prompt text is unchanged
        meetings_after = workflow_manager.get_prompts_by_category("Meetings")
        assert len(meetings_after) == 1
        assert meetings_after[0].text == "Summarize the meeting."
        assert meetings_after[0].title == "Summarize"

        git_after = workflow_manager.get_prompts_by_category("Git")
        assert len(git_after) == 1
        assert git_after[0].title == "Create branch"

        # Workflow paths persisted correctly
        paths = workflow_manager.get_workflow_file_paths()
        assert paths["design_spec_path"] == "d:\\new\\spec.md"
        assert paths["questions_file_path"] == "d:\\new\\questions.md"

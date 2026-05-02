"""Tests for workflow_availability.get_prompt_availability."""

import pytest

from workflow_availability import get_prompt_availability


# ---------------------------------------------------------------------------
# Prompt 0 — requires design_spec_path only
# ---------------------------------------------------------------------------


class TestPrompt0:
    def test_prompt_0_no_design_spec_path(self) -> None:
        available, reason = get_prompt_availability(0, "", "/some/questions.md")
        assert available is False
        assert reason == "Missing design spec path"

    def test_prompt_0_with_design_spec_path(self) -> None:
        available, reason = get_prompt_availability(0, "/spec/design.md", "")
        assert available is True
        assert reason == ""

    def test_prompt_0_with_both_paths(self) -> None:
        available, reason = get_prompt_availability(
            0, "/spec/design.md", "/some/questions.md"
        )
        assert available is True
        assert reason == ""


# ---------------------------------------------------------------------------
# Prompt 1 — requires both design_spec_path and questions_file_path
# ---------------------------------------------------------------------------


class TestPrompt1:
    def test_prompt_1_no_design_spec_path(self) -> None:
        available, reason = get_prompt_availability(1, "", "/some/questions.md")
        assert available is False
        assert reason == "Missing design spec path"

    def test_prompt_1_no_questions_path(self) -> None:
        available, reason = get_prompt_availability(1, "/spec/design.md", "")
        assert available is False
        assert reason == "Missing questions file path"

    def test_prompt_1_with_both_paths(self) -> None:
        available, reason = get_prompt_availability(
            1, "/spec/design.md", "/some/questions.md"
        )
        assert available is True
        assert reason == ""


# ---------------------------------------------------------------------------
# Prompt 2 — requires design_spec_path only
# ---------------------------------------------------------------------------


class TestPrompt2:
    def test_prompt_2_no_design_spec_path(self) -> None:
        available, reason = get_prompt_availability(2, "", "/some/questions.md")
        assert available is False
        assert reason == "Missing design spec path"

    def test_prompt_2_with_design_spec_path(self) -> None:
        available, reason = get_prompt_availability(2, "/spec/design.md", "")
        assert available is True
        assert reason == ""

    def test_prompt_2_with_both_paths(self) -> None:
        available, reason = get_prompt_availability(
            2, "/spec/design.md", "/some/questions.md"
        )
        assert available is True
        assert reason == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_out_of_range_index(self) -> None:
        with pytest.raises(IndexError, match="Unknown prompt index"):
            get_prompt_availability(99, "/spec/design.md", "/some/questions.md")

    def test_negative_index(self) -> None:
        with pytest.raises(IndexError, match="Unknown prompt index"):
            get_prompt_availability(-1, "/spec/design.md", "/some/questions.md")

    def test_empty_strings_are_empty(self) -> None:
        """Whitespace-only strings should be treated as empty."""
        available, reason = get_prompt_availability(0, "   ", "")
        assert available is False
        assert reason == "Missing design spec path"

    def test_whitespace_only_questions_path(self) -> None:
        """Whitespace-only questions path for prompt 1 should fail."""
        available, reason = get_prompt_availability(1, "/spec/design.md", "  \t\n")
        assert available is False
        assert reason == "Missing questions file path"

"""Tests for workflow_prompt_templates module."""

import textwrap
from pathlib import Path

import pytest

from workflow_prompt_templates import (
    BUILT_IN_CATEGORY_NAME,
    TEMPLATE_FILE_NAME,
    load_builtin_prompts,
    parse_standard_prompts,
    substitute_placeholders,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tmp(tmp_path: Path, content: str, filename: str = "standard-prompts.txt") -> Path:
    """Write *content* to a temp file and return its Path."""
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ===========================================================================
# parse_standard_prompts
# ===========================================================================

class TestParseStandardPrompts:
    """Tests for parse_standard_prompts()."""

    def test_parse_multiple_blocks(self, tmp_path: Path):
        """A file with several ## blocks returns one dict per block."""
        p = _write_tmp(tmp_path, textwrap.dedent("""\
            ## First
            Body one.

            ## Second
            Body two.
        """))
        result = parse_standard_prompts(p)
        assert len(result) == 2
        assert result[0]["title"] == "First"
        assert result[0]["body"] == "Body one."
        assert result[1]["title"] == "Second"
        assert result[1]["body"] == "Body two."

    def test_blank_lines_between_blocks_are_ignored(self, tmp_path: Path):
        """Extra blank lines between blocks do not pollute body text."""
        p = _write_tmp(tmp_path, textwrap.dedent("""\
            ## Alpha


            ## Beta
        """))
        result = parse_standard_prompts(p)
        assert len(result) == 2
        assert result[0]["body"] == ""
        assert result[1]["body"] == ""

    def test_multiline_body_preserved(self, tmp_path: Path):
        """Body lines within a block are preserved including internal blanks."""
        p = _write_tmp(tmp_path, textwrap.dedent("""\
            ## Title
            Line one.

            Line three.
        """))
        result = parse_standard_prompts(p)
        assert result[0]["body"] == "Line one.\n\nLine three."

    def test_no_headers_raises_value_error(self, tmp_path: Path):
        """A non-empty file with no ## headers raises ValueError."""
        p = _write_tmp(tmp_path, "Just some text without headers.\n")
        with pytest.raises(ValueError):
            parse_standard_prompts(p)

    def test_empty_file_returns_empty_list(self, tmp_path: Path):
        """A zero-byte file returns an empty list."""
        p = _write_tmp(tmp_path, "")
        assert parse_standard_prompts(p) == []

    def test_whitespace_only_file_returns_empty_list(self, tmp_path: Path):
        """A file containing only whitespace returns an empty list."""
        p = _write_tmp(tmp_path, "   \n  \n")
        assert parse_standard_prompts(p) == []

    def test_single_block(self, tmp_path: Path):
        """A file with exactly one block works."""
        p = _write_tmp(tmp_path, textwrap.dedent("""\
            ## Only
            Only body.
        """))
        result = parse_standard_prompts(p)
        assert len(result) == 1
        assert result[0]["title"] == "Only"
        assert result[0]["body"] == "Only body."

    def test_file_not_found_raises(self, tmp_path: Path):
        """A missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_standard_prompts(tmp_path / "nonexistent.txt")

    def test_lines_before_first_header_raise_value_error(self, tmp_path: Path):
        """Non-blank lines before the first ## header raise ValueError with line number."""
        p = _write_tmp(tmp_path, textwrap.dedent("""\
            This is line 1.
            This is line 2.
            ## Title
            Body.
        """))
        with pytest.raises(ValueError, match="line 1"):
            parse_standard_prompts(p)

    def test_lines_before_first_header_second_line(self, tmp_path: Path):
        """Error reports the correct line number when the first offending line is not line 1."""
        p = _write_tmp(tmp_path, textwrap.dedent("""\

            This is line 2.
            ## Title
            Body.
        """))
        with pytest.raises(ValueError, match="line 2"):
            parse_standard_prompts(p)

    def test_trailing_newline_not_significant(self, tmp_path: Path):
        """A trailing newline at EOF does not add an extra empty line to body."""
        p = _write_tmp(tmp_path, "## A\nBody.\n")
        result = parse_standard_prompts(p)
        assert result[0]["body"] == "Body."

    def test_title_strips_nothing_beyond_hash_prefix(self, tmp_path: Path):
        """Title is everything after '## ' including trailing spaces."""
        p = _write_tmp(tmp_path, "##   Spaces  \nBody.\n")
        result = parse_standard_prompts(p)
        # Title preserves whatever follows "## " exactly.
        assert result[0]["title"] == "  Spaces  "

    def test_body_preserves_internal_blank_lines(self, tmp_path: Path):
        """Blank lines inside a block body are preserved."""
        p = _write_tmp(tmp_path, textwrap.dedent("""\
            ## T
            A


            B
        """))
        result = parse_standard_prompts(p)
        assert result[0]["body"] == "A\n\n\nB"


# ===========================================================================
# substitute_placeholders
# ===========================================================================

class TestSubstitutePlaceholders:
    """Tests for substitute_placeholders()."""

    def test_replace_design_spec_path(self):
        """____ is replaced with the design_spec_path value."""
        result = substitute_placeholders(
            "Check ____. Also ____.", "/path/to/spec.md", ""
        )
        assert result == "Check /path/to/spec.md. Also /path/to/spec.md."

    def test_replace_questions_file_path(self):
        """#### is replaced with the questions_file_path value."""
        result = substitute_placeholders(
            "See #### for answers.", "", "/path/to/questions.md"
        )
        assert result == "See /path/to/questions.md for answers."

    def test_replace_both_tokens(self):
        """Both tokens are replaced in the same text."""
        result = substitute_placeholders(
            "Review ____ and answer ####.", "/spec.md", "/questions.md"
        )
        assert result == "Review /spec.md and answer /questions.md."

    def test_multiple_occurrences_replaced(self):
        """Multiple occurrences of the same token are all replaced."""
        result = substitute_placeholders(
            "____ ____. ____", "/spec.md", ""
        )
        assert result == "/spec.md /spec.md. /spec.md"

    def test_empty_design_spec_leaves_unchanged(self):
        """An empty design_spec_path leaves ____ tokens unchanged."""
        result = substitute_placeholders("Check ____.", "", "/q.md")
        assert result == "Check ____."

    def test_empty_questions_path_leaves_unchanged(self):
        """An empty questions_file_path leaves #### tokens unchanged."""
        result = substitute_placeholders("See ####.", "/s.md", "")
        assert result == "See ####."

    def test_both_empty_leaves_all_unchanged(self):
        """Both paths empty means no substitution at all."""
        result = substitute_placeholders("____ ####", "", "")
        assert result == "____ ####"

    def test_no_tokens_in_text_is_noop(self):
        """Text without tokens is returned unchanged."""
        result = substitute_placeholders("Hello world.", "/s.md", "/q.md")
        assert result == "Hello world."


# ===========================================================================
# load_builtin_prompts
# ===========================================================================

class TestLoadBuiltinPrompts:
    """Tests for load_builtin_prompts()."""

    def test_returns_prompt_objects(self, tmp_path: Path):
        """Correct Prompt objects are returned with substituted bodies."""
        _write_tmp(tmp_path, textwrap.dedent("""\
            ## Critical Questions
            Review ____ and ####.
        """))
        prompts = load_builtin_prompts(
            tmp_path, "/design.md", "/questions.md"
        )
        assert len(prompts) == 1
        p = prompts[0]
        assert p.title == "Critical Questions"
        assert p.text == "Review /design.md and /questions.md."
        assert p.category == BUILT_IN_CATEGORY_NAME

    def test_category_is_builtin(self, tmp_path: Path):
        """All returned prompts have category = BUILT_IN_CATEGORY_NAME."""
        _write_tmp(tmp_path, textwrap.dedent("""\
            ## A
            Body a.

            ## B
            Body b.
        """))
        prompts = load_builtin_prompts(tmp_path, "", "")
        assert all(p.category == BUILT_IN_CATEGORY_NAME for p in prompts)

    def test_missing_file_returns_empty_list(self, tmp_path: Path):
        """If the template file does not exist, returns an empty list."""
        prompts = load_builtin_prompts(tmp_path, "/s.md", "/q.md")
        assert prompts == []

    def test_multiple_blocks(self, tmp_path: Path):
        """All blocks in the file are loaded as separate Prompt objects."""
        _write_tmp(tmp_path, textwrap.dedent("""\
            ## First
            First body ____

            ## Second
            Second body ####
        """))
        prompts = load_builtin_prompts(
            tmp_path, "/spec.md", "/questions.md"
        )
        assert len(prompts) == 2
        assert prompts[0].title == "First"
        assert prompts[0].text == "First body /spec.md"
        assert prompts[1].title == "Second"
        assert prompts[1].text == "Second body /questions.md"

    def test_template_file_name_constant(self):
        """TEMPLATE_FILE_NAME matches the expected filename."""
        assert TEMPLATE_FILE_NAME == "standard-prompts.txt"

    def test_builtin_category_name_constant(self):
        """BUILT_IN_CATEGORY_NAME has the expected value."""
        assert BUILT_IN_CATEGORY_NAME == "Built-in Workflow"

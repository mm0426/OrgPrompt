"""Parsing and placeholder substitution for structured workflow prompt templates."""

from pathlib import Path

from prompt_manager import Prompt

BUILT_IN_CATEGORY_NAME = "Built-in Workflow"
TEMPLATE_FILE_NAME = "standard-prompts.txt"


def parse_standard_prompts(file_path: Path) -> list[dict]:
    """Parse ``## Title`` + body blocks from a standard-prompts.txt file.

    Returns a list of ``{"title": str, "body": str}`` dicts, one per block.

    Rules:
    - Each block starts with exactly ``## `` followed by its title (no leading
      spaces).
    - Everything after the title line until the next ``## `` line or EOF is the
      body.
    - Blank lines between blocks are ignored; blank lines within a body are
      preserved.
    - A trailing newline at EOF is not significant.
    - An empty file (zero bytes) returns an empty list.
    - A non-existent file raises ``FileNotFoundError``.
    - If the file contains text but no ``## `` headers, raises ``ValueError``.
    - If lines appear before the first ``## `` header, raises ``ValueError``
      with the offending line number.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"prompt template file not found: {file_path}")

    raw = file_path.read_text(encoding="utf-8")

    # An empty file (or file with only whitespace) is valid but yields nothing.
    if not raw.strip():
        return []

    lines = raw.split("\n")
    blocks: list[dict] = []
    current_title: str | None = None
    current_body_lines: list[str] = []
    seen_header = False

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("## "):
            # Flush the previous block, if any.
            if current_title is not None:
                blocks.append(_finalise_block(current_title, current_body_lines))

            current_title = line[3:]  # strip the leading "## "
            current_body_lines = []
            seen_header = True
        else:
            if not seen_header and line.strip():
                raise ValueError(
                    f"line {line_number}: content found before first ## header"
                )
            # Accumulate body lines for the current block (even blank ones).
            current_body_lines.append(line)

    # Flush the last block.
    if current_title is not None:
        blocks.append(_finalise_block(current_title, current_body_lines))

    if not blocks:
        raise ValueError("no prompt blocks found")

    return blocks


def _finalise_block(title: str, body_lines: list[str]) -> dict:
    """Join body lines and strip one trailing newline if present.

    The parser splits on ``\\n`` which adds a synthetic empty string after a
    trailing newline.  We strip that single trailing empty entry but preserve
    intentional blank lines within the body.
    """
    body = "\n".join(body_lines)
    # Remove the single trailing newline that comes from the file's final
    # newline character (the split produces a trailing empty element).
    if body.endswith("\n"):
        body = body[:-1]
    return {"title": title, "body": body}


def substitute_placeholders(
    text: str,
    design_spec_path: str,
    questions_file_path: str,
) -> str:
    """Replace placeholder tokens in *text* with the supplied paths.

    - Every ``____`` is replaced with *design_spec_path*.
    - Every ``####`` is replaced with *questions_file_path*.
    - Literal string replacement; no regex escaping.
    - If a path is an empty string the corresponding token is left unchanged.
    """
    if design_spec_path:
        text = text.replace("____", design_spec_path)
    if questions_file_path:
        text = text.replace("####", questions_file_path)
    return text


def load_builtin_prompts(
    config_dir: Path,
    design_spec_path: str,
    questions_file_path: str,
) -> list[Prompt]:
    """Load built-in workflow prompts from *config_dir*/standard-prompts.txt.

    Parses the file, substitutes placeholders in each block, and returns
    ``Prompt`` objects with ``category`` set to
    :pydata:`BUILT_IN_CATEGORY_NAME`.

    If the template file is missing, returns an empty list (no error).
    """
    template_path = config_dir / TEMPLATE_FILE_NAME
    if not template_path.exists():
        return []

    blocks = parse_standard_prompts(template_path)

    prompts: list[Prompt] = []
    for block in blocks:
        substituted_body = substitute_placeholders(
            block["body"], design_spec_path, questions_file_path
        )
        prompts.append(
            Prompt(
                title=block["title"],
                text=substituted_body,
                category=BUILT_IN_CATEGORY_NAME,
            )
        )
    return prompts

"""Compute prompt availability based on required workflow inputs.

Availability matrix (per RFC Section 8.2):

  Index 0 — requires design_spec_path only.
  Index 1 — requires design_spec_path and questions_file_path.
  Index 2 — requires design_spec_path only.

Returns a tuple of (is_available: bool, reason: str).
When the prompt is available the reason string is empty.
"""


def _is_empty(value: str) -> bool:
    """Return True when *value* is empty or whitespace-only."""
    return not value.strip()


def get_prompt_availability(
    prompt_index: int,
    design_spec_path: str,
    questions_file_path: str,
) -> tuple[bool, str]:
    """Determine whether the prompt at *prompt_index* is available.

    Parameters
    ----------
    prompt_index:
        0-based index of the prompt in standard-prompts.txt.
    design_spec_path:
        Path to the design specification document.
    questions_file_path:
        Path to the questions / answers file.

    Returns
    -------
    tuple[bool, str]
        ``(is_available, reason)`` — *reason* is an empty string when
        the prompt is available, or a human-readable message otherwise.

    Raises
    ------
    IndexError
        If *prompt_index* does not correspond to a known prompt.
    """
    if prompt_index == 0:
        if _is_empty(design_spec_path):
            return (False, "Missing design spec path")
        return (True, "")

    if prompt_index == 1:
        if _is_empty(design_spec_path):
            return (False, "Missing design spec path")
        if _is_empty(questions_file_path):
            return (False, "Missing questions file path")
        return (True, "")

    if prompt_index == 2:
        if _is_empty(design_spec_path):
            return (False, "Missing design spec path")
        return (True, "")

    raise IndexError(f"Unknown prompt index: {prompt_index}")

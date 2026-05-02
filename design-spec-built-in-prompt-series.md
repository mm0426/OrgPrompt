# Design Spec: Built-In Prompt Series with File Path Variables

## 1. Summary

Add a built-in three-prompt workflow to OrgPrompt where the prompt text is fixed, and only file path variables change per run.

The three prompt templates are source-controlled in `standard-prompts.txt` and use placeholders:

- `____` -> design spec path
- `####` -> questions file path created by Prompt 1

Users need a lightweight UX to set and update these file paths without editing prompt text manually.

For this spec effort, the design spec path is:

- `d:\utilities\OrgPrompt\design-spec-built-in-prompt-series.md`

## 2. Problem Statement

Current behavior:

- OrgPrompt loads static prompts from `prompts.json`.
- There is no concept of a prompt workflow with shared variables.
- There is no UI to capture per-workflow file names/paths.

Resulting friction:

- Users must hand-edit prompt text for each run.
- Prompt consistency drops because users may alter non-file parts.
- Prompt 2 cannot be safely prepared until Prompt 1 produces the questions file path.

## 3. Goals

- Add one built-in prompt series with exactly three prompts from `standard-prompts.txt`.
- Keep prompt wording immutable at runtime; only placeholders are substituted.
- Add UI for users to enter/set file paths used by placeholders.
- Support the dependency that `####` is unknown until Prompt 1 completes.
- Keep backward compatibility with existing `prompts.json` user prompts.

## 4. Non-Goals

- No generalized templating language beyond `____` and `####` in this iteration.
- No automatic creation of files by OrgPrompt itself.
- No editing UI for built-in prompt body text.
- No cloud sync or multi-workspace profile management.

## 5. User Stories

1. As a user, I can set a design spec file path once and reuse it in all three prompts.
2. As a user, I can run Prompt 1 without having a questions file path yet.
3. As a user, after Prompt 1 runs externally, I can set the questions file path and run Prompt 2.
4. As a user, I can clearly see why Prompt 2 is unavailable when `####` is not set.
5. As a user, I can reset/update either path without editing JSON by hand.

## 6. Prompt Series Definition

Source file:

- `standard-prompts.txt`

### 6.1 Template File Format

The file uses a structured format where each prompt block is delimited by a `## Title` header line followed by the prompt body. Blocks are separated by one or more blank lines.

Formal grammar:

```
template_file = block (blank_line+ block)* blank_line*
block         = "## " TITLE newline BODY
TITLE         = non-empty text (no trailing whitespace)
BODY          = non-empty text (may span multiple lines)
blank_line    = line containing only whitespace or empty
```

Rules:

- Each block starts with exactly `## ` followed by the title (no leading spaces).
- The title line is the only metadata line; everything after it until the next `## ` line or end-of-file is the prompt body.
- Blank lines between blocks are ignored; blank lines within a body are preserved.
- No comments or other metadata are allowed in the file.
- Trailing newline at end-of-file is not significant.
- Lines starting with `## ` within a body are treated as body text (only the first `## ` line after a blank-line boundary starts a new block).

Current `standard-prompts.txt` (before migration):

```
Review this project summary - ____. Identify any unclear, missing, or risky elements I should address before we start. Frame your response as a series of critical questions I need to answer and write those questions to a new file in md format.


update ____ with details that answer all of the questions in #### (while keeping all details that don't contradict the answers and also keeping the design spec format).  Ask me if you are not sure about high level decisions.


I have an RFC at ____.  Use the ralphinho-rfc-pipeline pattern:  1. Decompose it into work units with a dependency DAG  2. For each layer, run units in parallel using the Task tool  3. Each unit gets: research → plan → implement → test → review  4. Use separate agents for each stage (author-bias elimination)  5. Land via merge queue with conflict recovery
```

Target `standard-prompts.txt` (after migration to structured format):

```
## Critical Questions
Review this project summary - ____. Identify any unclear, missing, or risky elements I should address before we start. Frame your response as a series of critical questions I need to answer and write those questions to a new file in md format.

## Update Spec from Answers
update ____ with details that answer all of the questions in #### (while keeping all details that don't contradict the answers and also keeping the design spec format).  Ask me if you are not sure about high level decisions.

## RFC Pipeline
I have an RFC at ____.  Use the ralphinho-rfc-pipeline pattern:  1. Decompose it into work units with a dependency DAG  2. For each layer, run units in parallel using the Task tool  3. Each unit gets: research → plan → implement → test → review  4. Use separate agents for each stage (author-bias elimination)  5. Land via merge queue with conflict recovery
```

Prompt order and required variables:

1. Prompt 1 (Critical Questions): requires `____` only.
2. Prompt 2 (Update Spec from Answers): requires `____` and `####`.
3. Prompt 3 (RFC Pipeline): requires `____` only.

Position in the file determines display order. If blocks are reordered in `standard-prompts.txt`, the UI order changes to match. Variable requirements follow the position (Prompt 1 = first block, Prompt 2 = second block, etc.).

### 6.2 Substitution Rules

- Replace every `____` token with `design_spec_path`.
- Replace every `####` token with `questions_file_path`.
- Substitution is literal string replacement; no escaping transformation.
- If a required variable is missing, the prompt is marked unavailable and cannot be copied.

### 6.3 Path Handling and Edge Cases

- Stored paths preserve the exact user input (could be relative, absolute, or contain typos).
- Paths containing `____` or `####` themselves are not expected; no special handling required (pathological case).
- Windows backslash paths (e.g., `D:\folder\questions.md`) are stored and substituted as-is. The resolved prompt text does not require sanitization before clipboard copy — the receiving application handles the raw text.
- No validation on file existence at copy time. The file might be about to be created (pre-create workflow). Warnings about non-existent files are informational only.

## 7. UX/UI Proposal

### 7.1 Entry Point

Add a new button in the prompt window near search:

- `Workflow Files...`

Visibility rules:

- Visible only when the built-in category is loaded (i.e., `standard-prompts.txt` exists and parsed successfully).
- Hidden when `standard-prompts.txt` is missing or malformed (built-in category is omitted per Section 10.5).
- Not grayed out or disabled — simply absent. This avoids cluttering the UI with a non-functional button when the feature is unavailable.

Clicking opens a modal dialog for file path configuration.

### 7.2 File Path Dialog

Fields:

- Design spec path (required for Prompts 1, 2, 3)
- Questions file path (required only for Prompt 2)

Controls:

- Text entry for each field
- `Browse...` button per field (file picker)
- `Save`
- `Cancel`
- `Clear Questions Path` (quick reset for new runs)

Browse behavior:

- When the user clicks `Browse...`, the file picker opens to the directory of the current path value. If the current path is empty or its parent directory does not exist, the picker opens to the user's home directory.

Clear behavior:

- `Clear Questions Path` clears the questions path field and saves immediately (no need to click Save separately). Prompt 2 becomes unavailable.
- Clearing the questions path also clears any cached/resolved Prompt 2 text in memory (forces re-render on next access).
- There is no "Reset All" option in this iteration. Users clear each field individually. A "Reset All" button may be added in a future iteration.

Validation:

- Empty design spec path: block save with inline message.
- Non-empty path: allow save even if file does not exist yet, but show warning.
- Questions path may be empty; this disables Prompt 2 only.
- Validation is checked at save time. It is also re-checked when the prompt window opens (to show current state in the status bar), but not on a periodic background timer.

### 7.3 Prompt List Behavior

Built-in series appears as the first category in the treeview:

- `Built-in Workflow`

Placement and visual treatment:

- Always appears as the first category in the list (before all user categories).
- Uses the same expand/collapse behavior as user categories.
- Displayed with a distinct icon (a wrench/gear bitmap or Unicode symbol) to differentiate from user categories.
- The built-in category node text uses the same bold font as other category nodes.

Each prompt displays state:

- Ready
- Missing design spec path
- Missing questions file path

Selection behavior:

- Selecting an unavailable prompt updates status bar with missing input reason.
- `Ok` button remains disabled for unavailable prompt.

### 7.4 First-Run Flow

1. User sets design spec path.
2. User runs Prompt 1 and pastes into assistant.
3. Assistant creates questions markdown file.
4. User returns to OrgPrompt and sets questions file path.
5. Prompt 2 becomes available.

### 7.5 Questions File Lifecycle

- The questions file is always created by the external assistant (e.g., Claude), never by OrgPrompt itself.
- The file is expected to be markdown (`.md`), but OrgPrompt does not validate the file extension or format. Any text file path is accepted.
- The user cannot create the questions file through OrgPrompt; they must run Prompt 1 externally first, then point OrgPrompt to the resulting file.

## 8. Data Model and Storage

Persist workflow inputs in `prompts.json` under `settings`:

```json
{
  "settings": {
    "auto_close": true,
    "show_notifications": true,
    "workflow_files": {
      "design_spec_path": "",
      "questions_file_path": ""
    }
  }
}
```

Compatibility requirements:

- If `workflow_files` is missing, default to empty strings.
- Existing categories/prompts remain unchanged.
- Save only the settings section fields managed by the app; do not mutate user prompt text.

### 8.1 Prompt Dataclass

The existing `Prompt` dataclass is **not modified** for this feature:

```python
@dataclass
class Prompt:
    title: str
    text: str
    category: str
```

Built-in prompts use the same `Prompt` dataclass with `category = "Built-in Workflow"`. Availability is computed externally (not stored on the `Prompt` object) to keep the data model clean and decoupled from workflow-specific concerns.

### 8.2 Availability Computation

Availability is a function of the current workflow settings, computed on demand:

```python
def get_prompt_availability(
    prompt_index: int,
    design_spec_path: str,
    questions_file_path: str
) -> tuple[bool, str]:
```

Returns `(is_available, reason_string)`:

| Index | design_spec_path | questions_file_path | Available | Reason |
|-------|-----------------|--------------------|-----------|------------|
| 0 (Prompt 1) | empty | any | No | "Missing design spec path" |
| 0 (Prompt 1) | non-empty | any | Yes | — |
| 1 (Prompt 2) | empty | any | No | "Missing design spec path" |
| 1 (Prompt 2) | non-empty | empty | No | "Missing questions file path" |
| 1 (Prompt 2) | non-empty | non-empty | Yes | — |
| 2 (Prompt 3) | empty | any | No | "Missing design spec path" |
| 2 (Prompt 3) | non-empty | any | Yes | — |

Prompt index is determined by position in `standard-prompts.txt` (0-based). This avoids coupling availability logic to specific prompt titles.

## 9. Architecture Changes

### 9.1 PromptManager

Add responsibilities:

- Load and parse template blocks from `standard-prompts.txt`.
- Materialize built-in prompts by substituting placeholders from settings.
- Compute per-prompt availability and reason (delegated to external function per Section 8.2).
- Expose workflow settings getters/setters with safe JSON write-back.
- Prepend built-in category to the categories list.

Suggested API additions:

- `get_workflow_file_paths() -> dict[str, str]`
- `set_workflow_file_paths(design_spec_path: str, questions_file_path: str) -> None`
- `get_built_in_prompts() -> list[Prompt]`
- `get_built_in_category_name() -> str` (returns `"Built-in Workflow"` or `None` if templates unavailable)

Implementation notes:

- Keep immutable base templates in memory.
- Re-render built-in prompt text each time settings change.
- The `reload()` method must also re-read `standard-prompts.txt`, not just `prompts.json`. This ensures users see fresh prompt text after editing the template file and reopening the prompt window.
- Built-in prompts are NOT persisted to `prompts.json`'s `categories` array. They are computed at load time from `standard-prompts.txt` and injected into the in-memory prompt list.
- The `categories` property must return built-in category first, then user categories.

### 9.2 Safe JSON Write-Back

`set_workflow_file_paths()` writes only the `settings.workflow_files` section of `prompts.json`. The write strategy:

1. Read the current file content into memory.
2. Update only `settings.workflow_files` in the in-memory dict.
3. Write the full dict to a temporary file in the same directory (e.g., `prompts.json.tmp`).
4. Rename the temp file to `prompts.json` (atomic on most filesystems).
5. If any step fails (read error, write error, rename error), log the error and keep the old in-memory values. Show a status message to the user.

This avoids:
- Losing concurrent edits (we always read-then-write the latest file).
- Corrupting the file (atomic rename ensures either old or new content).
- Holding a file lock (no long-lived lock needed; the read-modify-write cycle is brief).
- File-deleted-between-read-and-write: the write creates a fresh file with the updated settings plus empty categories (matching the default config behavior). The user's prompts are lost, but this is an exceptional case. A log warning is emitted.

### 9.3 PromptWindow

Add responsibilities:

- Render `Workflow Files...` button (visible only when built-in prompts are loaded).
- Show modal dialog for path management.
- Display availability state for built-in prompts.
- Block copy action when required placeholders are unresolved.
- Display built-in category first in the treeview with a distinct icon.

Implementation notes:

- Reuse existing status bar for validation feedback.
- Trigger list refresh after settings save.
- The `_refresh_list()` method must call `get_built_in_prompts()` and insert the built-in category before iterating user categories.

### 9.4 Optional Helper Module

If needed for separation of concerns, add:

- `workflow_prompt_templates.py` for parsing `standard-prompts.txt` and substitution helpers. This module owns:
  - Parsing the `## Title` + body format.
  - Token substitution (`____` and `####`).
  - Malformed-file detection and error reporting.

## 10. Detailed Behavior Rules

1. `design_spec_path` is required global input.
2. `questions_file_path` is optional globally but required by Prompt 2.
3. Prompt copy operation must always use resolved text currently in memory.
4. Search should include resolved built-in text and titles. The built-in category header itself does not appear as a search result — only individual prompts within it are searchable.
5. If `standard-prompts.txt` is missing or malformed, app logs error and omits built-in category without crashing. The `Workflow Files...` button is also hidden.
6. `reload()` re-reads both `prompts.json` and `standard-prompts.txt` on every invocation. This is called each time the prompt window opens, so users always see fresh content.
7. Built-in prompts are never persisted to the `categories` array in `prompts.json`. They exist only in memory, derived from `standard-prompts.txt` at load time.
8. The built-in category always appears first in the treeview, before all user categories.

## 11. Error Handling

- File read errors for `standard-prompts.txt`: log and continue with user prompts only.
- Malformed `standard-prompts.txt` (e.g., no `## ` headers found, empty file): log specific error (e.g., "no prompt blocks found", "line 5: expected ## header") and omit built-in category.
- JSON write errors while saving settings: show status message and keep old values.
- Invalid browse result (cancel/no path): ignore safely.
- Tk exceptions in modal lifecycle: fail closed and keep app responsive.
- `prompts.json` deleted between read and write: log warning, write new file with updated settings and empty categories (consistent with default config creation behavior).

## 12. Testing Plan

### 12.1 Pre-Feature Regression Baseline

Before implementing new features, add a regression test suite for existing `PromptManager` and `PromptWindow` behavior:

- `test_load_prompts_from_json` — verifies prompts load from a test `prompts.json`.
- `test_categories_order` — verifies category list matches JSON order.
- `test_search_by_title` — verifies case-insensitive title search.
- `test_search_by_text` — verifies case-insensitive text search.
- `test_get_prompts_by_category` — verifies category filtering.
- `test_reload_refreshes_data` — verifies reload picks up file changes.
- `test_missing_json_creates_default` — verifies default config creation.
- `test_settings_property` — verifies settings access.

This provides a safety net before modifying `PromptManager`.

### 12.2 Unit Tests (New Feature)

- Prompt template parsing from `standard-prompts.txt`:
  - Parses multiple `## Title` + body blocks correctly.
  - Handles blank lines between blocks.
  - Handles multi-line body text.
  - Returns error for file with no `## ` headers.
  - Returns error for empty file.
  - Handles file with only one block.
- Placeholder substitution:
  - Replaces `____` with design spec path.
  - Replaces `####` with questions file path.
  - Replaces multiple occurrences of same token.
  - Leaves tokens unchanged when path is empty (prompt text still contains raw tokens).
- Availability logic:
  - Each prompt with missing/complete variables per the matrix in Section 8.2.
  - Prompt 2 unavailable when only design spec path is set.
  - Prompt 1 and 3 available with only design spec path set.
- Settings round-trip:
  - Read/write `workflow_files` in `prompts.json`.
  - Missing `workflow_files` key defaults to empty strings.
  - Existing categories and prompts are preserved after settings write.

### 12.3 UI Tests (Mocked Tk Patterns, Consistent with Existing Tests)

- Dialog opens from `Workflow Files...` button.
- Save updates manager and refreshes tree.
- Prompt 2 disabled when questions path is empty.
- Status bar message reflects missing inputs.
- Built-in category appears first in treeview.
- `Workflow Files...` button hidden when `standard-prompts.txt` is missing.
- Browse button opens file picker starting at current path's directory.

### 12.4 Regression Tests

- Existing non-workflow prompts still load/search/copy unchanged.
- App startup still succeeds with legacy `prompts.json` (no `workflow_files` key).
- App startup succeeds when `standard-prompts.txt` is missing.

## 13. Acceptance Criteria

1. A built-in category with exactly three prompts is visible, appearing first in the treeview with a distinct icon.
2. Prompt text is sourced from `standard-prompts.txt` templates with `## Title` headers.
3. Only `____` and `####` vary at runtime via configured paths.
4. User can set/update both file paths from UI.
5. Prompt 1 and 3 require only design spec path; Prompt 2 requires both.
6. Unavailable prompts cannot be copied and show clear reason in the status bar.
7. Existing prompt functionality remains backward compatible.
8. `Workflow Files...` button is hidden when built-in prompts are unavailable.

## 14. Rollout Plan

Phase 0 (Pre-requisite):

- Add regression test suite for existing `PromptManager` behavior.
- Clean up the `nul` artifact file at project root.
- Migrate `standard-prompts.txt` to the `## Title` structured format.

Phase 1:

- Implement `standard-prompts.txt` parsing and `PromptManager` support.
- Implement availability computation.
- Add unit tests for parsing, substitution, and availability.

Phase 2:

- Implement `PromptWindow` dialog, `Workflow Files...` button, availability states, and treeview integration.
- Add UI tests.
- Add regression tests.

Phase 3:

- Manual QA on Windows tray flow and placeholder substitution.
- Verify reload picks up `standard-prompts.txt` changes.

Phase 4:

- Update README with workflow usage steps.

## 15. Open Questions

All previously open questions are now resolved:

1. ~~Should stored paths be absolute, workspace-relative, or preserve exact user input?~~ **Resolved:** Preserve exact user input. No conversion is applied.
2. ~~Should Prompt 2 allow copy when questions path does not exist yet (pre-create workflow), or strictly require existing file?~~ **Resolved:** Allow copy. File existence is not checked at copy time; warnings are informational only.
3. ~~Should built-in prompts be displayed as read-only in preview (visual lock indicator)?~~ **Resolved:** Not in this iteration. Built-in prompts cannot be edited (no editing UI exists for them per Non-Goals), so a lock indicator is unnecessary.

## 16. Ideas for Future Improvement

- Support named workflow profiles (one per project).
- Add tokenized variables with explicit names (for example `{{design_spec_path}}`).
- Add one-click action to open configured files in editor.
- Add command to auto-detect latest questions file created after Prompt 1.
- Add import/export for workflow settings.
- Add a "Reset All" button in the file path dialog.
- Add periodic background check for file path validity.
- Allow built-in prompts to be shown with a visual read-only indicator in the preview pane.

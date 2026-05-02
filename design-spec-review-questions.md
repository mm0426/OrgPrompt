# Design Spec Review: Critical Questions

Review of `design-spec-built-in-prompt-series.md` against the current codebase.
Questions are grouped by severity: **Blockers**, **Risks**, and **Clarifications**.

---

## Blockers

These must be resolved before implementation starts.

### B1. How are prompts titled in `standard-prompts.txt`?

The file contains three prompt blocks with **no title metadata**. The `Prompt` dataclass requires a `title` field, and the UI treeview displays titles as the primary label.

Options:
- Add titles as structured headers (e.g., `## Title` prefix lines)?
- Hardcode titles in `PromptManager` (e.g., "Critical Questions", "Update Spec from Answers", "RFC Pipeline")?
- Store titles as a separate mapping in code?

**Why it matters:** Without a title strategy, the built-in category will show empty or placeholder titles in the treeview.

### B2. How does `PromptManager` write back to `prompts.json` without corrupting user data?

Currently `PromptManager` has **zero write operations**. The `_load()` method reads JSON and builds in-memory structures, but there is no save/flush mechanism. Adding `set_workflow_file_paths()` means writing to `prompts.json` mid-session.

Questions:
- Does the manager read the file, merge the new settings, and write the whole file back? This risks losing concurrent edits.
- Should writes be atomic (write to temp file, then rename)?
- Should `PromptManager` hold a file lock during write?
- What happens if the file is deleted or locked by another process between read and write?

**Why it matters:** A naive write-back could wipe user prompt edits or corrupt the JSON file.

### B3. What is the exact format of `standard-prompts.txt`?

The spec says prompts are "source-controlled in `standard-prompts.txt`" but does not define a parsing format. The current file uses blank-line separation, but there is no formal spec for:
- How to delimit prompt blocks (blank line? `---` separator? numbered headers?)
- Whether prompts can span multiple lines (currently they are single-line, but what if future prompts wrap?)
- Whether comments or metadata are allowed in the file
- Whether the trailing newline at end-of-file is significant

**Why it matters:** An informal parsing contract will break silently when the file is edited.

---

## Risks

These could cause significant rework if not addressed early.

### R1. How does the built-in category coexist with user categories in the treeview?

The `PromptWindow` treeview currently loads categories from `prompts.json`. The design spec says built-in prompts appear as a category called "Built-in Workflow", but does not specify:
- Where in the category list it appears (first? last? pinned?)
- Whether it uses the same expand/collapse behavior as user categories
- Whether it is visually distinguishable from user categories (icon? font style? separator?)
- Whether it survives search (Section 10.4 says "Search should include resolved built-in text and titles" but doesn't say if the category header itself appears in search results)

**Risk:** Without a clear placement strategy, the built-in category could be buried or visually confused with user content.

### R2. What happens when `standard-prompts.txt` is updated while the app is running?

The spec says (Section 10.5) "If `standard-prompts.txt` is missing or malformed, app logs error and omits built-in category without crashing." But it does not address:
- Should `reload()` also re-read `standard-prompts.txt`, or only `prompts.json`?
- If a user edits `standard-prompts.txt` and clicks the tray icon, do they see stale or fresh prompts?
- The current `show_prompt_window()` calls `self.prompt_manager.reload()` every time the window opens. Should this also reload templates?

**Risk:** Users could see outdated prompt text after updating the template file, leading to confusion.

### R3. How are built-in prompts represented in the `Prompt` dataclass?

Currently `Prompt` has fields: `title`, `text`, `category`. The design spec adds the concept of "availability" (ready / missing design spec / missing questions file). Options:
- Add an `available: bool` field to `Prompt`?
- Add an `availability_reason: str` field?
- Keep availability as a computed property outside `Prompt`, keyed on title or index?
- Create a subclass `BuiltInPrompt(Prompt)` with extra fields?

**Risk:** Polluting the `Prompt` dataclass with workflow-specific fields couples the data model to one feature. A subclass or external mapping keeps things cleaner but adds complexity.

### R4. No tests exist for `prompt_manager.py` or `prompt_window.py`

The spec calls for unit tests and UI tests in Section 12, but the two modules most affected by this feature have **zero test coverage**. The existing test suite (5 files, ~1,800 lines) covers logging, single-instance, tray manager, and main entry point only.

Questions:
- Should the first task be writing a regression test suite for the existing `PromptManager` and `PromptWindow` behavior, before adding new features?
- How confident are we that the new feature won't break existing search, copy, or category behavior without a baseline test suite?

**Risk:** Implementing new features on untested modules means any regression will go undetected until manual QA.

### R5. The `nul` artifact file

There is a file named `nul` at the project root (1 line, appears to be garbage from a Windows `%TEMP%` expansion). This should be cleaned up before the feature branch starts to avoid confusion.

**Risk:** Low, but it indicates the working directory state may not be clean.

---

## Clarifications

These need answers but are unlikely to cause rework.

### C1. Should the `Workflow Files...` button be always visible or only when built-in prompts are loaded?

If `standard-prompts.txt` is missing (Section 10.5), the built-in category is omitted. Should the `Workflow Files...` button also be hidden, or remain visible (disabled?) so users know the feature exists?

### C2. What is the "questions file" lifecycle?

Section 7.4 describes the flow: Prompt 1 runs externally, assistant creates a questions markdown file, user returns to set the path. Questions:
- Is the questions file always created by the assistant, or can the user create it manually?
- Is the file always markdown, or could it be any format?
- Should OrgPrompt validate the file extension?

### C3. Should the modal dialog remember the last-browsed directory?

When the user clicks `Browse...`, should the file picker open to the directory of the current path value, the last-browsed directory, or a default location?

### C4. What happens to the questions path when the user starts a new project?

Section 7.2 has a `Clear Questions Path` button. But:
- Should clearing the questions path also clear any cached/resolved Prompt 2 text?
- Should there be a "Reset All" option that clears both paths?
- Is there any concept of "workflow sessions" or is it purely ad-hoc?

### C5. Should path validation check for file existence on every window open?

Section 7.2 says "allow save even if file does not exist yet, but show warning." Questions:
- Is the warning checked once at save time, or re-checked every time the prompt window opens?
- If the design spec file is deleted after being set, should Prompt 1 still be available?
- Should there be a periodic background check?

### C6. How does the `####` placeholder interact with paths containing special characters?

Section 6 says "Substitution is literal string replacement; no escaping transformation." But:
- What if the questions file path contains `____` or `####` itself (pathological but possible)?
- What if the path contains backslashes on Windows (e.g., `D:\folder\questions.md`) -- should they be escaped for the prompt context, or left raw?
- Does the resolved prompt text need any sanitization before being copied to clipboard?

### C7. Are the three prompts always in fixed order, or can the template file define ordering?

The spec hardcodes "Prompt 1, Prompt 2, Prompt 3" with specific variable requirements. If someone reorders the blocks in `standard-prompts.txt`, should:
- The order change in the UI?
- The variable requirements follow the prompt or the position?
- Is position significant at all, or is it purely based on which placeholders are present?

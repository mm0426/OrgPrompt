# PRD: Edit Prompt Before Copying

## Status
Draft — 2026-06-28

---

## Problem Statement

When a user selects a prompt in OrgPrompt, the only way to copy it is via **Ok** (or Enter / double-click), which copies the *exact* stored text. There is no opportunity for quick inline edits — e.g., changing a placeholder value, trimming trailing whitespace, or appending context before pasting into an AI assistant.

Users currently must:
1. Copy to clipboard → paste somewhere else → edit there → copy again.
2. Or open the `prompts.json` file and modify it permanently (which they may not want).

This adds friction for a common workflow: **select, tweak slightly, then use**.

---

## Proposed Solution

Add an editable text area between prompt selection and clipboard copy so users can freely edit the chosen prompt before clicking Ok to copy.

### Current Flow
```
Select Prompt → Preview (read-only) → Click Ok / Enter → Copy exact stored text
```

### New Flow
```
Select Prompt → Editable Text Area ← user edits here → Click Ok / Enter → Copy edited text
```

---

## Requirements

### Functional

| ID | Requirement |
|----|-------------|
| FR-1 | The preview area becomes an editable `tk.Text` widget (state=`NORMAL`) when a prompt is selected. |
| FR-2 | Clicking **Ok** copies the *current contents* of the text area — not necessarily the stored prompt text. |
| FR-3 | Pressing Enter / double-click on the tree still triggers copy with whatever is in the editable area at that moment. |
| FR-4 | Selecting a different prompt replaces the text area content with that new prompt's stored text (overwriting any prior edits). |
| FR-5 | The status bar message after successful copy remains unchanged (`✓ Copied to clipboard!`). |

### Non-functional / UX

| ID | Requirement |
|----|-------------|
| NFR-1 | Visual distinction: the editable area should look clearly different from a read-only preview (e.g., white background instead of `#f5f5f5`, or a subtle border). |
| NFR-2 | The label on the frame changes from **"Preview"** to something like **"Edit / Preview"**. |
| NFR-3 | Keyboard focus remains in the tree by default (so arrow keys still navigate prompts); user must click into the text area or use Tab to edit. |

### Out of Scope

- Saving edited versions back to `prompts.json`.
- Undo/redo history
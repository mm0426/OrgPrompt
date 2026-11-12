# Technical Implementation Plan: Edit Prompt Before Copying

**Author:** Senior Technical Lead & Solutions Architect  
**Date:** 2026-06-28  
**PRD Reference:** `PRD-editable-prompt-before-copy.md` (Draft)

---

## Table of Contents
1. [Executive Summary & Tech Stack](#executive-summary--tech-stack)
2. [Architecture & System Design](#architecture--system-design)
3. [Phase-by-Phase Breakdown](#phase-by-phase-breakdown)
4. [Risk Assessment & Edge Cases](#risk-assessment--edge-cases)
5. [Testing & QA Strategy](#testing--qa-strategy)

---

## 1. Executive Summary & Tech Stack

### Overview
This change converts the read-only prompt preview area in OrgPrompt's Tkinter GUI into an editable text widget, allowing users to modify a selected prompt inline before copying it to the clipboard. The core logic shift is that **the copy action reads from the live widget content rather than from stored data**. No new backend services or databases are required — this is purely a frontend (GUI) change within the existing Tkinter application.

### Recommended Tech Stack
| Layer | Technology / Component | Notes |
|-------|------------------------|-------|
| **Frontend** | Python `tkinter` (`ttk`) + custom widgets | Existing codebase; no new dependencies needed. The preview widget transitions from a read-only `Text` (state=`DISABLED`) to an editable one (state=`NORMAL`). |
| **Backend / Logic** | Pure Python — existing copy-to-clipboard logic via `tkinter.Clipboard()` or platform-native clipboard APIs | No server, no API layer. All changes are in-process GUI event handlers. |
| **Data Store** | Existing `prompts.json` (read-only for this feature) | Out of scope: edits do not persist back to disk. |
| **Infrastructure / CI-CD** | None required — local desktop application, no deployment pipeline involved | If a test suite exists, it runs locally or in GitHub Actions.

### Key Architectural Decision
> The copy handler must be decoupled from the data model and instead read directly from the widget's current text. This is achieved by introducing an internal method `_get_current_preview_text()` that returns `self.preview_widget.get("1.0", "end-1c")` regardless of whether the content was loaded or edited.

---

## 2. Architecture & System Design

### High-Level Architectural Changes
```
┌───────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Tree View    │────▶│ Editable Preview │────▶│ Copy to Clipboard│
│  (Prompt List) │     │  Text Widget     │     │  Handler         │
│                │◀────│ (state=NORMAL)   │     │                  │
└───────────────┘     └──────────────────┘     └──────────────────┘
       ▲                       ▲                        ^
       │ Select prompt        │ User edits inline      │ Ok / Enter
       │ replaces content     │ (no persistence)       │ triggers copy
```

### Data Flow Changes
| Step | Before This Change | After This Change |
|------|-------------------|------------------|
| 1. Prompt selected in tree | Stored text loaded into read-only `Text` widget (`state=DISABLED`) | Stored text loaded into editable `Text` widget (`state=NORMAL`) |
| 2. User clicks Ok / presses Enter | Copy handler reads from **stored data model** (e.g., dict/list) and writes to clipboard | Copy handler reads from **widget content directly** via `_get_current_preview_text()` and writes to clipboard |
| 3. Different prompt selected | Stored text replaces widget content; prior edits lost | Same behavior — stored text overwrites any inline edits in the widget (FR-4) |

### Widget State Transition Table
| Trigger | Old `state` Value | New `state` Value | Rationale |
|---------|-------------------|-------------------|-----------|
| Prompt selected / loaded | `DISABLED` | `NORMAL` | Allows user to edit inline (FR-1) |
| Copy action triggered | N/A — state unchanged | State remains `NORMAL`; content is read and copied as-is | No need to toggle back; widget stays editable for subsequent edits |

### New / Modified Internal Methods & API Surface
No external APIs are introduced. The following internal methods on the main application class (or relevant controller) require modification or addition:

| Method Name | Type | Description |
|-------------|------|-------------|
| `_get_current_preview_text()` | **New** private method | Returns `self.preview_widget.get("1.0", "end-1c")`. Replaces any prior logic that read from the data model for copy operations. |
| `_on_prompt_selected(prompt_data)` | Modified existing handler | After loading prompt text into widget, ensure widget state is set to `NORMAL` (if not already). No other behavioral change needed — FR-4 is satisfied by overwriting content on selection. |
| `_copy_to_clipboard()` or equivalent copy handler | Modified existing handler | Replace the source of truth from stored data with a call to `_get_current_preview_text()`. Status bar message remains unchanged (FR-5). |

### Visual / Styling Changes Required
| Element | Current State | Target State | Requirement Ref. |
|---------|--------------|-------------|------------------|
| Preview area background color | `#f5f5f5` (gray) — read-only look | White (`"white"`) or a distinct editable-style fill | NFR-1 |
| Frame label text | **Preview** | **Edit / Preview** | NFR-2 |
| Widget border | None or subtle | Optional: add `relief="solid", bd=1` for visual distinction of editability | NFR-1 (suggestion) |

---

## 3. Phase-by-Phase Breakdown

### Phase 1 — Foundation & Backend Logic Changes *(Estimated Effort: ~2 hours)*
| # | Task | Details | Acceptance Criteria |
|---|------|---------|---------------------|
| 1.1 | Identify the copy handler method(s) in codebase | Locate `_copy_to_clipboard()` or equivalent; trace where it reads prompt text from (data model vs widget). | Copy source is identified and documented. |
| 1.2 | Implement `_get_current_preview_text()` helper | Add private method that returns current widget content via `self.preview_widget.get("1.0", "end-1c")`. | Method exists, returns correct string for any widget state. |
| 1.3 | Refactor copy handler to use new helper | Replace the data-model read with a call to `_get_current_preview_text()`. Verify status bar message is untouched (FR-5). | Copying after edit reflects edited text; copying without edits still works identically. |

### Phase 2 — Core Widget & UI Changes *(Estimated Effort: ~1 hour)*
| # | Task | Details | Acceptance Criteria |
|---|------|---------|---------------------|
| 2.1 | Change preview widget state to `NORMAL` on load / selection | In `_on_prompt_selected()` or equivalent, set `self.preview_widget.config(state="NORMAL")`. Ensure this is applied every time a prompt loads (FR-4). | Widget accepts keyboard input; user can type/delete in the area. |
| 2.2 | Update frame label from "Preview" to **Edit / Preview** | Modify the ttk Label or Frame text attribute accordingly (NFR-2). | UI displays new label on all prompt selections. |
| 2.3 | Apply visual distinction styling | Change background color and optionally add a border (`relief="solid", bd=1`) so users can visually distinguish editability from read-only state (NFR-1). | Editable area looks distinct; no regression in overall UI aesthetics. |

### Phase 3 — Keyboard & Focus Integration *(Estimated Effort: ~2 hours)*
| # | Task | Details | Acceptance Criteria |
|---|------|---------|---------------------|
| 3.1 | Ensure keyboard focus remains on tree by default (NFR-3) | After loading a prompt, explicitly call `self.tree.focus_set()` or equivalent so arrow keys navigate the list without requiring user to click back into it. | Arrow up/down navigates prompts; no need to re-click tree after editing in text area. |
| 3.2 | Verify Enter key behavior on both widgets (FR-3) | Confirm that pressing **Enter** while focus is on the tree triggers copy with current widget content, and that double-click also works as before. No behavioral regression expected since source of truth shifted to widget. | Both Enter-on-tree and double-copy work; edited text is copied in all cases. |
| 3.3 | Verify Tab key moves focus from tree → preview area (NFR-3) | Ensure standard Tkinter tab-ordering works so users can reach the editable area via keyboard without clicking. | Pressing **Tab** shifts focus to the text widget; pressing again cycles through other widgets as expected.

### Phase 4 — Testing, Polish & Deployment *(Estimated Effort: ~2 hours)*
| # | Task | Details | Acceptance Criteria |
|---|------|---------|---------------------|
| 4.1 | Write / update unit tests for copy handler and `_get_current_preview_text()` | Cover the new helper method; verify it returns widget content, not stored data. | All existing + new unit tests pass locally.
| 4.2 | Manual E2E smoke test across all FRs & NFRs | Walk through each requirement in a checklist (see Section 5). | Every acceptance criterion is satisfied manually before merge. |
| 4.3 | Code review and merge to main branch | Submit PR with clear diff highlighting the widget state change, copy handler refactor, and styling updates.

---

## 4. Risk Assessment & Edge Cases

### Technical Risks
| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|-----------|
| R1 | **Copy handler still reads from data model** — if the refactor is incomplete, edits are silently ignored and stored text is copied instead. | High | Medium | Add a unit test that explicitly sets widget content to differ from stored prompt; assert clipboard contains edited value after copy.
| R2 | **Widget state leaks between prompts** — `state=NORMAL` persists across selections, which could allow stale edits if `_on_prompt_selected()` doesn't overwrite the text area. | Medium | Low (FR-4 requires overwriting) | Ensure `_on_prompt_selected()` always calls `.delete("1.0", "end")` before inserting new prompt text.
| R3 | **Focus management regression** — after editing in the preview, pressing arrow keys may not navigate the tree if focus is still on the widget. | Medium | High (Tkinter default behavior) | Explicitly manage focus: set to tree after selection; document that users must Tab or click into text area to edit.
| R4 | **Enter key conflict** — Enter in a `Text` widget may insert a newline instead of triggering copy if the handler is bound at the wrong level. | Medium | Low (existing behavior) | Verify event binding scope: ensure `<Return>` on tree triggers copy; do not bind it globally to all widgets.

### Security Risks
| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|-----------|
| S1 | **Clipboard content injection** — user could paste malicious or extremely large text into the widget and copy it. Not a security vulnerability per se, but clipboard APIs have size limits on some platforms (e.g., Windows ~64KB). | Low | Medium | No action required for MVP; document as known limitation if needed.

### Scalability Concerns
| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|-----------|
| SC1 | **Large prompt text** — Tkinter `Text` widgets can handle large content, but performance may degrade with very long prompts (>50KB). Not expected in this use case. | Low | Very Low | No action required; monitor if users report lag.

### Edge Cases to Handle Explicitly
| # | Scenario | Expected Behavior |
|---|----------|------------------|
| E1 | User edits prompt, then selects a different one without copying | New prompt text overwrites the widget (FR-4); prior edits are lost. No confirmation dialog needed.
| E2 | Prompt is empty or contains only whitespace in `prompts.json` | Widget displays blank/whitespace; user can type freely and copy whatever they enter.
| E3 | User copies without editing at all | Behavior identical to pre-change: stored text copied, status bar shows ✓ message (FR-5).
| E4 | Rapid double-click on tree while focus is in the preview area | Double-click should still trigger copy with current widget content; no crash or unexpected behavior.

---

## 5. Testing & QA Strategy

### Test Pyramid Overview
```
         ┌──────────────┐
         │   E2E /      │     ~3-4 manual scenarios (smoke test)
         │ Manual Smoke │
    ─────│──────────────│─────
  ┌──────▼──────────────▼──────┐
  │       Unit Tests           │     Cover new helper + refactored copy handler
  │   (_get_current_preview_   │
  │    text, _copy_to_clipboard)│
  └─────────────────────────────┘
```

### Required Test Cases — Functional (FR)
| ID | Requirement Ref. | Description | Expected Result |
|----|-----------------|-------------|------------------|
| TC-FR1 | FR-1 | Select a prompt; verify the preview widget accepts keyboard input (`state=NORMAL`). | Widget is editable; user can type, delete, and select text.
| TC-FR2 | FR-2 | Edit the selected prompt in the preview area (e.g., append " [edited]"); click **Ok**. Verify clipboard contains edited version. | Clipboard holds `original_text + " [edited]"`, not just stored text.
| TC-FR3a | FR-3 | With focus on tree, press Enter after editing in preview. Verify copy uses current widget content. | Edited text is copied; status bar shows ✓ message.
| TC-FR3b | FR-3 | Double-click a prompt node while the preview area contains edited text from a prior selection (if applicable). | Copy triggers with whatever is currently displayed, not stale data.
| TC-FR4 | FR-4 | Edit Prompt A in preview; then select Prompt B. Verify widget content changes to Prompt B's stored text and edits are lost. | Widget shows Prompt B exactly as stored; no residual edits from Prompt A.
| TC-FR5 | FR-5 | After any copy action, verify status bar displays `✓ Copied to clipboard!` unchanged. | Status message matches original wording exactly.

### Required Test Cases — Non-functional / UX (NFR)
| ID | Requirement Ref. | Description | Expected Result |
|----|-----------------|-------------|------------------|
| TC-NFR1a | NFR-1 | Verify the preview area background color is visually distinct from read-only gray (`#f5f5f5`). | Background appears white or clearly different.
| TC-NFR2 | NFR-2 | Frame label reads **Edit / Preview** (or equivalent). | Label text matches target string.
| TC-NFR3a | NFR-3 | After selecting a prompt, arrow keys navigate the tree without requiring user to click back into it. | Focus is on tree; Up/Down moves selection.
| TC-NFR3b | NFR-3 | Pressing **Tab** from the tree shifts focus to the preview text area for editing. | Tab cycles: Tree → Preview Text Area → other widgets (standard Tkinter tab order).

### Required Test Cases — Edge & Risk Coverage
| ID | Ref. | Description | Expected Result |
|----|------|-------------|------------------|
| TC-E1  | E1   | Edit Prompt A, select Prompt B without copying; verify no crash and content is overwritten cleanly.
| TC-E2  | E2   | Select a prompt that has empty or whitespace-only text in `prompts.json`; edit it to non-empty; copy. Clipboard contains user's edited text.
| TC-R1  | R1   | **Critical regression test**: Set widget content programmatically (or via UI) to differ from stored data, then trigger copy. Assert clipboard matches widget, not storage.

### Test Execution Checklist Before Merge
- [ ] All unit tests pass locally (`pytest` or equivalent)
- [ ] Manual smoke test covers every TC-FR and TC-NFR row above
- [ ] No visual regression in the overall application window (layout intact after styling changes)
- [ ] Code reviewed by at least one peer; diff is clean with no unintended side effects on other handlers
---

## Appendix: File-Level Change Summary
| File / Module | Type of Change | Key Lines Affected |
|---------------|----------------|--------------------|
| Main GUI controller (e.g., `app.py` or equivalent) — `_on_prompt_selected()` handler | Modify widget state to `NORMAL`; ensure content overwrite on selection. |
| Same file — copy-to-clipboard method(s) | Replace data-model read with call to new helper.
| Same file — UI initialization / styling block | Update frame label text; apply background color and optional border changes.
| Test suite (if exists, e.g., `tests/`) | Add unit tests for `_get_current_preview_text()` and refactored copy handler. |

---
*End of Technical Implementation Plan*

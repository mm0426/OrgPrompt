# OrgPrompt

A Windows system tray utility for quick access to AI prompts.

## Features

- **System Tray Icon**: Always accessible from the Windows system tray
- **Categorized Prompts**: Organize prompts by category (Coding, Writing, Analysis, etc.)
- **Search**: Ranked filtering across all prompts (title matches first; every word must match)
- **Edit before copy**: Tweak a prompt in the preview box for one-time use; the saved prompt is unchanged
- **Favorites**: Pin prompts (right-click → Add to Favorites); they appear at the top and in the tray menu
- **Frequently Used**: Your 5 most-copied prompts appear automatically near the top
- **New prompts from the app**: "New Prompt…" or "Save as New Prompt…" (from edited text)
- **Open in Editor**: Opens the selected prompt's file; edits are picked up automatically
- **Remembers layout**: Window size/position and expanded categories persist between sessions
- **Auto-close**: Window closes automatically after copying (configurable)

## Installation

1. Install Python 3.10 or later
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   python main.py
   ```

2. Click the tray icon to open the prompt selector (or right-click it and pick a favorite to copy it directly)
3. Search or browse categories to find a prompt
4. Optionally edit the text in the **Edit / Preview** box
5. Click **Ok** (or Enter / Ctrl+Enter / double-click) to copy, then paste into your AI application

## Customizing Prompts

Edit `prompts.json` to add your own prompts:

```json
{
  "settings": {
    "auto_close": true,
    "show_notifications": true
  },
  "categories": [
    {
      "name": "My Category",
      "prompts": [
        {
          "title": "My Prompt",
          "text": "This is my custom prompt text..."
        },
        {
          "title": "Longer Prompt",
          "file": "prompts/my-category/longer-prompt.md",
          "pinned": true
        }
      ]
    }
  ]
}
```

### Settings

- `auto_close`: Close window after copying (default: true)
- `show_notifications`: Show a Windows notification on copy (default: true)

### Prompt fields

- `text` or `file`: inline text, or a path (relative to `prompts.json`) to a `.md` file
- `pinned`: `true` to show the prompt under Favorites and in the tray menu

Usage counts and window layout are kept in `orgprompt_state.json` (not in `prompts.json`).

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Esc` | Close window |
| `Enter` (in search) | Copy the top match |
| `Enter` (in list) | Copy selected prompt / expand-collapse category |
| `Ctrl+Enter` | Copy (works while editing the preview) |
| `↓` (in search) | Move into the results |
| `↑` (top of list) | Back to the search box |
| `←` `→` | Collapse / expand category |
| `Ctrl+F` | Focus search |

## Troubleshooting

Logs are written to `%TEMP%\orgprompt\orgprompt.log`, including errors from the
UI and background threads. If the app ever dies outright, a Python traceback of
every thread is written to `%TEMP%\orgprompt\orgprompt_fault.log`. If the tray
icon fails repeatedly, OrgPrompt restarts it, and exits cleanly after 5 failures
so it can simply be relaunched.

## Built-in Prompt Workflow

OrgPrompt includes a built-in three-prompt workflow sourced from `standard-prompts.txt`. Prompt text is immutable at runtime -- only file path placeholders change.

### The Three Prompts

| # | Name | Requires |
|---|------|----------|
| 1 | **Critical Questions** | Design spec path |
| 2 | **Update Spec from Answers** | Design spec path + questions file path |
| 3 | **RFC Pipeline** | Design spec path |

- **Critical Questions** reviews a project summary and generates critical questions for you to answer.
- **Update Spec from Answers** updates a design spec with your answers to those questions.
- **RFC Pipeline** decomposes an RFC into work units with a dependency DAG for parallel execution.

### First-Run Setup

1. Click the tray icon to open OrgPrompt
2. Click **"Workflow Files..."** (visible when built-in prompts are loaded)
3. Set your design spec file path and click **Save**
4. Copy Prompt 1 (Critical Questions) and paste into your AI assistant
5. After the assistant creates a questions file, return to OrgPrompt
6. Click **"Workflow Files..."** again and set the questions file path
7. Prompt 2 (Update Spec from Answers) is now available

### Prompt Availability

- Prompts 1 and 3 need only the design spec path
- Prompt 2 needs both the design spec path and the questions file path
- Unavailable prompts are shown in gray and cannot be copied

### File Path Management

- Use **"Workflow Files..."** to set or update paths at any time
- Use **"Clear Questions Path"** to reset between runs (saves immediately)
- The **Browse** button opens a file picker starting at the current path's directory

### Template Format

For advanced users who want to edit `standard-prompts.txt`:

- Each prompt block starts with `## Title` followed by the prompt body
- `____` is replaced with the design spec path
- `####` is replaced with the questions file path
- Changes take effect the next time the prompt window opens

## License

MIT

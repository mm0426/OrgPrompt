# OrgPrompt

A Windows system tray utility for quick access to AI prompts.

## Features

- **System Tray Icon**: Always accessible from the Windows system tray
- **Categorized Prompts**: Organize prompts by category (Coding, Writing, Analysis, etc.)
- **Search**: Real-time filtering across all prompts
- **Preview**: See the full prompt text before copying
- **Keyboard Navigation**: Use arrow keys to navigate, Enter to select, Escape to close
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

2. Click the tray icon to open the prompt selector
3. Search or browse categories to find a prompt
4. Click a prompt to copy it to your clipboard
5. Paste into your AI application

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
        }
      ]
    }
  ]
}
```

### Settings

- `auto_close`: Close window after copying (default: true)
- `show_notifications`: Show toast notification on copy (default: true)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Esc` | Close window |
| `Enter` | Copy selected prompt |
| `↑` `↓` | Navigate prompts |

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

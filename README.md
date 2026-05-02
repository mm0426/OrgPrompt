# OrgPrompt

A cross-platform system tray utility for quick access to AI prompts.

## Features

- **System Tray Icon**: Always accessible from the system tray
- **Categorized Prompts**: Organize prompts by category (Coding, Writing, Analysis, etc.)
- **Search**: Real-time filtering across all prompts
- **Preview**: See the full prompt text before copying
- **Keyboard Navigation**: Use arrow keys to navigate, Enter to select, Escape to close
- **Auto-close**: Window closes automatically after copying (configurable)

## Requirements

- Python 3.10 or later

## Installation

### Linux (Debian/Ubuntu)

```bash
sudo apt install python3-tk python3-gi gir1.2-ayatanaappindicator3-0.1 libnotify-bin python3-venv
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> On GNOME Wayland, you also need the [AppIndicator Support](https://extensions.gnome.org/extension/615/appindicator-support/) extension for the tray icon to appear.

### Linux (Fedora)

```bash
sudo dnf install python3-tkinter python3-gobject gtk3 libnotify
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows

```bash
pip install -r requirements.txt
```

### Optional: notify2 (Linux)

For a more reliable notification backend, install `notify2`:
```bash
pip install notify2
```
This is not required — OrgPrompt falls back to `notify-send` (which is included with `libnotify-bin`) if `notify2` is not installed.

## Usage

**Linux:**
```bash
./orgprompt.sh
```

**Windows:**
```
orgprompt.bat
```

Click the tray icon to open the prompt selector, search or browse to find a prompt, and click to copy it to your clipboard.

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
- `show_notifications`: Show desktop notification on copy (default: true)

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

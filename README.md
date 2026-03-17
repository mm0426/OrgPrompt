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

## License

MIT

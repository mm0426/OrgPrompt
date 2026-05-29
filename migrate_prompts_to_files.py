"""One-time migration: extract inline prompt text into individual .md files.

Run once:  python migrate_prompts_to_files.py

Converts prompts.json from inline ``text`` fields to ``file`` references
pointing to ``prompts/{category}/{slug}.md``.

Backs up the original JSON as prompts.json.bak.
"""

import json
import re
from pathlib import Path


def slugify(text: str) -> str:
    """Convert a title to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _load_json(config_path: Path) -> dict:
    """Load JSON, tolerating hand-edited files with invalid escape sequences.

    Handles cases like ``D:\\utilities`` where the lone backslash before ``u``
    creates an invalid ``\\uXXXX`` escape in JSON.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fixed = _fix_missing_commas(raw)
        fixed = _fix_invalid_escapes(fixed)
        return json.loads(fixed)


def _fix_invalid_escapes(text: str) -> str:
    """Fix invalid JSON escape sequences inside string values.

    Walks the text character by character, tracking whether we are inside
    a JSON string.  Doubles backslashes that start invalid escape sequences.
    """
    result = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if not in_string:
            result.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue
        # Inside a string
        if ch == '\\' and i + 1 < n:
            next_ch = text[i + 1]
            if next_ch in '"\\/bfnrt':
                result.append(ch)
                result.append(next_ch)
                i += 2
            elif next_ch == 'u' and i + 5 < n and all(
                c in '0123456789abcdefABCDEF' for c in text[i + 2:i + 6]
            ):
                result.append(text[i:i + 6])
                i += 6
            else:
                result.append('\\\\')
                result.append(next_ch)
                i += 2
        elif ch == '"':
            in_string = False
            result.append(ch)
            i += 1
        else:
            result.append(ch)
            i += 1
    return ''.join(result)


def _fix_missing_commas(text: str) -> str:
    """Insert missing commas between JSON array/object elements.

    Handles cases like ``}\\n{`` (no comma between array items) and
    ``]\\n[`` or ``}\\n{`` at the structural level.
    """
    fixed = re.sub(r'}\s*\n(\s*){', r'},\n\1{', text)
    return fixed


def migrate(config_path: Path) -> None:
    """Run the migration."""
    if not config_path.exists():
        print(f"ERROR: {config_path} not found")
        return

    data = _load_json(config_path)

    # Check if already migrated (all prompts use file references)
    has_inline = False
    for category in data.get("categories", []):
        for prompt in category.get("prompts", []):
            if "text" in prompt and "file" not in prompt:
                has_inline = True
                break
        if has_inline:
            break

    if not has_inline:
        print("Already migrated — no inline text found.")
        return

    base_dir = config_path.parent
    prompts_dir = base_dir / "prompts"

    for category in data.get("categories", []):
        cat_name = category.get("name", "Uncategorized")
        cat_dir = prompts_dir / slugify(cat_name)
        cat_dir.mkdir(parents=True, exist_ok=True)

        for prompt in category.get("prompts", []):
            text = prompt.pop("text", "")
            if not text:
                continue

            slug = slugify(prompt.get("title", "untitled"))
            file_path = cat_dir / f"{slug}.md"
            rel_path = file_path.relative_to(base_dir)

            # Handle duplicate slugs
            counter = 1
            while file_path.exists():
                file_path = cat_dir / f"{slug}-{counter}.md"
                rel_path = file_path.relative_to(base_dir)
                counter += 1

            file_path.write_text(text, encoding="utf-8")
            prompt["file"] = str(rel_path).replace("\\", "/")
            print(f"  {rel_path}")

    # Backup original
    backup_path = config_path.with_suffix(".json.bak")
    config_path.replace(backup_path)
    print(f"\nBackup: {backup_path}")

    # Write migrated JSON
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Updated: {config_path}")


if __name__ == "__main__":
    config_path = Path(__file__).parent / "prompts.json"
    migrate(config_path)

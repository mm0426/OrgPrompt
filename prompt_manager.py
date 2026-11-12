"""Prompt management - loading, caching, searching, and editing prompts."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

logger = logging.getLogger("orgprompt.prompt_manager")

STANDARD_PROMPTS_FILE = "standard-prompts.txt"


@dataclass
class Prompt:
    """Represents a single prompt."""
    title: str
    text: str
    category: str
    pinned: bool = False
    # Relative path (from the config dir) of the .md file backing this prompt,
    # or None when the text is stored inline in prompts.json.
    file: Optional[str] = None
    # Position in prompts.json (category index, prompt index). -1 for prompts
    # that don't come from prompts.json (built-in workflow prompts).
    cat_index: int = -1
    index: int = -1

    @property
    def key(self) -> str:
        """Stable identifier used for usage tracking and tray favorites."""
        return f"{self.category}::{self.title}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "prompt"


class PromptManager:
    """Manages prompt loading, searching, and edits to prompts.json."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent / "prompts.json"
        self._data: dict = {}
        self._prompts: list[Prompt] = []
        self._categories: list[str] = []
        self._builtin_cache: list[Prompt] | None = None
        self._signature: tuple = ()
        self._load()

    # --- Loading ---

    def _read_config_data(self) -> dict:
        """Read and parse prompts.json, tolerating invalid escape sequences."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = f.read()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Tolerate hand-edited files with invalid escape sequences
            fixed = re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', raw)
            fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', fixed)
            return json.loads(fixed)

    def _write_config_data(self, data: dict) -> None:
        """Atomically write prompts.json (write temp file, then rename)."""
        tmp_path = self.config_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        tmp_path.replace(self.config_path)

    def _load(self) -> None:
        """Load prompts from JSON file.

        Supports both inline ``text`` and file references via ``file``.
        When ``file`` is present, the prompt text is read from that file
        (relative to the config directory).
        """
        if not self.config_path.exists():
            self._create_default_config()
            return

        self._data = self._read_config_data()

        # Build into locals and assign at the end so readers on other threads
        # (the tray menu) never see a half-built list.
        prompts: list[Prompt] = []
        categories: list[str] = []

        for cat_index, category in enumerate(self._data.get("categories", [])):
            cat_name = category.get("name", "Uncategorized")
            categories.append(cat_name)
            for index, prompt in enumerate(category.get("prompts", [])):
                text = prompt.get("text", "")
                file_ref = prompt.get("file")
                if file_ref:
                    file_path = self.config_path.parent / file_ref
                    try:
                        text = file_path.read_text(encoding="utf-8")
                    except FileNotFoundError:
                        logger.warning(
                            "Prompt file not found: %s (referenced by '%s')",
                            file_path, prompt.get("title", "Untitled"),
                        )
                prompts.append(Prompt(
                    title=prompt.get("title", "Untitled"),
                    text=text,
                    category=cat_name,
                    pinned=bool(prompt.get("pinned", False)),
                    file=file_ref or None,
                    cat_index=cat_index,
                    index=index,
                ))

        self._prompts = prompts
        self._categories = categories
        self._signature = self._compute_signature()

    def _create_default_config(self) -> None:
        """Create a default configuration file."""
        default = {
            "settings": {"auto_close": True, "show_notifications": True},
            "categories": [{
                "name": "General",
                "prompts": [{
                    "title": "Example Prompt",
                    "text": "This is an example prompt. Edit prompts.json to add your own!"
                }]
            }]
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2)
        self._load()

    def _compute_signature(self) -> tuple:
        """Fingerprint (mtime + size) of every file prompts are loaded from."""
        config_dir = self.config_path.parent
        paths = [self.config_path, config_dir / STANDARD_PROMPTS_FILE]
        paths += [config_dir / p.file for p in self._prompts if p.file]
        signature = []
        for path in paths:
            try:
                st = path.stat()
                signature.append((str(path), st.st_mtime_ns, st.st_size))
            except OSError:
                signature.append((str(path), None, None))
        return tuple(signature)

    def reload(self) -> None:
        """Reload prompts from file."""
        self._builtin_cache = None
        self._load()

    def reload_if_changed(self) -> bool:
        """Reload only if prompts.json or any prompt file changed on disk.

        Returns True if a reload happened.
        """
        if self._compute_signature() == self._signature:
            return False
        logger.info("Prompt files changed on disk; reloading")
        self.reload()
        return True

    @property
    def settings(self) -> dict:
        """Get settings from config."""
        return self._data.get("settings", {"auto_close": True, "show_notifications": True})

    # --- Workflow support methods ---

    def get_workflow_file_paths(self) -> dict[str, str]:
        """Get workflow file paths from settings.

        Returns dict with 'design_spec_path' and 'questions_file_path' keys.
        Defaults to empty strings if workflow_files key is missing.
        """
        wf = self.settings.get("workflow_files", {})
        return {
            "design_spec_path": wf.get("design_spec_path", ""),
            "questions_file_path": wf.get("questions_file_path", ""),
        }

    def set_workflow_file_paths(
        self, design_spec_path: str, questions_file_path: str
    ) -> bool:
        """Save workflow file paths to prompts.json.

        Uses atomic write: read -> modify -> write to temp -> rename.
        Returns True on success, False on failure.
        """
        try:
            data = self._read_config_data()
            if "settings" not in data:
                data["settings"] = {}
            data["settings"]["workflow_files"] = {
                "design_spec_path": design_spec_path,
                "questions_file_path": questions_file_path,
            }
            self._write_config_data(data)
            self.reload()
            return True
        except Exception:
            logger.exception(
                "Failed to save workflow file paths to %s", self.config_path
            )
            return False

    def get_built_in_prompts(self) -> list[Prompt]:
        """Get built-in workflow prompts with placeholders substituted.

        Returns cached prompts when available. Returns empty list if
        standard-prompts.txt is missing or malformed.
        """
        if self._builtin_cache is not None:
            return self._builtin_cache

        from workflow_prompt_templates import load_builtin_prompts

        paths = self.get_workflow_file_paths()
        config_dir = self.config_path.parent
        try:
            self._builtin_cache = load_builtin_prompts(
                config_dir, paths["design_spec_path"], paths["questions_file_path"]
            )
            return self._builtin_cache
        except (FileNotFoundError, ValueError):
            self._builtin_cache = []
            return []

    def get_built_in_category_name(self) -> str | None:
        """Return 'Built-in Workflow' if built-in prompts are available, else None."""
        from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

        return BUILT_IN_CATEGORY_NAME if self.get_built_in_prompts() else None

    def get_prompt_availability_for(self, prompt_index: int) -> tuple[bool, str]:
        """Get availability for a built-in prompt by index."""
        from workflow_availability import get_prompt_availability

        paths = self.get_workflow_file_paths()
        return get_prompt_availability(
            prompt_index, paths["design_spec_path"], paths["questions_file_path"]
        )

    def get_availability(self, prompt: Prompt) -> tuple[bool, str]:
        """Availability of any prompt. User prompts are always available."""
        from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

        if prompt.category != BUILT_IN_CATEGORY_NAME:
            return (True, "")
        for idx, bp in enumerate(self.get_built_in_prompts()):
            if bp is prompt or bp.title == prompt.title:
                return self.get_prompt_availability_for(idx)
        return (True, "")

    def get_built_in_prompt_count(self) -> int:
        """Get number of built-in prompts."""
        return len(self.get_built_in_prompts())

    # --- Queries ---

    @property
    def categories(self) -> list[str]:
        """Get list of category names.

        Built-in workflow category appears first when built-in prompts are
        available.
        """
        built_in = self.get_built_in_category_name()
        if built_in:
            return [built_in] + self._categories
        return self._categories

    @property
    def user_categories(self) -> list[str]:
        """Category names from prompts.json (excludes the built-in category)."""
        return list(self._categories)

    def get_prompts_by_category(self, category: str) -> list[Prompt]:
        """Get all prompts in a category."""
        return [p for p in self._prompts if p.category == category]

    def get_all_prompts(self) -> list[Prompt]:
        """Get all prompts."""
        return self._prompts

    def get_pinned_prompts(self) -> list[Prompt]:
        """Get prompts marked as favorites, in prompts.json order."""
        return [p for p in self._prompts if p.pinned]

    def find_by_key(self, key: str) -> Optional[Prompt]:
        """Find a user or built-in prompt by its key."""
        for prompt in self._prompts + self.get_built_in_prompts():
            if prompt.key == key:
                return prompt
        return None

    def get_source_path(self, prompt: Optional[Prompt]) -> Path:
        """File a prompt's text lives in (for opening in an editor)."""
        from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

        if prompt is None:
            return self.config_path
        if prompt.category == BUILT_IN_CATEGORY_NAME:
            return self.config_path.parent / STANDARD_PROMPTS_FILE
        if prompt.file:
            return self.config_path.parent / prompt.file
        return self.config_path

    def search(
        self, query: str, popularity: Optional[Mapping[str, int]] = None
    ) -> list[Prompt]:
        """Search prompts by title or text, including built-in workflow prompts.

        Every word in the query must appear in the title or text. Results are
        ranked: title starts with the query, title contains the query, title
        contains all words, title contains some words, then text-only matches.
        Ties are broken by ``popularity`` (key -> use count), then file order.
        """
        all_prompts = self._prompts + self.get_built_in_prompts()

        q = query.strip().lower()
        if not q:
            return all_prompts

        tokens = q.split()
        popularity = popularity or {}
        scored = []
        for order, p in enumerate(all_prompts):
            title = p.title.lower()
            text = p.text.lower()
            if not all(t in title or t in text for t in tokens):
                continue
            if title.startswith(q):
                tier = 0
            elif q in title:
                tier = 1
            elif all(t in title for t in tokens):
                tier = 2
            elif any(t in title for t in tokens):
                tier = 3
            else:
                tier = 4
            scored.append((tier, -popularity.get(p.key, 0), order, p))

        scored.sort(key=lambda s: s[:3])
        return [s[3] for s in scored]

    def get_category_prompt_count(self, category: str) -> int:
        """Get number of prompts in a category, including built-in prompts."""
        from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

        count = len([p for p in self._prompts if p.category == category])
        if category == BUILT_IN_CATEGORY_NAME:
            count += len(self.get_built_in_prompts())
        return count

    # --- Edits ---

    def set_pinned(self, prompt: Prompt, pinned: bool) -> bool:
        """Mark/unmark a prompt as a favorite in prompts.json.

        Returns True on success, False on failure (e.g. built-in prompt, or
        prompts.json changed so the prompt can't be located).
        """
        if prompt.cat_index < 0 or prompt.index < 0:
            return False
        try:
            data = self._read_config_data()
            entry = data["categories"][prompt.cat_index]["prompts"][prompt.index]
            if entry.get("title", "Untitled") != prompt.title:
                logger.warning(
                    "Cannot pin '%s': prompts.json changed on disk", prompt.title
                )
                return False
            if pinned:
                entry["pinned"] = True
            else:
                entry.pop("pinned", None)
            self._write_config_data(data)
            self.reload()
            return True
        except Exception:
            logger.exception("Failed to update favorite for '%s'", prompt.title)
            return False

    def add_prompt(self, category: str, title: str, text: str) -> Prompt:
        """Create a new prompt saved as a .md file and referenced in prompts.json.

        The file goes in ``prompts/<category-slug>/<title-slug>.md``. A new
        category is created if needed.

        Raises:
            ValueError: if a field is empty or the category is reserved.
            OSError: if writing fails.
        """
        from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

        category = category.strip()
        title = title.strip()
        if not category:
            raise ValueError("Category is required.")
        if not title:
            raise ValueError("Title is required.")
        if not text.strip():
            raise ValueError("Prompt text is required.")
        if category == BUILT_IN_CATEGORY_NAME:
            raise ValueError(f"'{BUILT_IN_CATEGORY_NAME}' is reserved.")

        config_dir = self.config_path.parent
        folder = Path("prompts") / _slugify(category)
        base = _slugify(title)
        rel_path = folder / f"{base}.md"
        n = 2
        while (config_dir / rel_path).exists():
            rel_path = folder / f"{base}-{n}.md"
            n += 1

        data = self._read_config_data()
        categories = data.setdefault("categories", [])
        target = next((c for c in categories if c.get("name") == category), None)
        if target is None:
            target = {"name": category, "prompts": []}
            categories.append(target)

        (config_dir / folder).mkdir(parents=True, exist_ok=True)
        (config_dir / rel_path).write_text(text, encoding="utf-8")
        target.setdefault("prompts", []).append(
            {"title": title, "file": rel_path.as_posix()}
        )
        try:
            self._write_config_data(data)
        except Exception:
            (config_dir / rel_path).unlink(missing_ok=True)
            raise

        self.reload()
        new = next(p for p in self._prompts if p.file == rel_path.as_posix())
        logger.info("Added prompt '%s' to category '%s'", title, category)
        return new

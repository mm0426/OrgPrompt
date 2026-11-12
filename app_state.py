"""Persistent app state: prompt usage counts and UI preferences.

Kept in its own file (not prompts.json) so that everyday use - copying
prompts, resizing the window, expanding categories - never rewrites the
user's hand-maintained prompt library.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("orgprompt.app_state")

STATE_FILE_NAME = "orgprompt_state.json"


class AppState:
    """Usage statistics and UI state, saved as JSON."""

    def __init__(self, path: Optional[Path] = None, persist: bool = True):
        """
        Args:
            path: State file location (default: next to this module).
            persist: If False, state lives in memory only (used in tests).
        """
        self.path = path or Path(__file__).parent / STATE_FILE_NAME
        self.persist = persist
        self._usage: dict[str, dict] = {}
        self._ui: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.persist or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            usage = data.get("usage", {})
            ui = data.get("ui", {})
            self._usage = usage if isinstance(usage, dict) else {}
            self._ui = ui if isinstance(ui, dict) else {}
        except (OSError, ValueError, AttributeError):
            logger.warning("Could not read %s; starting with empty state", self.path)

    def save(self) -> None:
        """Write state atomically. Failures are logged, never raised."""
        if not self.persist:
            return
        try:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps({"usage": self._usage, "ui": self._ui}, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except OSError:
            logger.exception("Failed to save app state to %s", self.path)

    # --- Usage ---

    def record_use(self, key: str) -> None:
        entry = self._usage.get(key)
        if not isinstance(entry, dict):
            entry = {"count": 0}
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_used"] = datetime.now().isoformat(timespec="seconds")
        self._usage[key] = entry
        self.save()

    def use_count(self, key: str) -> int:
        entry = self._usage.get(key)
        return int(entry.get("count", 0)) if isinstance(entry, dict) else 0

    def usage_counts(self) -> dict[str, int]:
        return {k: self.use_count(k) for k in self._usage}

    def most_used(self) -> list[str]:
        """Keys ordered by use count (desc), then most recently used."""
        entries = [
            (self.use_count(k), str(v.get("last_used", "")), k)
            for k, v in self._usage.items()
            if isinstance(v, dict) and self.use_count(k) > 0
        ]
        entries.sort(reverse=True)
        return [k for _, _, k in entries]

    # --- UI ---

    def get_ui(self, name: str, default: Any = None) -> Any:
        return self._ui.get(name, default)

    def set_ui(self, name: str, value: Any, save: bool = True) -> None:
        self._ui[name] = value
        if save:
            self.save()

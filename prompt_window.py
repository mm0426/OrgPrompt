"""Main prompt selection window with search, favorites, and inline editing.

The window is created once and then hidden/shown (not destroyed/recreated),
so reopening it is instant.
"""

import logging
import os
import re
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

from app_state import AppState
from clipboard import Notifier, copy_with_notification
from prompt_manager import Prompt, PromptManager
from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME

logger = logging.getLogger("orgprompt.prompt_window")

FAVORITES_ID = "__favorites__"
FREQUENT_ID = "__frequent__"
FREQUENT_LIMIT = 5
SEARCH_DEBOUNCE_MS = 150
RELOAD_CHECK_SECONDS = 1.0
DEFAULT_WIDTH, DEFAULT_HEIGHT = 560, 660
MIN_WIDTH, MIN_HEIGHT = 440, 420
DEFAULT_STATUS = "Select a prompt, edit it if you like, then Ok (Ctrl+Enter) to copy"
PREVIEW_LABEL = "Edit / Preview"
PREVIEW_LABEL_EDITED = "Edit / Preview — edited (saved prompt is unchanged)"

_GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


def open_in_editor(path: Path) -> None:
    """Open a file with its default app, falling back to Notepad on Windows."""
    if sys.platform == "win32":
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except OSError:
            subprocess.Popen(["notepad.exe", str(path)])
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(path)])


def _point_on_screen(root: tk.Misc, x: int, y: int) -> bool:
    """True if the screen point is on some monitor."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            monitor = ctypes.windll.user32.MonitorFromPoint(wintypes.POINT(x, y), 0)
            return bool(monitor)
        except Exception:
            pass
    return 0 <= x < root.winfo_screenwidth() and 0 <= y < root.winfo_screenheight()


class PromptWindow:
    """Popup window for selecting prompts."""

    def __init__(
        self,
        prompt_manager: PromptManager,
        on_close: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        state: Optional[AppState] = None,
        notifier: Optional[Notifier] = None,
        on_prompts_changed: Optional[Callable[[], None]] = None,
    ):
        self.prompt_manager = prompt_manager
        self.on_close = on_close
        self.on_quit = on_quit
        self.state = state if state is not None else AppState(persist=False)
        self.notifier = notifier
        self.on_prompts_changed = on_prompts_changed
        self.root: Optional[tk.Toplevel] = None
        self.selected_prompt: Optional[Prompt] = None
        self._loaded_text = ""
        # Tree item id -> Prompt / section id. Item ids are generated, so
        # prompts with duplicate titles never collide.
        self._items: dict[str, Prompt] = {}
        self._sections: dict[str, str] = {}
        self._next_id = 0
        saved = self.state.get_ui("expanded")
        self._expanded: set[str] = (
            set(saved) if isinstance(saved, list) else {FAVORITES_ID, FREQUENT_ID}
        )
        self._search_after_id: Optional[str] = None
        self._last_reload_check = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Show the window (creating it on first use)."""
        if self.root is not None and self.root.winfo_exists():
            if self.root.state() != "withdrawn":
                # Already open: just bring it forward, keep any edits.
                self.bring_to_front()
                return
            if self.prompt_manager.reload_if_changed():
                self._notify_prompts_changed()
            self._update_workflow_button()
        else:
            self.prompt_manager.reload_if_changed()
            self._build()

        self._reset_for_open()
        self.root.deiconify()
        self.bring_to_front()
        self.search_entry.focus_set()

    def bring_to_front(self) -> None:
        """Bring existing window to front if open.

        If the window doesn't exist or has been destroyed, this method
        does nothing (silent no-op).
        """
        if self.root is not None and self.root.winfo_exists():
            try:
                self.root.lift()
                self.root.focus_force()
            except tk.TclError:
                # Window was destroyed or invalid
                pass

    def _close(self) -> None:
        """Hide the window (it is reused next time)."""
        if self.root is None or not self.root.winfo_exists():
            return
        self._save_geometry()
        self.root.withdraw()
        if self.on_close:
            self.on_close()

    def destroy(self) -> None:
        """Destroy the window for good (on app exit)."""
        if self.root is not None and self.root.winfo_exists():
            self._save_geometry()
            self.root.destroy()
        self.root = None

    def _quit_app(self) -> None:
        """Close the window and quit the application."""
        self._close()
        if self.on_quit:
            self.on_quit()

    def _reset_for_open(self) -> None:
        """Fresh state each time the window is opened."""
        self.search_var.set("")
        self._cancel_pending_search()
        self.selected_prompt = None
        self._set_preview_text("")
        self.status_var.set(DEFAULT_STATUS)
        self._refresh_list()
        self.tree.yview_moveto(0)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.root = tk.Toplevel()
        self.root.withdraw()
        self.root.title("OrgPrompt - Select a Prompt")
        self.root.resizable(True, True)
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._apply_initial_geometry()
        self._setup_ui()
        self._bind_events()

    def _apply_initial_geometry(self) -> None:
        """Restore the last size/position if it's still on a monitor."""
        width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT
        saved = self.state.get_ui("geometry")
        match = _GEOMETRY_RE.match(saved) if isinstance(saved, str) else None
        if match:
            w, h, x, y = (int(v) for v in match.groups())
            if w >= MIN_WIDTH and h >= MIN_HEIGHT:
                width, height = w, h
                # Require the title bar to be reachable
                if _point_on_screen(self.root, x + 60, y + 15):
                    self.root.geometry(f"{w}x{h}+{x}+{y}")
                    return
        x = max((self.root.winfo_screenwidth() - width) // 2, 0)
        y = max((self.root.winfo_screenheight() - height) // 2, 0)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _save_geometry(self) -> None:
        try:
            if self.root.state() == "normal":
                self.state.set_ui("geometry", self.root.geometry())
        except tk.TclError:
            pass

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Search row ---
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="🔍").pack(side=tk.LEFT, padx=(0, 5))

        # Workflow Files button (only visible when built-in prompts available)
        self.workflow_btn = ttk.Button(
            search_frame, text="Workflow Files...", command=self._open_workflow_dialog, width=16
        )
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var, font=("Segoe UI", 11)
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._update_workflow_button()
        self.search_var.trace_add("write", self._on_search_change)

        # --- Bottom rows (packed before the expanding middle so they never
        #     get squeezed out when the window is small) ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="New Prompt…", command=self._new_prompt).pack(side=tk.LEFT)
        ttk.Button(
            button_frame, text="Open in Editor", command=self._open_selected_in_editor
        ).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Button(button_frame, text="Exit", command=self._quit_app, width=8).pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ttk.Button(button_frame, text="Cancel", command=self._close, width=8).pack(
            side=tk.RIGHT, padx=(5, 0)
        )
        ttk.Button(button_frame, text="Ok", command=self._select_prompt, width=8).pack(
            side=tk.RIGHT
        )

        self.status_var = tk.StringVar(value=DEFAULT_STATUS)
        ttk.Label(main_frame, textvariable=self.status_var, font=("Segoe UI", 9)).pack(
            side=tk.BOTTOM, fill=tk.X, pady=(5, 0)
        )

        # --- Editable preview ---
        self.preview_frame = ttk.LabelFrame(main_frame, text=PREVIEW_LABEL, padding="5")
        self.preview_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        text_frame = ttk.Frame(self.preview_frame)
        text_frame.pack(fill=tk.X)
        self.preview_text = tk.Text(
            text_frame,
            height=7,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="white",
            undo=True,
            relief=tk.SOLID,
            borderwidth=1,
        )
        preview_scroll = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=self.preview_text.yview
        )
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        preview_buttons = ttk.Frame(self.preview_frame)
        preview_buttons.pack(fill=tk.X, pady=(5, 0))
        self.reset_btn = ttk.Button(
            preview_buttons, text="Reset Edits", command=self._reset_edits, state=tk.DISABLED
        )
        self.reset_btn.pack(side=tk.LEFT)
        self.save_as_btn = ttk.Button(
            preview_buttons, text="Save as New Prompt…", command=self._save_as_new,
            state=tk.DISABLED,
        )
        self.save_as_btn.pack(side=tk.LEFT, padx=(5, 0))

        # --- Prompt tree (fills remaining space) ---
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("category",),
            show="tree headings",
            selectmode="browse"
        )
        self.tree.heading("#0", text="Prompt", anchor=tk.W)
        self.tree.heading("category", text="Category", anchor=tk.W)
        self.tree.column("#0", width=360, minwidth=200)
        self.tree.column("category", width=130, minwidth=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("favorites", font=("Segoe UI", 10, "bold"), foreground="#B8860B")
        self.tree.tag_configure("frequent", font=("Segoe UI", 10, "bold"), foreground="#2E7D32")
        self.tree.tag_configure("builtin", font=("Segoe UI", 10, "bold"), foreground="#2E5A8B")
        self.tree.tag_configure("user", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("prompt", font=("Segoe UI", 10))
        self.tree.tag_configure("ready", font=("Segoe UI", 10))
        self.tree.tag_configure("unavailable", font=("Segoe UI", 10), foreground="#999999")

        self.context_menu = tk.Menu(self.root, tearoff=0)

    def _bind_events(self) -> None:
        """Bind keyboard and mouse events."""
        self.root.bind("<Escape>", lambda e: self._close())
        self.root.bind("<Control-Return>", self._on_ctrl_return)
        self.root.bind("<Control-f>", self._focus_search)
        self.root.bind("<FocusIn>", self._on_focus_in)

        self.search_entry.bind("<Return>", self._on_search_return)
        self.search_entry.bind("<Down>", self._on_search_down)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Return>", self._on_tree_return)
        self.tree.bind("<ButtonRelease-1>", self._on_click)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Up>", self._on_tree_up)
        self.tree.bind("<Right>", lambda e: self._on_tree_left_right(expand=True))
        self.tree.bind("<Left>", lambda e: self._on_tree_left_right(expand=False))

        # Widget-level binding so the Text class binding can't insert a
        # newline before the copy happens.
        self.preview_text.bind("<Control-Return>", self._on_ctrl_return)
        self.preview_text.bind("<<Modified>>", self._on_preview_modified)

    # ------------------------------------------------------------------
    # List building
    # ------------------------------------------------------------------

    def _on_search_change(self, *args) -> None:
        """Debounce: rebuild the list shortly after typing stops."""
        self._cancel_pending_search()
        self._search_after_id = self.root.after(SEARCH_DEBOUNCE_MS, self._refresh_list)

    def _cancel_pending_search(self) -> None:
        if self._search_after_id is not None:
            try:
                self.root.after_cancel(self._search_after_id)
            except tk.TclError:
                pass
            self._search_after_id = None

    def _flush_search(self) -> None:
        """Apply a pending debounced search immediately."""
        if self._search_after_id is not None:
            self._cancel_pending_search()
            self._refresh_list()

    def _refresh_list(self) -> None:
        """Rebuild the tree from the search box and section state."""
        self._search_after_id = None
        self.tree.delete(*self.tree.get_children())
        self._items.clear()
        self._sections.clear()

        query = self.search_var.get().strip()
        if query:
            for prompt in self.prompt_manager.search(query, self.state.usage_counts()):
                self._insert_prompt("", prompt)
        else:
            pinned = self.prompt_manager.get_pinned_prompts()
            if pinned:
                self._insert_section(FAVORITES_ID, "★ Favorites", pinned, "favorites")
            frequent = self._frequent_prompts(exclude={p.key for p in pinned})
            if frequent:
                self._insert_section(FREQUENT_ID, "↻ Frequently Used", frequent, "frequent")
            for category in self.prompt_manager.categories:
                if category == BUILT_IN_CATEGORY_NAME:
                    prompts = self.prompt_manager.get_built_in_prompts()
                    self._insert_section(category, f"⚙ {category}", prompts, "builtin")
                else:
                    prompts = self.prompt_manager.get_prompts_by_category(category)
                    self._insert_section(category, category, prompts, "user")

        self._restore_selection()

    def _insert_section(self, section_id: str, label: str, prompts: list[Prompt], tag: str) -> None:
        expanded = section_id in self._expanded
        iid = f"s{self._next_id}"
        self._next_id += 1
        self._sections[iid] = section_id
        arrow = "▼" if expanded else "▶"
        self.tree.insert(
            "", tk.END, iid=iid,
            text=f"{arrow} {label} ({len(prompts)})",
            tags=("category", tag),
            open=expanded,
        )
        if expanded:
            for prompt in prompts:
                self._insert_prompt(iid, prompt, in_favorites=section_id == FAVORITES_ID)

    def _insert_prompt(self, parent: str, prompt: Prompt, in_favorites: bool = False) -> str:
        is_available, reason = self.prompt_manager.get_availability(prompt)
        text = prompt.title
        if prompt.pinned and not in_favorites:
            text += "  ★"
        if not is_available:
            text += f" ({reason})"
        if parent:
            text = f"  {text}"
        iid = f"p{self._next_id}"
        self._next_id += 1
        self.tree.insert(
            parent, tk.END, iid=iid, text=text,
            values=(prompt.category,),
            tags=("prompt", "ready" if is_available else "unavailable"),
        )
        self._items[iid] = prompt
        return iid

    def _frequent_prompts(self, exclude: set[str]) -> list[Prompt]:
        result: list[Prompt] = []
        for key in self.state.most_used():
            if key in exclude:
                continue
            prompt = self.prompt_manager.find_by_key(key)
            if prompt is not None:
                result.append(prompt)
                if len(result) >= FREQUENT_LIMIT:
                    break
        return result

    def _restore_selection(self) -> None:
        """Re-select the previewed prompt after a rebuild, if it's visible."""
        if self.selected_prompt is None:
            return
        key = self.selected_prompt.key
        for iid, prompt in self._items.items():
            if prompt.key == key:
                # Swap in the freshly loaded object (pinned flag, indexes)
                self.selected_prompt = prompt
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                return

    def _first_prompt_iid(self) -> Optional[str]:
        for iid in self._all_iids():
            if iid in self._items:
                return iid
        return None

    def _all_iids(self) -> list[str]:
        result = []
        for top in self.tree.get_children():
            result.append(top)
            result.extend(self.tree.get_children(top))
        return result

    def _iid_for_section(self, section_id: str) -> Optional[str]:
        return next((i for i, s in self._sections.items() if s == section_id), None)

    def _select_item(self, iid: str) -> None:
        """Select an item and, for prompts, load the preview immediately."""
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)
        prompt = self._items.get(iid)
        if prompt is not None:
            self._load_prompt(prompt)

    def _toggle_section(self, section_id: str, expand: Optional[bool] = None) -> None:
        if expand is None:
            expand = section_id not in self._expanded
        if expand:
            self._expanded.add(section_id)
        else:
            self._expanded.discard(section_id)
        self.state.set_ui("expanded", sorted(self._expanded))
        self._refresh_list()
        iid = self._iid_for_section(section_id)
        if iid is not None:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)

    # ------------------------------------------------------------------
    # Preview / editing
    # ------------------------------------------------------------------

    def _current_text(self) -> str:
        return self.preview_text.get("1.0", "end-1c")

    def _is_dirty(self) -> bool:
        return self.selected_prompt is not None and self._current_text() != self._loaded_text

    def _set_preview_text(self, text: str) -> None:
        self._loaded_text = text
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self.preview_text.edit_reset()
        self.preview_text.edit_modified(False)
        self.preview_text.mark_set(tk.INSERT, "1.0")
        self.preview_text.yview_moveto(0)
        self._update_edit_state()

    def _load_prompt(self, prompt: Prompt) -> None:
        """Load a prompt's stored text into the editable preview."""
        self.selected_prompt = prompt
        self._set_preview_text(prompt.text)
        is_available, reason = self.prompt_manager.get_availability(prompt)
        self.status_var.set(reason if not is_available else DEFAULT_STATUS)

    # Kept for compatibility with older callers/tests.
    _show_preview = _load_prompt

    def _on_preview_modified(self, event=None) -> None:
        if not self.preview_text.edit_modified():
            return
        self.preview_text.edit_modified(False)
        self._update_edit_state()

    def _update_edit_state(self) -> None:
        dirty = self._is_dirty()
        self.preview_frame.configure(text=PREVIEW_LABEL_EDITED if dirty else PREVIEW_LABEL)
        self.reset_btn.configure(state=tk.NORMAL if dirty else tk.DISABLED)
        has_text = bool(self._current_text().strip())
        self.save_as_btn.configure(state=tk.NORMAL if has_text else tk.DISABLED)

    def _reset_edits(self) -> None:
        if self.selected_prompt is not None:
            self._set_preview_text(self._loaded_text)
            self.status_var.set("Edits discarded")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_tree_select(self, event=None) -> None:
        """Selection changed - load the prompt into the preview."""
        selection = self.tree.selection()
        if not selection:
            return
        prompt = self._items.get(selection[0])
        if prompt is None:
            return
        if (
            self.selected_prompt is not None
            and prompt.key == self.selected_prompt.key
            and (self._is_dirty() or prompt.text == self._loaded_text)
        ):
            # Same prompt re-selected (e.g. after a list rebuild): keep any
            # edits; only reload if the stored text changed on disk.
            self.selected_prompt = prompt
            return
        self._load_prompt(prompt)

    def _on_click(self, event) -> None:
        """Toggle a section when its header is clicked."""
        item = self.tree.identify_row(event.y)
        if item in self._sections:
            self._toggle_section(self._sections[item])

    def _on_tree_double_click(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if item in self._items:
            self._select_item(item)
            self._select_prompt()

    def _on_tree_return(self, event=None) -> str:
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            if item in self._sections:
                self._toggle_section(self._sections[item])
            elif item in self._items:
                self._select_prompt()
        return "break"

    def _on_tree_up(self, event=None) -> Optional[str]:
        """Up arrow on the first row moves focus back to the search box."""
        focus = self.tree.focus()
        children = self.tree.get_children()
        if not focus or (children and focus == children[0]):
            self._focus_search()
            return "break"
        return None

    def _on_tree_left_right(self, expand: bool) -> Optional[str]:
        focus = self.tree.focus()
        if focus in self._sections:
            section_id = self._sections[focus]
            if (section_id in self._expanded) != expand:
                self._toggle_section(section_id, expand)
            return "break"
        if focus in self._items and not expand:
            parent = self.tree.parent(focus)
            if parent:
                self.tree.selection_set(parent)
                self.tree.focus(parent)
                self.tree.see(parent)
                return "break"
        return None

    def _focus_search(self, event=None) -> str:
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)
        return "break"

    def _on_search_down(self, event=None) -> str:
        """Down arrow in the search box moves into the results."""
        self._flush_search()
        target = self._first_prompt_iid()
        if target is None:
            children = self.tree.get_children()
            target = children[0] if children else None
        if target is not None:
            self.tree.focus_set()
            self._select_item(target)
        return "break"

    def _on_search_return(self, event=None) -> str:
        """Enter in the search box copies the top match."""
        self._flush_search()
        if self.search_var.get().strip():
            target = self._first_prompt_iid()
            if target is None:
                self.status_var.set("No matching prompts")
                return "break"
            self._select_item(target)
        self._select_prompt()
        return "break"

    def _on_ctrl_return(self, event=None) -> str:
        self._select_prompt()
        return "break"

    def _on_focus_in(self, event=None) -> None:
        """Pick up prompt files edited in an external editor."""
        now = time.monotonic()
        if now - self._last_reload_check < RELOAD_CHECK_SECONDS:
            return
        self._last_reload_check = now
        try:
            if self.prompt_manager.reload_if_changed():
                self._notify_prompts_changed()
                self.status_var.set("Prompts reloaded from disk")
        except Exception:
            logger.exception("Failed to reload prompts")

    def _on_right_click(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.focus_set()
        self._select_item(item)
        menu = self.context_menu
        menu.delete(0, tk.END)

        prompt = self._items.get(item)
        if prompt is not None:
            is_user_prompt = prompt.cat_index >= 0
            menu.add_command(label="Copy", command=self._select_prompt)
            if is_user_prompt:
                menu.add_command(
                    label="Remove from Favorites" if prompt.pinned else "Add to Favorites",
                    command=lambda: self._toggle_pin(prompt),
                )
            menu.add_command(label="Open in Editor", command=lambda: self._open_in_editor(prompt))
            menu.add_separator()
            menu.add_command(
                label="New Prompt…",
                command=lambda: self._new_prompt(category=prompt.category if is_user_prompt else ""),
            )
        else:
            section_id = self._sections.get(item, "")
            if section_id in self.prompt_manager.user_categories:
                menu.add_command(
                    label=f"New Prompt in '{section_id}'…",
                    command=lambda: self._new_prompt(category=section_id),
                )
            else:
                return
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _select_prompt(self) -> None:
        """Copy the (possibly edited) preview text to the clipboard."""
        prompt = self.selected_prompt
        if prompt is None:
            self.status_var.set("Select a prompt first")
            return

        is_available, reason = self.prompt_manager.get_availability(prompt)
        if not is_available:
            self.status_var.set(f"Cannot copy: {reason}")
            return

        text = self._current_text()
        if not text.strip():
            self.status_var.set("Nothing to copy")
            return

        edited = text != self._loaded_text
        settings = self.prompt_manager.settings
        message = f"Copied: {prompt.title}" + (" (edited)" if edited else "")
        if copy_with_notification(
            text,
            settings.get("show_notifications", True),
            notifier=self.notifier,
            message=message,
        ):
            self.state.record_use(prompt.key)
            self.status_var.set("✓ Copied to clipboard!")
            if settings.get("auto_close", True):
                self.root.after(300, self._close)
        else:
            self.status_var.set("Copy failed — see log for details")

    def _toggle_pin(self, prompt: Prompt) -> None:
        pinned = not prompt.pinned
        if self.prompt_manager.set_pinned(prompt, pinned):
            if pinned:
                self._expanded.add(FAVORITES_ID)
            self._notify_prompts_changed()
            self.status_var.set(
                f"Added '{prompt.title}' to Favorites" if pinned
                else f"Removed '{prompt.title}' from Favorites"
            )
        else:
            self.status_var.set("Couldn't update Favorites — see log for details")

    def _open_selected_in_editor(self) -> None:
        self._open_in_editor(self.selected_prompt)

    def _open_in_editor(self, prompt: Optional[Prompt]) -> None:
        path = self.prompt_manager.get_source_path(prompt)
        try:
            open_in_editor(path)
            self.status_var.set(f"Opened {path.name} — changes load when you return here")
        except Exception:
            logger.exception("Failed to open %s", path)
            self.status_var.set(f"Couldn't open {path.name}")

    def _new_prompt(self, category: str = "", title: str = "", text: str = "") -> None:
        from new_prompt_dialog import NewPromptDialog

        NewPromptDialog(
            parent=self.root,
            prompt_manager=self.prompt_manager,
            on_saved=self._on_prompt_added,
            title=title,
            category=category,
            text=text,
        ).show()

    def _save_as_new(self) -> None:
        text = self._current_text()
        if not text.strip():
            return
        prompt = self.selected_prompt
        category = ""
        title = ""
        if prompt is not None:
            title = f"{prompt.title} (copy)"
            if prompt.category != BUILT_IN_CATEGORY_NAME:
                category = prompt.category
        self._new_prompt(category=category, title=title, text=text)

    def _on_prompt_added(self, prompt: Prompt) -> None:
        self._expanded.add(prompt.category)
        self.state.set_ui("expanded", sorted(self._expanded))
        self.search_var.set("")
        self._cancel_pending_search()
        self.selected_prompt = prompt
        self._notify_prompts_changed()
        for iid, item in self._items.items():
            if item.key == prompt.key:
                self._select_item(iid)
                break
        self.status_var.set(f"Saved new prompt '{prompt.title}'")

    def _notify_prompts_changed(self) -> None:
        """Refresh after prompts.json changed and tell the app (tray menu)."""
        self._update_workflow_button()
        self._refresh_list()
        if self.on_prompts_changed is not None:
            try:
                self.on_prompts_changed()
            except Exception:
                logger.exception("on_prompts_changed callback failed")

    def _update_workflow_button(self) -> None:
        available = self.prompt_manager.get_built_in_category_name() is not None
        packed = self.workflow_btn.winfo_manager() == "pack"
        if available and not packed:
            self.workflow_btn.pack(side=tk.RIGHT, padx=(5, 0), before=self.search_entry)
        elif not available and packed:
            self.workflow_btn.pack_forget()

    def _open_workflow_dialog(self) -> None:
        """Open the workflow files configuration dialog."""
        from workflow_files_dialog import WorkflowFilesDialog

        WorkflowFilesDialog(
            parent=self.root,
            prompt_manager=self.prompt_manager,
            on_save=self._on_workflow_settings_saved
        ).show()

    def _on_workflow_settings_saved(self) -> None:
        """Called after workflow settings are saved."""
        self._expanded.add(BUILT_IN_CATEGORY_NAME)
        self._notify_prompts_changed()

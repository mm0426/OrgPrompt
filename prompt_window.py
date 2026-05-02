"""Main prompt selection window with search and categories."""

import platform
import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk
from typing import Optional, Callable
from prompt_manager import Prompt, PromptManager
from workflow_prompt_templates import BUILT_IN_CATEGORY_NAME
from clipboard import copy_with_notification


def _get_font_family(style: str = "ui") -> str:
    """Return a suitable font family for the current platform."""
    system = platform.system()
    if style == "mono":
        return {
            "Windows": "Consolas",
            "Linux": "monospace",
        }.get(system, "monospace")
    return {
        "Windows": "Segoe UI",
        "Linux": "sans-serif",
    }.get(system, "sans-serif")


class PromptWindow:
    """Popup window for selecting prompts."""

    def __init__(
        self,
        prompt_manager: PromptManager,
        on_close: Optional[Callable] = None,
        on_quit: Optional[Callable] = None
    ):
        self.prompt_manager = prompt_manager
        self.on_close = on_close
        self.on_quit = on_quit
        self.root: Optional[tk.Toplevel] = None
        self.selected_prompt: Optional[Prompt] = None
        self._expanded_categories: set[str] = set()
        self._all_expanded = True  # Start with all expanded

    def show(self) -> None:
        """Show the prompt selection window."""
        if self.root is not None and self.root.winfo_exists():
            self.bring_to_front()
            return

        self.root = tk.Toplevel()
        self.root.title("OrgPrompt - Select a Prompt")
        self.root.resizable(True, True)

        self._setup_ui()
        self._bind_events()

        # Expand all categories initially
        self._expanded_categories = set(self.prompt_manager.categories)
        self._refresh_list()

        # Center window on screen
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"+{x}+{y}")

        self.root.focus_force()

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

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        # Configure styles
        style = ttk.Style()
        ui_font = _get_font_family("ui")
        tree_font = tkFont.Font(family=ui_font, size=10)
        rowheight = tree_font.metrics("linespace") + 6
        style.configure("Treeview", font=tree_font, rowheight=rowheight)
        style.configure("Treeview.Heading", font=(ui_font, 10, "bold"))

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        search_label = ttk.Label(search_frame, text="🔍")
        search_label.pack(side=tk.LEFT, padx=(0, 5))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=(ui_font, 11))
        self.search_entry.pack(fill=tk.X, expand=True)
        self.search_entry.focus_set()

        # Workflow Files button (only visible when built-in prompts available)
        self.workflow_btn = ttk.Button(
            search_frame, text="Workflow Files...", command=self._open_workflow_dialog, width=16
        )
        if self.prompt_manager.get_built_in_category_name():
            self.workflow_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Prompt list with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("title", "category"),
            show="tree headings",
            selectmode="browse",
            height=18
        )
        self.tree.heading("#0", text="Prompt", anchor=tk.W)
        self.tree.heading("category", text="Category", anchor=tk.W)
        self.tree.column("#0", width=350, minwidth=200)
        self.tree.column("category", width=130, minwidth=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="5")
        preview_frame.pack(fill=tk.X, pady=(10, 0))

        self.preview_text = tk.Text(
            preview_frame,
            height=6,
            wrap=tk.WORD,
            font=(_get_font_family("mono"), 9),
            state=tk.DISABLED,
            bg="#f5f5f5"
        )
        self.preview_text.pack(fill=tk.X)

        # Status bar
        self.status_var = tk.StringVar(value="Select a prompt and click Ok to copy")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, font=(ui_font, 9))
        status_bar.pack(fill=tk.X, pady=(5, 0))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        exit_button = ttk.Button(button_frame, text="Exit", command=self._quit_app, width=10)
        exit_button.pack(side=tk.RIGHT, padx=(5, 0))

        cancel_button = ttk.Button(button_frame, text="Cancel", command=self._close, width=10)
        cancel_button.pack(side=tk.RIGHT, padx=(5, 0))

        ok_button = ttk.Button(button_frame, text="Ok", command=self._select_prompt, width=10)
        ok_button.pack(side=tk.RIGHT)

    def _bind_events(self) -> None:
        """Bind keyboard and mouse events."""
        self.root.bind("<Escape>", lambda e: self._close())
        self.root.bind("<Return>", lambda e: self._select_prompt())
        self.root.bind("<Double-Button-1>", lambda e: self._select_prompt())

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self._select_prompt())
        self.tree.bind("<Return>", lambda e: self._select_prompt())
        self.tree.bind("<ButtonRelease-1>", self._on_click)

        # Close when window loses focus (optional, can be toggled)
        # self.root.bind("<FocusOut>", lambda e: self._close())

    def _on_search_change(self, *args) -> None:
        """Handle search text change."""
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the prompt list based on search and category state."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = self.search_var.get().strip()
        settings = self.prompt_manager.settings

        if query:
            # Search mode: show matching prompts flat
            prompts = self.prompt_manager.search(query)
            for prompt in prompts:
                tag = "prompt"
                if prompt.category == BUILT_IN_CATEGORY_NAME:
                    builtin_prompts = self.prompt_manager.get_built_in_prompts()
                    for idx, bp in enumerate(builtin_prompts):
                        if bp.title == prompt.title:
                            _, reason = self.prompt_manager.get_prompt_availability_for(idx)
                            if reason:
                                tag = "unavailable"
                            break
                self.tree.insert(
                    "",
                    tk.END,
                    text=prompt.title,
                    values=(prompt.category,),
                    tags=(tag,),
                    iid=f"prompt::{prompt.category}::{prompt.title}"
                )
        else:
            # Category mode: show categorized
            for category in self.prompt_manager.categories:
                count = self.prompt_manager.get_category_prompt_count(category)
                is_expanded = category in self._expanded_categories

                cat_id = f"cat::{category}"
                is_builtin = category == BUILT_IN_CATEGORY_NAME
                icon = "⚙ " if is_builtin else ""  # gear icon
                cat_tag = "builtin" if is_builtin else "user"
                self.tree.insert(
                    "",
                    tk.END,
                    text=f"{icon}{'▼' if is_expanded else '▶'} {category} ({count})",
                    tags=("category", cat_tag),
                    open=is_expanded,
                    iid=cat_id
                )

                if is_expanded:
                    if is_builtin:
                        # Built-in prompts: show availability state
                        builtin_prompts = self.prompt_manager.get_built_in_prompts()
                        for idx, prompt in enumerate(builtin_prompts):
                            is_available, reason = self.prompt_manager.get_prompt_availability_for(idx)
                            status = "" if is_available else f" ({reason})"
                            prompt_tag = "unavailable" if not is_available else "ready"
                            self.tree.insert(
                                cat_id,
                                tk.END,
                                text=f"  {prompt.title}{status}",
                                values=(category,),
                                tags=("prompt", prompt_tag),
                                iid=f"prompt::{category}::{prompt.title}"
                            )
                    else:
                        # User prompts: standard display
                        for prompt in self.prompt_manager.get_prompts_by_category(category):
                            self.tree.insert(
                                cat_id,
                                tk.END,
                                text=f"  {prompt.title}",
                                values=(category,),
                                tags=("prompt",),
                                iid=f"prompt::{category}::{prompt.title}"
                            )

        # Configure tag colors and fonts
        tag_font = _get_font_family("ui")
        self.tree.tag_configure("builtin", font=(tag_font, 10, "bold"), foreground="#2E5A8B")
        self.tree.tag_configure("user", font=(tag_font, 10, "bold"))
        self.tree.tag_configure("prompt", font=(tag_font, 10))
        self.tree.tag_configure("ready", font=(tag_font, 10))
        self.tree.tag_configure("unavailable", font=(tag_font, 10), foreground="#999999")

    def _on_tree_select(self, event) -> None:
        """Handle tree selection change - show preview."""
        selection = self.tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if item_id.startswith("prompt::"):
            # Prompt selected - show preview
            parts = item_id.split("::", 2)
            if len(parts) >= 3:
                category, title = parts[1], parts[2]

                # Look up the prompt — built-in category uses a different source
                if category == BUILT_IN_CATEGORY_NAME:
                    prompts = [
                        p for p in self.prompt_manager.get_built_in_prompts()
                        if p.title == title
                    ]
                else:
                    prompts = [
                        p for p in self.prompt_manager.get_prompts_by_category(category)
                        if p.title == title
                    ]

                if prompts:
                    self._show_preview(prompts[0])

                    # Show availability reason in status bar for unavailable built-in prompts
                    if category == BUILT_IN_CATEGORY_NAME:
                        builtin_prompts = self.prompt_manager.get_built_in_prompts()
                        for idx, bp in enumerate(builtin_prompts):
                            if bp.title == title:
                                is_available, reason = self.prompt_manager.get_prompt_availability_for(idx)
                                if not is_available:
                                    self.status_var.set(reason)
                                break

    def _on_click(self, event) -> None:
        """Handle click on tree item."""
        # Get item at click position
        item = self.tree.identify_row(event.y)
        if not item:
            return

        if item.startswith("cat::"):
            # Category clicked - toggle expansion
            category = item.replace("cat::", "")
            if category in self._expanded_categories:
                self._expanded_categories.remove(category)
            else:
                self._expanded_categories.add(category)
            self._refresh_list()

    def _show_preview(self, prompt: Prompt) -> None:
        """Show prompt preview."""
        self.selected_prompt = prompt
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", prompt.text)
        self.preview_text.config(state=tk.DISABLED)

    def _select_prompt(self) -> None:
        """Copy selected prompt to clipboard and close."""
        selection = self.tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if not item_id.startswith("prompt::"):
            return

        parts = item_id.split("::", 2)
        if len(parts) < 3:
            return

        category, title = parts[1], parts[2]

        # Look up the prompt — built-in category uses a different source
        if category == BUILT_IN_CATEGORY_NAME:
            prompts = [
                p for p in self.prompt_manager.get_built_in_prompts()
                if p.title == title
            ]
        else:
            prompts = [
                p for p in self.prompt_manager.get_prompts_by_category(category)
                if p.title == title
            ]

        if not prompts:
            return

        # Check availability for built-in prompts — block copy if unavailable
        if category == BUILT_IN_CATEGORY_NAME:
            builtin_prompts = self.prompt_manager.get_built_in_prompts()
            for idx, bp in enumerate(builtin_prompts):
                if bp.title == title:
                    is_available, reason = self.prompt_manager.get_prompt_availability_for(idx)
                    if not is_available:
                        self.status_var.set(f"Cannot copy: {reason}")
                        return
                    break

        prompt = prompts[0]
        settings = self.prompt_manager.settings

        # Copy to clipboard
        if copy_with_notification(prompt.text, settings.get("show_notifications", True)):
            self.status_var.set("✓ Copied to clipboard!")

            # Auto-close if enabled
            if settings.get("auto_close", True):
                self.root.after(300, self._close)

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
        # Re-expand categories to include any newly available prompts
        self._expanded_categories = set(self.prompt_manager.categories)
        self._refresh_list()

    def _close(self) -> None:
        """Close the window."""
        if self.root:
            self.root.destroy()
            self.root = None
            if self.on_close:
                self.on_close()

    def _quit_app(self) -> None:
        """Close the window and quit the application."""
        self._close()
        if self.on_quit:
            self.on_quit()

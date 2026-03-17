"""Main prompt selection window with search and categories."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from prompt_manager import Prompt, PromptManager
from clipboard import copy_with_notification


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
        self.root.geometry("450x550")
        self.root.resizable(True, True)

        # Center window on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 450) // 2
        y = (self.root.winfo_screenheight() - 550) // 2
        self.root.geometry(f"+{x}+{y}")

        self._setup_ui()
        self._bind_events()

        # Expand all categories initially
        self._expanded_categories = set(self.prompt_manager.categories)
        self._refresh_list()

        self.root.focus_force()
        self.root.wait_window()

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
        style.configure("Treeview", font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

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
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 11))
        self.search_entry.pack(fill=tk.X, expand=True)
        self.search_entry.focus_set()

        # Prompt list with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("title", "category"),
            show="tree headings",
            selectmode="browse"
        )
        self.tree.heading("#0", text="Prompt", anchor=tk.W)
        self.tree.heading("category", text="Category", anchor=tk.W)
        self.tree.column("#0", width=300, minwidth=200)
        self.tree.column("category", width=100, minwidth=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="5")
        preview_frame.pack(fill=tk.X, pady=(10, 0))

        self.preview_text = tk.Text(
            preview_frame,
            height=4,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED,
            bg="#f5f5f5"
        )
        self.preview_text.pack(fill=tk.X)

        # Status bar
        self.status_var = tk.StringVar(value="Select a prompt and click Ok to copy")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, font=("Segoe UI", 9))
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
                self.tree.insert(
                    "",
                    tk.END,
                    text=prompt.title,
                    values=(prompt.category,),
                    tags=("prompt",),
                    iid=f"prompt::{prompt.category}::{prompt.title}"
                )
        else:
            # Category mode: show categorized
            for category in self.prompt_manager.categories:
                count = self.prompt_manager.get_category_prompt_count(category)
                is_expanded = category in self._expanded_categories

                cat_id = f"cat::{category}"
                self.tree.insert(
                    "",
                    tk.END,
                    text=f"{'▼' if is_expanded else '▶'} {category} ({count})",
                    tags=("category",),
                    open=is_expanded,
                    iid=cat_id
                )

                if is_expanded:
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
        self.tree.tag_configure("category", font=("Segoe UI", 10, "bold"))
        self.tree.tag_configure("prompt", font=("Segoe UI", 10))

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
                prompts = [p for p in self.prompt_manager.get_prompts_by_category(category) if p.title == title]
                if prompts:
                    self._show_preview(prompts[0])

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
        prompts = [p for p in self.prompt_manager.get_prompts_by_category(category) if p.title == title]
        if not prompts:
            return

        prompt = prompts[0]
        settings = self.prompt_manager.settings

        # Copy to clipboard
        if copy_with_notification(prompt.text, settings.get("show_notifications", True)):
            self.status_var.set("✓ Copied to clipboard!")

            # Auto-close if enabled
            if settings.get("auto_close", True):
                self.root.after(300, self._close)

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

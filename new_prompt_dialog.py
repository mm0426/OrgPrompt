"""Dialog for creating a new prompt (also used by "Save as New Prompt")."""

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from prompt_manager import Prompt, PromptManager

logger = logging.getLogger("orgprompt.new_prompt_dialog")


class NewPromptDialog:
    """Modal dialog: title, category, and text for a new prompt.

    The prompt is saved as ``prompts/<category>/<title>.md`` and referenced
    from prompts.json, matching how existing prompts are stored.
    """

    def __init__(
        self,
        parent: tk.Misc,
        prompt_manager: PromptManager,
        on_saved: Optional[Callable[[Prompt], None]] = None,
        title: str = "",
        category: str = "",
        text: str = "",
    ):
        self.parent = parent
        self.prompt_manager = prompt_manager
        self.on_saved = on_saved
        self.initial_title = title
        self.initial_category = category
        self.initial_text = text
        self.dialog: Optional[tk.Toplevel] = None

    def show(self) -> None:
        self._build()
        self.dialog.grab_set()
        self.title_entry.focus_set()
        self.title_entry.select_range(0, tk.END)

    def _build(self) -> None:
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("New Prompt")
        self.dialog.transient(self.parent)
        self.dialog.minsize(420, 360)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        ttk.Label(frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.title_var = tk.StringVar(value=self.initial_title)
        self.title_entry = ttk.Entry(frame, textvariable=self.title_var)
        self.title_entry.grid(row=0, column=1, sticky=tk.EW, pady=(0, 5))

        ttk.Label(frame, text="Category:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.category_var = tk.StringVar(value=self.initial_category)
        self.category_combo = ttk.Combobox(
            frame,
            textvariable=self.category_var,
            values=self.prompt_manager.user_categories,
        )
        self.category_combo.grid(row=1, column=1, sticky=tk.EW, pady=(0, 5))

        ttk.Label(frame, text="Prompt text:").grid(row=2, column=0, columnspan=2, sticky=tk.W)
        text_frame = ttk.Frame(frame)
        text_frame.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
        self.text = tk.Text(
            text_frame, wrap=tk.WORD, font=("Consolas", 9), undo=True, height=14,
            relief=tk.SOLID, borderwidth=1,
        )
        scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.insert("1.0", self.initial_text)
        self.text.edit_reset()

        ttk.Label(
            frame,
            text="Type a new category name to create one. Saved as a .md file under prompts/.",
            font=("Segoe UI", 8),
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(10, 0))
        ttk.Button(buttons, text="Save", command=self._on_save, width=10).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=self._on_cancel, width=10).pack(
            side=tk.LEFT, padx=(5, 0)
        )

        self.dialog.bind("<Escape>", lambda e: self._on_cancel())
        self.dialog.bind("<Control-Return>", self._on_ctrl_return)
        self.text.bind("<Control-Return>", self._on_ctrl_return)

        self._center_on_parent(560, 480)

    def _center_on_parent(self, width: int, height: int) -> None:
        try:
            self.parent.update_idletasks()
            px, py = self.parent.winfo_rootx(), self.parent.winfo_rooty()
            pw, ph = self.parent.winfo_width(), self.parent.winfo_height()
            x = px + max((pw - width) // 2, 0)
            y = py + max((ph - height) // 2, 0)
            self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        except tk.TclError:
            self.dialog.geometry(f"{width}x{height}")

    def _on_ctrl_return(self, event=None) -> str:
        self._on_save()
        return "break"

    def _on_save(self) -> None:
        title = self.title_var.get()
        category = self.category_var.get()
        text = self.text.get("1.0", "end-1c")
        try:
            prompt = self.prompt_manager.add_prompt(category, title, text)
        except ValueError as e:
            messagebox.showwarning("New Prompt", str(e), parent=self.dialog)
            return
        except Exception as e:
            logger.exception("Failed to save new prompt")
            messagebox.showerror("New Prompt", f"Couldn't save the prompt:\n\n{e}", parent=self.dialog)
            return
        self._destroy()
        if self.on_saved is not None:
            self.on_saved(prompt)

    def _on_cancel(self) -> None:
        self._destroy()

    def _destroy(self) -> None:
        if self.dialog is not None:
            try:
                self.dialog.grab_release()
                self.dialog.destroy()
            except tk.TclError:
                pass
            self.dialog = None

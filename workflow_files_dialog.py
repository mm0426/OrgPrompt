"""Modal dialog for configuring workflow file paths."""

import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from typing import Optional, Callable

from prompt_manager import PromptManager

import logging

logger = logging.getLogger(__name__)


class WorkflowFilesDialog:
    """Modal dialog for configuring workflow file paths."""

    def __init__(
        self,
        parent: tk.Widget,
        prompt_manager: PromptManager,
        on_save: Optional[Callable] = None,
    ):
        self.prompt_manager = prompt_manager
        self.on_save = on_save
        self.dialog: Optional[tk.Toplevel] = None
        self.design_spec_var: tk.StringVar = tk.StringVar()
        self.questions_file_var: tk.StringVar = tk.StringVar()
        self.parent = parent

    def show(self) -> None:
        """Open the dialog modally."""
        try:
            self._build_dialog()
            self._populate_fields()
            self._center_on_parent()
            self.dialog.grab_set()
            self.dialog.focus_force()
            self.dialog.wait_window()
        except tk.TclError:
            logger.exception("Failed to open workflow files dialog")

    def _build_dialog(self) -> None:
        """Create and layout the dialog widgets."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Configure Workflow File Paths")
        self.dialog.minsize(400, 250)
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Bind Escape to cancel
        self.dialog.bind("<Escape>", lambda _event: self._on_cancel())

        outer = ttk.Frame(self.dialog, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        # --- Design spec path ---
        ttk.Label(outer, text="Design spec path:").pack(anchor=tk.W)

        design_row = ttk.Frame(outer)
        design_row.pack(fill=tk.X, pady=(0, 8))

        self.design_spec_entry = ttk.Entry(
            design_row, textvariable=self.design_spec_var
        )
        self.design_spec_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        ttk.Button(
            design_row, text="Browse...", command=self._browse_design_spec
        ).pack(side=tk.RIGHT)

        # --- Questions file path ---
        ttk.Label(outer, text="Questions file path:").pack(anchor=tk.W)

        questions_row = ttk.Frame(outer)
        questions_row.pack(fill=tk.X, pady=(0, 4))

        self.questions_entry = ttk.Entry(
            questions_row, textvariable=self.questions_file_var
        )
        self.questions_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        ttk.Button(
            questions_row, text="Browse...", command=self._browse_questions
        ).pack(side=tk.RIGHT)

        # --- Validation / warning label ---
        self.message_var: tk.StringVar = tk.StringVar()
        self.message_label = ttk.Label(outer, textvariable=self.message_var)
        self.message_label.pack(anchor=tk.W, pady=(4, 4))

        # --- Clear questions path ---
        ttk.Button(
            outer, text="Clear Questions Path", command=self._clear_questions
        ).pack(anchor=tk.W, pady=(4, 8))

        # --- Save / Cancel buttons ---
        button_row = ttk.Frame(outer)
        button_row.pack(side=tk.BOTTOM, pady=(4, 0))

        ttk.Button(button_row, text="Save", command=self._on_save).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(button_row, text="Cancel", command=self._on_cancel).pack(
            side=tk.LEFT
        )

        # Focus the design spec entry
        self.design_spec_entry.focus_set()

    def _populate_fields(self) -> None:
        """Pre-populate fields from prompt_manager."""
        paths = self.prompt_manager.get_workflow_file_paths()
        self.design_spec_var.set(paths.get("design_spec_path", ""))
        self.questions_file_var.set(paths.get("questions_file_path", ""))

    def _center_on_parent(self) -> None:
        """Position the dialog centered on the parent window."""
        self.dialog.update_idletasks()
        dialog_w = self.dialog.winfo_width()
        dialog_h = self.dialog.winfo_height()

        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()

        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2

        self.dialog.geometry(f"+{x}+{y}")

    # --- Browse helpers ---

    def _browse_design_spec(self) -> None:
        """Open file picker for the design spec path."""
        initial_dir = self._initial_dir_for(self.design_spec_var.get())
        filepath = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select Design Spec File",
            initialdir=initial_dir,
        )
        if filepath:
            self.design_spec_var.set(filepath)

    def _browse_questions(self) -> None:
        """Open file picker for the questions file path."""
        initial_dir = self._initial_dir_for(self.questions_file_var.get())
        filepath = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select Questions File",
            initialdir=initial_dir,
        )
        if filepath:
            self.questions_file_var.set(filepath)

    @staticmethod
    def _initial_dir_for(path_value: str) -> str:
        """Determine the starting directory for a file picker.

        Returns the parent directory of *path_value* when it exists,
        otherwise the user's home directory.
        """
        if path_value:
            parent = str(Path(path_value).parent)
            if Path(parent).is_dir():
                return parent
        return str(Path.home())

    # --- Validation ---

    def _validate(self) -> bool:
        """Check inputs and update the message label.

        Returns True when saving should proceed.
        """
        design_spec = self.design_spec_var.get().strip()
        questions = self.questions_file_var.get().strip()

        if not design_spec:
            self.message_var.set("Design spec path is required")
            self.message_label.configure(foreground="red")
            return False

        warnings: list[str] = []

        if not Path(design_spec).exists():
            warnings.append("Design spec file does not exist")

        if questions and not Path(questions).exists():
            warnings.append("Questions file does not exist")

        if warnings:
            self.message_var.set("; ".join(warnings))
            self.message_label.configure(foreground="orange")
        else:
            self.message_var.set("")

        return True

    # --- Actions ---

    def _on_save(self) -> None:
        """Validate and persist the file paths."""
        if not self._validate():
            return

        design_spec = self.design_spec_var.get().strip()
        questions = self.questions_file_var.get().strip()

        success = self.prompt_manager.set_workflow_file_paths(design_spec, questions)

        if not success:
            self.message_var.set("Failed to save settings")
            self.message_label.configure(foreground="red")
            return

        if self.on_save is not None:
            self.on_save()

        self._destroy_dialog()

    def _clear_questions(self) -> None:
        """Clear the questions path and save immediately."""
        design_spec = self.design_spec_var.get().strip()

        self.questions_file_var.set("")

        success = self.prompt_manager.set_workflow_file_paths(design_spec, "")

        if not success:
            self.message_var.set("Failed to save settings")
            self.message_label.configure(foreground="red")
            return

        # Clear any previous messages
        self.message_var.set("")

        if self.on_save is not None:
            self.on_save()

    def _on_cancel(self) -> None:
        """Close the dialog without saving."""
        self._destroy_dialog()

    def _destroy_dialog(self) -> None:
        """Safely destroy the dialog window."""
        if self.dialog is not None:
            try:
                self.dialog.grab_release()
                self.dialog.destroy()
            except tk.TclError:
                pass
            self.dialog = None

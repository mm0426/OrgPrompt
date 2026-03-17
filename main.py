"""OrgPrompt - System tray AI prompt utility.

A Windows system tray application that provides quick access to a categorized
library of AI prompts with search functionality.
"""

import tkinter as tk

from prompt_manager import PromptManager
from prompt_window import PromptWindow
from single_instance import SingleInstance
from tray_manager import TrayManager


class OrgPromptApp:
    """Main application class."""

    def __init__(self):
        # Create hidden root window to prevent "tk" window from appearing
        self.root = tk.Tk()
        self.root.withdraw()

        self.prompt_manager = PromptManager()
        self.tray_manager = TrayManager(
            on_click=self.show_prompt_window,
            on_quit=self.quit
        )
        self.prompt_window = None
        self.running = True

    def show_prompt_window(self) -> None:
        """Show the prompt selection window.

        Thread-safe: Can be called from any thread (e.g., pystray callback).
        """
        # Check if window already exists and bring to front
        window = self.prompt_window
        if window is not None and window.root is not None and window.root.winfo_exists():
            # Use after() to marshal to main thread (Tkinter is not thread-safe)
            window.root.after(0, window.bring_to_front)
            return

        # Reload prompts in case file was edited
        self.prompt_manager.reload()

        # Create and show window in main thread
        self.prompt_window = PromptWindow(
            prompt_manager=self.prompt_manager,
            on_close=self._on_window_close,
            on_quit=self.quit
        )
        self.prompt_window.show()

    def _on_window_close(self) -> None:
        """Handle window close."""
        self.prompt_window = None

    def quit(self) -> None:
        """Quit the application."""
        self.running = False
        self.tray_manager.stop()

    def run(self) -> None:
        """Run the application."""
        print("OrgPrompt started. Click the tray icon to select a prompt.")
        print("Right-click and select 'Quit' to exit.")

        # Run tray icon (this blocks)
        self.tray_manager.start()


def main():
    """Entry point."""
    # Ensure only one instance runs
    lock = SingleInstance("orgprompt")
    if not lock.acquire():
        print("OrgPrompt is already running.")
        return

    try:
        app = OrgPromptApp()
        app.run()
    finally:
        lock.release()


if __name__ == "__main__":
    main()

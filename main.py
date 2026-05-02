"""OrgPrompt - System tray AI prompt utility.

A Windows system tray application that provides quick access to a categorized
library of AI prompts with search functionality.
"""

import logging
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from logging_config import LogMessages, setup_logging
from prompt_manager import PromptManager
from prompt_window import PromptWindow
from single_instance import SingleInstance
from tray_manager import TrayManager

# Global logger instance
logger: Optional[logging.Logger] = None


def show_error_message(title: str, message: str) -> None:
    """Show an error message to the user.

    This function attempts to show a GUI error message. If that fails
    (e.g., in pythonw.exe without a display), it logs the error instead.

    Args:
        title: Error message title
        message: Error message content
    """
    root = None
    try:
        # Try to show a message box using tkinter
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
    except Exception as e:
        # If message box fails, just log it
        if logger:
            logger.error(f"Failed to show error message: {e}")
    finally:
        # Always clean up the root window to prevent resource leaks
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


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
        All Tk operations are marshaled to the main thread via root.after().
        """
        if not self.running:
            return
        try:
            self.root.after(0, self._show_prompt_window_main_thread)
        except tk.TclError:
            pass  # Root already destroyed during shutdown

    def _show_prompt_window_main_thread(self) -> None:
        """Show the prompt window — must run on the Tk main thread."""
        if logger:
            logger.info(LogMessages.MSG_WINDOW_SHOWING)

        # Check if window already exists and bring to front
        window = self.prompt_window
        if window is not None and window.root is not None and window.root.winfo_exists():
            window.bring_to_front()
            return

        # Reload prompts in case file was edited
        self.prompt_manager.reload()

        # Create and show window
        self.prompt_window = PromptWindow(
            prompt_manager=self.prompt_manager,
            on_close=self._on_window_close,
            on_quit=self.quit
        )
        self.prompt_window.show()

    def _on_window_close(self) -> None:
        """Handle window close."""
        self.prompt_window = None
        if logger:
            logger.info(LogMessages.MSG_WINDOW_CLOSED)

    def quit(self) -> None:
        """Quit the application.

        Thread-safe: Can be called from any thread.
        """
        self.running = False
        # Schedule Tk cleanup on the main thread, then stop the mainloop
        try:
            self.root.after(0, self._quit_main_thread)
        except tk.TclError:
            pass  # Root already destroyed during shutdown

    def _quit_main_thread(self) -> None:
        """Perform cleanup on the Tk main thread and exit mainloop."""
        self.tray_manager.stop()
        self.root.destroy()

    def run(self) -> None:
        """Run the application.

        Starts pystray in a daemon thread and runs the Tk mainloop on the
        main thread, ensuring Tk events are always processed reliably.
        """
        if logger:
            logger.info(LogMessages.MSG_TRAY_STARTING)

        # Start tray icon in a daemon thread so it doesn't block the main thread
        tray_thread = threading.Thread(target=self.tray_manager.start, daemon=True)
        tray_thread.start()

        # Run Tk mainloop on the main thread — this blocks until root.destroy()
        self.root.mainloop()

        if logger:
            logger.info(LogMessages.MSG_TRAY_STOPPED)


def main() -> int:
    """Entry point for the application.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    global logger

    # Setup logging first - this works with pythonw.exe
    try:
        logger = setup_logging()
        logger.info(LogMessages.MSG_STARTUP)
        logger.debug("Log file: %TEMP%\\orgprompt\\orgprompt.log")
    except Exception as e:
        # If logging setup fails, try to print to stderr (may not work with pythonw)
        print(f"Failed to setup logging: {e}", file=sys.stderr)
        # Continue anyway - we'll show a GUI error if things fail

    # Ensure only one instance runs
    lock = SingleInstance("orgprompt")
    if not lock.acquire():
        if logger:
            logger.info(LogMessages.MSG_INSTANCE_LOCK_FAILED)
        else:
            print("OrgPrompt is already running.", file=sys.stderr)
        return 0  # Not really an error, just already running

    try:
        if logger:
            logger.info(LogMessages.MSG_INSTANCE_LOCK_ACQUIRED)

        # Create and run the application
        app = OrgPromptApp()
        app.run()

        if logger:
            logger.info(LogMessages.MSG_SHUTDOWN)
        return 0

    except KeyboardInterrupt:
        if logger:
            logger.info(LogMessages.MSG_INTERRUPTED)
        return 0

    except Exception as e:
        if logger:
            logger.exception(LogMessages.MSG_ERROR_UNEXPECTED)

        # Show error to user via GUI
        try:
            # Use user-friendly log path (just filename, not full path)
            error_msg = f"An unexpected error occurred:\n\n{str(e)}\n\nCheck the log file for details:\n%TEMP%\\orgprompt\\orgprompt.log"
            show_error_message("OrgPrompt Error", error_msg)
        except Exception:
            pass  # If we can't show the error, we've already logged it

        return 1

    finally:
        # Always release the lock
        lock.release()
        if logger:
            logger.info(LogMessages.MSG_INSTANCE_LOCK_RELEASED)


if __name__ == "__main__":
    sys.exit(main())


"""OrgPrompt - System tray AI prompt utility.

A Windows system tray application that provides quick access to a categorized
library of AI prompts with search functionality.

Threading model: Tk runs on the main thread; pystray runs on a background
"tray" thread. The tray thread never touches Tk directly - it posts callables
to a queue that the main thread drains every POLL_MS milliseconds.
"""

import logging
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from app_state import AppState
from clipboard import copy_with_notification
from logging_config import (
    LogMessages,
    enable_faulthandler,
    install_exception_hooks,
    setup_logging,
)
from prompt_manager import PromptManager
from prompt_window import PromptWindow
from single_instance import SingleInstance
from tray_manager import TrayManager

# Global logger instance
logger: Optional[logging.Logger] = None

# Module logger; safe to use even if setup_logging() failed (no handlers).
_log = logging.getLogger("orgprompt.app")


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

    POLL_MS = 100
    MAX_TRAY_RESTARTS = 5
    # A tray icon that ran this long before failing resets the restart count.
    TRAY_STABLE_SECONDS = 600

    def __init__(self):
        # Create hidden root window to prevent "tk" window from appearing
        self.root = tk.Tk()
        self.root.withdraw()
        # Log exceptions raised in Tk callbacks (otherwise lost under pythonw)
        self.root.report_callback_exception = self._report_callback_exception

        self.prompt_manager = PromptManager()
        self.state = AppState()
        self.tray_manager = TrayManager(
            on_click=self.show_prompt_window,
            on_quit=self.quit,
            get_favorites=self._get_favorites,
            on_favorite=self.copy_favorite,
        )
        self.prompt_window: Optional[PromptWindow] = None
        self.running = True
        self._commands: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._root_destroyed = False

    # --- Cross-thread plumbing ---

    def _post(self, command: Callable[[], None]) -> None:
        """Queue a callable to run on the Tk main thread (thread-safe)."""
        self._commands.put(command)

    def _process_commands(self) -> None:
        """Run queued commands, then reschedule. Main thread only."""
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                break
            try:
                command()
            except Exception:
                _log.exception("Error while handling a tray command")
        if not self._root_destroyed:
            self.root.after(self.POLL_MS, self._process_commands)

    @staticmethod
    def _report_callback_exception(exc_type, exc_value, exc_tb) -> None:
        _log.error(
            "Unhandled exception in UI callback",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    # --- Public API (callable from any thread) ---

    def show_prompt_window(self) -> None:
        """Show the prompt selection window. Thread-safe."""
        if self.running:
            self._post(self._show_prompt_window_main_thread)

    def copy_favorite(self, key: str) -> None:
        """Copy a favorite prompt (from the tray menu). Thread-safe."""
        if self.running:
            self._post(lambda: self._copy_favorite_main_thread(key))

    def quit(self) -> None:
        """Quit the application. Thread-safe."""
        self.running = False
        self._post(self._quit_main_thread)

    # --- Main-thread handlers ---

    def _show_prompt_window_main_thread(self) -> None:
        """Show the prompt window — must run on the Tk main thread."""
        _log.info(LogMessages.MSG_WINDOW_SHOWING)
        if self.prompt_window is None:
            self.prompt_window = PromptWindow(
                prompt_manager=self.prompt_manager,
                on_close=self._on_window_close,
                on_quit=self.quit,
                state=self.state,
                notifier=self.tray_manager.notify,
                on_prompts_changed=self.tray_manager.refresh_menu,
            )
        self.prompt_window.show()

    def _on_window_close(self) -> None:
        """Handle window close (the window is hidden, not destroyed)."""
        _log.info(LogMessages.MSG_WINDOW_CLOSED)

    def _get_favorites(self) -> list[tuple[str, str]]:
        return [(p.key, p.title) for p in self.prompt_manager.get_pinned_prompts()]

    def _copy_favorite_main_thread(self, key: str) -> None:
        if self.prompt_manager.reload_if_changed():
            self.tray_manager.refresh_menu()
        prompt = self.prompt_manager.find_by_key(key)
        if prompt is None:
            self.tray_manager.notify("OrgPrompt", "That favorite no longer exists.")
            return
        settings = self.prompt_manager.settings
        if copy_with_notification(
            prompt.text,
            settings.get("show_notifications", True),
            notifier=self.tray_manager.notify,
            message=f"Copied: {prompt.title}",
        ):
            self.state.record_use(prompt.key)

    def _quit_main_thread(self) -> None:
        """Perform cleanup on the Tk main thread and exit mainloop."""
        if self._root_destroyed:
            return
        if self.prompt_window is not None:
            try:
                self.prompt_window.destroy()
            except Exception:
                _log.exception("Error closing prompt window")
        self.tray_manager.stop()
        self._root_destroyed = True
        self.root.destroy()

    # --- Tray thread ---

    def _run_tray(self) -> None:
        """Run the tray icon, restarting it if it dies unexpectedly.

        If the icon keeps failing, quit the app so the single-instance lock
        is released and the user can simply start OrgPrompt again (instead of
        a zombie process with no icon blocking relaunch).
        """
        restarts = 0
        while self.running:
            started = time.monotonic()
            try:
                self.tray_manager.start()
            except Exception:
                _log.exception(LogMessages.MSG_TRAY_ERROR)
            if not self.running:
                break
            if time.monotonic() - started > self.TRAY_STABLE_SECONDS:
                restarts = 0
            restarts += 1
            if restarts > self.MAX_TRAY_RESTARTS:
                _log.error(
                    "Tray icon failed %d times; shutting down so OrgPrompt "
                    "can be restarted cleanly", restarts - 1,
                )
                self.quit()
                break
            delay = min(2 ** restarts, 30)
            _log.warning(
                "Tray icon stopped unexpectedly; restarting in %ds (attempt %d/%d)",
                delay, restarts, self.MAX_TRAY_RESTARTS,
            )
            time.sleep(delay)

    def run(self) -> None:
        """Run the application.

        Starts pystray in a daemon thread and runs the Tk mainloop on the
        main thread, ensuring Tk events are always processed reliably.
        """
        _log.info(LogMessages.MSG_TRAY_STARTING)

        tray_thread = threading.Thread(target=self._run_tray, daemon=True, name="tray")
        tray_thread.start()

        self.root.after(self.POLL_MS, self._process_commands)
        # Blocks until root.destroy()
        self.root.mainloop()

        _log.info(LogMessages.MSG_TRAY_STOPPED)


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
        install_exception_hooks(logger)
        enable_faulthandler()
    except Exception as e:
        # If logging setup fails, try to print to stderr (may not work with pythonw)
        try:
            print(f"Failed to setup logging: {e}", file=sys.stderr)
        except Exception:
            pass
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
            if getattr(lock, "recovered_stale", False) is True:
                logger.warning(
                    "Previous OrgPrompt session did not shut down cleanly "
                    "(see orgprompt_fault.log for any crash traceback)"
                )

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

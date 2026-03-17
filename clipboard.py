"""Clipboard operations and notifications."""

import pyperclip
import threading
from typing import Optional


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard.

    Args:
        text: Text to copy

    Returns:
        True if successful, False otherwise
    """
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def show_notification(title: str, message: str) -> None:
    """Show a toast notification on Windows.

    Args:
        title: Notification title
        message: Notification message
    """
    try:
        from win11toast import toast
        toast(title, message)
    except ImportError:
        # Fallback to win10toast
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=2, threaded=True)
        except ImportError:
            # No notification library available, silently skip
            pass


def copy_with_notification(text: str, notification: bool = True) -> bool:
    """Copy text to clipboard and optionally show notification.

    Args:
        text: Text to copy
        notification: Whether to show notification

    Returns:
        True if copy successful
    """
    success = copy_to_clipboard(text)
    if success and notification:
        # Show notification in background thread to not block UI
        threading.Thread(
            target=show_notification,
            args=("OrgPrompt", "Prompt copied to clipboard!"),
            daemon=True
        ).start()
    return success

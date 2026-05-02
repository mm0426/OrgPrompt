"""Clipboard operations."""

import threading

import pyperclip

from notifications import notify


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
        threading.Thread(
            target=notify,
            args=("OrgPrompt", "Prompt copied to clipboard!"),
            daemon=True
        ).start()
    return success

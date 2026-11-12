"""Clipboard operations and notifications."""

import logging
from typing import Callable, Optional

import pyperclip

logger = logging.getLogger("orgprompt.clipboard")

# notifier(title, message) - e.g. TrayManager.notify, which uses the tray
# icon's built-in Windows notification (no extra thread or library).
Notifier = Callable[[str, str], None]


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
        logger.exception("Failed to copy to clipboard")
        return False


def copy_with_notification(
    text: str,
    notification: bool = True,
    notifier: Optional[Notifier] = None,
    message: str = "Prompt copied to clipboard!",
) -> bool:
    """Copy text to clipboard and optionally show a notification.

    Args:
        text: Text to copy
        notification: Whether to show a notification
        notifier: Callable used to show the notification
        message: Notification message

    Returns:
        True if copy successful
    """
    success = copy_to_clipboard(text)
    if success and notification and notifier is not None:
        try:
            notifier("OrgPrompt", message)
        except Exception:
            logger.exception("Failed to show notification")
    return success

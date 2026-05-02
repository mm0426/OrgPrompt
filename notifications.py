"""Platform-aware notification backend."""

import subprocess
import sys


def notify(title: str, message: str) -> None:
    """Show a desktop notification.

    On Windows, uses win11toast or win10toast.
    On Linux, uses notify-send subprocess.
    Falls back silently if no backend is available.
    """
    if sys.platform == "win32":
        _notify_windows(title, message)
    else:
        _notify_linux(title, message)


def _notify_windows(title: str, message: str) -> None:
    try:
        from win11toast import toast
        toast(title, message)
    except ImportError:
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=2, threaded=True)
        except ImportError:
            pass


def _notify_linux(title: str, message: str) -> None:
    try:
        import notify2
        if not notify2.is_initted():
            notify2.init("OrgPrompt")
        notify2.Notification(title, message).show()
    except ImportError:
        _notify_send(title, message)


def _notify_send(title: str, message: str) -> None:
    try:
        subprocess.run(
            ["notify-send", title, message],
            check=True,
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

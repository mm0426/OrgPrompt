"""Single instance lock to prevent multiple application instances."""

import os
import sys
import tempfile
from typing import Optional


class SingleInstance:
    """File-based lock to ensure only one application instance runs."""

    def __init__(self, app_name: str):
        self.lock_path = os.path.join(tempfile.gettempdir(), f"{app_name}.lock")
        self.lock_file: Optional[object] = None

    def _is_process_alive(self, pid: int) -> bool:
        """Check if a process with the given PID is running.

        Args:
            pid: Process ID to check.

        Returns:
            True if the process exists and is running, False otherwise.
        """
        if pid <= 0:
            return False

        if sys.platform == "win32":
            # Windows: use ctypes to check process existence
            # os.kill() on Windows is limited and may not work for other processes
            try:
                import ctypes

                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, pid
                )
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    return True
                return False
            except (OSError, AttributeError):
                return False
        else:
            # Unix: use os.kill(pid, 0) to check process existence
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False
            except ValueError:
                return False

    def acquire(self, _retry_count: int = 0) -> bool:
        """Try to acquire the instance lock.

        Args:
            _retry_count: Internal use only - retry counter to prevent infinite recursion.

        Returns:
            True if lock acquired (no other instance running)
            False if lock failed (another instance is running)
        """
        MAX_RETRIES = 3

        try:
            # Try to create and lock the file exclusively
            # On Windows, opening with 'x' mode fails if file exists
            self.lock_file = open(self.lock_path, "x")
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            return True
        except FileExistsError:
            # Lock file exists - check if the process is still alive
            try:
                with open(self.lock_path, "r") as f:
                    pid_str = f.read().strip()

                if not pid_str:
                    # Empty lock file - stale, remove it
                    os.remove(self.lock_path)
                    if _retry_count < MAX_RETRIES:
                        return self.acquire(_retry_count + 1)
                    return False

                try:
                    pid = int(pid_str)
                except ValueError:
                    # Invalid PID in file - stale, remove it
                    os.remove(self.lock_path)
                    if _retry_count < MAX_RETRIES:
                        return self.acquire(_retry_count + 1)
                    return False

                if not self._is_process_alive(pid):
                    # Process is dead - stale lock, remove and retry
                    os.remove(self.lock_path)
                    if _retry_count < MAX_RETRIES:
                        return self.acquire(_retry_count + 1)
                    return False

                # Process is still running - another instance is active
                return False
            except (OSError, PermissionError):
                # Can't read/remove lock file - assume another instance
                return False
        except PermissionError:
            # Permission issue, assume another instance
            return False

    def release(self) -> None:
        """Release the instance lock."""
        if self.lock_file:
            try:
                self.lock_file.close()
                os.remove(self.lock_path)
            except (OSError, FileNotFoundError):
                pass
            self.lock_file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

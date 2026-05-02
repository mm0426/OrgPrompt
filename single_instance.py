"""Single instance lock to prevent multiple application instances."""

import logging
import os
import sys
import tempfile
from typing import Optional

# Get a logger for this module
logger = logging.getLogger("orgprompt.single_instance")


class SingleInstance:
    """File-based lock to ensure only one application instance runs.

    Stores both PID and executable path in the lock file to avoid
    false positives from PID reuse (common on Windows where PIDs
    recycle quickly to unrelated system processes).
    """

    def __init__(self, app_name: str):
        self.lock_path = os.path.join(tempfile.gettempdir(), f"{app_name}.lock")
        self.lock_file: Optional[object] = None
        self._exe_path = sys.executable
        logger.debug(f"SingleInstance initialized with lock path: {self.lock_path}")

    def _is_same_process(self, pid: int) -> bool:
        """Check if the process with the given PID is the same executable.

        Verifies both that the process exists AND that its executable path
        matches this process's executable, to avoid false positives from
        PID recycling.

        Args:
            pid: Process ID to check.

        Returns:
            True if the process exists and is running the same executable.
            False if the process is dead or is a different program.
        """
        if pid <= 0:
            logger.debug(f"Invalid PID: {pid}")
            return False

        if sys.platform == "win32":
            try:
                import ctypes
                import ctypes.wintypes

                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

                handle = kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, pid
                )
                if not handle:
                    logger.debug(f"Process {pid} not found")
                    return False

                try:
                    # Query the full executable path of the process
                    buf = ctypes.create_unicode_buffer(1024)
                    size = ctypes.wintypes.DWORD(1024)
                    result = kernel32.QueryFullProcessImageNameW(
                        handle, 0, buf, ctypes.byref(size)
                    )
                    if result:
                        actual_path = buf.value.lower().replace("/", "\\")
                        expected_path = self._exe_path.lower().replace("/", "\\")
                        is_same = actual_path == expected_path
                        if is_same:
                            logger.debug(
                                f"Process {pid} is same executable: {actual_path}"
                            )
                        else:
                            logger.info(
                                f"Process {pid} is different program "
                                f"(expected: {expected_path}, "
                                f"actual: {actual_path}), "
                                f"treating as stale lock"
                            )
                        return is_same
                    else:
                        logger.debug(
                            f"Could not query image name for PID {pid}"
                        )
                        return False
                finally:
                    kernel32.CloseHandle(handle)
            except (OSError, AttributeError) as e:
                logger.debug(f"Error checking process {pid}: {e}")
                return False
        else:
            # Unix: use os.kill(pid, 0) for existence check
            # PID recycling is less common on Unix, and exe path
            # matching via /proc is platform-specific, so just check existence
            try:
                os.kill(pid, 0)
                logger.debug(f"Process {pid} is alive (Unix)")
                return True
            except (OSError, ProcessLookupError):
                logger.debug(f"Process {pid} not found (Unix)")
                return False
            except ValueError:
                logger.debug(f"Invalid PID {pid} (Unix)")
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

        logger.debug(f"Attempting to acquire lock (retry {_retry_count}/{MAX_RETRIES})")

        try:
            # Try to create and lock the file exclusively
            # On Windows, opening with 'x' mode fails if file exists
            self.lock_file = open(self.lock_path, "x")
            # Store PID and executable path for reliable stale detection
            self.lock_file.write(f"{os.getpid()}\n{self._exe_path}\n")
            self.lock_file.flush()
            logger.info(f"Lock acquired successfully: {self.lock_path}")
            return True
        except FileExistsError:
            # Lock file exists - check if the process is still alive AND is us
            logger.debug("Lock file exists, checking if process is alive")
            try:
                with open(self.lock_path, "r") as f:
                    lines = f.read().strip().splitlines()

                if len(lines) < 1 or not lines[0].strip():
                    # Empty lock file - stale, remove it
                    logger.warning("Empty lock file found, treating as stale")
                    os.remove(self.lock_path)
                    if _retry_count < MAX_RETRIES:
                        return self.acquire(_retry_count + 1)
                    return False

                try:
                    pid = int(lines[0].strip())
                except ValueError:
                    # Invalid PID in file - stale, remove it
                    logger.warning(
                        f"Invalid PID in lock file: {repr(lines[0])}, "
                        f"treating as stale"
                    )
                    os.remove(self.lock_path)
                    if _retry_count < MAX_RETRIES:
                        return self.acquire(_retry_count + 1)
                    return False

                if not self._is_same_process(pid):
                    # Process is dead or a different program - stale lock
                    logger.info(
                        f"Stale lock file detected (PID {pid} is not "
                        f"the same executable), removing and retrying"
                    )
                    os.remove(self.lock_path)
                    if _retry_count < MAX_RETRIES:
                        return self.acquire(_retry_count + 1)
                    return False

                # Same process is still running - another instance is active
                logger.info(f"Another instance is already running (PID {pid})")
                return False
            except (OSError, PermissionError) as e:
                # Can't read/remove lock file - assume another instance
                logger.warning(f"Cannot access lock file: {e}, assuming another instance")
                return False
        except PermissionError as e:
            # Permission issue, assume another instance
            logger.warning(f"Permission error accessing lock file: {e}")
            return False

    def release(self) -> None:
        """Release the instance lock."""
        if self.lock_file:
            try:
                self.lock_file.close()
                os.remove(self.lock_path)
                logger.info(f"Lock released: {self.lock_path}")
            except (OSError, FileNotFoundError) as e:
                logger.warning(f"Error releasing lock: {e}")
            self.lock_file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

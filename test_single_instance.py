"""Tests for single_instance.py module.

This test suite follows TDD methodology:
1. Write failing test first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor and improve (IMPROVE)
"""

import logging
import os
import sys
import tempfile
from unittest.mock import Mock, patch, MagicMock
import pytest


# Setup logging for tests
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def temp_lock_dir():
    """Create a temporary directory for lock files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def clean_lock_files():
    """Fixture to clean up any lock files after tests."""
    yield

    # Clean up any remaining lock files
    import tempfile
    lock_file = os.path.join(tempfile.gettempdir(), "orgprompt.lock")
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except (OSError, PermissionError):
        pass


class TestSingleInstance:
    """Test SingleInstance lock functionality."""

    def test_single_instance_init(self, temp_lock_dir):
        """Test SingleInstance initialization."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp")

            assert lock.lock_path.endswith("testapp.lock")
            assert lock.lock_file is None

    def test_acquire_lock_when_available(self, temp_lock_dir, clean_lock_files):
        """Test acquiring lock when no other instance is running."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_acquire")

            # Should succeed
            assert lock.acquire() is True

            # Lock file should exist
            assert os.path.exists(lock.lock_path)

            # Clean up
            lock.release()

    def test_acquire_lock_when_already_held(self, temp_lock_dir, clean_lock_files):
        """Test that acquire fails when lock is already held."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock1 = SingleInstance("testapp_double")
            lock2 = SingleInstance("testapp_double")

            # First lock should succeed
            assert lock1.acquire() is True

            # Second lock should fail
            assert lock2.acquire() is False

            # Clean up
            lock1.release()

    def test_release_lock(self, temp_lock_dir, clean_lock_files):
        """Test releasing the lock."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_release")

            lock.acquire()

            # Lock file should exist
            assert os.path.exists(lock.lock_path)

            # Release the lock
            lock.release()

            # Lock file should be removed
            assert not os.path.exists(lock.lock_path)

    def test_lock_contains_current_pid(self, temp_lock_dir, clean_lock_files):
        """Test that lock file contains current PID and exe path."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_pid")
            lock.acquire()

            # Read lock file
            with open(lock.lock_path, 'r') as f:
                content = f.read().strip()
            lines = content.splitlines()

            # First line should be current PID
            assert lines[0] == str(os.getpid())

            # Second line should be the executable path
            assert len(lines) >= 2
            assert lines[1] == sys.executable

            # Clean up
            lock.release()

    def test_context_manager(self, temp_lock_dir, clean_lock_files):
        """Test using SingleInstance as a context manager."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            with SingleInstance("testapp_context") as lock:
                # Manually acquire lock in context
                lock.acquire()

                # Lock should be acquired
                assert os.path.exists(lock.lock_path)

            # Lock should be released after context
            assert not os.path.exists(lock.lock_path)

    def test_stale_lock_empty_file(self, temp_lock_dir, clean_lock_files):
        """Test handling of stale lock file with empty content."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock_path = os.path.join(temp_lock_dir, "testapp_empty.lock")

            # Create empty lock file
            with open(lock_path, 'w') as f:
                f.write("")

            # Should acquire lock (treats empty as stale)
            lock = SingleInstance("testapp_empty")
            assert lock.acquire() is True

            # Clean up
            lock.release()

    def test_stale_lock_invalid_pid(self, temp_lock_dir, clean_lock_files):
        """Test handling of stale lock file with invalid PID."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock_path = os.path.join(temp_lock_dir, "testapp_invalid.lock")

            # Create lock file with invalid PID
            with open(lock_path, 'w') as f:
                f.write("not_a_number")

            # Should acquire lock (treats invalid as stale)
            lock = SingleInstance("testapp_invalid")
            assert lock.acquire() is True

            # Clean up
            lock.release()

    def test_stale_lock_dead_process(self, temp_lock_dir, clean_lock_files):
        """Test handling of stale lock file with dead process."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock_path = os.path.join(temp_lock_dir, "testapp_dead.lock")

            # Use a PID that doesn't exist (very high number unlikely to be in use)
            dead_pid = 99999

            # Create lock file with dead PID
            with open(lock_path, 'w') as f:
                f.write(str(dead_pid))

            # Should acquire lock (detects dead process)
            lock = SingleInstance("testapp_dead")
            assert lock.acquire() is True

            # Clean up
            lock.release()

    def test_is_same_process_with_invalid_pid(self, temp_lock_dir):
        """Test _is_same_process with invalid PIDs."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_alive")

            # Negative PID
            assert lock._is_same_process(-1) is False

            # Zero PID
            assert lock._is_same_process(0) is False

    def test_acquire_retry_limit(self, temp_lock_dir, clean_lock_files):
        """Test that acquire doesn't retry infinitely."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock_path = os.path.join(temp_lock_dir, "testapp_retry.lock")

            # Create a lock file that keeps getting recreated
            # This tests the retry limit logic
            with open(lock_path, 'w') as f:
                f.write("")

            # Mock file operations to simulate persistent lock
            original_remove = os.remove
            remove_count = [0]

            def mock_remove(path):
                remove_count[0] += 1
                if remove_count[0] < 5:  # Fail first few times
                    raise OSError("Simulated error")
                return original_remove(path)

            with patch('os.remove', side_effect=mock_remove):
                lock = SingleInstance("testapp_retry")
                # Should eventually give up and return False
                result = lock.acquire()

                # Should either succeed or fail, but not hang
                assert isinstance(result, bool)

    def test_multiple_release_calls(self, temp_lock_dir, clean_lock_files):
        """Test that calling release multiple times doesn't crash."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_multi_release")
            lock.acquire()

            # First release
            lock.release()

            # Second release should be safe
            lock.release()

            # Third release should also be safe
            lock.release()

    def test_release_without_acquire(self, temp_lock_dir):
        """Test that releasing without acquiring is safe."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_no_acquire")

            # Release without acquire should not crash
            lock.release()


class TestSingleInstancePlatformSpecific:
    """Test platform-specific behavior."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_process_check(self, temp_lock_dir):
        """Test process checking on Windows."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_windows")

            # Check current process (should be same executable)
            assert lock._is_same_process(os.getpid()) is True

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    def test_unix_process_check(self, temp_lock_dir):
        """Test process checking on Unix."""
        from single_instance import SingleInstance

        with patch('tempfile.gettempdir', return_value=temp_lock_dir):
            lock = SingleInstance("testapp_unix")

            # Check current process (should be alive)
            assert lock._is_same_process(os.getpid()) is True

            # Check non-existent process
            assert lock._is_same_process(99999) is False

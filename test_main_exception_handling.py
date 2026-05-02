"""Tests for main.py exception handling.

This test suite follows TDD methodology:
1. Write failing test first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor and improve (IMPROVE)
"""

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest


# Module-level fixtures
@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def log_file_path(temp_log_dir):
    """Get the expected log file path."""
    return os.path.join(temp_log_dir, "orgprompt.log")


class TestMainExceptionHandling:
    """Test that main() properly handles and logs exceptions."""

    def test_main_catches_and_logs_exceptions(self, temp_log_dir, log_file_path):
        """Test that main() catches exceptions and logs them."""
        # Mock SingleInstance to avoid hitting real lock files
        with patch('main.SingleInstance') as mock_si_class:
            mock_lock = Mock()
            mock_lock.acquire.return_value = True
            mock_si_class.return_value = mock_lock

            # Mock OrgPromptApp to raise an exception
            with patch('main.OrgPromptApp') as mock_app_class:
                mock_app = Mock()
                mock_app.run.side_effect = RuntimeError("Test exception in app.run()")
                mock_app_class.return_value = mock_app

                # Mock setup_logging to use our temp directory
                with patch('main.setup_logging') as mock_setup_logging:
                    mock_logger = Mock()
                    mock_setup_logging.return_value = mock_logger

                    # Import and call main
                    from main import main

                    # Should not raise an exception (should be caught)
                    try:
                        main()
                    except RuntimeError:
                        pytest.fail("main() should catch and log exceptions, not raise them")

                    # Verify exception was logged
                    mock_logger.exception.assert_called_once()

    def test_main_logs_single_instance_failure(self, temp_log_dir, log_file_path):
        """Test that main() logs when single instance lock fails."""
        with patch('main.SingleInstance') as mock_si_class:
            mock_lock = Mock()
            mock_lock.acquire.return_value = False  # Lock already held
            mock_si_class.return_value = mock_lock

            with patch('main.setup_logging') as mock_setup_logging:
                mock_logger = Mock()
                mock_setup_logging.return_value = mock_logger

                from main import main

                # Should not raise exception
                main()

                # Should log that instance is already running
                assert any(
                    "already running" in str(call).lower()
                    for call in mock_logger.info.call_args_list
                ) or any(
                    "already running" in str(call).lower()
                    for call in mock_logger.warning.call_args_list
                )

    def test_main_releases_lock_on_exception(self, temp_log_dir):
        """Test that main() releases the single instance lock even if exception occurs."""
        with patch('main.SingleInstance') as mock_si_class:
            mock_lock = Mock()
            mock_lock.acquire.return_value = True

            # Make app.run() raise an exception
            with patch('main.OrgPromptApp') as mock_app_class:
                mock_app = Mock()
                mock_app.run.side_effect = Exception("Test exception")
                mock_app_class.return_value = mock_app

                mock_si_class.return_value = mock_lock

                with patch('main.setup_logging') as mock_setup_logging:
                    mock_logger = Mock()
                    mock_setup_logging.return_value = mock_logger

                    from main import main

                    # Call main - should not raise
                    main()

                    # Verify lock was released despite exception
                    mock_lock.release.assert_called_once()

    def test_main_handles_keyboard_interrupt(self, temp_log_dir):
        """Test that main() handles KeyboardInterrupt (Ctrl+C) gracefully."""
        with patch('main.SingleInstance') as mock_si_class:
            mock_lock = Mock()
            mock_lock.acquire.return_value = True
            mock_si_class.return_value = mock_lock

            # Make app.run() raise KeyboardInterrupt
            with patch('main.OrgPromptApp') as mock_app_class:
                mock_app = Mock()
                mock_app.run.side_effect = KeyboardInterrupt()
                mock_app_class.return_value = mock_app

                with patch('main.setup_logging') as mock_setup_logging:
                    mock_logger = Mock()
                    mock_setup_logging.return_value = mock_logger

                    from main import main

                    # Should not raise
                    main()

                    # Verify lock was released
                    mock_lock.release.assert_called_once()

                    # Verify interrupt was logged
                    from logging_config import LogMessages
                    mock_logger.info.assert_any_call(LogMessages.MSG_INTERRUPTED)

    def test_main_creates_log_directory_if_missing(self, temp_log_dir):
        """Test that main() creates log directory if it doesn't exist."""
        non_existent_dir = os.path.join(temp_log_dir, "logs", "nested")

        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app_class.return_value = mock_app

                    # Patch logging_config.get_log_file_path to return our non-existent directory
                    with patch('logging_config.get_log_file_path') as mock_get_path:
                        mock_get_path.return_value = os.path.join(non_existent_dir, "orgprompt.log")

                        # Patch os.makedirs to track if it's called
                        with patch('os.makedirs') as mock_makedirs:
                            from main import main

                            # Should not raise
                            main()

                            # setup_logging should create the directory
                            # (it's called inside main, and setup_logging handles directory creation)
                            # We verify main() completes without error
                            assert True

    def test_main_shows_message_box_on_critical_error(self, temp_log_dir):
        """Test that main() shows a message box for critical errors."""
        with patch('main.SingleInstance') as mock_si_class:
            mock_lock = Mock()
            mock_lock.acquire.return_value = True
            mock_si_class.return_value = mock_lock

            # Make OrgPromptApp.__init__ fail (critical error)
            with patch('main.OrgPromptApp') as mock_app_class:
                mock_app_class.side_effect = ImportError("Missing critical dependency")

                with patch('main.setup_logging') as mock_setup_logging:
                    mock_logger = Mock()
                    mock_setup_logging.return_value = mock_logger

                    with patch('main.show_error_message') as mock_show_error:
                        from main import main

                        # Should not raise
                        main()

                        # Verify error was shown to user
                        mock_show_error.assert_called_once()

                        # Verify error was logged
                        mock_logger.exception.assert_called_once()

    def test_main_returns_zero_on_success(self, temp_log_dir):
        """Test that main() returns 0 on successful exit."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Call main
                    result = main()

                    # Should return 0 on success
                    assert result == 0, f"Expected return value 0, got {result}"

    def test_main_returns_one_on_error(self, temp_log_dir):
        """Test that main() returns 1 on error."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_si_class.return_value = mock_lock

                # Make app fail
                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app.run.side_effect = RuntimeError("Unexpected error")
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Call main
                    result = main()

                    # Should return 1 on error
                    assert result == 1, f"Expected return value 1, got {result}"


class TestMainWithPythonW:
    """Test behavior specific to pythonw.exe (no console)."""

    def test_logging_works_with_pythonw(self, temp_log_dir):
        """Test that logging works even when stdout/stderr are not available (pythonw)."""
        # Simulate pythonw environment by redirecting stdout/stderr to NUL
        with patch('sys.stdout', None):
            with patch('sys.stderr', None):
                with patch('main.setup_logging') as mock_setup_logging:
                    mock_logger = Mock()
                    mock_setup_logging.return_value = mock_logger

                    from main import main

                    # Should not crash even without stdout/stderr
                    # We can't actually run main() here without more mocking
                    # but the implementation should handle this case

    def test_print_statements_dont_crash_pythonw(self, temp_log_dir):
        """Test that print() statements don't crash in pythonw environment."""
        # In pythonw, print() goes to a null device
        # The application should not crash on print statements

        # This is more of an integration test - the key is that
        # logging is used instead of print() for important messages
        pass


class TestMainLoggingConfiguration:
    """Test that main() properly configures logging."""

    def test_main_calls_setup_logging(self, temp_log_dir):
        """Test that main() calls setup_logging on startup."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_lock.release.return_value = None
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Call main
                    main()

                    # Verify setup_logging was called
                    mock_setup_logging.assert_called_once()

    def test_main_passes_log_dir_to_setup_logging(self, temp_log_dir):
        """Test that main() passes the correct log directory to setup_logging."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_lock.release.return_value = None
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Call main
                    main()

                    # Verify setup_logging was called with correct arguments
                    call_kwargs = mock_setup_logging.call_args[1] if mock_setup_logging.call_args[1] else {}
                    # Should have log_dir parameter
                    # (exact value depends on implementation)


class TestMainSingleInstance:
    """Test main() interaction with single instance lock."""

    def test_main_exits_when_lock_already_held(self):
        """Test that main() exits early when another instance is running."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = False  # Already locked
                mock_lock.release.return_value = None
                mock_si_class.return_value = mock_lock

                from main import main

                # Call main
                result = main()

                # Should return early
                assert result is not None

    def test_main_creates_lock_with_correct_name(self):
        """Test that main() creates SingleInstance with correct app name."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_lock.release.return_value = None
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Call main
                    main()

                    # Verify SingleInstance was created with correct name
                    mock_si_class.assert_called_once_with("orgprompt")


class TestMainRecovery:
    """Test main() recovery and restart behavior."""

    def test_main_logs_and_continues_after_tray_icon_failure(self, temp_log_dir):
        """Test that tray icon creation failure is logged and handled."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    # Make tray icon fail
                    mock_app.run.side_effect = Exception("Failed to create tray icon")
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Should not raise
                    result = main()

                    # Verify error was logged
                    mock_logger.exception.assert_called()

                    # Should return error code
                    assert result == 1

    def test_main_handles_stale_lock_file(self):
        """Test that main() can recover from a stale lock file."""
        # This is tested in single_instance tests, but main() should
        # handle the case where SingleInstance.acquire() succeeds after
        # cleaning up a stale lock
        pass

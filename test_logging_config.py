"""Tests for logging configuration module.

This test suite follows TDD methodology:
1. Write failing test first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor and improve (IMPROVE)
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional
import pytest


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def log_file_path(temp_log_dir):
    """Get the expected log file path."""
    return os.path.join(temp_log_dir, "orgprompt.log")


@pytest.fixture
def clean_logger():
    """Fixture to ensure clean logger state for each test."""
    logger = logging.getLogger("orgprompt")
    handlers_copy = logger.handlers[:]

    yield

    # Clean up handlers after test
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    # Restore original handlers if any
    for handler in handlers_copy:
        logger.addHandler(handler)


class TestLoggingConfiguration:
    """Test logging configuration setup."""

    def test_setup_logging_creates_log_file(self, temp_log_dir, log_file_path, clean_logger):
        """Test that setup_logging creates a log file at the expected path."""
        from logging_config import setup_logging

        # Setup logging with custom directory
        logger = setup_logging(log_dir=temp_log_dir)

        # Verify log file exists
        assert os.path.exists(log_file_path), f"Log file not created at {log_file_path}"

        # Verify it's a file
        assert os.path.isfile(log_file_path), "Log path is not a file"

        # Clean up
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_setup_logging_returns_logger(self, temp_log_dir, clean_logger):
        """Test that setup_logging returns a configured logger."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)

        # Verify we got a logger
        assert isinstance(logger, logging.Logger), "setup_logging should return a Logger"

        # Verify logger has the correct name
        assert logger.name == "orgprompt", f"Logger name should be 'orgprompt', got '{logger.name}'"

        # Verify logger has handlers
        assert len(logger.handlers) > 0, "Logger should have at least one handler"

        # Clean up
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_logger_writes_to_file(self, temp_log_dir, log_file_path, clean_logger):
        """Test that the logger actually writes messages to the log file."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)

        # Write a test message
        test_message = "Test log message for file writing verification"
        logger.info(test_message)

        # Flush and close handlers to ensure message is written
        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        # Read the log file and verify message exists
        with open(log_file_path, 'r') as f:
            content = f.read()

        assert test_message in content, f"Test message not found in log file. Content: {content}"

    def test_logger_handles_different_log_levels(self, temp_log_dir, log_file_path, clean_logger):
        """Test that logger respects different log levels."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)

        # Log messages at different levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # Flush and close handlers
        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        # Read the log file
        with open(log_file_path, 'r') as f:
            content = f.read()

        # Verify messages are present (INFO and above should be logged)
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content
        assert "Critical message" in content

    def test_logger_format_includes_timestamp(self, temp_log_dir, log_file_path, clean_logger):
        """Test that log messages include timestamps."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)
        logger.info("Test message for timestamp")

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        with open(log_file_path, 'r') as f:
            first_line = f.readline().strip()

        # Verify log line has timestamp format (YYYY-MM-DD HH:MM:SS)
        import re
        timestamp_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
        assert re.search(timestamp_pattern, first_line), f"No timestamp found in: {first_line}"

    def test_logger_format_includes_level(self, temp_log_dir, log_file_path, clean_logger):
        """Test that log messages include log level."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)
        logger.info("Test message for level")

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        with open(log_file_path, 'r') as f:
            content = f.read()

        assert "INFO" in content, "Log level INFO not found in output"

    def test_logger_format_includes_logger_name(self, temp_log_dir, log_file_path, clean_logger):
        """Test that log messages include logger name."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)
        logger.info("Test message for logger name")

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        with open(log_file_path, 'r') as f:
            content = f.read()

        assert "orgprompt" in content, "Logger name 'orgprompt' not found in output"

    def test_get_log_file_path_returns_expected_path(self, temp_log_dir):
        """Test that get_log_file_path returns the correct path."""
        from logging_config import get_log_file_path

        log_path = get_log_file_path(log_dir=temp_log_dir)

        expected_path = os.path.join(temp_log_dir, "orgprompt.log")
        assert log_path == expected_path, f"Expected {expected_path}, got {log_path}"

    def test_get_log_file_path_default_location(self):
        """Test that get_log_file_path uses default location when no dir specified."""
        from logging_config import get_log_file_path

        log_path = get_log_file_path()

        # Should default to temp directory with orgprompt subdirectory
        import tempfile
        expected_dir = os.path.join(tempfile.gettempdir(), "orgprompt")
        assert log_path.startswith(expected_dir), f"Log path should start with {expected_dir}"

        # Should end with orgprompt.log
        assert log_path.endswith("orgprompt.log"), f"Log path should end with orgprompt.log, got {log_path}"

    def test_logger_rotates_large_files(self, temp_log_dir, clean_logger):
        """Test that logger rotates log files when they get too large."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir, max_bytes=1024)  # Small size for testing

        # Write enough data to trigger rotation
        for i in range(100):
            logger.info(f"Log message {i}: " + "x" * 100)  # Large message

        # Flush and close handlers
        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        # Check that rotation occurred (backup file created)
        log_files = list(Path(temp_log_dir).glob("orgprompt.log*"))
        assert len(log_files) > 1, f"Expected multiple log files due to rotation, found {len(log_files)}"

    def test_setup_logging_idempotent(self, temp_log_dir, clean_logger):
        """Test that calling setup_logging multiple times doesn't duplicate handlers."""
        from logging_config import setup_logging

        # Call setup_logging twice
        logger1 = setup_logging(log_dir=temp_log_dir)
        initial_handlers = len(logger1.handlers)

        logger2 = setup_logging(log_dir=temp_log_dir)
        final_handlers = len(logger2.handlers)

        # Should be the same logger instance
        assert logger1 is logger2, "setup_logging should return the same logger instance"

        # Should not add duplicate handlers
        assert final_handlers == initial_handlers, f"Handler count changed from {initial_handlers} to {final_handlers}"

        # Clean up
        for handler in logger1.handlers[:]:
            handler.close()
            logger1.removeHandler(handler)

    def test_logger_handles_unicode_characters(self, temp_log_dir, log_file_path, clean_logger):
        """Test that logger properly handles unicode and emoji characters."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)

        # Log unicode and emoji
        test_messages = [
            "Test with unicode: café",
            "Test with emoji: 🎉",
            "Test with special chars: © ® ™",
            "Test with cyrillic: привет",
            "Test with chinese: 你好",
        ]

        for msg in test_messages:
            logger.info(msg)

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        # Verify all messages are in the log file
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        for msg in test_messages:
            assert msg in content, f"Message '{msg}' not found in log file"

    def test_logger_handles_exceptions(self, temp_log_dir, log_file_path, clean_logger):
        """Test that logger can properly log exception information."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)

        try:
            raise ValueError("Test exception for logging")
        except ValueError:
            logger.exception("An error occurred")

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        with open(log_file_path, 'r') as f:
            content = f.read()

        # Verify exception details are logged
        assert "An error occurred" in content
        assert "ValueError: Test exception for logging" in content
        assert "Traceback" in content or "Exception" in content


class TestLoggingEdgeCases:
    """Test edge cases and error conditions."""

    def test_setup_logging_with_invalid_directory(self, clean_logger):
        """Test setup_logging with a directory that cannot be created."""
        from logging_config import setup_logging

        # Use an invalid path (assuming we can't create at this location)
        # On most systems, we can't create a directory at root level
        invalid_dir = "/invalid_path_that_cannot_be_created/orgprompt"

        # Should either raise an appropriate error or fallback to a valid location
        # The implementation should handle this gracefully
        try:
            logger = setup_logging(log_dir=invalid_dir)
            # If it succeeds, it should have fallen back to a valid location
            assert logger is not None
            # Clean up
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        except (OSError, PermissionError) as e:
            # If it raises, it should be an appropriate error
            assert True  # Expected behavior

    def test_logging_with_none_values(self, clean_logger):
        """Test logging when parameters are None."""
        from logging_config import setup_logging

        # Should handle None log_dir gracefully
        logger = setup_logging(log_dir=None)
        assert logger is not None

        # Clean up
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_logging_with_empty_log_messages(self, temp_log_dir, clean_logger):
        """Test that empty log messages are handled correctly."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)
        logger.info("")

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        # Should not crash and log file should exist
        log_path = os.path.join(temp_log_dir, "orgprompt.log")
        assert os.path.exists(log_path)


class TestLoggingIntegration:
    """Integration tests for logging behavior."""

    def test_multiple_loggers_share_configuration(self, temp_log_dir, clean_logger):
        """Test that child loggers inherit configuration."""
        from logging_config import setup_logging

        setup_logging(log_dir=temp_log_dir)

        # Create child loggers
        child_logger1 = logging.getLogger("orgprompt.module1")
        child_logger2 = logging.getLogger("orgprompt.module2")

        # They should write to the same log file
        child_logger1.info("Child logger 1 message")
        child_logger2.info("Child logger 2 message")

        # Get the main logger and close its handlers
        main_logger = logging.getLogger("orgprompt")
        for handler in main_logger.handlers[:]:
            handler.flush()
            handler.close()
            main_logger.removeHandler(handler)

        log_path = os.path.join(temp_log_dir, "orgprompt.log")
        with open(log_path, 'r') as f:
            content = f.read()

        assert "Child logger 1 message" in content
        assert "Child logger 2 message" in content

    def test_logging_level_can_be_changed(self, temp_log_dir, clean_logger):
        """Test that log level can be dynamically changed."""
        from logging_config import setup_logging

        logger = setup_logging(log_dir=temp_log_dir)

        # Set to WARNING level
        logger.setLevel(logging.WARNING)

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")

        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)

        log_path = os.path.join(temp_log_dir, "orgprompt.log")
        with open(log_path, 'r') as f:
            content = f.read()

        # Only WARNING should be present
        assert "Debug message" not in content
        assert "Info message" not in content
        assert "Warning message" in content

"""Logging configuration for OrgPrompt application.

This module provides centralized logging configuration that works with
both python.exe and pythonw.exe (which suppresses stdout/stderr).

Key features:
- File-based logging (works with pythonw.exe)
- Automatic log rotation
- Proper exception formatting
- Thread-safe logging
"""

import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# Logger name for the application
LOGGER_NAME = "orgprompt"

# Default log file name
LOG_FILE_NAME = "orgprompt.log"

# Default maximum log file size (5 MB)
DEFAULT_MAX_BYTES = 5 * 1024 * 1024

# Default number of backup files to keep
DEFAULT_BACKUP_COUNT = 3

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Logging level
LOG_LEVEL = logging.INFO


def get_log_file_path(log_dir: Optional[str] = None) -> str:
    """Get the path to the log file.

    Args:
        log_dir: Directory for log files. If None, uses system temp directory.

    Returns:
        Full path to the log file.
    """
    if log_dir is None:
        log_dir = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "orgprompt")

    # Create log directory if it doesn't exist
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    return os.path.join(log_dir, LOG_FILE_NAME)


def setup_logging(
    log_dir: Optional[str] = None,
    log_file: Optional[str] = None,
    level: int = LOG_LEVEL,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    format_string: str = LOG_FORMAT,
    date_format: str = DATE_FORMAT
) -> logging.Logger:
    """Setup logging configuration for the application.

    This function configures a rotating file handler that writes to a log file.
    It's safe to call multiple times - subsequent calls will return the existing
    logger without adding duplicate handlers.

    Args:
        log_dir: Directory for log files. If None, uses a subdirectory of TEMP.
        log_file: Full path to log file. If provided, overrides log_dir.
        level: Logging level (default: INFO).
        max_bytes: Maximum size of log file before rotation (default: 5 MB).
        backup_count: Number of backup files to keep (default: 3).
        format_string: Format string for log messages.
        date_format: Format string for timestamps.

    Returns:
        Configured logger instance.
    """
    # Get or create the logger
    logger = logging.getLogger(LOGGER_NAME)

    # If logger already has handlers, return it (avoid duplicate handlers)
    if logger.handlers:
        return logger

    # Determine log file path
    if log_file is None:
        log_file = get_log_file_path(log_dir)

    # Create log directory if it doesn't exist
    log_directory = os.path.dirname(log_file)
    if log_directory:
        Path(log_directory).mkdir(parents=True, exist_ok=True)

    # Create rotating file handler
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
    except (OSError, PermissionError) as e:
        # Fallback to temp directory if specified location fails
        fallback_log = os.path.join(
            os.environ.get("TEMP", tempfile.gettempdir()),
            LOG_FILE_NAME
        )
        file_handler = RotatingFileHandler(
            fallback_log,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )

    # Set formatter
    formatter = logging.Formatter(format_string, datefmt=date_format)
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    # Set log level
    logger.setLevel(level)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    # Log initialization
    logger.info("Logging initialized")
    logger.debug(f"Log file: {log_file}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name. If None, returns the main orgprompt logger.
              If provided, returns a child logger (e.g., "orgprompt.module").

    Returns:
        Logger instance.
    """
    if name is None:
        return logging.getLogger(LOGGER_NAME)

    # Create child logger if name doesn't start with LOGGER_NAME
    if not name.startswith(LOGGER_NAME + "."):
        name = f"{LOGGER_NAME}.{name}"

    return logging.getLogger(name)


# Logging message constants
class LogMessages:
    """Standardized logging messages."""

    # Application lifecycle
    MSG_STARTUP = "OrgPrompt starting"
    MSG_SHUTDOWN = "OrgPrompt shutting down"
    MSG_INTERRUPTED = "OrgPrompt interrupted by user"
    MSG_RESTARTING = "OrgPrompt restarting"

    # Single instance
    MSG_INSTANCE_LOCK_ACQUIRED = "Single instance lock acquired"
    MSG_INSTANCE_LOCK_FAILED = "Another instance is already running"
    MSG_INSTANCE_LOCK_RELEASED = "Single instance lock released"
    MSG_INSTANCE_LOCK_ERROR = "Error acquiring single instance lock"

    # Tray icon
    MSG_TRAY_STARTING = "Starting system tray icon"
    MSG_TRAY_STARTED = "System tray icon started"
    MSG_TRAY_STOPPING = "Stopping system tray icon"
    MSG_TRAY_STOPPED = "System tray icon stopped"
    MSG_TRAY_ERROR = "Error with system tray icon"

    # Window management
    MSG_WINDOW_SHOWING = "Showing prompt window"
    MSG_WINDOW_SHOWN = "Prompt window shown"
    MSG_WINDOW_CLOSING = "Closing prompt window"
    MSG_WINDOW_CLOSED = "Prompt window closed"
    MSG_WINDOW_ERROR = "Error with prompt window"

    # Prompt management
    MSG_PROMPTS_LOADING = "Loading prompts from file"
    MSG_PROMPTS_LOADED = "Prompts loaded successfully"
    MSG_PROMPTS_RELOADING = "Reloading prompts"
    MSG_PROMPTS_RELOADED = "Prompts reloaded"
    MSG_PROMPTS_ERROR = "Error loading prompts"

    # General errors
    MSG_ERROR_UNEXPECTED = "An unexpected error occurred"
    MSG_ERROR_CRITICAL = "A critical error occurred"

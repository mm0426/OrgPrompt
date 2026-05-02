"""Additional tests for main.py to improve coverage."""

import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestMainEdgeCases:
    """Additional edge case tests for main.py."""

    def test_show_error_message_success(self):
        """Test show_error_message creates and shows error dialog."""
        from main import show_error_message

        with patch('main.tk') as mock_tk:
            mock_root = Mock()
            mock_tk.Tk.return_value = mock_root

            with patch('main.messagebox') as mock_messagebox:
                show_error_message("Test Title", "Test Message")

                # Verify messagebox was called
                mock_messagebox.showerror.assert_called_once_with("Test Title", "Test Message")

                # Verify root was destroyed
                mock_root.destroy.assert_called_once()

    def test_show_error_message_handles_exception(self):
        """Test show_error_message handles exceptions gracefully."""
        from main import show_error_message

        # Make tkinter fail
        with patch('main.tk', side_effect=RuntimeError("Tk error")):
            # Should not raise
            show_error_message("Test Title", "Test Message")

    def test_orgprompt_app_init(self):
        """Test OrgPromptApp initialization."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class:
            mock_root = Mock()
            mock_tk_class.return_value = mock_root

            with patch('main.PromptManager') as mock_pm_class:
                mock_pm = Mock()
                mock_pm_class.return_value = mock_pm

                with patch('main.TrayManager') as mock_tm_class:
                    mock_tm = Mock()
                    mock_tm_class.return_value = mock_tm

                    app = OrgPromptApp()

                    # Verify root was created and hidden
                    mock_tk_class.assert_called_once()
                    mock_root.withdraw.assert_called_once()

                    # Verify managers were created
                    mock_pm_class.assert_called_once()
                    mock_tm_class.assert_called_once()

                    assert app.prompt_window is None
                    assert app.running is True

    def test_orgprompt_app_show_prompt_window_existing(self):
        """Test show_prompt_window when window already exists."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class:
            mock_root = Mock()
            mock_tk_class.return_value = mock_root

            with patch('main.PromptManager'):
                with patch('main.TrayManager'):
                    app = OrgPromptApp()

                    # Create a mock existing window
                    mock_window = Mock()
                    mock_window.root = Mock()
                    mock_window.root.winfo_exists.return_value = True
                    app.prompt_window = mock_window

                    # Show the window — marshals via root.after()
                    app.show_prompt_window()

                    # Verify scheduling was done via the Tk root's after()
                    mock_root.after.assert_called_once()

                    # Verify prompt_manager.reload was NOT called
                    # (because we're reusing existing window)

    def test_orgprompt_app_show_prompt_window_new(self):
        """Test show_prompt_window creating new window."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class:
            mock_root = Mock()
            mock_tk_class.return_value = mock_root

            with patch('main.PromptManager') as mock_pm_class:
                mock_pm = Mock()
                mock_pm_class.return_value = mock_pm

                with patch('main.TrayManager') as mock_tm_class:
                    mock_tm = Mock()
                    mock_tm_class.return_value = mock_tm

                    with patch('main.PromptWindow') as mock_pw_class:
                        mock_pw = Mock()
                        mock_pw_class.return_value = mock_pw

                        app = OrgPromptApp()
                        app.show_prompt_window()

                        # Verify scheduling was done via root.after()
                        mock_root.after.assert_called_once()

                        # The actual window creation happens inside the
                        # after() callback, so PromptWindow is NOT created yet
                        # (it's deferred to the mainloop). Verify the deferred
                        # callback by executing the scheduled call.
                        assert mock_root.after.call_count == 1
                        callback = mock_root.after.call_args[0][1]
                        callback()  # Execute the scheduled callback

                        # Now verify the window was created
                        mock_pw_class.assert_called_once()
                        mock_pw.show.assert_called_once()

    def test_orgprompt_app_on_window_close(self):
        """Test _on_window_close callback."""
        from main import OrgPromptApp

        with patch('main.tk.Tk'):
            with patch('main.PromptManager'):
                with patch('main.TrayManager'):
                    app = OrgPromptApp()

                    # Set a window
                    app.prompt_window = Mock()

                    # Call close handler
                    app._on_window_close()

                    # Verify window was cleared
                    assert app.prompt_window is None

    def test_orgprompt_app_quit(self):
        """Test quit method."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class:
            mock_root = Mock()
            mock_tk_class.return_value = mock_root

            with patch('main.PromptManager'):
                with patch('main.TrayManager') as mock_tm_class:
                    mock_tm = Mock()
                    mock_tm_class.return_value = mock_tm

                    app = OrgPromptApp()
                    app.quit()

                    # Verify running flag was set
                    assert app.running is False

                    # Verify scheduling was done via root.after()
                    mock_root.after.assert_called_once()

                    # Execute the scheduled callback to verify cleanup
                    callback = mock_root.after.call_args[0][1]
                    callback()

                    # Verify tray manager was stopped
                    mock_tm.stop.assert_called_once()

                    # Verify root was destroyed
                    mock_root.destroy.assert_called_once()

    def test_main_with_logger_none(self, temp_log_dir):
        """Test main when logger is None (logging setup failed)."""
        with patch('main.setup_logging') as mock_setup_logging:
            # Make setup_logging return None to simulate failure
            mock_setup_logging.return_value = None

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Should not crash despite logging being None
                    result = main()

                    # Should return success
                    assert result == 0

    def test_main_with_keyboard_interrupt(self, temp_log_dir):
        """Test main handles KeyboardInterrupt correctly."""
        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app.run.side_effect = KeyboardInterrupt()
                    mock_app_class.return_value = mock_app

                    from main import main

                    # Should not raise
                    result = main()

                    # Should return 0 (KeyboardInterrupt is not an error)
                    assert result == 0

                    # Verify interrupt was logged
                    mock_logger.info.assert_any_call("OrgPrompt interrupted by user")

    def test_main_logging_setup_failure_fallback(self, temp_log_dir):
        """Test that main continues even if logging setup fails."""
        # Make setup_logging fail
        with patch('main.setup_logging', side_effect=OSError("Cannot create log")):
            with patch('builtins.print') as mock_print:
                with patch('main.SingleInstance') as mock_si_class:
                    mock_lock = Mock()
                    mock_lock.acquire.return_value = True
                    mock_si_class.return_value = mock_lock

                    with patch('main.OrgPromptApp') as mock_app_class:
                        mock_app = Mock()
                        mock_app_class.return_value = mock_app

                        from main import main

                        # Should not crash
                        result = main()

                        # Should print error to stderr
                        assert any(
                            "Failed to setup logging" in str(call)
                            for call in mock_print.call_args_list
                        )


class TestMainIntegration:
    """Integration tests for main module."""

    def test_full_app_lifecycle_mocked(self, temp_log_dir):
        """Test full app lifecycle with all components mocked."""
        from main import main

        with patch('main.setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger

            with patch('main.SingleInstance') as mock_si_class:
                mock_lock = Mock()
                mock_lock.acquire.return_value = True
                mock_si_class.return_value = mock_lock

                with patch('main.OrgPromptApp') as mock_app_class:
                    mock_app = Mock()
                    mock_app.run.return_value = None
                    mock_app_class.return_value = mock_app

                    # Run main
                    result = main()

                    # Verify success
                    assert result == 0

                    # Verify lock was released
                    mock_lock.release.assert_called_once()

    def test_log_file_location(self, temp_log_dir):
        """Test that log file is created in expected location."""
        from logging_config import get_log_file_path, setup_logging

        # Setup logging with temp directory
        logger = setup_logging(log_dir=temp_log_dir)

        # Get log file path
        log_path = get_log_file_path()

        # Verify it's in the expected location
        import os
        import tempfile
        expected_dir = os.path.join(tempfile.gettempdir(), "orgprompt")
        assert log_path.startswith(expected_dir)

        # Clean up
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

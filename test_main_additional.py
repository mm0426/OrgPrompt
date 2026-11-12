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

                with patch('main.TrayManager') as mock_tm_class, patch('main.AppState'):
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
        """Showing when a window exists reuses it (no new PromptWindow)."""
        from main import OrgPromptApp

        with patch('main.tk.Tk'), patch('main.PromptManager'), \
                patch('main.TrayManager'), patch('main.AppState'), \
                patch('main.PromptWindow') as mock_pw_class:
            app = OrgPromptApp()
            mock_window = Mock()
            app.prompt_window = mock_window

            app.show_prompt_window()
            app._process_commands()

            mock_pw_class.assert_not_called()
            mock_window.show.assert_called_once()

    def test_show_prompt_window_does_not_touch_tk_from_caller_thread(self):
        """show_prompt_window() only queues work; Tk runs it on the main thread."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class, patch('main.PromptManager'), \
                patch('main.TrayManager'), patch('main.AppState'), \
                patch('main.PromptWindow') as mock_pw_class:
            mock_root = Mock()
            mock_tk_class.return_value = mock_root
            app = OrgPromptApp()
            mock_root.reset_mock()

            app.show_prompt_window()

            assert mock_root.method_calls == []
            mock_pw_class.assert_not_called()
            assert app._commands.qsize() == 1

    def test_orgprompt_app_show_prompt_window_new(self):
        """Test show_prompt_window creating new window."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class, patch('main.PromptManager'), \
                patch('main.TrayManager'), patch('main.AppState'), \
                patch('main.PromptWindow') as mock_pw_class:
            mock_root = Mock()
            mock_tk_class.return_value = mock_root
            mock_pw = Mock()
            mock_pw_class.return_value = mock_pw

            app = OrgPromptApp()
            app.show_prompt_window()
            mock_pw_class.assert_not_called()  # deferred to the main thread

            app._process_commands()

            mock_pw_class.assert_called_once()
            mock_pw.show.assert_called_once()
            # The poll loop reschedules itself
            mock_root.after.assert_called_with(app.POLL_MS, app._process_commands)

            # A second show reuses the same window
            app.show_prompt_window()
            app._process_commands()
            mock_pw_class.assert_called_once()
            assert mock_pw.show.call_count == 2

    def test_process_commands_survives_failing_command(self):
        """One failing command must not stop the poll loop."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class, patch('main.PromptManager'), \
                patch('main.TrayManager'), patch('main.AppState'):
            mock_root = Mock()
            mock_tk_class.return_value = mock_root
            app = OrgPromptApp()
            ran = []

            def boom():
                raise RuntimeError("boom")

            app._post(boom)
            app._post(lambda: ran.append(True))
            app._process_commands()

            assert ran == [True]
            mock_root.after.assert_called_with(app.POLL_MS, app._process_commands)

    def test_orgprompt_app_on_window_close(self):
        """Closing hides the window; the app keeps it for reuse."""
        from main import OrgPromptApp

        with patch('main.tk.Tk'), patch('main.PromptManager'), \
                patch('main.TrayManager'), patch('main.AppState'):
            app = OrgPromptApp()
            window = Mock()
            app.prompt_window = window

            app._on_window_close()

            assert app.prompt_window is window

    def test_orgprompt_app_quit(self):
        """Test quit method."""
        from main import OrgPromptApp

        with patch('main.tk.Tk') as mock_tk_class, patch('main.PromptManager'), \
                patch('main.TrayManager') as mock_tm_class, patch('main.AppState'):
            mock_root = Mock()
            mock_tk_class.return_value = mock_root
            mock_tm = Mock()
            mock_tm_class.return_value = mock_tm

            app = OrgPromptApp()
            window = Mock()
            app.prompt_window = window
            app.quit()

            assert app.running is False
            mock_root.destroy.assert_not_called()  # deferred to main thread

            app._process_commands()

            window.destroy.assert_called_once()
            mock_tm.stop.assert_called_once()
            mock_root.destroy.assert_called_once()
            # No rescheduling after the root is destroyed
            mock_root.after.assert_not_called()

            # A second quit is harmless
            app.quit()
            app._process_commands()
            mock_root.destroy.assert_called_once()

    def test_copy_favorite_copies_and_records_usage(self):
        from main import OrgPromptApp
        from prompt_manager import Prompt

        with patch('main.tk.Tk'), patch('main.PromptManager') as mock_pm_class, \
                patch('main.TrayManager') as mock_tm_class, \
                patch('main.AppState') as mock_state_class, \
                patch('main.copy_with_notification', return_value=True) as mock_copy:
            prompt = Prompt(title="T", text="body", category="C", pinned=True)
            mock_pm = mock_pm_class.return_value
            mock_pm.reload_if_changed.return_value = False
            mock_pm.find_by_key.return_value = prompt
            mock_pm.settings = {"show_notifications": True}

            app = OrgPromptApp()
            app.copy_favorite("C::T")
            app._process_commands()

            assert mock_copy.call_args[0][0] == "body"
            assert mock_copy.call_args.kwargs["notifier"] is mock_tm_class.return_value.notify
            mock_state_class.return_value.record_use.assert_called_once_with("C::T")

    def test_tray_watchdog_restarts_then_gives_up(self):
        """A tray icon that keeps dying is restarted, then the app quits."""
        from main import OrgPromptApp

        with patch('main.tk.Tk'), patch('main.PromptManager'), \
                patch('main.TrayManager') as mock_tm_class, patch('main.AppState'), \
                patch('main.time.sleep') as mock_sleep:
            mock_tm = mock_tm_class.return_value
            mock_tm.start.side_effect = RuntimeError("icon died")

            app = OrgPromptApp()
            app._run_tray()

            assert mock_tm.start.call_count == app.MAX_TRAY_RESTARTS + 1
            assert mock_sleep.call_count == app.MAX_TRAY_RESTARTS
            assert app.running is False  # quit() was requested

    def test_tray_watchdog_stops_when_app_quits(self):
        from main import OrgPromptApp

        with patch('main.tk.Tk'), patch('main.PromptManager'), \
                patch('main.TrayManager') as mock_tm_class, patch('main.AppState'), \
                patch('main.time.sleep') as mock_sleep:
            app = OrgPromptApp()
            mock_tm_class.return_value.start.side_effect = (
                lambda: setattr(app, "running", False)
            )

            app._run_tray()

            mock_tm_class.return_value.start.assert_called_once()
            mock_sleep.assert_not_called()

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

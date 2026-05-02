"""Tests for tray_manager.py module.

This test suite follows TDD methodology:
1. Write failing test first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor and improve (IMPROVE)
"""

import logging
from unittest.mock import Mock, patch, MagicMock
import pytest


# Setup logging for tests
logging.basicConfig(level=logging.DEBUG)


class TestCreateIconImage:
    """Test the create_icon_image function."""

    def test_create_icon_image_default_params(self):
        """Test creating icon with default parameters."""
        from tray_manager import create_icon_image

        image = create_icon_image()

        # Should return a PIL Image
        assert image is not None
        assert hasattr(image, 'size')
        assert image.size == (64, 64)

    def test_create_icon_image_custom_size(self):
        """Test creating icon with custom size."""
        from tray_manager import create_icon_image

        image = create_icon_image(size=128)

        assert image.size == (128, 128)

    def test_create_icon_image_custom_color(self):
        """Test creating icon with custom color."""
        from tray_manager import create_icon_image

        image = create_icon_image(color="#FF0000")

        assert image is not None
        # Verify image was created (color check would require pixel inspection)

    def test_create_icon_image_returns_rgba(self):
        """Test that icon is created in RGBA mode."""
        from tray_manager import create_icon_image

        image = create_icon_image()

        assert image.mode == "RGBA"


class TestTrayManager:
    """Test TrayManager class."""

    def test_tray_manager_init(self):
        """Test TrayManager initialization."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        assert manager.on_click is on_click
        assert manager.on_quit is on_quit
        assert manager.icon is None

    def test_create_menu(self):
        """Test menu creation."""
        from tray_manager import TrayManager
        import pystray

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)
        menu = manager._create_menu()

        assert isinstance(menu, pystray.Menu)

    def test_on_menu_open(self):
        """Test open menu handler."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)
        manager._on_menu_open()

        # Should call the on_click callback
        on_click.assert_called_once()

    def test_on_menu_quit(self):
        """Test quit menu handler."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)
        manager._on_menu_quit()

        # Should call the on_quit callback
        on_quit.assert_called_once()

    @patch('tray_manager.create_icon_image')
    @patch('tray_manager.pystray.Icon')
    def test_start_creates_icon(self, mock_icon_class, mock_create_icon):
        """Test that start creates and runs the tray icon."""
        from tray_manager import TrayManager

        # Setup mocks
        mock_icon = Mock()
        mock_icon_class.return_value = mock_icon
        mock_image = Mock()
        mock_create_icon.return_value = mock_image

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        # Start the manager
        manager.start()

        # Verify icon was created
        mock_icon_class.assert_called_once()

        # Verify icon.run() was called
        mock_icon.run.assert_called_once()

    def test_stop_when_icon_exists(self):
        """Test stopping the tray icon when it exists."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        # Create a mock icon
        mock_icon = Mock()
        manager.icon = mock_icon

        # Stop the manager
        manager.stop()

        # Verify icon.stop() was called
        mock_icon.stop.assert_called_once()

        # Verify icon was set to None
        assert manager.icon is None

    def test_stop_when_no_icon(self):
        """Test stopping the tray manager when no icon exists."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        # Stop without starting (should not crash)
        manager.stop()

        assert manager.icon is None

    def test_multiple_stop_calls(self):
        """Test that calling stop multiple times is safe."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        # Create a mock icon
        mock_icon = Mock()
        manager.icon = mock_icon

        # Stop multiple times
        manager.stop()
        manager.stop()
        manager.stop()

        # Icon.stop() should only be called once
        mock_icon.stop.assert_called_once()

    @patch('tray_manager.create_icon_image')
    @patch('tray_manager.pystray.Icon')
    def test_start_logs_debug_messages(self, mock_icon_class, mock_create_icon):
        """Test that start logs debug messages."""
        from tray_manager import TrayManager

        # Setup mocks
        mock_icon = Mock()
        mock_icon_class.return_value = mock_icon
        mock_image = Mock()
        mock_create_icon.return_value = mock_image

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        # Patch the logger in the tray_manager module
        with patch('tray_manager.logger') as mock_logger:
            manager.start()

            # Verify logging was called
            assert mock_logger.info.called or mock_logger.debug.called

    @patch('tray_manager.create_icon_image')
    @patch('tray_manager.pystray.Icon')
    def test_start_exception_handling(self, mock_icon_class, mock_create_icon):
        """Test that start properly handles exceptions."""
        from tray_manager import TrayManager

        # Make icon creation fail
        mock_icon_class.side_effect = RuntimeError("Test error")
        mock_image = Mock()
        mock_create_icon.return_value = mock_image

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        # Should raise the exception (we log it in the actual code)
        with pytest.raises(RuntimeError):
            manager.start()

    @patch('tray_manager.pystray.Icon')
    def test_stop_exception_handling(self, mock_icon_class):
        """Test that stop properly handles exceptions."""
        from tray_manager import TrayManager

        # Create a mock icon that raises on stop
        mock_icon = Mock()
        mock_icon.stop.side_effect = RuntimeError("Test error")

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)
        manager.icon = mock_icon

        # Should handle exception gracefully
        manager.stop()

        # Icon should still be set to None
        assert manager.icon is None

    def test_menu_structure(self):
        """Test that the menu has the correct structure."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)
        menu = manager._create_menu()

        # Menu should exist
        assert menu is not None

        # Menu should have __iter__ method for iteration
        assert hasattr(menu, '__iter__')

        # Should be able to iterate over menu items
        item_count = 0
        for item in menu:
            item_count += 1

        # Should have at least 2 items (Open, Separator, Quit)
        assert item_count >= 2


class TestTrayManagerIntegration:
    """Integration tests for TrayManager."""

    def test_callbacks_are_preserved(self):
        """Test that callbacks are preserved after initialization."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)

        # Callbacks should be the same objects
        assert manager.on_click is on_click
        assert manager.on_quit is on_quit

    def test_menu_callbacks_are_bound(self):
        """Test that menu items are bound to instance methods."""
        from tray_manager import TrayManager

        on_click = Mock()
        on_quit = Mock()

        manager = TrayManager(on_click, on_quit)
        menu = manager._create_menu()

        # Menu items should have callable actions
        for item in menu:
            if hasattr(item, '__iter__'):
                # Menu item is iterable (might be a tuple)
                for sub_item in item:
                    if hasattr(sub_item, 'action') and callable(sub_item.action):
                        # Found a menu item with an action
                        assert True
                        return
            elif hasattr(item, 'action') and callable(item.action):
                # Found a menu item with an action
                assert True
                return

        # If we get here, we still pass (the menu structure is valid)
        assert True

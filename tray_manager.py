"""System tray icon management."""

import logging
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

# Get a logger for this module
logger = logging.getLogger("orgprompt.tray_manager")

MAX_MENU_TITLE = 50


def create_icon_image(size: int = 64, color: str = "#4A90D9") -> Image.Image:
    """Create a simple icon image.

    Args:
        size: Icon size in pixels
        color: Icon color (hex)

    Returns:
        PIL Image object
    """
    logger.debug(f"Creating icon image (size={size}, color={color})")
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw a simple document/prompt icon
    margin = size // 8
    doc_left = margin
    doc_top = margin
    doc_right = size - margin
    doc_bottom = size - margin

    # Document background (rounded rectangle approximation)
    draw.rectangle(
        [doc_left, doc_top, doc_right, doc_bottom],
        fill=color,
        outline="#2E5A8B",
        width=2
    )

    # Lines representing text
    line_margin = size // 5
    line_spacing = size // 8
    line_height = 2
    line_color = "white"

    for i in range(3):
        y = doc_top + line_margin + (i * line_spacing)
        draw.rectangle(
            [doc_left + line_margin // 2, y, doc_right - line_margin // 2, y + line_height],
            fill=line_color
        )

    return image


def _menu_title(title: str) -> str:
    """Shorten a prompt title for the menu; escape '&' (Windows mnemonic)."""
    if len(title) > MAX_MENU_TITLE:
        title = title[: MAX_MENU_TITLE - 1] + "…"
    return title.replace("&", "&&")


class TrayManager:
    """Manages the system tray icon.

    Callbacks are invoked on the tray thread; the app is responsible for
    marshalling them to the Tk main thread.
    """

    def __init__(
        self,
        on_click: Callable,
        on_quit: Callable,
        get_favorites: Optional[Callable[[], list[tuple[str, str]]]] = None,
        on_favorite: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            on_click: Called when "Open" is chosen (or the icon is clicked).
            on_quit: Called when "Quit" is chosen.
            get_favorites: Returns ``[(key, title), ...]`` for the menu.
            on_favorite: Called with a favorite's key when it's chosen.
        """
        self.on_click = on_click
        self.on_quit = on_quit
        self.get_favorites = get_favorites
        self.on_favorite = on_favorite
        self.icon: Optional[pystray.Icon] = None
        logger.debug("TrayManager initialized")

    def _favorite_items(self) -> list:
        if self.get_favorites is None:
            return []
        try:
            favorites = self.get_favorites()
        except Exception:
            logger.exception("Failed to load favorites for tray menu")
            return []
        if not favorites:
            return []

        def make_action(key: str) -> Callable[[], None]:
            # Zero-argument lambda: pystray inspects the argument count.
            return lambda: self._on_menu_favorite(key)

        items = [pystray.MenuItem("Favorites", None, enabled=False)]
        items += [
            pystray.MenuItem(f"   {_menu_title(title)}", make_action(key))
            for key, title in favorites
        ]
        items.append(pystray.Menu.SEPARATOR)
        return items

    def _menu_items(self) -> tuple:
        return tuple(self._favorite_items()) + (
            pystray.MenuItem("Open", self._on_menu_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_menu_quit),
        )

    def _create_menu(self) -> pystray.Menu:
        """Create the tray menu (rebuilt from favorites on refresh_menu)."""
        logger.debug("Creating tray menu")
        return pystray.Menu(self._menu_items)

    def refresh_menu(self) -> None:
        """Rebuild the menu, e.g. after favorites change."""
        if self.icon is None:
            return
        try:
            self.icon.update_menu()
        except Exception:
            logger.exception("Failed to refresh tray menu")

    def notify(self, title: str, message: str) -> None:
        """Show a Windows notification from the tray icon (non-blocking)."""
        icon = self.icon
        if icon is None or not getattr(icon, "HAS_NOTIFICATION", False):
            return
        try:
            icon.remove_notification()
            icon.notify(message, title)
        except Exception:
            logger.exception("Failed to show notification")

    def _on_menu_open(self) -> None:
        """Handle open menu click."""
        logger.debug("Open menu item clicked")
        self.on_click()

    def _on_menu_quit(self) -> None:
        """Handle quit menu click."""
        logger.debug("Quit menu item clicked")
        self.on_quit()

    def _on_menu_favorite(self, key: str) -> None:
        logger.debug("Favorite menu item clicked: %s", key)
        if self.on_favorite is not None:
            self.on_favorite(key)

    def start(self) -> None:
        """Start the tray icon. Blocks until the icon stops."""
        try:
            logger.info("Creating system tray icon")
            icon_image = create_icon_image()

            self.icon = pystray.Icon(
                "orgprompt",
                icon_image,
                "OrgPrompt - AI Prompt Manager",
                menu=self._create_menu()
            )

            logger.info("Starting system tray icon")
            self.icon.run()
        except Exception as e:
            logger.exception(f"Error starting tray icon: {e}")
            raise

    def stop(self) -> None:
        """Stop the tray icon."""
        if self.icon:
            logger.info("Stopping system tray icon")
            try:
                self.icon.stop()
                logger.info("System tray icon stopped")
            except Exception as e:
                logger.warning(f"Error stopping tray icon: {e}")
            finally:
                self.icon = None

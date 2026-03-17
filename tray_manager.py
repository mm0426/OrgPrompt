"""System tray icon management."""

import pystray
from PIL import Image, ImageDraw
from typing import Callable, Optional


def create_icon_image(size: int = 64, color: str = "#4A90D9") -> Image.Image:
    """Create a simple icon image.

    Args:
        size: Icon size in pixels
        color: Icon color (hex)

    Returns:
        PIL Image object
    """
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


class TrayManager:
    """Manages the system tray icon."""

    def __init__(self, on_click: Callable, on_quit: Callable):
        self.on_click = on_click
        self.on_quit = on_quit
        self.icon: Optional[pystray.Icon] = None

    def _create_menu(self) -> pystray.Menu:
        """Create the tray menu."""
        return pystray.Menu(
            pystray.MenuItem("Open", self._on_menu_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_menu_quit)
        )

    def _on_menu_open(self) -> None:
        """Handle open menu click."""
        self.on_click()

    def _on_menu_quit(self) -> None:
        """Handle quit menu click."""
        self.on_quit()

    def start(self) -> None:
        """Start the tray icon."""
        icon_image = create_icon_image()

        self.icon = pystray.Icon(
            "orgprompt",
            icon_image,
            "OrgPrompt - AI Prompt Manager",
            menu=self._create_menu()
        )

        self.icon.run()

    def stop(self) -> None:
        """Stop the tray icon."""
        if self.icon:
            self.icon.stop()
            self.icon = None

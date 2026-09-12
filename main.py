"""HWInfo64 Visualizer — entry point."""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from app import App  # noqa: E402


def main() -> None:
    """Launch the application."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
